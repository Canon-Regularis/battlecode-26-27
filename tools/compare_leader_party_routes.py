"""Paired frozen-artifact route-planner comparison with controls and fuel stress.

Requires compiled ZIPs produced by benchmark_leader_party.py pack.
Writes ignored job/replay outputs plus a compact results JSON under .cambc/.
Unexpected action errors are recorded for BOTH teams; VM faults remain separate.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import zipfile

ROOT=Path(__file__).resolve().parents[1]
CLI=ROOT/'.venv/Scripts/cambc.exe'


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('label');p.add_argument('--maps',nargs='+',required=True)
    p.add_argument('--controls',action='store_true')
    p.add_argument('--fuel',type=int)
    p.add_argument('--jobs',type=int,default=4)
    p.add_argument('--summarize',action='store_true')
    args=p.parse_args()
    artifacts={'original':ROOT/'.cambc/leader-party-validated.zip',
               'subhan':ROOT/'.cambc/leader-party-subhan-v1.zip',
               'D1':ROOT/'.cambc/D1-compiled.zip',
               'gold_diamond':ROOT/'.cambc/gold_diamond-compiled.zip'}
    def team(name):
        path=artifacts[name]
        with zipfile.ZipFile(path) as z:language=json.loads(z.read('manifest.json'))['language']
        return dict(name=name,path=str(path),language=language)
    out=ROOT/'replays/leader-party'/args.label;out.mkdir(parents=True,exist_ok=True)
    pairs=[(v,o) for v in ['original','subhan'] for o in ['D1','gold_diamond']] if args.controls else [('subhan','original')]
    jobs=[];meta=[]
    for variant,opponent in pairs:
        for m in args.maps:
            for swap in range(2):
                ident=f'{len(jobs):04d}'
                a,b=(opponent,variant) if swap else (variant,opponent)
                jobs.append(dict(apiVersion=1,id=ident,teamA=team(a),teamB=team(b),
                                 map=str(ROOT/'maps'/(m+'.map26a')),replay=str(out/(ident+'.zip'))))
                meta.append(dict(variant=variant,opponent=opponent,map=m,side='teamB' if swap else 'teamA'))
    receipt=ROOT/'.cambc'/(args.label+'-results.json')
    if not args.summarize:
        receipt.write_text(json.dumps(dict(status='running',planned_games=len(jobs))))
        for batch,start in enumerate(range(0,len(jobs),120)):
            manifest=ROOT/'.cambc'/f'{args.label}-{batch}.jsonl'
            manifest.write_text(''.join(json.dumps(j)+'\n' for j in jobs[start:start+120]))
            command=[str(CLI),'run-batch','--jsonl',str(manifest),'--jobs',str(args.jobs),'--release','--log-limit','200000']
            if args.fuel is not None:command+=['--fuel-quantum',str(args.fuel)]
            with (ROOT/'.cambc'/f'{args.label}-{batch}-events.jsonl').open('w') as events:
                subprocess.run(command,cwd=ROOT,stdout=events,check=True)
            print(f'{args.label}: completed batch {batch+1}',flush=True)
    rows=[]
    for j,info in zip(jobs,meta):
        with zipfile.ZipFile(j['replay']) as z:
            raw=ROOT/'.cambc'/(args.label+'-summary.camstat');raw.write_bytes(z.read('summary.camstat'))
            d=json.loads(subprocess.check_output([str(CLI),'summary',str(raw),'-o','-']))
            logs={side:z.read(f'team-{letter}.stdout').replace(b'\0',b'').decode(errors='replace')
                  for side,letter in [('teamA','a'),('teamB','b')]}
        side=info['side'];other='teamA' if side=='teamB' else 'teamB'
        scores={t['team']:int(t['submittedGems']) for t in d['teams']}
        outcome=d['match']['outcome']
        def metric(side,key):return sum(float(c['metrics'][key]) for c in d['champions'] if c['team']==side)
        rows.append(dict(**info,result='win' if outcome==side else 'loss' if outcome==other else 'draw',
                         ours=scores[side],theirs=scores[other],zero_score_tiebreak=scores[side]==scores[other]==0,
                         rounds=d['match']['roundsStarted'],seed=d['match']['seed'],faults=d['diagnostics']['botFaults'],
                         our_errors=logs[side].count('LP_ERROR'),opponent_errors=logs[other].count('LP_ERROR'),
                         our_deaths=metric(side,'deaths'),opponent_deaths=metric(other,'deaths'),
                         our_gold=metric(side,'earnedGold'),opponent_gold=metric(other,'earnedGold'),
                         draft=[line for line in logs[side].splitlines() if line.startswith('SUBHAN_DRAFT')],
                         replay=str(Path(j['replay']).relative_to(ROOT))))
    totals=[]
    for v,o in pairs:
        rs=[r for r in rows if r['variant']==v and r['opponent']==o]
        total=dict(variant=v,opponent=o,games=len(rs),wins=sum(r['result']=='win' for r in rs),
                   losses=sum(r['result']=='loss' for r in rs),draws=sum(r['result']=='draw' for r in rs),
                   our_gems=sum(r['ours'] for r in rs),opponent_gems=sum(r['theirs'] for r in rs),
                   our_errors=sum(r['our_errors'] for r in rs),opponent_errors=sum(r['opponent_errors'] for r in rs),
                   our_faults=sum(r['faults'][r['side']] for r in rs))
        totals.append(total);print(json.dumps(total),flush=True)
    report=dict(status='complete',fuel=args.fuel or 'engine default',maps=args.maps,totals=totals,matches=rows,
                artifact_sha256={name:hashlib.sha256(path.read_bytes()).hexdigest() for name,path in artifacts.items()})
    receipt.write_text(json.dumps(report,indent=2)+'\n')
    print(f'Saved {len(rows)} complete games to {receipt}',flush=True)


if __name__=='__main__':main()
