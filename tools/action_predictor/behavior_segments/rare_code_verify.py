"""Reconstruct analytic edits, held-game selection, and checkpoint forecasts."""
import json
import time
import numpy as np
import torch
from .rare_code_edit import ROOT, REPORT, WORK, BASE, BASE_WORK, select, solve_head, make_state, metrics, checks
from .rare_code_predictor import RareCodePredictor
from . import model
from .data import load
from .study import check, evaluate
from ..data import digest
from ..audit import immutable_json


def run():
    torch.set_num_threads(4)
    frozen = json.loads((REPORT/'plan.json').read_text())
    result = json.loads((REPORT/'result.json').read_text())
    selection = json.loads((REPORT/'selection.json').read_text())
    for kind in ('sources', 'inputs'):
        for p,h in frozen[kind].items(): assert digest(ROOT/p) == h, p
    for p,h in result['bindings'].items(): assert digest(ROOT/p) == h, p
    assert result['selection_sha256'] == digest(REPORT/'selection.json')
    assert selection['plan_sha256'] == digest(REPORT/'plan.json')
    bank = np.load(WORK/'fitting-hidden.npz'); labels = bank['labels']
    banks = {s:bank[f'history{s:g}'] for s in frozen['history_scales']}
    ids = json.loads((WORK/'fitting-identities.json').read_text())
    name, candidates, folds = select(banks, labels, ids['groups'], frozen['ridge_values'])
    assert name == selection['selected'] and candidates == selection['candidates'] and folds == selection['folds']
    candidate = candidates[name]; supported = sorted(set(map(int, labels)))
    weight,bias = solve_head(banks[candidate['history_scale']], labels, candidate['ridge'], supported)
    base = torch.load(BASE_WORK/'S01-run/final.pt',map_location='cpu',weights_only=False)['model']
    saved = torch.load(WORK/'selected.pt',map_location='cpu',weights_only=False)
    expected = make_state(base,candidate['history_scale'],weight,bias)
    assert 'optimizer' not in saved and saved['base_checkpoint_sha256'] == digest(BASE_WORK/'S01-run/final.pt')
    assert digest(WORK/'selected.pt') == selection['checkpoint_sha256']
    for k,v in expected.items(): assert torch.equal(v,saved['model'][k]) and torch.isfinite(v).all(), k
    changed = {k:int((v != base[k]).sum()) for k,v in expected.items() if not torch.equal(v,base[k])}
    assert changed == result['changed_tensors']
    assert set(changed) <= {'memory.weight_ih','code.weight','code.bias'}
    assert torch.equal(expected['memory.weight_ih'][:,:32],base['memory.weight_ih'][:,:32])
    assert torch.equal(expected['memory.weight_ih'][:,55:],base['memory.weight_ih'][:,55:])
    plan = json.loads((BASE/'protocol.json').read_text()); check(plan)
    discovery = json.loads((BASE/'discovery.json').read_text()); windows,maps = load()
    cache = {w['key']: model.encode_window(w,maps[w['payload']],plan['schema'])[0] for w in windows}
    net = model.SegmentPolicy(plan['schema'],8).eval(); captured = {}
    handle = net.code.register_forward_pre_hook(lambda module,args: captured.update(hidden=args[0].detach().numpy()))
    for scale,x in banks.items():
        net.load_state_dict(make_state(base,scale)); actual=[]; identities=[]; truth=[]; groups=[]
        with torch.no_grad():
            for w in windows:
                if w['partition'] != 'fit': continue
                net(**cache[w['key']]); take=cache[w['key']]['observed'].bool().numpy()
                actual.extend(captured['hidden'][take])
                for i in np.flatnonzero(take):
                    identities.append([w['key'],int(i)]); truth.append(discovery['labels'][w['key']][i]);groups.append(w['group'])
        np.testing.assert_array_equal(actual,x)
        assert identities == ids['identities'] and groups == ids['groups'] and truth == labels.tolist()
    handle.remove()
    predictor = RareCodePredictor(); reproduced = {}
    for split in ('fit','evaluation'):
        value = evaluate(predictor.net,windows,maps,cache,discovery,split,time.perf_counter()+300)
        assert value == json.loads((WORK/f'{split}-predictions.json').read_text())
        y=[r['code_label'] for r in value['records']]
        codes=metrics(y,[r['code_prediction'] for r in value['records']],sorted(set(y)|set(supported)))
        assert codes == result['results'][split]['codes']
        reference=json.loads((BASE_WORK/'S01-run'/f'{split}-predictions.json').read_text())
        assert checks(value,reference,codes,supported,sorted(set(y)-set(supported))) == result['results'][split]['checks']
        reproduced[split]=len(y)
    # Exercise streaming code classification with exactly the same first-window causal inputs.
    window=next(w for w in windows if w['partition']=='evaluation'); state=None
    with torch.no_grad(): batch_codes=predictor.net(**cache[window['key']])['code'].argmax(-1).tolist()
    for i,step in enumerate(window['steps']):
        out=predictor.predict(step['input'] if step['observed'] else None,maps[window['payload']],step['round'],
                              step['previous'],step['previous_mask'],state)
        assert out['code']==batch_codes[i]
        state=out['state']
    for p,h in frozen['inputs'].items(): assert digest(ROOT/p)==h,p
    immutable_json(REPORT/'verification.json',dict(result_sha256=digest(REPORT/'result.json'),
        sources={str(p.relative_to(ROOT)):digest(p) for p in (ROOT/'tools/action_predictor/behavior_segments/rare_code_verify.py',ROOT/'tools/action_predictor/behavior_segments/rare_code_predictor.py')},
        exact_hidden_rows_per_scale=len(labels),exact_selected_forecasts=reproduced,
        analytic_selection_and_weights_reproduced=True,changed_tensors=changed,
        streaming_code_predictions=32,original_inputs_unchanged=True,optimizer_updates=0))
    print(json.dumps(dict(changed=changed,reproduced=reproduced,streaming_codes=32),indent=2))


if __name__=='__main__': run()
