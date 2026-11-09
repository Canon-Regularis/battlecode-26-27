"""Focused V10 personal-PRE/cache roundtrip, not a repeated replay audit."""
import json
import numpy as np
from .algorithmic.study import ROOT,WORK,REPORT,JOBS,job_run
from .audit import immutable_json
from .data import digest

def run():
    jobs=json.loads(JOBS.read_text());selected=[]
    for split in ('train','validation'):
        for version in ('2.0.0','3.0.0'):
            eligible=[j for j in jobs if j['split']==split and j['record']['engine_version']==version]
            selected.extend(eligible[:2])
    rows=0;bindings=[]
    for j in selected:
        offset,c,b=job_run(j);saved=np.load(WORK/(j['split']+'-candidates.npy'),mmap_mode='r');np.testing.assert_array_equal(c,saved[offset:offset+len(c)]);rows+=len(c);bindings.append(b)
    receipt=dict(method='Regenerate both complete bounded libraries from hash-valid raw personal PRE snapshots and pinned historical engine movement supplements in8eligible games spanning both engines/splits. No replay archive opened, no simulation. PRE actor/cursor/root checks run. Emitter signature receives observation,supplement,public route only; no label, future state or current outcome. No carried memory or sampled adjacency.',games=len(selected),rows=rows,all_commands_equal=True,bindings=bindings,sources={p.name:digest(p) for p in (ROOT/'tools/action_predictor/algorithmic').glob('*.py')},reserved_opened=0)
    immutable_json(REPORT/'C00-roundtrip.json',receipt);print('V10 roundtrip',len(selected),rows)

if __name__=='__main__':run()
