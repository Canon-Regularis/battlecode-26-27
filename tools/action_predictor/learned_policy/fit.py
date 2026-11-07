"""One registered sequential-policy fit; no extra fit or deployment orchestration."""
import argparse,json,subprocess,time,copy
import numpy as np
import torch
from .sequence_data import ROOT,BASE,WORK,REPORT
from .model import GoalPolicy
from .data import load,chunks,causal_inputs,geometry,targets
from .inference import infer,select_state
from ..priority_fit_v3 import load_base
from ..movement_experts.evaluate import summary,paired
from ..audit import immutable_json
from ..data import digest
from .. import reliable_train as rt

def freeze():
    names=('model.py','data.py','inference.py','fit.py','execution.py','actor.py','public_inputs.py','test_execution.py','test_causality.py')
    value=dict(id='V16-goal-policy-pilot',fits=['L00','L01'],seed=20261114,learned_goals=4,initial_root_retention=.99,retention_learned=True,random_goal_offset_initial_std=.1,goal_offset_unit='32tiles; randomseedinitialization, no named strategy/direction preference',auxiliary_goal_weight=.05,training=dict(lr=.0003,weight_decay=.01,clip=5,max_rounds=35,patience=6,min_improvement=.0001,actor_batch=32,unroll=8,dropout='No extra dropout beyond the reused model; complexity controlled by shared execution and weight decay',checkpoint='whole original DEV observed command NLL only, auxiliary target loss excluded'),
      interpretation='Two same-parameter policies; L00 resets goalbelief/positions, L01learns retention across actualroot gaps, conditioned on remembered relative goal/soft root age and current observation. Allaction/spatial heads trainable from warmM01. Achieved endpoint supervises goalforecast, NOT actual Fish intent. Policy predicts goals from past only and lowlevel executes conditioned on predicted goals. Four latent states may collapse or represent tactical phases; report rather than force interpretations.',
      observations='Reused M01 current/action representation plus16actual earlier personal observations withavailability/roundgaps, all119fieldpersonallyknown champ/camp/self/dead entitytokens, ALLpublicaltars andALLtiles in bothspawnrectangles. No nearestentitycutoff, manualobjective ranking or hidden dynamic state. New learned entity/goal projections initializezero to preserve warmexecution initially. Oldgoal-memory scoring unused.',
      sequence='Irregular selected observations with true intervening ownroot counts/order-last16windows and masks; no pretend consecutive sampledturns. Goal belief and worldgoalestimates persist across chunks; gradients detach every8selectednodes. Trainingteacherforced Fish past, deployedcontroller updates only its own executedactions. Unobserved intermediate decision posterior unavailable, gap dynamics explicitly imputed; replay fidelity is not closed-loop performance.',
      runtime='SDK4dispatch implemented and call-recording tested, not engine-tested. HostTorchpolicy first, native export/liveSDKobservationbridge/draftlearning/unavailable purchase arguments and target identity remain required for eventual complete executable bot. No hand-designed farming/banking/pathfinding fallback.',sources={n:digest(__file__.replace('fit.py',n)) for n in names},sequence_plan_sha256=digest(REPORT/'sequence-plan.json'),achieved_goal_plan_sha256=digest(REPORT/'achieved-goal-plan.json'),new_fits=0,reserved_opened=0)
    immutable_json(REPORT/'policy-design.json',value);return value

def verify():
    old=ROOT/'tools/action_predictor/experiments';bindings={}
    expected={BASE/'combined-train.npz':'39386010575ad30add064fdae750680f34cfcc732c4fd00fb657875ff4c61ffb',BASE.parent/'v4/validation.npz':'01a15e1e10f68922334a5367bb825c8ef9bbe228ae7a9e86e92aae9609b204ed',BASE/'runs/M01/model.pt':json.loads((old/'v5/M01.json').read_text())['checkpoint_sha256'],BASE.parent/'v8/runs/P05/model.pt':json.loads((old/'v8/P05.json').read_text())['checkpoint_sha256']}
    for split in ('train','validation'):
        for name in ('sequences','goals'):expected[WORK/f'{split}-{name}.npz']=json.loads((REPORT/f'{split}-{name}.json').read_text())['arrays_sha256' if name=='sequences' else 'sha256']
        expected[WORK/f'{split}-public.json']=json.loads((REPORT/f'{split}-public.json').read_text())['cache_sha256']
        legacy=json.loads((old/f'v13/{split}-probabilities.json').read_text());v14=json.loads((old/f'v14/{split}-data.json').read_text())
        for name in ('modes','mode-logq'):
            p=BASE.parent/f'v13/{split}-{name}.npy';expected[p]=legacy['files'][name]
        expected[BASE.parent/f'v14/{split}-type-logp.npy']=v14['files']['type-logp']
    v7=json.loads((old/'v7/data-ready.json').read_text())
    for name,h in v7['files'].items():
        if name=='observations.npy' or any(name==f'{s}-{k}.npy' for s in ('train','validation') for k in ('sequence','gaps','direction','available','near_obstacle')):expected[BASE.parent/'v7'/name]=h
    g=json.loads((old/'v9/G00.json').read_text())
    for split in ('train','validation'):expected[BASE.parent/f'v9/runs/G00/{split}-predictions.npz']=g['train_predictions_sha256' if split=='train' else 'predictions_sha256']
    entities=json.loads((old/'v9/entity-cache-ready.json').read_text())
    for name,h in entities['files'].items():expected[BASE.parent/'v9/entities'/name]=h
    for p,h in expected.items():assert digest(p)==h,str(p);bindings[str(p.relative_to(ROOT))]=h
    immutable_json(REPORT/'policy-input-bindings.json',dict(files=bindings,new_fits=0,reserved_opened=0));return bindings

def run(identifier):
    design=freeze();rt.setup(20261114);directory=WORK/'runs'/identifier;assert not directory.exists(),'Preserve attempted fit';directory.mkdir(parents=True);verify();teacher,saved=load_base();model=GoalPolicy(teacher,identifier=='L01');data={s:load(s,saved) for s in ('train','validation')};t=data['train'];v=data['validation'];opt=torch.optim.AdamW([p for p in model.parameters() if p.requires_grad],lr=.0003,weight_decay=.01);rng=np.random.default_rng(20261114);trace=[];best=float('inf');selected=0;updates=0;commit=subprocess.run(['git','rev-parse','HEAD'],cwd=ROOT,capture_output=True,text=True,check=True).stdout.strip();tick=time.perf_counter()
    for epoch in range(1,36):
        state=model.empty(32);model.train();seen=np.zeros(len(t['raw']['y']),np.uint8);total=0.;aux_total=0.;start=time.perf_counter()
        for rows in chunks(t['sequences'],rng):
            opt.zero_grad();losses=[];auxiliary=[];denominator=0
            for ids in rows:
                valid=ids>=0;ix=np.maximum(ids,0);mask=torch.from_numpy(valid);step=model.begin(**causal_inputs(t,ix),state=state);target=targets(t,ix);loss,post=model.observed(step,**geometry(t,ix),**{k:target[k] for k in ('y','py','priority_parameter_nll')});aux=model.achieved_goal_loss(step,target['achieved'],target['achievement_available']);losses.append(loss[mask].sum());auxiliary.append(aux[mask].sum());denominator+=int(valid.sum());state=select_state(state,post,mask);seen[ids[valid]]+=1
            primary=torch.stack(losses).sum()/denominator;aux=torch.stack(auxiliary).sum()/denominator;objective=primary+.05*aux;objective.backward();torch.nn.utils.clip_grad_norm_([p for p in model.parameters() if p.requires_grad],5);opt.step();updates+=1;total+=float(primary.detach())*denominator;aux_total+=float(aux.detach())*denominator;state={k:v.detach() for k,v in state.items()}
        assert np.all(seen==1);forecast,_=infer(model,v,decode=False);nll=float(forecast['nll'].mean());trace.append(dict(round=epoch,train_command_nll=total/len(seen),train_achieved_aux_nll=aux_total/len(seen),DEV_command_nll=nll,updates=updates,seconds=time.perf_counter()-start));torch.save(dict(state=model.state_dict(),optimizer=opt.state_dict(),mean=saved['mean'],std=saved['std'],config=saved['config'],persistent=model.persistent,round=epoch,source_commit=commit,torch_rng=torch.get_rng_state(),numpy_rng=rng.bit_generator.state,design_sha256=digest(REPORT/'policy-design.json')),directory/f'round-{epoch:02d}.pt');print(identifier,trace[-1],flush=True)
        if nll<best-.0001:best=nll;selected=epoch
        if epoch-selected>=6:break
    selected_state=torch.load(directory/f'round-{selected:02d}.pt',weights_only=False);model.load_state_dict(selected_state['state']);results={};comparisons={};hashes={}
    for split,d in data.items():
        forecast,goals=infer(model,d,decode=True);np.savez_compressed(directory/f'{split}-predictions.npz',**forecast);np.savez_compressed(directory/f'{split}-goals.npz',**goals);hashes[split]=digest(directory/f'{split}-predictions.npz');direction=np.load(BASE.parent/f'v7/{split}-direction.npy');masks={'all':np.ones(len(d['raw']['y']),bool)}
        if split=='train':masks['natural']=np.load(BASE.parent/'v9/frequency/natural-mask.npy')
        q=dict(raw=d['raw'],direction=direction,available=np.load(BASE.parent/f'v7/{split}-available.npy'),near=np.load(BASE.parent/f'v7/{split}-near_obstacle.npy'));results[split]={k:summary(q,forecast,m) for k,m in masks.items()}
        if split=='validation':
            comparisons['G00']=paired(q,forecast,d['baseline'])
            if identifier=='L01':
                with np.load(WORK/'runs/L00/validation-predictions.npz') as z:control={k:z[k] for k in z.files}
                comparisons['L00']=paired(q,forecast,control)
    immutable_json(REPORT/f'{identifier}.json',dict(selected_round=selected,trace=trace,parameters=sum(p.numel() for p in model.parameters()),completed_updates=updates,selected_updates=trace[selected-1]['updates'],results=results,comparisons=comparisons,predictions_sha256=hashes,checkpoint_sha256=digest(directory/f'round-{selected:02d}.pt'),design_sha256=digest(REPORT/'policy-design.json'),source_commit=commit,seconds=time.perf_counter()-tick,new_fits=1,reserved_opened=0,promoted=False,three_seed_confirmed=False));print('Completed',identifier,'fresh Sol xhigh review required',flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('identifier',choices=['L00','L01']);run(p.parse_args().identifier)
