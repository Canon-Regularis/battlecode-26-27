"""Final-review reporting corrections from saved outputs only; no inference/fit."""
import json
import numpy as np
from .protocol import ROOT,BASE,WORK,REPORT
from .data import read
from ..audit import immutable_json
from ..data import digest

def run():
    result={};bindings={}
    for split in ('train','validation'):
        rawpath=BASE/'combined-train.npz' if split=='train' else BASE.parent/'v4/validation.npz'
        with np.load(rawpath) as z:y=z['y'];py=z['py']
        p=read(WORK/f'runs/X00/{split}-predictions.npz');old=read(BASE.parent/f'v9/runs/G00/{split}-predictions.npz');c=read(WORK/f'runs/X00/{split}-components.npz');ix=c['index'];heads=c['head_modes'];gate=c['gate'];correct=(heads==py[ix,None])&(py[ix,None]<289);mixture=(c['mixture_mode']==py[ix])&(py[ix]<289);available=correct.any(1);typed=p['prediction'][ix]==y[ix];larger=gate.argmax(1);top_correct=correct[np.arange(len(ix)),larger];ties=gate[:,0]==gate[:,1];direction=np.load(BASE.parent/f'v7/{split}-direction.npy');contexts={'all_movement':y[ix]==8,'typed_movement':(y[ix]==8)&typed,'change':(y[ix]==8)&(direction[ix]==3)};rows={}
        for name,m in contexts.items():
            miss=m&available&~mixture;equal=miss&ties
            rows[name]=dict(rows=int(m.sum()),available_mode_misses=int(miss.sum()),correct_mode_in_lower_weight_head=int((miss&~top_correct&~ties).sum()),correct_mode_in_larger_weight_head=int((miss&top_correct&~ties).sum()),equal_gate_weight_misses=int(equal.sum()))
            assert rows[name]['available_mode_misses']==sum(rows[name][k] for k in ('correct_mode_in_lower_weight_head','correct_mode_in_larger_weight_head','equal_gate_weight_misses'))
        # Correct preservation scope: wrong move forecasts may change destination
        # even when the recorded action belongs to another family.
        changed=p['proposed_coordinate']!=old['proposed_coordinate'];recorded_other=~np.isin(y,[3,8]);predicted_other=~np.isin(p['prediction'],[3,8]);assert not (changed&predicted_other).any()
        result[split]=dict(mode_weight_decomposition=rows,recorded_nonmovement_rows_with_changed_wrong_movement_destination=int((changed&recorded_other).sum()),preserved_predicted_nonmovement_commands=True,preserved_type_choices=bool(np.array_equal(p['prediction'],old['prediction'])))
        bindings[split]=dict(predictions=digest(WORK/f'runs/X00/{split}-predictions.npz'),G00_predictions=digest(BASE.parent/f'v9/runs/G00/{split}-predictions.npz'),components=digest(WORK/f'runs/X00/{split}-components.npz'),direction=digest(BASE.parent/f'v7/{split}-direction.npy'))
    immutable_json(REPORT/'X00-final-review-addendum.json',dict(results=result,bindings=bindings,source_sha256=digest(__file__),command='python -m tools.action_predictor.movement_experts.final_addendum',supersedes='Broad preservation wording in X00-REPORT.md: types, nonmovement conditional parameter paths, commands with PREDICTED nonmovement families, and nonmovement category scores/losses stay unchanged. It does not mean every wrong movement forecast on a recorded nonmovement row has unchanged destination.',interpretation='Gate weight alone does not choose a command. Both weights AND complete component probability shapes determine the correctly implemented mixture MAP. No A00 fallback-veto mismatch. Decomposition is diagnostic after inference, not intent supervision or oracle routing. Exact scalar-gate MAP reachability remains proposed, not executed.',new_fits=0,new_inference=0,reserved_opened=0));print(json.dumps(result))

if __name__=='__main__':run()
