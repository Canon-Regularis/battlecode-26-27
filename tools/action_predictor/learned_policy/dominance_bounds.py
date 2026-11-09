"""Conservative fixed-distribution reweighting bound, not an inferred policy."""
import json
import sys
import numpy as np
from .sequence_data import ROOT, BASE, WORK, REPORT
from ..audit import immutable_json
from ..data import digest


def run(identifier, split):
    path=WORK/f'runs/{identifier}/{split}-components.npz'
    with np.load(path) as z: index=z['index'];modes=z['head_modes'];mixture=z['mixture_mode']
    dataset=BASE/'combined-train.npz' if split=='train' else BASE.parent/'v4/validation.npz'
    with np.load(dataset) as z:y=z['y'][index];target=z['py'][index]
    with np.load(WORK/f'runs/{identifier}/{split}-predictions.npz') as z:typed=z['prediction'][index]==y
    direction=np.load(BASE.parent/f'v7/{split}-direction.npy')[index]
    same=(modes==modes[:,:1]).all(-1);valid=(target>=0)&(target<289)
    common_wrong=same&(modes[:,0]!=target);forced=common_wrong|~valid
    correct=(mixture==target)&valid
    masks=dict(move=y==8,blocked=y==3,continuation=(y==8)&(direction==2),change=(y==8)&(direction==3))
    results={}
    for name,m in masks.items():
        results[name]=dict(rows=int(m.sum()),actual_conditional_correct=int((m&correct).sum()),
            common_top_destination_wrong=int((m&common_wrong).sum()),
            recorded_coordinate_unrepresentable=int((m&~valid).sum()),
            conservative_conditional_ceiling_under_current_reweighting=int((m&~forced).sum()),
            current_conditional_errors_provably_unfixable_by_current_reweighting=int((m&~correct&forced).sum()),
            typed_destination_errors=int((m&typed&~correct).sum()),
            typed_destination_errors_provably_unfixable_by_current_reweighting=int((m&typed&~correct&forced).sum()))
    immutable_json(REPORT/f'{identifier}-{split}-dominance-bound.json',dict(
        results=results,component_artifact_sha256=digest(path),
        component_receipt_sha256=digest(REPORT/f'{identifier}-{split}-components.json'),
        input_receipt_sha256=digest(REPORT/'policy-input-bindings.json'),
        direction_sha256=digest(BASE.parent/f'v7/{split}-direction.npy'),source_sha256=digest(__file__),
        proof='If every component has the same first-argmax coordinate q and q differs from recorded t, q weakly dominates t in every component. If q<t, ties also choose q. If q>t, each component must strictly prefer q. Thus t cannot be first-argmax of any nonnegative current mixture. This includes the deterministic tie rule.',
        interpretation='Conservative oracle upper bound holding CURRENT component distributions and past state fixed. Other non-common-mode rows may also be unreachable; their reachability is unresolved. It is not achieved accuracy, a full-policy/architecture ceiling, an intent label or oracle routing used by the predictor. Retraining components or changing past goal state can change the bound.',
        new_fits=0,reserved_opened=0))
    print(identifier,split,results,flush=True)


if __name__=='__main__':run(*sys.argv[1:])
