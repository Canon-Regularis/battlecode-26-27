"""Read-only checkpoint/activation/gradient diagnosis; no optimizer construction."""
import json,hashlib
from collections import Counter
import numpy as np
import torch
from .data import ROOT,REPORT,WORK,load
from . import model
from .study import check,targets,loss_terms
from ..audit import immutable_json
from ..data import digest


def describe(a):
    a=np.asarray(a);return dict(mean=float(a.mean()),std=float(a.std()),min=float(a.min()),max=float(a.max()))


def run():
    torch.set_num_threads(4);plan=json.loads((REPORT/'protocol.json').read_text());check(plan)
    saved=torch.load(WORK/'S01-run/final.pt',map_location='cpu',weights_only=False)
    initial=torch.load(WORK/'S01-run/initial.pt',map_location='cpu',weights_only=True)
    result=json.loads((REPORT/'S01.json').read_text())
    for name in ('initial.pt','final.pt'):
        path=WORK/'S01-run'/name;assert digest(path)==result['bindings'][str(path.relative_to(ROOT))]
    net=model.SegmentPolicy(plan['schema'],plan['codes']);net.load_state_dict(saved['model']);net.eval()
    windows,maps=load();windows=[w for w in windows if w['partition']=='fit'];d=json.loads((REPORT/'discovery.json').read_text())
    selected={w['key'] for w in sorted(windows,key=lambda w:hashlib.sha256(w['key'].encode()).hexdigest())[:16]}
    captured={};gates=[];contexts=[]
    def codes_hook(module,args):captured['hidden']=args[0].detach()
    def context_hook(module,args,out):captured['context_raw']=out.detach()
    def memory_hook(module,args):
        x,h=args;ih=x@module.weight_ih.T+module.bias_ih;hh=h@module.weight_hh.T+module.bias_hh
        ir,iz,inn=ih.chunk(3,-1);hr,hz,hn=hh.chunk(3,-1)
        r=(ir+hr).sigmoid();z=(iz+hz).sigmoid();n=(inn+r*hn).tanh()
        captured.setdefault('gates',[]).append(torch.cat((r,z,n),-1).detach())
        captured.setdefault('inputs',[]).append(x.detach())
    hooks=[net.code.register_forward_pre_hook(codes_hook),net.context.register_forward_hook(context_hook),net.memory.register_forward_pre_hook(memory_hook)]
    hidden=[];logits=[];labels=[];observed_inputs=[];gradient=[];ablations={k:[] for k in ('normal','zero_code_bias','zero_map_context','zero_history','history_x5')}
    row_targets=[]
    for w in windows:
        args,_=model.encode_window(w,maps[w['payload']],plan['schema']);take=args['observed'].bool();captured.clear()
        with torch.no_grad():out=net(**args)
        hidden.append(captured['hidden'][take].numpy());logits.append(out['code'][take].numpy())
        truth=np.asarray(d['labels'][w['key']])[take.numpy()];labels.extend(truth.tolist())
        gates.append(torch.cat(captured['gates'])[take].numpy());observed_inputs.append(torch.cat(captured['inputs'])[take].numpy())
        contexts.append(captured['context_raw'][take].numpy())
        if w['key'] not in selected:continue
        row_targets.extend(truth.tolist())
        ablations['normal'].extend(out['code'][take].argmax(-1).tolist())
        ablations['zero_code_bias'].extend((out['code'][take]-net.code.bias.detach()).argmax(-1).tolist())
        # Counterfactual activation edits, not new trained policies.
        def zero_context(module,args,value):return torch.zeros_like(value)
        handle=net.context.register_forward_hook(zero_context)
        with torch.no_grad():changed=net(**args)
        handle.remove();ablations['zero_map_context'].extend(changed['code'][take].argmax(-1).tolist())
        for name,factor in (('zero_history',0),('history_x5',5)):
            altered=dict(args,previous=args['previous']*factor)
            if factor==0:altered['previous_mask']=torch.zeros_like(args['previous_mask'])
            with torch.no_grad():changed=net(**altered)
            ablations[name].extend(changed['code'][take].argmax(-1).tolist())
        out=net(**args);support,movement,goal=targets(w,d['endpoints'][w['key']],maps[w['payload']]['width'])
        terms=loss_terms(out,support,movement,goal,torch.tensor(d['labels'][w['key']]),args['observed'])
        parameters=[p for name,p in net.named_parameters() if name.startswith(('memory.','context.','code.'))]
        gradients=[]
        for term,weight in zip(terms,(1.,.2,.2)):
            g=torch.autograd.grad(term*weight,parameters,retain_graph=True,allow_unused=True)
            gradients.append(torch.cat([torch.zeros_like(p).flatten() if v is None else v.flatten() for v,p in zip(g,parameters)]).detach().double())
        n=[float(g.norm()) for g in gradients]
        cos=lambda a,b:float(torch.dot(a,b)/(a.norm()*b.norm()).clamp_min(1e-30))
        gradient.append(dict(key=w['key'],weighted_norms=n,code_vs_move_cosine=cos(gradients[2],gradients[0]),code_vs_goal_cosine=cos(gradients[2],gradients[1])))
    for h in hooks:h.remove()
    h=np.concatenate(hidden);l=np.concatenate(logits);y=np.asarray(labels);g=np.concatenate(gates);x=np.concatenate(observed_inputs);c=np.concatenate(contexts)
    p=torch.from_numpy(l).softmax(-1).numpy();frequency=np.bincount(y,minlength=8)/len(y)
    params={name:dict(initial_norm=float(initial[name].norm()),final_norm=float(v.norm()),change_norm=float((v-initial[name]).norm()),max_abs=float(v.abs().max())) for name,v in net.state_dict().items()}
    weight=net.code.weight.detach().numpy();bias=net.code.bias.detach().numpy();pairs={}
    for k in sorted(set(y)-{0}):
        selected_y=y==k;state=h[selected_y]@(weight[0]-weight[k]);margin=state+bias[0]-bias[k]
        pairs[str(k)]=dict(rows=int(selected_y.sum()),class0_minus_class_bias=float(bias[0]-bias[k]),hidden_contribution=describe(state),total_margin=describe(margin),
            mean_probabilities=p[selected_y].mean(0).tolist())
    centered=h-h.mean(0);singular=np.linalg.svd(centered,compute_uv=False);energy=singular**2
    prior_nll=float(-np.log(frequency[y]).mean());learned_nll=float(torch.nn.functional.cross_entropy(torch.from_numpy(l),torch.from_numpy(y)))
    output=dict(source_sha256=digest(__file__),checkpoint_sha256=digest(WORK/'S01-run/final.pt'),scope='Fitting-only read-only weights/activations;16fixed-hash windows for interventions and gradients. No optimizer construction or parameter updates.',
        rows=len(y),target_counts=dict(Counter(map(int,y))),predicted_counts=dict(Counter(map(int,p.argmax(-1)))),
        initial_code_bias=initial['code.bias'].tolist(),final_code_bias=bias.tolist(),mean_probabilities=p.mean(0).tolist(),
        majority_frequency=frequency.tolist(),constant_empirical_prior_nll=prior_nll,learned_code_nll=learned_nll,
        probability_std=p.std(0).tolist(),hidden_std=describe(h.std(0)),hidden_top3_variance_fraction=float(energy[:3].sum()/energy.sum()),
        context_preactivation=describe(c),context_tanh_saturated_fraction=float((np.abs(np.tanh(c))>.99).mean()),
        reset_gate=describe(g[:,:48]),update_gate=describe(g[:,48:96]),candidate_state=describe(g[:,96:]),
        update_gate_above_099=float((g[:,48:96]>.99).mean()),candidate_saturated_fraction=float((abs(g[:,96:])>.99).mean()),
        input_block_rms=dict(context=float(np.sqrt((x[:,:32]**2).mean())),history_values=float(np.sqrt((x[:,32:55]**2).mean())),history_masks=float(np.sqrt((x[:,55:78]**2).mean()))),
        true_class_margins=pairs,parameters=params,gradient_probes=gradient,
        activation_interventions={k:dict(rows=len(v),accuracy=float(np.mean(np.asarray(v)==row_targets)),predicted_counts=dict(Counter(v))) for k,v in ablations.items()},optimizer_updates=0)
    immutable_json(REPORT/'weight-audit.json',output)
    print(json.dumps({k:v for k,v in output.items() if k not in ('parameters','gradient_probes','true_class_margins')},indent=2))
    print('CLASS MARGINS',json.dumps(pairs,indent=2))
    print('GRADIENT SUMMARY',json.dumps(dict(mean_weighted_norms=np.mean([r['weighted_norms'] for r in gradient],0).tolist(),mean_code_move_cosine=float(np.mean([r['code_vs_move_cosine'] for r in gradient])),mean_code_goal_cosine=float(np.mean([r['code_vs_goal_cosine'] for r in gradient])))))


if __name__=='__main__':run()
