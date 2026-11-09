"""Retain full-array frozen-context parity and baseline archive reproduction."""
import json
from pathlib import Path
import sys
import numpy as np
import torch
from . import reliable_train as rt
from .priority_fit_v2 import ROOT,WORK,REPORTS,BASE,VAL,context_directory,load_base
from .priority_dependencies import verify_dependencies,BASE_PREDICTIONS
from .more_replays import frozen,sha

def run():
    dependencies=verify_dependencies();rt.setup(26);model,saved=load_base();results={}
    for split,path in [('train',BASE/'combined-train.npz'),('validation',VAL)]:
        with np.load(path) as z:raw={key:z[key] for key in z.files}
        data,_=rt.model_data(raw,saved['config'],(saved['mean'],saved['std']))
        cached=np.load(context_directory()/(split+'.npy'),mmap_mode='r')
        assert cached.shape==(len(raw['y']),128) and cached.dtype==np.float32
        changed=0;maximum=0.
        with torch.no_grad():
            for start in range(0,len(raw['y']),256):
                stop=min(len(raw['y']),start+256)
                _,fresh=model(data['x'][start:stop],data['history'][start:stop])
                actual=fresh.numpy();old=cached[start:stop]
                changed+=int(np.count_nonzero(actual!=old));maximum=max(maximum,float(np.abs(actual-old).max()))
        assert changed==0,(split,changed,maximum)
        results[split]=dict(rows=len(raw['y']),changed_elements=changed,maximum_error=maximum,
            data_sha256=sha(path),context_sha256=sha(context_directory()/(split+'.npy')))
        if split=='validation':
            fresh_prediction=rt.infer(model,data)
            with np.load(BASE_PREDICTIONS) as z:
                assert set(z.files)==set(fresh_prediction)
                for key in z.files:assert np.array_equal(z[key],fresh_prediction[key]),key
        del data,raw,cached
    frozen(REPORTS/'priority-context-parity-v2.json',dict(passed=True,results=results,
        baseline_prediction_arrays_exact=True,baseline_predictions_sha256=sha(BASE_PREDICTIONS),
        dependencies_sha256=dependencies,source_sha256=sha(__file__),new_fits=0))
    with (WORK/'commands.jsonl').open('a') as f:f.write(json.dumps(dict(argv=[sys.executable,'-m','tools.action_predictor.priority_cache_audit_v2'],source_sha256=sha(__file__)))+'\n')
    print('All447510 cached contexts and all8 baseline prediction arrays reproduce exactly; fits:0',flush=True)

if __name__=='__main__':run()
