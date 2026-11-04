"""Compare the C++ port against Subhan's exact Python search at commit 97f761f.

Retrieves two SDK-independent files from local Git objects; does not change branches.
Tests identical ranking, route order, tie handling, scores, and timing on 240 cases.
"""
from pathlib import Path
import importlib.util
import json
import math
import random
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[3]
HERE=Path(__file__).resolve().parent
REFERENCE='97f761f04ed3d3e85a6f2217df345629baab58c8'
folder=ROOT/'.cambc/subhan-translation-reference'
folder.mkdir(exist_ok=True)
for name in ['settings.py','planner.py']:
    (folder/name).write_bytes(subprocess.check_output(['git','show',f'{REFERENCE}:bots/economy-bot/src/{name}'],cwd=ROOT))
sys.path.insert(0,str(folder))
from planner import CampGroupInfo,LoopPlanner,RiskProfile
from settings import SearchConfig

executable=ROOT/'.cambc/subhan-planner-test.exe'
subprocess.run(['C:/msys64/mingw64/bin/g++.exe','-std=c++20','-O2','-Wall','-Wextra','-I',str(HERE.parent/'src'),str(HERE/'planner_driver.cpp'),str(HERE.parent/'src/loop_planner.cpp'),'-o',str(executable)],check=True)
rng=random.Random(20261104)
cases=[];expected=[]
for case in range(240):
    n=rng.randint(1,9);a=rng.randint(1,4)
    camps=[CampGroupInfo((i,0),rng.randint(0,80),rng.randint(0,200),rng.randint(5,90),rng.randint(10,120)) for i in range(n)]
    dist=[[0 if i==j else rng.choice([-1,rng.randint(1,70)]) for j in range(n)] for i in range(n)]
    altar=[[rng.choice([-1,rng.randint(1,40)]) for _ in range(n)] for _ in range(a)]
    spawn=[rng.choice([-1,rng.randint(1,50)]) for _ in range(n)]
    cr=[rng.random() for _ in range(n)];ar=[rng.random() for _ in range(a)]
    config=SearchConfig(beam_width=rng.randint(1,5),max_camps=rng.randint(1,6),max_expansions=rng.choice([0,1,8,32,128,768]),gold_weight=.02,opening_weight=.15,risk_tolerance=.2)
    # Include exact ties and completely unreachable legs, not only random scores.
    if case%12==0:
        camps=[CampGroupInfo((i,0),10,30,5,20) for i in range(n)];dist=[[0 if i==j else 2 for j in range(n)] for i in range(n)];altar=[[2]*n for _ in range(a)];spawn=[2]*n;cr=[0.]*n;ar=[0.]*a
    reference=LoopPlanner(camps,dist,altar,spawn,config=config,risk=RiskProfile(tuple(cr),tuple(ar))).find_loops(limit=3)
    expected.append(reference)
    values=[n,a,config.beam_width,config.max_camps,config.max_expansions,3,.02,.15,.2]
    for i,g in enumerate(camps):values.extend([g.gems,g.gold,g.service_turns,g.respawn_turns,spawn[i],cr[i]])
    for row in dist+altar:values.extend(row)
    values.extend(ar);cases.append(' '.join(map(str,values)))
output=subprocess.check_output([str(executable)],input=(str(len(cases))+'\n'+'\n'.join(cases)+'\n').encode()).decode().splitlines()
assert len(output)==len(expected)
for index,(line,reference) in enumerate(zip(output,expected)):
    tokens=iter(line.split());assert int(next(tokens))==len(reference),(index,'count')
    for loop in reference:
        ai=int(next(tokens));count=int(next(tokens));route=tuple(int(next(tokens)) for _ in range(count));score=float(next(tokens));period=int(next(tokens));first=int(next(tokens))
        assert (ai,route)==(loop.altar_index,loop.camp_indices),(index,'rank/route',(ai,route),loop)
        assert math.isclose(score,loop.evaluation.score,rel_tol=1e-12,abs_tol=1e-14),(index,'score')
        assert (period,first)==(loop.evaluation.period,loop.evaluation.first_deposit),(index,'timing')
print('PASS: 240 differential cases match Subhan Python rankings, routes, scores and timing')
