"""Fixed-output ranking/calibration diagnostic, not a threshold search or fit."""
import argparse,json
import numpy as np
from .protocol import BASE,WORK,REPORT
from .fit import load
from .evaluate import read,binary
from ..audit import immutable_json
from ..data import digest

def ranking(y,probability):
    positive=y==14;positives=int(positive.sum());negatives=len(y)-positives
    order=np.argsort(-probability,kind='stable');p=positive[order];s=probability[order]
    ends=np.r_[np.flatnonzero(s[:-1]!=s[1:]),len(s)-1];tp=np.cumsum(p)[ends];fp=ends+1-tp
    precision=tp/(ends+1);recall=tp/max(1,positives)
    ap=float(np.sum(np.diff(np.r_[0,recall])*precision)) if positives else None
    auc=float(np.trapezoid(np.r_[0,recall],np.r_[0,fp/max(1,negatives)])) if positives and negatives else None
    stats={}
    for name,mask in [('ward',positive),('recall',y==10),('other',~positive)]:
        values=probability[mask];stats[name]=dict(rows=len(values),mean=float(values.mean()) if len(values) else None,quantiles=np.quantile(values,[0,.1,.5,.9,1]).tolist() if len(values) else None)
    return dict(average_precision=ap,AUROC=auc,probability_by_true_family=stats,ties='Whole equal-score groups; trapezoidal ROC, stepwise precision-recall average precision. No threshold selection.')

def run(identifier,evaluation):
    ev=json.loads((REPORT/f'{evaluation}-evaluation.json').read_text());assert ev['typing']==identifier
    out={};hashes={}
    for split in ('train','validation'):
        data=load(split);y=data['raw']['y'];p=read(WORK/f'evaluations/{evaluation}/{split}-primary.npz');control=read(WORK/f'evaluations/control/{split}-primary.npz');masks={'all':np.ones(len(y),bool)}
        if split=='train':masks['natural']=np.load(BASE.parent/'v9/frequency/natural-mask.npy')
        out[split]={}
        for sampling,mask in masks.items():
            rows={}
            for name,forecast in [('specialist',p),('G00',control)]:
                prob=forecast['ward_probability'][mask];label=y[mask];prediction=forecast['prediction'][mask];positive=label==14;guess=prediction==14;tp=int((positive&guess).sum());fp=int((~positive&guess).sum());fn=int((positive&~guess).sum());den=2*tp+fp+fn
                rows[name]=dict(rows=len(label),ward_rows=int(positive.sum()),binary_fixed_half=binary(label,prob),ranking=ranking(label,prob),complete_predicted_ward=dict(TP=tp,FP=fp,FN=fn,F1=2*tp/den if den else None,precision=tp/(tp+fp) if tp+fp else None,recall=tp/(tp+fn) if tp+fn else None,recall_to_ward=int((guess&(label==10)).sum())),missed_ward_predicted_types={str(int(k)):int(((prediction==k)&positive).sum()) for k in np.unique(prediction[positive]) if k!=14})
            out[split][sampling]=rows
        hashes[split]=digest(WORK/f'evaluations/{evaluation}/{split}-primary.npz')
    immutable_json(REPORT/f'{identifier}-typing-diagnosis.json',dict(results=out,evaluation=evaluation,prediction_hashes=hashes,source_sha256=digest(__file__),fit_report_sha256=digest(REPORT/f'{identifier}.json'),evaluation_sha256=digest(REPORT/f'{evaluation}-evaluation.json'),commands=[f'python -m tools.action_predictor.ward_experts.typing_diagnosis {identifier} {evaluation}'],interpretation='Ranking/calibration from fixed selected outputs on original denominators; no threshold search, optimizer or architecture change. TRAIN in-sample and natural sampling same eligible groups; not group-held-out evidence. Binary half threshold differs from hierarchical15way choice; only latter is complete prediction.',new_fits=0,reserved_opened=0));print(identifier,'fixed typing diagnosis complete',flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('identifier');p.add_argument('evaluation');a=p.parse_args();run(a.identifier,a.evaluation)
