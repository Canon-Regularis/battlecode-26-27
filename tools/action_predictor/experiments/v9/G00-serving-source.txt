"""Comparable prepared-input CPU serving cost for G00/G01."""
from pathlib import Path
import json,sys,time
import numpy as np
import torch
from . import reliable_train as rt
from .fundamental_audit import WORK,REPORTS,arrays,log
from .priority_fit_v3 import BASE,VAL,load_base,read
from .priority_residual_fit import head as priority_head
from .priority_head import flatten
from .movement_mixture import MovementMixture
from .entity_serving_benchmark import memory
from .more_replays import frozen,sha

@torch.no_grad()
def run(identifier):
    rt.setup(26);report=read(REPORTS/(identifier+'.json'));path=WORK/'runs'/identifier/'model.pt';assert sha(path)==report['checkpoint_sha256'];state=torch.load(path,weights_only=True,map_location='cpu')
    plan=read(REPORTS/(identifier+'-plan.json'))
    for p,d in plan['sources'].items():assert sha(p)==d
    teacher,saved=load_base();mixture=MovementMixture(teacher,state['specialized']);mixture.load_state_dict(state['state_dict']);mixture.eval();priority=priority_head(teacher.priority)
    ps=torch.load(BASE.parent/'v8/runs/P05/model.pt',weights_only=True,map_location='cpu');priority.load_state_dict(ps['head_state']);priority.eval()
    raw=arrays(VAL);data,_=rt.model_data(raw,saved['config'],(saved['mean'],saved['std']))
    with np.load(BASE.parent/'v8/priority-validation.npz') as z:values=torch.from_numpy(z['values']);extra=torch.from_numpy((flatten(z['values'],z['history']).astype(np.float32)-ps['extra_mean'].numpy())/ps['extra_std'].numpy())
    rows=np.linspace(0,len(raw['y'])-1,64,dtype=np.int64)
    def forward(row):
        a=slice(int(row),int(row)+1);x=data['x'][a];h=data['history'][a];grid=data['grid'][a].float();valid=data['valid'][a];rules=data['rules'][a];logits,context=teacher(x,h);family=logits.argmax(-1)
        if int(family) in (8,3):lp,_,_=mixture(x,h,grid,valid,family,rules,context)
        else:lp=teacher.parameter_logits(context,grid,valid,family,rules).log_softmax(-1)
        output=priority(context,extra[a]);integer=priority.integer(output,values[a]) if int(family)==9 else None
        return int(lp.argmax()),int(integer) if integer is not None else None
    for row in rows[:8]:forward(row)
    before=memory();times=[]
    for _ in range(3):
        for row in rows:
            t=time.perf_counter_ns();forward(row);times.append((time.perf_counter_ns()-t)/1e6)
    params={id(p):p for m in (mixture,priority) for p in m.parameters()};buffers={id(p):p for m in (mixture,priority) for p in m.buffers()}
    result=dict(id=identifier,checkpoint_sha256=report['checkpoint_sha256'],sources={str(Path(__file__).resolve()):sha(__file__),str(Path(__file__).with_name('entity_serving_benchmark.py').resolve()):sha(Path(__file__).with_name('entity_serving_benchmark.py'))},cpu_threads=4,batch_size=1,distinct_rows=64,repeats=3,rows=rows.tolist(),milliseconds=dict(mean=float(np.mean(times)),median=float(np.median(times)),p95=float(np.quantile(times,.95)),maximum=float(np.max(times))),total_complete_predictor_parameters=sum(p.numel() for p in params.values()),parameter_bytes=sum(p.numel()*p.element_size() for p in params.values()),buffer_bytes=sum(p.numel()*p.element_size() for p in buffers.values()),process_memory_before=before,process_memory_after=memory(),scope='Same64prepared causal rows/3repeats as P05/E00/E01, fresh process and no concurrent training. Includes actual predicted-family mixture use, fresh teacher/expert GRUs and priority integer decode when selected. Excludes observation feature construction; RSS includes runtime/prepared data, not only model.',reserved_opened=0,new_fits=0)
    frozen(REPORTS/(identifier+'-serving.json'),result);(REPORTS/(identifier+'-serving-source.txt')).write_bytes(Path(__file__).read_bytes());print(json.dumps(result['milliseconds']))

if __name__=='__main__':log([sys.executable,'-m','tools.action_predictor.movement_serving',*sys.argv[1:]]);run(sys.argv[1])
