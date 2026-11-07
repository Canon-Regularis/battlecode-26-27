"""Measured winner-probability/likelihood consistency, not another fit."""
import json,sys
import numpy as np
import torch
from .consistent_study import load
from .consistent_data import WORK,REPORT
from .command_mixture import canonical,agreement,log_mass
from .audit import immutable_json
from .data import digest

def run(identifier):
    d=load('validation');path=WORK/f'runs/{identifier}/validation-predictions.npz' if identifier.startswith('B') else WORK/f'controls/{identifier}-validation.npz'
    with np.load(path) as z:p={k:z[k] for k in z.files}
    chosen=canonical(np.stack((p['prediction'],p['coordinate'],p['priority']),-1));commands=np.concatenate((canonical(d['c']),d['modes']),1);q=np.concatenate((d['point-logq'],d['mode-logq']),1);eq=(commands==chosen[:,None]).all(-1);assert eq.any(1).all();winner_q=np.where(eq,q,-np.inf).max(-1)
    probability=log_mass(torch.from_numpy(p['log_weights']),torch.from_numpy(agreement(d['c'],chosen)),torch.from_numpy(winner_q)).numpy();error=float(np.max(np.abs(probability-p['command_log_probability'])));assert error<1e-6
    target_in_options=np.array(d['matches']).any(1)
    # If the correct point command exists, a higher recorded-command probability
    # than the decoded winner would demonstrate the old objective/decoder defect.
    violation=(-p['nll']>p['command_log_probability']+1e-6)&target_in_options
    assert not violation.any()
    immutable_json(REPORT/f'{identifier}-probability-contract.json',dict(rows=len(chosen),winner_likelihood_vs_decoder_max_log_error=error,available_correct_point_rows=int(target_in_options.sum()),recorded_point_higher_probability_than_emitted=int(violation.sum()),prediction_sha256=digest(path),source_sha256=digest(__file__),new_fits=0,reserved_opened=0))
    print(identifier,'contract',error,'violations',int(violation.sum()),flush=True)

if __name__=='__main__':run(sys.argv[1])
