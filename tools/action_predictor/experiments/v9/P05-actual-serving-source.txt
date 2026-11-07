"""Time actual prepared-input predictor.distributions, including all work."""
from pathlib import Path
import json,sys,time
from unittest.mock import patch
import numpy as np
import torch
from . import reliable_train as rt
from .fundamental_audit import WORK,REPORTS,arrays,log
from .priority_fit_v3 import BASE,VAL,read,load_base,context_directory
from .priority_residual_fit import VOCAB
from .priority_residual_predictor import PriorityResidualPredictor
from .priority_head import flatten
from .movement_predictor import MovementMixturePredictor
from .entity_serving_benchmark import memory
from .more_replays import frozen,sha

@torch.no_grad()
def run(identifier):
    assert identifier in ('P05','G00','G01');rt.setup(26);norm=context_directory()/'extra-normalization.npz';vocab=read(VOCAB);pcp=BASE.parent/'v8/runs/P05/model.pt'
    if identifier=='P05':predictor=PriorityResidualPredictor(BASE/'runs/M01/model.pt',norm,vocab,pcp)
    else:
        report=read(REPORTS/(identifier+'.json'));checkpoint=WORK/'runs'/identifier/'model.pt';assert sha(checkpoint)==report['checkpoint_sha256']
        predictor=MovementMixturePredictor(BASE/'runs/M01/model.pt',norm,vocab,pcp,checkpoint,report['checkpoint_sha256'])
    saved=torch.load(BASE/'runs/M01/model.pt',weights_only=True,map_location='cpu');raw=arrays(VAL);data,_=rt.model_data(raw,saved['config'],(saved['mean'],saved['std']))
    with np.load(BASE.parent/'v8/priority-validation.npz') as z:values=torch.from_numpy(z['values']);extra=torch.from_numpy((flatten(z['values'],z['history']).astype(np.float32)-predictor.extra_mean.numpy())/predictor.extra_std.numpy())
    rows=np.linspace(0,len(raw['y'])-1,64,dtype=np.int64)
    def inputs(row):
        s=slice(int(row),int(row)+1)
        return dict(x=data['x'][s],history=data['history'][s],grid=data['grid'][s].float(),valid=data['valid'][s],rules=data['rules'][s],extra=extra[s],priority_values=values[s])
    prepared=[inputs(r) for r in rows]
    def forward(inp):
        out=predictor.distributions(inp);family=int(out['action'].argmax());coordinate=int(out['coordinate'].argmax());integer=int(predictor.head.integer(out['priority_raw'],inp['priority_values'])[0]) if family==9 else None
        return family,coordinate,integer
    for inp in prepared[:8]:forward(inp)
    # Confirm the actual implementation's duplicated teacher-coordinate work,
    # outside timing. No optimization or changed predictions hidden in benchmark.
    baseline=arrays(BASE.parent/'v8/runs/P05/validation-predictions.npz');row=int(np.flatnonzero(np.isin(baseline['prediction'],[8,3]))[0]);inp=inputs(row)
    with patch.object(predictor.model,'parameter_logits',wraps=predictor.model.parameter_logits) as calls:
        forward(inp);teacher_calls=calls.call_count
    before=memory();latencies=[]
    for _ in range(3):
        for inp in prepared:
            t=time.perf_counter_ns();forward(inp);latencies.append((time.perf_counter_ns()-t)/1e6)
    modules=(predictor.movement,predictor.head) if identifier!='P05' else (predictor.model,predictor.head);params={id(p):p for m in modules for p in m.parameters()}
    code=Path(__file__);predictor_code=code.with_name('movement_predictor.py') if identifier!='P05' else code.with_name('priority_predictor.py')
    result=dict(id=identifier,sources={str(code.resolve()):sha(code),str(predictor_code.resolve()):sha(predictor_code)},actual_distributions_method=True,teacher_parameter_calls_on_proposed_movement=teacher_calls,cpu_threads=4,batch_size=1,rows=rows.tolist(),distinct_rows=64,repeats=3,milliseconds=dict(mean=float(np.mean(latencies)),median=float(np.median(latencies)),p95=float(np.quantile(latencies,.95)),maximum=float(np.max(latencies))),parameters=sum(p.numel() for p in params.values()),parameter_bytes=sum(p.numel()*p.element_size() for p in params.values()),process_memory_before=before,process_memory_after=memory(),scope='ACTUAL predictor.distributions on prepared causal inputs plus exact priority decoding when chosen; includes first teacher coordinates AND replacement-mixture teacher coordinates. Excludes feature construction/replay I/O and command-dictionary packaging. Fresh process per model with no concurrent training.',supersedes_cost_interpretation='Old G00/G01-serving.json used reduced kernel work, not current serving implementation. Preserve old receipts as reduced-kernel measurements; no prediction metrics changed.',new_fits=0,reserved_opened=0)
    frozen(REPORTS/(identifier+'-actual-serving.json'),result);(REPORTS/(identifier+'-actual-serving-source.txt')).write_bytes(code.read_bytes());print(json.dumps(dict(id=identifier,teacher_calls=teacher_calls,ms=result['milliseconds'])))

if __name__=='__main__':log([sys.executable,'-m','tools.action_predictor.movement_serving_actual',*sys.argv[1:]]);run(sys.argv[1])
