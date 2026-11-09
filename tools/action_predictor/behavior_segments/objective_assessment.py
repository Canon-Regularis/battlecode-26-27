"""Assess selection utility and adaptive termination without autonomous-play claims."""
from collections import Counter
import time
import torch
from . import objective_experiment as fit
from .objective_policy import candidates,choose,movement
from . import model
from ..audit import immutable_json


@torch.no_grad()
def evaluate():
    fit.check(fit.read(fit.REPORT/'assessment-plan.json'))
    p,parent,architecture,_,_=fit.inputs();fit.check(fit.read(fit.REPORT/'fit.json'));torch.set_num_threads(4)
    head=fit.new(p);head.load_state_dict(torch.load(fit.WORK/'selected.pt',weights_only=True));policy=fit.base.policy(fit.read(fit.base.REPORT/'plan.json'),parent,architecture)
    windows,maps=fit.base.heading.original.load();encoded,history,bound=fit.base.prior.encoded(windows,maps,architecture)
    ids=[dict(fold=-1,canonical=True) for w in windows];labeled=fit.examples(windows,maps,history,ids)
    targets={(r['key'],r['position']):r for r in labeled};records=[]
    for w in windows:
        args=encoded[w['key']];states=[];hook=policy.parent.parent.backbone.code.register_forward_pre_hook(lambda module,args:states.append(args[0]))
        try:out=policy(**args)
        finally:hook.remove()
        context=torch.cat((states[0],out['code'].softmax(-1)),-1);support,labels=model.move_support(w)
        probabilities=out['move'].masked_fill(~support,-1e9).softmax(-1);remembered=None
        for i,s in enumerate(w['steps']):
            if not s['observed']:continue
            cs=candidates(s['input'],maps[w['payload']]);scores=head(torch.stack([torch.cat((context[i],torch.tensor(c['features']))) for c in cs])).tolist() if cs else []
            selected,remembered,reason=choose(cs,scores,remembered,p['margin']);fresh,_,_=choose(cs,scores,None,0)
            baseline=int(probabilities[i].argmax());a=movement(selected,s['input'],maps[w['payload']],probabilities[i].tolist()) if selected else baseline
            b=movement(fresh,s['input'],maps[w['payload']],probabilities[i].tolist()) if fresh else baseline
            record=dict(key=w['key'],group=w['group'],split=w['partition'],position=i,selected=remembered,reason=reason,
                labels=int(labels[i]),baseline=baseline,adaptive=a,reselect=b,scores=scores,candidate_keys=[c['key'] for c in cs])
            t=targets.get((w['key'],i))
            if t:
                utilities={c['key']:c['utility'] for c in t['candidates']};nearest=min(t['candidates'],key=lambda c:(c['features'][8],c['key']))
                record['utility']=dict(selected=utilities.get(remembered,0.),nearest=nearest['utility'],uniform=sum(utilities.values())/len(utilities),oracle=max(utilities.values()))
            records.append(record)
    summaries={}
    for split in ('fit','evaluation'):
        rs=[r for r in records if r['split']==split];ms=[r for r in rs if r['labels']>=0];us=[r for r in rs if 'utility' in r]
        summaries[split]=dict(movement_rows=len(ms),**{k:sum(r[k]==r['labels'] for r in ms) for k in ('baseline','adaptive','reselect')},
            utility_rows=len(us),utility={k:sum(r['utility'][k] for r in us)/len(us) for k in ('selected','nearest','uniform','oracle')},decisions=dict(Counter(r['reason'] for r in rs)))
    x=summaries['evaluation'];checks=dict(utility=x['utility']['selected']>max(x['utility']['nearest'],x['utility']['uniform']),
        movement=x['adaptive']>x['baseline'] and x['adaptive']>x['reselect'])
    return dict(summary=summaries,checks=checks,all_checks_pass=all(checks.values()),records=records,source_bindings=bound)


def run():
    result=evaluate();immutable_json(fit.WORK/'predictions.json',result)
    immutable_json(fit.REPORT/'result.json',dict(summary=result['summary'],checks=result['checks'],all_checks_pass=result['all_checks_pass'],bindings=fit.bindings([fit.WORK/'predictions.json',fit.WORK/'selected.pt']),promoted=False))
    print(result['summary']['evaluation'],result['checks'],flush=True)


if __name__=='__main__':run()
