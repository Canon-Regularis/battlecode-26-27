"""Consume committed order manifests and independently anchored old cohorts."""
import json
import subprocess

import numpy as np
import torch

from ..data import digest
from .anchored import ROOT,anchored_inputs,committed_manifest
from .schema_asinh import FIELDS

LOCAL=ROOT/'.cambc/action-predictor/v23'
OUT=ROOT/'tools/action_predictor/experiments/v23'


def load():
    fit,controls,bindings=anchored_inputs()  # Must precede optimizer/tests/cache use.
    commit=subprocess.run(['git','rev-parse','HEAD'],cwd=ROOT,check=True,capture_output=True,text=True).stdout.strip()
    manifests={}
    for name in ('order-cache-ready.json','order-asinh-plan.json','order-asinh-ready.json',
                 'zero-control-plan.json','zero-control-equivalence.json'):
        value,more=committed_manifest(commit,'tools/action_predictor/experiments/v23/'+name)
        manifests[name]=value;bindings.update(more)
    if not manifests['zero-control-equivalence.json']['reuse_accepted']:
        raise RuntimeError('Retained zero-information control is not validated')
    for name,expected in manifests['zero-control-equivalence.json']['bindings'].items():
        if digest(ROOT/name)!=expected:raise RuntimeError('Retained control dependency changed: '+name)
        bindings[name]=expected
    ready=manifests['order-asinh-ready.json']
    if ready['fields']!=list(FIELDS) or ready['rows']!=6132 or ready['fit_rows']!=5876:
        raise RuntimeError('Order schema/population changed')
    for name,expected in ready['files'].items():
        if digest(ROOT/name)!=expected:raise RuntimeError('Order feature input changed: '+name)
        bindings[name]=expected
    index_path=LOCAL/'index.npy'
    if digest(index_path)!=ready['index_sha256']:raise RuntimeError('Order row identities changed')
    bindings[str(index_path.relative_to(ROOT))]=ready['index_sha256']
    indices=np.load(index_path)
    raw=np.load(LOCAL/'asinh-raw-features.npy')
    features=np.load(LOCAL/'asinh-features.npy')
    if features.shape!=(6132,32) or features.dtype!=np.float32 or not np.isfinite(features).all():
        raise RuntimeError('Invalid order features')
    fit_at=np.searchsorted(indices,fit['index'].numpy())
    np.testing.assert_array_equal(indices[fit_at],fit['index'].numpy())
    with np.load(LOCAL/'asinh-normalizer.npz') as z:mean,std=z['mean'],z['std']
    # Independent normalization consumption check, excluding control rows.
    truth=raw[fit_at].astype(np.float64)
    np.testing.assert_array_equal(mean,truth.mean(0).astype(np.float32))
    np.testing.assert_array_equal(std,np.maximum(truth.std(0,ddof=1),.01).astype(np.float32))
    np.testing.assert_array_equal(features,(raw-mean)/std)
    result=dict(broad_fit=fit,original_fit=controls['fit'],
                same_fit_groups=controls['same_fit_groups'],held_groups=controls['held_groups'])
    for name,d in result.items():
        at=np.searchsorted(indices,d['index'].numpy())
        np.testing.assert_array_equal(indices[at],d['index'].numpy())
        d['order']=torch.from_numpy(np.array(features[at],copy=True))
        d['order_available']=torch.from_numpy(np.array(raw[at][:,[0,8,16,24]]>0,copy=True))
    references=np.zeros((4,6),np.float32)
    reference_available=np.zeros(4,bool)
    for pool in range(4):
        mask=raw[fit_at,pool*8]>0
        if mask.any():
            references[pool]=features[fit_at[mask],pool*8+2:pool*8+8].astype(np.float64).mean(0)
            reference_available[pool]=True
    return result,bindings,dict(references=references,available=reference_available),manifests


def numeric_mean_inputs(order,available,references,reference_available):
    result=order.clone()
    for pool in range(4):
        if reference_available[pool]:
            selected=available[:,pool]
            result[selected,pool*8+2:pool*8+8]=torch.as_tensor(references[pool],dtype=order.dtype)
    return result
