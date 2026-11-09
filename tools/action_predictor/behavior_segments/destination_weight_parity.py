"""Postfit full-network selection parity and descriptive goal-distance diagnostics."""
import time
from pathlib import Path
import numpy as np
import torch
from . import destination_weight_fit as fit,code_movement_fit as prior,code_path_fit as movement
from . import data as original,model
from .destination_weights import install
from ..audit import immutable_json
from ..data import digest


def run():
    start=time.perf_counter();plan,architecture,_,_=fit.inputs();rows,ids=fit.cached()
    selection=fit.read(fit.REPORT/'selection.json');fit.check(selection);chosen=selection['selected']
    windows,maps=original.load();bykey={w['key']:w for w in windows};torch.set_num_threads(4)
    fold_results=[]
    for fold in range(4):
        held=[i for i,r in enumerate(ids) if r['fold']==fold and r['canonical']]
        directory=fit.WORK/'tuning'/f"lr{chosen['learning_rate']:g}-fold{fold}"
        trace=fit.read(directory/'trace.json')
        expected=trace['initial'] if chosen['epoch']==0 else trace['epochs'][chosen['epoch']-1]['validation']
        backbone=prior.backbone(fit.ROOT/plan['fold_backbones'][fold],architecture)
        head=fit.new_head(fit.ROOT/plan['fold_backbones'][fold],architecture)
        head.load_state_dict(torch.load(directory/f"epoch-{chosen['epoch']:03d}.pt",weights_only=False)['model']);install(backbone,head)
        outputs={};predictions=[];losses=[];errors=[]
        with torch.no_grad():
            for ri in held:
                item=ids[ri];key=item['key'];w=bykey[key]
                if key not in outputs:
                    args,_=model.encode_window(w,maps[w['payload']],architecture['schema']);outputs[key]=backbone(**args)['goal']
                logits=outputs[key][item['position']].flatten();cell=int(logits.argmax());width=rows[ri]['width']
                p=[cell%width,cell//width];predictions.append(p);g=rows[ri]['goal']
                losses.append(float(-logits.log_softmax(-1)[g[1]*width+g[0]]));errors.append(max(abs(p[0]-g[0]),abs(p[1]-g[1])))
        assert predictions==expected['predictions']
        assert sum(e<=2 for e in errors)==expected['within2'] and errors.count(0)==expected['exact'] and sum(errors)==expected['error_sum']
        error=abs(float(np.mean(losses))-expected['nll']);assert error<2e-6
        fold_results.append(dict(fold=fold,exact_predictions=len(predictions),nll_absolute_difference=error))
    edited=fit.read(fit.WORK/'evaluation-predictions.json');base=fit.read(movement.WORK/'predicted-evaluation-predictions.json')
    fit.check(fit.read(fit.REPORT/'result.json'));distance={};same_current={};changed=0
    for name,package in [('original',base),('edited',edited)]:
        values={'near':[],'far':[]};same=0
        for row in package['records']:
            step=bykey[row['key']]['steps'][row['position']];origin=step['input']['observation']['own'].get('position')
            if row['goal_label'] is None:continue
            g=row['goal_label'];d=max(abs(g[0]-origin['x']),abs(g[1]-origin['y']))
            values['near' if d<=2 else 'far'].append(row)
            same+=row['goal_prediction']==[origin['x'],origin['y']]
        distance[name]={k:dict(rows=len(v),within2=sum(r['goal_error']<=2 for r in v),exact=sum(r['goal_error']==0 for r in v),
            mean_error=float(np.mean([r['goal_error'] for r in v])) if v else None) for k,v in values.items()}
        same_current[name]=same
    changed=sum(a['goal_prediction']!=b['goal_prediction'] for a,b in zip(edited['records'],base['records']))
    immutable_json(fit.REPORT/'parity-supplement.json',dict(result_sha256=digest(fit.REPORT/'result.json'),
        sources=fit.bindings([Path(__file__)]),full_network_selected_fold_parity=fold_results,
        goal_distance_from_current=distance,current_position_predictions_on_goal_rows=same_current,
        changed_goal_choices_on_all699_queries=changed,seconds=time.perf_counter()-start,
        qualification='Postfit descriptive diagnostics only; no new optimization or checkpoint selection.'))
    print('Full-network selected-fold predictions match exactly; diagnostics',distance,flush=True)


if __name__=='__main__':run()
