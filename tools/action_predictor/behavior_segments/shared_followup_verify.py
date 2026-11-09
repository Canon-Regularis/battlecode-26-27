"""Verify direct edits and64-weight refits without replaying optimization."""
import argparse,time
import numpy as np
import torch
from . import shared_execution_edit as edit,shared_readout_fit as refit
from .planner_weight_verify import equal
from .shared_execution_edit_predictor import CalibratedSharedPlanner
from .shared_readout_predictor import ReadoutSharedPlanner
from ..audit import immutable_json
from ..data import digest


def streaming(prior,predictor,predictions):
    _,_,architecture,_,_=prior.inputs();windows,maps=prior.prior.base.heading.original.load();_,history,_=prior.prior.base.prior.encoded(windows,maps,architecture);bank=torch.load(prior.WORK/'evaluation.pt',weights_only=False);expected={(r['key'],r['position']):(r,p) for r,p in zip(bank['records'],predictions)};evaluation=[w for w in windows if w['partition']=='evaluation'];activity={w['key']:sum(r['active'] for r in bank['records'] if r['key']==w['key']) for w in evaluation};chosen=[evaluation[0]]
    for w in sorted(evaluation,key=lambda w:-activity[w['key']]):
        if w not in chosen:chosen.append(w)
        if len(chosen)==3:break
    turns=active=absent=0
    for w in chosen:
        state=None
        for i,s in enumerate(w['steps']):
            v=predictor.predict(s['input'] if s['observed'] else None,maps[w['payload']],s['round'],s['previous'],s['previous_mask'],state,previous_moves=history[w['key']][i]);state=v['state'];turns+=1
            if not s['observed']:continue
            r,pred=expected[(w['key'],i)];assert state['objective_identity']==r['selected'];own=s['input']['observation']['own'].get('position')
            if own is not None:
                dx,dy=prior.prior.model.OFFSETS[pred];assert v['shared_movement']==(own['x']+dx,own['y']+dy) and v['shared_execution_used'];active+=r['active'];absent+=not r['active']
    assert active>0 and absent>0;return dict(turns=turns,active=active,absent=absent)


def edits():
    start=time.perf_counter();p=edit.inputs();torch.set_num_threads(1)
    for name in ('selection','result'):edit.check(edit.read(edit.REPORT/(name+'.json')))
    cs,direct=edit.candidates(p);s=edit.read(edit.REPORT/'selection.json');assert cs==s['candidates'] and direct==s['direct'] and edit.choose(cs,direct,p)==s['selected']
    original=edit.weights('full');selected=torch.load(edit.WORK/'selected.pt',weights_only=True);assert equal(selected,edit.edit(original,**s['selected']['setting']));changed={k:int((v!=original[k]).sum()) for k,v in selected.items()};torch.set_num_threads(4);r=edit.read(edit.REPORT/'result.json');actual=edit.assessment();assert all(equal(v,r[k]) for k,v in actual.items())
    stream=streaming(edit.prior,CalibratedSharedPlanner(),r['results']['evaluation']['predictions']);immutable_json(edit.REPORT/'verification.json',dict(result_sha256=digest(edit.REPORT/'result.json'),source_sha256=digest(__file__),settings_reproduced=len(cs),selection_exact=True,weight_edits_exact=True,changed_scalars=changed,all_forecasts_reproduced=True,streaming=stream,optimizer_updates=0,seconds=time.perf_counter()-start));print('VERIFIED weight edits',changed,stream,flush=True)


def readouts():
    start=time.perf_counter();p=refit.inputs();torch.set_num_threads(1)
    for name in ('fit','result'):refit.check(refit.read(refit.REPORT/(name+'.json')))
    s=refit.read(refit.REPORT/'selection.json');updates=0;final_deltas={};banks={n:refit.bank(n) for n in ['fold0','fold1','fold2','fold3','full']};direct=refit.read(refit.prior.REPORT/'selection.json')['candidates']['goal'][0]['nll_sum']
    for arm in refit.ARMS:
        values={}
        for name in ['fold0','fold1','fold2','fold3','full']:
            b=banks[name];full=name=='full';fold=-1 if full else int(name[-1]);directory=refit.WORK/arm/('refit' if full else name);epochs=s['selected'][arm]['epoch'] if full else p['epochs'];indices=np.arange(len(b['records'])) if full else np.array([i for i,r in enumerate(b['records']) if r['fold']!=fold]);trace=refit.read(directory/'trace.json');initial=refit.weights(name)['layers.2.weight'];assert torch.equal(torch.load(directory/'epoch-000.pt',weights_only=True)['weight'],initial);rng=np.random.default_rng(p['seed']);u=0
            assert len(trace['epochs'])==epochs
            for e in trace['epochs']:
                assert e['order']==rng.permutation(indices).tolist();assert len(e['norms'])==(len(indices)+p['batch']-1)//p['batch'] and np.isfinite(e['norms']).all();u+=len(e['norms'])
            updates+=u;final=torch.load(directory/'final.pt',weights_only=False);assert final['rng']==rng.bit_generator.state;assert list(final['model'])==['weight'] and torch.isfinite(final['model']['weight']).all();final_deltas[arm+'/'+name]=float((final['model']['weight']-initial).norm())
            for group in final['optimizer']['param_groups']:assert group['lr']==p['lr'] and group['weight_decay']==0
            for state in final['optimizer']['state'].values():assert int(state['step'])==u and all(not torch.is_tensor(v) or torch.isfinite(v).all() for v in state.values())
            if epochs:assert final_deltas[arm+'/'+name]>0
            if full:
                selected=torch.load(refit.WORK/(arm+'-selected.pt'),weights_only=True);original=refit.weights('full');assert torch.equal(selected['layers.2.weight'],final['model']['weight']);assert all(torch.equal(v,original[k]) for k,v in selected.items() if k!='layers.2.weight')
            else:
                held=np.array([i for i,r in enumerate(b['records']) if r['fold']==fold and r['canonical']]);net=refit.Readout(initial)
                for e in range(0,epochs+1,p['every']):
                    net.load_state_dict(torch.load(directory/f'epoch-{e:03d}.pt',weights_only=True));v=refit.score(net,b,held);assert equal(v,trace['validation'][str(e)]);values.setdefault(e,[]).append(v)
                other=refit.read(refit.WORK/'likelihood'/name/'trace.json');assert [e['order'] for e in trace['epochs']]==[e['order'] for e in other['epochs']]
        cs=[dict(epoch=e,**refit.combine(vs)) for e,vs in values.items()];assert cs==s['candidates'][arm] and refit.select(cs,direct)==s['selected'][arm]
    torch.set_num_threads(4);r=refit.read(refit.REPORT/'result.json');actual=refit.assessment();assert all(equal(v,r[k]) for k,v in actual.items());streams={a:streaming(refit.prior,ReadoutSharedPlanner(a),r['results']['evaluation'][a]['predictions']) for a in refit.ARMS}
    immutable_json(refit.REPORT/'verification.json',dict(result_sha256=digest(refit.REPORT/'result.json'),source_sha256=digest(__file__),fold_measurements=24,optimizer_updates_accounted=updates,only64_weights_trainable=True,all_other_weights_preserved=True,selected_weights_exact=True,all_forecasts_reproduced=True,matched_sampling=True,final_readout_weight_changes=final_deltas,streaming=streams,optimizer_replays=0,seconds=time.perf_counter()-start));print('VERIFIED readout refits',updates,streams,flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('command',choices=('edits','readouts'));globals()[parser.parse_args().command]()
