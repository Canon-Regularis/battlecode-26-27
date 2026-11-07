"""Reuse hash-bound causal caches; no replay, reserved data or new extraction."""
import json
import numpy as np
import torch
from .protocol import ROOT,BASE,WORK,REPORT
from ..priority_fit_v3 import context_directory
from ..entity_set import EntityBank
from ..audit import immutable_json
from ..data import digest

def read(path):
    with np.load(path) as z:return {k:z[k] for k in z.files}

def verify():
    old=ROOT/'tools/action_predictor/experiments';g=json.loads((old/'v9/G00.json').read_text());c=json.loads((old/'v8/priority-context-ready-v3.json').read_text());entities=json.loads((old/'v9/entity-cache-ready.json').read_text());expected={BASE/'combined-train.npz':'39386010575ad30add064fdae750680f34cfcc732c4fd00fb657875ff4c61ffb',BASE.parent/'v4/validation.npz':'01a15e1e10f68922334a5367bb825c8ef9bbe228ae7a9e86e92aae9609b204ed',BASE.parent/'v9/runs/G00/model.pt':g['checkpoint_sha256']}
    for split in ('train','validation'):
        expected[context_directory()/f'{split}.npy']=c['contexts'][split];r=json.loads((old/f'v13/{split}-inputs.json').read_text());expected[BASE.parent/f'v13/{split}-x.npy']=r['files']['x'];expected[BASE.parent/f'v9/runs/G00/{split}-predictions.npz']=g['train_predictions_sha256' if split=='train' else 'predictions_sha256']
    for name,h in entities['files'].items():expected[BASE.parent/'v9/entities'/name]=h
    bindings={}
    for path,h in expected.items():assert digest(path)==h,str(path);bindings[str(path.relative_to(ROOT))]=h
    mask=BASE.parent/'v9/frequency/natural-mask.npy';natural=np.load(mask);assert natural.dtype==np.bool_ and natural.sum()==288801;assert digest(mask)==json.loads((old/'v9/frequency-data-ready.json').read_text())['mask_sha256']
    bindings[str(mask.relative_to(ROOT))]=digest(mask)
    immutable_json(REPORT/'input-bindings.json',dict(files=bindings,natural_identity_receipt_sha256=digest(old/'v9/frequency-data-ready.json'),entity_receipt_sha256=digest(old/'v9/entity-cache-ready.json'),scope='Hash reuse only; no495-game repeated audit or new replay extraction.',reserved_opened=0));return bindings

def load(split):
    path=BASE/'combined-train.npz' if split=='train' else BASE.parent/'v4/validation.npz'
    with np.load(path) as z:raw={k:z[k] for k in ('y','py','priority','group','grid','valid','move_mask','pos_known','hp_alive','channel')}
    x=np.load(BASE.parent/f'v13/{split}-x.npy',mmap_mode='r');context=np.load(context_directory()/f'{split}.npy',mmap_mode='r');global_=np.concatenate((context,np.asarray(x[:,:485])),1);assert global_.shape==(len(raw['y']),613)
    return dict(raw=raw,x=global_,entities=EntityBank(BASE.parent/'v9/entities',split,119),baseline=read(BASE.parent/f'v9/runs/G00/{split}-predictions.npz'),direction=np.load(BASE.parent/f'v7/{split}-direction.npy'),available=np.load(BASE.parent/f'v7/{split}-available.npy'),near=np.load(BASE.parent/f'v7/{split}-near_obstacle.npy'))

def batch(d,ids,mean,std,family=None):
    entities,mask=d['entities'].batch(ids);x=torch.from_numpy(np.clip((d['x'][ids]-mean)/std,-10,10));grid=torch.from_numpy(d['raw']['grid'][ids].astype(np.float32));valid=torch.from_numpy(d['raw']['valid'][ids]);f=torch.from_numpy(d['raw']['y'][ids] if family is None else np.asarray(family)).long();return x,grid,valid,entities,mask,f
