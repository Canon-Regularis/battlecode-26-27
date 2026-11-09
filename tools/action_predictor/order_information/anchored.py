"""Independently anchor consumed controls to committed historical receipts."""
import hashlib
import io
import json
import subprocess
from pathlib import Path

import numpy as np
import torch

ROOT=Path(__file__).resolve().parents[3]
PC00_COMMIT='72b1237e5cbd4bcd4c0297155932db996a339f19'
PC02_COMMIT='275b717b01b2f45341de341d65b28cbe248691d1'
PC00_COMPLETION='tools/action_predictor/experiments/v19/PC00-completion.json'
PC02_COMPLETION='tools/action_predictor/experiments/v22/PC02-completion.json'


def checksum(value):
    return hashlib.sha256(value).hexdigest()


def committed_manifest(commit,relative):
    blob=subprocess.run(['git','show',commit+':'+relative],cwd=ROOT,
                        check=True,capture_output=True).stdout
    path=ROOT/relative
    if path.read_bytes()!=blob:
        raise RuntimeError('Anchored manifest differs from historical commit: '+relative)
    return json.loads(blob),{relative:checksum(blob)}


def anchored_inputs():
    old,bindings=committed_manifest(PC00_COMMIT,PC00_COMPLETION)
    parent,more=committed_manifest(PC02_COMMIT,PC02_COMPLETION)
    bindings.update(more)
    old_expected={name.replace('\\','/'):value for name,value in old['bindings'].items()}
    new_expected={name.replace('\\','/'):value for name,value in parent['bindings'].items()}
    names=['tools/action_predictor/experiments/v19/PC00-data-ready.json',
           'tools/action_predictor/experiments/v19/PC00-plan.json']
    names += [f'.cambc/action-predictor/v19/PC00-cohorts/{name}.npz'
              for name in ('fit','same_fit_groups','held_groups')]
    names += ['.cambc/action-predictor/v21/PC01-cohort.npz']
    contents={}
    for name in names:
        expected=(old_expected if 'v19' in name else new_expected)[name]
        data=(ROOT/name).read_bytes()
        if checksum(data)!=expected:
            raise RuntimeError('Anchored input differs from historical receipt: '+name)
        bindings[name]=expected
        contents[name]=data
    controls={}
    for name in ('fit','same_fit_groups','held_groups'):
        path=f'.cambc/action-predictor/v19/PC00-cohorts/{name}.npz'
        with np.load(io.BytesIO(contents[path])) as z:
            controls[name]={key:torch.from_numpy(z[key]) for key in z.files}
    with np.load(io.BytesIO(contents['.cambc/action-predictor/v21/PC01-cohort.npz'])) as z:
        fit={key:torch.from_numpy(z[key]) for key in z.files}
    verify_membership(fit,controls)
    return fit,controls,bindings


def verify_membership(fit,controls):
    indices=fit['index'].numpy()
    original=controls['fit']['index'].numpy()
    if len(indices)!=5876 or len(np.unique(indices))!=5876:
        raise RuntimeError('Broad population changed')
    if not np.isin(original,indices).all():
        raise RuntimeError('Original fitted rows omitted')
    groups=set(fit['group'].tolist())
    if len(groups)!=55 or groups!=set(controls['fit']['group'].tolist()):
        raise RuntimeError('Fit-group membership changed')
    if groups & set(controls['held_groups']['group'].tolist()):
        raise RuntimeError('Held groups overlap fit')
    if not set(controls['same_fit_groups']['group'].tolist())<=groups:
        raise RuntimeError('Same-fit-group control includes other groups')
    all_controls=np.concatenate([d['index'].numpy() for d in controls.values()])
    if len(np.unique(all_controls))!=384:
        raise RuntimeError('Control row identities overlap')
    for name in ('same_fit_groups','held_groups'):
        if len(controls[name]['index'])!=128 or np.isin(controls[name]['index'].numpy(),indices).any():
            raise RuntimeError('Control row enters optimization')
