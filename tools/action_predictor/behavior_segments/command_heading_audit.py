"""No-fit audit of strictly earlier executed movements, on fitting windows only."""
import json,time
from collections import defaultdict,Counter
from pathlib import Path
import numpy as np
import torch
from . import data,expanded_code_data as expanded,heading_movement_fit as fit
from .model import OFFSETS
from ..trajectory_history.audit import eligible_jobs,ROOT_NAMES
from ..audit import cursor,immutable_json
from ..data import digest

REPORT=data.ROOT/'tools/action_predictor/experiments/v58'


def prior_moves(windows):
    """Each row receives only moves from the complete previous own turn."""
    jobs={j['record']['raw_sha256']:j for j in eligible_jobs()}
    bound=json.loads((data.REPORT/'data.json').read_text())['source_bindings']
    by_payload=defaultdict(list);result={};bindings={}
    for w in windows:by_payload[w['payload']].append(w)
    for payload,ws in by_payload.items():
        path=Path(jobs[payload]['manifest']['source'])/'extracted'/payload/'index.jsonl'
        actual=digest(path);assert actual==bound[str(path)];bindings[str(path)]=actual
        actors=defaultdict(list)
        for turn in map(json.loads,path.open(encoding='utf-8')):
            if turn.get('record')=='turn' and turn['roots']:actors[turn['actor']].append(turn)
        for w in ws:
            turns=actors[w['actor']];start=w['start_turn'];history=[]
            for t,s in enumerate(w['steps']):
                current=turns[start+t]
                query=next((r for r in current['roots'] if ROOT_NAMES.get(r['header']['step']['kind'],'<unknown>') not in data.ADMIN),current['roots'][0])
                assert query['event']==s['event'] and current['round']==s['round']
                moves=[]
                if t:
                    past=turns[start+t-1]
                    assert cursor(past['roots'][-1]['event'])<cursor(s['event'])
                    for root in past['roots']:
                        st=root['header']['step']
                        if ROOT_NAMES.get(st['kind'])=='move':
                            v=[st['to']['x']-st['from']['x'],st['to']['y']-st['from']['y']]
                            assert tuple(v) in OFFSETS and tuple(v)!=(0,0);moves.append(v)
                    dx=sum(v[0] for v in moves);dy=sum(v[1] for v in moves)
                    assert np.isclose(s['previous'][0],np.log1p(len(moves)))
                    assert np.isclose(s['previous'][15],np.log1p(len(moves)))
                    assert np.isclose(s['previous'][16],np.log1p(max(abs(dx),abs(dy))))
                history.append(moves)
            result[w['key']]=history
    return result,bindings


def run():
    start=time.perf_counter();REPORT.mkdir(parents=True,exist_ok=True);plan,_,_,_,_=fit.inputs();fit.check(fit.read(fit.REPORT/'verification.json'))
    windows,_=expanded.read();assert all(w['partition']=='fit' for w in windows)
    history,bindings=prior_moves(windows);d=fit.cached('full');selected=fit.read(fit.REPORT/'selection.json')['selected']
    net=fit.new_head(selected['hidden'],plan);net.load_state_dict(torch.load(fit.WORK/'selected.pt',weights_only=False)['model']);torch.set_num_threads(1)
    with torch.no_grad():pred=net(d['context'],d['heading'],d['baseline']).masked_fill(~d['support'],-1e9).argmax(-1)
    counts={k:Counter() for k in ('last_move','last_turn_net')}
    for i,w in enumerate(windows):
        last=None
        for t,s in enumerate(w['steps']):
            moves=history[w['key']][t];dx=sum(v[0] for v in moves);dy=sum(v[1] for v in moves)
            if moves:last=tuple(moves[-1])
            net_direction=((dx>0)-(dx<0),(dy>0)-(dy<0)) if dx or dy else None
            if s['movement'] is None:continue
            gold=int(d['labels'][i,t]);old=int(pred[i,t]);assert OFFSETS[gold]==tuple(s['movement'])
            for name,v in [('last_move',last),('last_turn_net',net_direction)]:
                c=counts[name];c['rows']+=1;c['old_correct']+=old==gold;p=old
                if v in OFFSETS:
                    q=OFFSETS.index(v)
                    if d['support'][i,t,q]:
                        p=q;c['available']+=1;c['rule_correct']+=q==gold
                        c['rescues']+=q==gold and old!=gold;c['regressions']+=q!=gold and old==gold
                c['hybrid_correct']+=p==gold
    immutable_json(REPORT/'command-history-audit.json',dict(counts=counts,source_sha256=digest(__file__),
        bindings=bindings,inputs=fit.bindings([fit.REPORT/'plan.json',fit.REPORT/'refit.json',fit.REPORT/'verification.json',data.REPORT/'data.json']),
        windows=len(windows),seconds=time.perf_counter()-start,qualification='Fitting-only heuristic diagnostic, not evaluation or achieved neural accuracy. '
        'Only previous-turn executed commands, already required for original history descriptor. Initial window reset. '
        'No optimizer or fresh backbone forecasts; actual V57 residual applied to frozen fitting cache.'))
    print(dict(counts),flush=True)


if __name__=='__main__':run()
