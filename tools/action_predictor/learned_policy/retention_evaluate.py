"""L02 versus retained L01 using the unchanged V16 evaluation functions."""
import json
import numpy as np
from .sequence_data import ROOT, BASE, WORK, REPORT
from .analysis import read, paired_categories
from ..movement_experts.evaluate import summary
from ..audit import immutable_json
from ..data import digest


def run():
    bindings={}; results={}
    for split in ('train','validation'):
        dataset=BASE/'combined-train.npz' if split=='train' else BASE.parent/'v4/validation.npz'
        raw=read(dataset); direction=np.load(BASE.parent/f'v7/{split}-direction.npy')
        d=dict(raw=raw,direction=direction)
        forecasts={name:read(WORK/f'runs/{name}/{split}-predictions.npz') for name in ('L01','L02')}
        masks={'all':np.ones(len(raw['y']),bool)}
        if split=='train':masks['natural']=np.load(BASE.parent/'v9/frequency/natural-mask.npy')
        scores={name:{k:summary(d,p,m) for k,m in masks.items()} for name,p in forecasts.items()}
        results[split]={'scores':scores}
        if split=='validation':
            results[split]['L02_minus_L01']=paired_categories(raw,forecasts['L02'],forecasts['L01'],masks['all'])
            results[split]['L02_minus_L00']=paired_categories(raw,forecasts['L02'],read(WORK/'runs/L00/validation-predictions.npz'),masks['all'])
        for name in forecasts:
            path=WORK/f'runs/{name}/{split}-predictions.npz';bindings[str(path.relative_to(ROOT))]=digest(path)
        for path in (dataset,BASE.parent/f'v7/{split}-direction.npy'):
            bindings[str(path.relative_to(ROOT))]=digest(path)
    immutable_json(REPORT/'L02-L01-comparison.json',dict(results=results,bindings=bindings,
        protocol_sha256=digest(REPORT/'L02-protocol.json'),source_sha256=digest(__file__),
        evaluation_sources={name:digest(__file__.replace('retention_evaluate.py',name)) for name in ('analysis.py','inference.py')},
        qualification='Primary direct retained L01 comparison. Original all-row denominators, unchanged summary/paired-category definitions, 2000 paired whole-group draws seed20261106. TRAIN in-sample; natural membership here uses augmented filter traversal. Supplemental natural-cadence result separately reported. Five reused DEV groups after checkpoint selection and one seed; not independent replication.',
        new_fits=0,reserved_opened=0))


if __name__=='__main__':run()
