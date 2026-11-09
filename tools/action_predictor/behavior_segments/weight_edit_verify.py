"""Check intended tensor edits and reproduce selected checkpoint predictions."""
import json,time
import torch
from .weight_edit import REPORT,WORK,BASE,BASE_WORK,edit,code_metrics,guard
from .data import ROOT,load
from .study import check,evaluate
from . import model
from ..audit import immutable_json
from ..data import digest


def run():
    torch.set_num_threads(4);frozen=json.loads((REPORT/'plan.json').read_text());result=json.loads((REPORT/'result.json').read_text())
    for group in ('sources','input_bindings'):
        for p,h in frozen[group].items():assert digest(ROOT/p)==h
    for p,h in result['bindings'].items():assert digest(ROOT/p)==h
    original=torch.load(BASE_WORK/'S01-run/final.pt',map_location='cpu',weights_only=False)['model'];changes={}
    for name,(scale,prior) in frozen['candidates'].items():
        saved=torch.load(WORK/(name+'.pt'),map_location='cpu',weights_only=False);expected=edit(original,saved['frequency'],scale,prior)
        assert set(saved['model'])==set(original)
        assert all(torch.equal(v,expected[k]) and torch.isfinite(v).all() for k,v in saved['model'].items())
        assert 'optimizer' not in saved
        changes[name]={k:int((v!=original[k]).sum()) for k,v in saved['model'].items() if not torch.equal(v,original[k])}
    plan=json.loads((BASE/'protocol.json').read_text());check(plan);d=json.loads((BASE/'discovery.json').read_text());windows,maps=load()
    cache={w['key']:model.encode_window(w,maps[w['payload']],plan['schema'])[0] for w in windows}
    from .edited_predictor import EditedBehaviorPredictor
    predictor=EditedBehaviorPredictor();reproduced={}
    selection=json.loads((REPORT/'selection.json').read_text());chosen=result['selected']
    for split,filename in [('fit',chosen+'-fit.json'),('evaluation','selected-evaluation.json')]:
        actual=evaluate(predictor.net,windows,maps,cache,d,split,time.perf_counter()+300)
        archived=json.loads((WORK/filename).read_text());assert actual==archived
        reference=json.loads((BASE_WORK/'S01-run'/(split+'-predictions.json')).read_text())
        checks=guard(actual['summary'],code_metrics(actual['records']),reference['summary'],code_metrics(reference['records']))
        expected=selection['fit_results'][chosen]['guards'] if split=='fit' else result['evaluation_guards']
        assert checks==expected;reproduced[split]=len(actual['records'])
    immutable_json(REPORT/'verification.json',dict(source_sha256=digest(__file__),loader_sha256=digest(__file__.replace('weight_edit_verify.py','edited_predictor.py')),
        result_sha256=digest(REPORT/'result.json'),exact_edits=changes,all_other_weights_unchanged=True,
        original_inputs_unchanged=True,no_optimizer_state_in_edited_files=True,selected_forecasts_exact=reproduced,guards_reproduced=True,optimizer_updates=0))
    print(json.dumps(dict(changes=changes,reproduced=reproduced),indent=2))


if __name__=='__main__':run()
