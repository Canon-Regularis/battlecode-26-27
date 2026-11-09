"""Verify expanded training data, optimizer accounting and the selected forecasts."""
import json
import time
from pathlib import Path
import numpy as np
import torch
from . import expanded_code_fit as fit,expanded_code_data as expanded,code_weight_fit as first
from . import data as original,model,segmentation
from .expanded_code_predictor import ExpandedCodePredictor
from .code_weight_verify import audit_trace,bound
from .rare_code_edit import metrics
from .study import evaluate
from ..audit import immutable_json
from ..data import digest


def run():
    start=time.perf_counter();plan,architecture,data,ids=fit.inputs()
    selection=json.loads((fit.REPORT/'selection.json').read_text());refit=json.loads((fit.REPORT/'refit.json').read_text())
    result=json.loads((fit.REPORT/'result.json').read_text())
    for receipt in (selection,refit,result):bound(receipt)
    assert selection['plan_sha256']==digest(fit.REPORT/'plan.json')
    assert refit['selection_sha256']==digest(fit.REPORT/'selection.json')
    assert result['refit_sha256']==digest(fit.REPORT/'refit.json')
    assert selection['selected']==min(selection['candidates'],key=lambda c:(-c['correct'],c['nll'],c['epoch'],c['learning_rate']))
    assembly=json.loads((fit.REPORT/'assembly-plan.json').read_text())
    for kind in ('sources','inputs'):
        for p,h in assembly[kind].items():assert digest(original.ROOT/p)==h,p
    receipt=json.loads((fit.REPORT/'data.json').read_text())
    for p,h in receipt['source_bindings'].items():assert digest(p)==h,p
    for p,h in receipt['output_bindings'].items():assert digest(original.ROOT/p)==h,p
    windows,maps=expanded.read();old_windows,old_maps=original.load()
    canonical={w['key']:w for w in old_windows if w['partition']=='fit'}
    assert all(w['partition']=='fit' for w in windows) and len(windows)==1607
    events=[(w['payload'],s['event']) for w in windows for s in w['steps']]
    assert len(events)==len(set(events))
    old,_,old_data,old_ids=first.load_cache();old_indices={r['key']:i for i,r in enumerate(old_ids)}
    discovery=json.loads((original.REPORT/'discovery.json').read_text())
    labels=json.loads((fit.WORK/'labels.json').read_text())['labels']
    net=model.SegmentPolicy(architecture['schema'],8).eval()
    net.load_state_dict(torch.load(first.INITIAL,map_location='cpu',weights_only=False)['model'])
    capture={};handle=net.context.register_forward_pre_hook(lambda module,args:capture.update(context=args[0].detach()))
    torch.set_num_threads(4)
    with torch.no_grad():
        for i,w in enumerate(windows):
            expected_labels=segmentation.assign([s['behavior'] for s in w['steps']],[s['behavior_mask'] for s in w['steps']],discovery['fitted']).tolist()
            assert expected_labels==labels[w['key']]==data['labels'][i].tolist()
            assert ids[i]==dict(key=w['key'],group=w['group'],fold=old['folds'][w['group']],canonical=w['key'] in canonical)
            args,_=model.encode_window(w,maps[w['payload']],architecture['schema']);output=net(**args)
            assert torch.equal(capture['context'],data['context'][i])
            for k in ('previous','previous_mask','rounds','observed'):assert torch.equal(args[k],data[k][i])
            if w['key'] in canonical:
                assert w==canonical[w['key']] and maps[w['payload']]==old_maps[w['payload']]
                for k in data:assert torch.equal(data[k][i],old_data[k][old_indices[w['key']]])
            if (i+1)%400==0:print('Verified expanded inputs',i+1,'/',len(windows),flush=True)
    handle.remove();torch.set_num_threads(1);accounting={};values={}
    baseline=json.loads((fit.WORK/'tuning/baseline.json').read_text())
    for lr in plan['learning_rates']:
        for fold in range(4):
            training,held=fit.partition_indices(ids,fold)
            initial=torch.load(original.ROOT/plan['fold_initial'][str(fold)],map_location='cpu',weights_only=False)['model']
            directory=fit.WORK/'tuning'/f'lr{lr:g}-fold{fold}'
            accounting[directory.name]=audit_trace(directory,plan,training,data['observed'],initial,first.PREFIXES,plan['epochs'],lr)
            net.load_state_dict(initial);zero=first.score(net,data,held);assert zero==baseline[f'{lr:g}/{fold}']
            values.setdefault((lr,0),[]).append(zero)
            for entry in json.loads((directory/'trace.json').read_text()):
                if 'validation' not in entry:continue
                net.load_state_dict(torch.load(directory/f"epoch-{entry['epoch']:03d}.pt",map_location='cpu',weights_only=False)['model'])
                actual=first.score(net,data,held);assert actual==entry['validation']
                values.setdefault((lr,entry['epoch']),[]).append(actual)
            print('Verified expanded',directory.name,flush=True)
    for c in selection['candidates']:
        rows=values[(c['learning_rate'],c['epoch'])]
        assert sum(v['rows'] for v in rows)==c['rows']==2945 and sum(v['correct'] for v in rows)==c['correct']
        assert sum(v['nll']*v['rows'] for v in rows)/c['rows']==c['nll']
        assert metrics(sum([v['labels'] for v in rows],[]),sum([v['predictions'] for v in rows],[]))==c['codes']
    chosen=selection['selected'];base=torch.load(original.ROOT/plan['full_initial'],map_location='cpu',weights_only=False)['model']
    accounting['refit']=audit_trace(fit.WORK/'refit',plan,np.arange(len(ids)),data['observed'],base,first.PREFIXES,chosen['epoch'],chosen['learning_rate'])
    predictor=ExpandedCodePredictor();saved=torch.load(fit.WORK/'selected.pt',map_location='cpu',weights_only=False)
    assert saved['selection_sha256']==digest(fit.REPORT/'selection.json') and 'optimizer' not in saved
    assert first.score(predictor.net,data,np.arange(len(ids)))==refit['fit']
    for k,v in base.items():
        if not k.startswith(first.PREFIXES):assert torch.equal(v,saved['model'][k])
    torch.set_num_threads(4)
    cache={w['key']:model.encode_window(w,old_maps[w['payload']],architecture['schema'])[0] for w in old_windows}
    reproduced={}
    for split in ('fit','evaluation'):
        actual=evaluate(predictor.net,old_windows,old_maps,cache,discovery,split,time.perf_counter()+300)
        assert actual==json.loads((fit.WORK/f'{split}-predictions.json').read_text())
        codes=metrics([r['code_label'] for r in actual['records']],[r['code_prediction'] for r in actual['records']])
        assert codes==result['results'][split]['codes'] and actual['summary']==result['results'][split]['summary']
        assert result['results'][split]['target_met']==(codes['accuracy']>=.85)
        reproduced[split]=len(actual['records'])
    assert result['target_met']==result['results']['evaluation']['target_met']
    w=next(w for w in old_windows if w['partition']=='evaluation');state=None
    with torch.no_grad():expected=predictor.net(**cache[w['key']])['code'].argmax(-1).tolist()
    for i,s in enumerate(w['steps']):
        output=predictor.predict(s['input'] if s['observed'] else None,old_maps[w['payload']],s['round'],s['previous'],s['previous_mask'],state)
        assert output['code']==expected[i];state=output['state']
    immutable_json(fit.REPORT/'verification.json',dict(result_sha256=digest(fit.REPORT/'result.json'),
        sources={str(p.relative_to(original.ROOT)):digest(p) for p in (Path(__file__),Path(__file__).with_name('expanded_code_predictor.py'))},
        exact_expanded_windows=1607,exact_original_windows=256,all_frozen_labels_reproduced=True,
        exact_validation_measurements=72,accounting=accounting,exact_final_forecasts=reproduced,
        original_inputs_preserved=True,streaming_predictions=32,seconds=time.perf_counter()-start))
    print('Verified expanded-data weights and',reproduced,'final forecasts',flush=True)


if __name__=='__main__':run()
