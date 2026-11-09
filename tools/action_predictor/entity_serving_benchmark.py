"""CPU model-kernel latency and memory, separately from replay/feature I/O."""
from pathlib import Path
import ctypes,json,sys,time
import numpy as np
import torch
from .fundamental_audit import ROOT,REPORTS,WORK,arrays,log
from .priority_fit_v3 import BASE,VAL,read,load_base,context_directory
from .priority_residual_fit import head as priority_head
from .entity_model import EntityMovementModel
from .entity_set import EntityBank
from .entity_cache import DIRECTORY
from .action_priority_head import classifier_features
from .priority_head import flatten
from .more_replays import sha,frozen
from . import reliable_train as rt

def memory():
    # Fresh process per model; report total process memory honestly, not as just
    # model memory. Prepared validation tensors and Torch runtime are included.
    from ctypes import wintypes
    class Counters(ctypes.Structure):
        _fields_=[('cb',wintypes.DWORD),('PageFaultCount',wintypes.DWORD),('PeakWorkingSetSize',ctypes.c_size_t),('WorkingSetSize',ctypes.c_size_t),('QuotaPeakPagedPoolUsage',ctypes.c_size_t),('QuotaPagedPoolUsage',ctypes.c_size_t),('QuotaPeakNonPagedPoolUsage',ctypes.c_size_t),('QuotaNonPagedPoolUsage',ctypes.c_size_t),('PagefileUsage',ctypes.c_size_t),('PeakPagefileUsage',ctypes.c_size_t)]
    counters=Counters();counters.cb=ctypes.sizeof(counters)
    ctypes.windll.kernel32.GetCurrentProcess.restype=wintypes.HANDLE
    process=ctypes.windll.kernel32.GetCurrentProcess()
    ctypes.windll.psapi.GetProcessMemoryInfo.argtypes=[wintypes.HANDLE,ctypes.POINTER(Counters),wintypes.DWORD]
    assert ctypes.windll.psapi.GetProcessMemoryInfo(process,ctypes.byref(counters),counters.cb)
    return dict(working_set_bytes=counters.WorkingSetSize,peak_working_set_bytes=counters.PeakWorkingSetSize)

@torch.no_grad()
def run(identifier):
    assert identifier in ('P05','E00','E01');rt.setup(26)
    original=read(ROOT/'tools/action_predictor/experiments/v5/M01.json');p05=read(REPORTS.parent/'v8/P05.json')
    cp=BASE/'runs/M01/model.pt';assert sha(cp)==original['checkpoint_sha256']
    teacher,saved=load_base();priority=priority_head(teacher.priority);priority_checkpoint=BASE.parent/'v8/runs/P05/model.pt';assert sha(priority_checkpoint)==p05['checkpoint_sha256']
    ps=torch.load(priority_checkpoint,weights_only=True,map_location='cpu');priority.load_state_dict(ps['head_state']);teacher.eval();priority.eval()
    with np.load(VAL) as z:raw={k:z[k] for k in z.files}
    data,_=rt.model_data(raw,saved['config'],(saved['mean'],saved['std']))
    with np.load(BASE.parent/'v8/priority-validation.npz') as z:
        values=torch.from_numpy(z['values']);extra=torch.from_numpy((flatten(z['values'],z['history']).astype(np.float32)-ps['extra_mean'].numpy())/ps['extra_std'].numpy())
    features=classifier_features(extra,values);ready=read(REPORTS/'entity-cache-ready.json');bank=EntityBank(DIRECTORY,'validation',ready['dimension'])
    model=None;checkpoint=priority_checkpoint
    if identifier!='P05':
        report=read(REPORTS/(identifier+'.json'));checkpoint=WORK/'runs'/identifier/'model.pt';assert sha(checkpoint)==report['checkpoint_sha256']
        state=torch.load(checkpoint,weights_only=True,map_location='cpu');plan=read(REPORTS/(identifier+'-plan.json'))
        assert state['plan_sha256']==sha(REPORTS/(identifier+'-plan.json')) and state['labels']==rt.LABELS
        for path,digest in plan['source_hashes'].items():assert sha(path)==digest
        model=EntityMovementModel(teacher,priority,ready['dimension'],state['config']['use_entities']);model.load_state_dict(state['state_dict']);model.eval()
    rows=np.linspace(0,len(raw['y'])-1,64,dtype=np.int64);prepared=[]
    for row in rows:
        entities,mask=bank.batch(np.array([row]));prepared.append((int(row),entities,mask))
    def forward(item):
        row,entities,mask=item;a=slice(row,row+1);x=data['x'][a];history=data['history'][a];grid=data['grid'][a].float();valid=data['valid'][a];rules=data['rules'][a]
        if model is None:
            logits,context=teacher(x,history);family=logits.argmax(-1);coordinate=teacher.parameter_logits(context,grid,valid,family,rules).softmax(-1)
        else:
            logits,movement,context=model(x,history,entities,mask,features[a]);family=logits.argmax(-1);coordinate=model.parameter_logits(movement,context,grid,valid,family,rules).softmax(-1)
        output=priority(context,extra[a]);integer=priority.integer(output,values[a]) if int(family)==rt.LABELS.index('priority') else None
        return int(family),int(coordinate.argmax(-1)),int(integer) if integer is not None else None
    for item in prepared[:8]:forward(item)
    before=memory();latency=[];commands=[]
    for repeat in range(3):
        for item in prepared:
            start=time.perf_counter_ns();result=forward(item);latency.append((time.perf_counter_ns()-start)/1e6)
            if repeat==0:commands.append(result)
    after=memory();modules=[model] if model is not None else [teacher,priority]
    params={id(p):p for m in modules for p in m.parameters()};buffers={id(p):p for m in modules for p in m.buffers()}
    result=dict(model=identifier,checkpoint_sha256=sha(checkpoint),source_sha256=sha(__file__),device='CPU',threads=4,batch_size=1,distinct_rows=64,repeats=3,timed_calls=len(latency),rows=rows.tolist(),milliseconds=dict(mean=float(np.mean(latency)),median=float(np.median(latency)),p95=float(np.quantile(latency,.95)),maximum=float(np.max(latency))),parameter_count=sum(p.numel() for p in params.values()),parameter_bytes=sum(p.numel()*p.element_size() for p in params.values()),buffer_bytes=sum(p.numel()*p.element_size() for p in buffers.values()),checkpoint_bytes=checkpoint.stat().st_size,process_memory_before=before,process_memory_after=after,scope='Model-kernel serving only, from prepared causal inputs: includes fresh teacher/student GRU, predicted-family spatial routing, priority mixture and exact integer decode when selected. Excludes replay loading and observation feature construction. Process RSS includes Torch/prepared validation tensors, not just model. Each CLI invocation uses a fresh process; no concurrent training during timing.',reserved_opened=0,new_fits=0)
    frozen(REPORTS/(identifier+'-serving.json'),result)
    (REPORTS/(identifier+'-serving-source.txt')).write_bytes(Path(__file__).read_bytes())
    print(json.dumps(result['milliseconds']))

if __name__=='__main__':log([sys.executable,'-m','tools.action_predictor.entity_serving_benchmark',*sys.argv[1:]]);run(sys.argv[1])
