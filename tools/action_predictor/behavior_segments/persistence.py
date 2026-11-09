"""No-fit causal baseline: classify the completed prior turn, assume persistence."""
import argparse,json
from collections import Counter
import numpy as np
from .data import REPORT,ROOT,load
from .segmentation import transform,emission
from ..audit import immutable_json
from ..data import digest


def forecast(previous,mask,fitted,default_code):
    if not any(mask):return int(default_code)
    values=transform(np.asarray([previous]),np.asarray([mask]),np.asarray(fitted['mean']),np.asarray(fitted['scale']))
    return int(emission(values,np.asarray([mask]),np.asarray(fitted['centers']))[0].argmin())


def freeze():
    d=json.loads((REPORT/'discovery.json').read_text());windows,_=load();counts=Counter()
    for w in windows:
        if w['partition']=='fit':counts.update(k for s,k in zip(w['steps'],d['labels'][w['key']]) if s['observed'])
    immutable_json(REPORT/'persistence-plan.json',dict(source_sha256=digest(__file__),discovery_sha256=digest(REPORT/'discovery.json'),
        data_sha256=digest(REPORT/'data.json'),default_code=counts.most_common(1)[0][0],
        rule='Nearest existing frozen prototype to the completed previous-turn descriptor; forecast that code persists into the current query. Use the fitting majority when previous descriptor is unavailable. All8frozen prototypes remain eligible, including unused ones. No current-turn actions, future descriptors or offline current code enter forecast.',
        scope='Postfit diagnostic motivated by a fitting-only check. No parameter optimization, new prototype fitting, selection or promotion. This is not an independent confirmatory experiment. Does not alterS00/S01 or their frozen gates.',optimizer_updates=0))


def evaluate():
    plan=json.loads((REPORT/'persistence-plan.json').read_text())
    assert digest(__file__)==plan['source_sha256'] and digest(REPORT/'discovery.json')==plan['discovery_sha256'] and digest(REPORT/'data.json')==plan['data_sha256']
    d=json.loads((REPORT/'discovery.json').read_text());windows,_=load();results={}
    for split in ('fit','evaluation'):
        records=[]
        for w in windows:
            if w['partition']!=split:continue
            for s,k in zip(w['steps'],d['labels'][w['key']]):
                if not s['observed']:continue
                p=forecast(s['previous'],s['previous_mask'],d['fitted'],plan['default_code'])
                records.append(dict(group=w['group'],event=s['event'],key=w['key'],target=k,prediction=p))
        recalls={k:sum(r['prediction']==k for r in records if r['target']==k)/sum(r['target']==k for r in records) for k in sorted({r['target'] for r in records})}
        results[split]=dict(rows=len(records),accuracy=sum(r['prediction']==r['target'] for r in records)/len(records),
            balanced_accuracy=float(np.mean(list(recalls.values()))),recalls=recalls,predicted_counts=dict(Counter(r['prediction'] for r in records)),
            groups={g:sum(r['prediction']==r['target'] for r in records if r['group']==g)/sum(r['group']==g for r in records) for g in sorted({r['group'] for r in records})})
    immutable_json(REPORT/'persistence-result.json',dict(plan_sha256=digest(REPORT/'persistence-plan.json'),results=results,optimizer_updates=0,
        qualification='Forecast agreement with frozen hindsight codes, not ground-truth objective accuracy. No goal/movement benefit tested or model replacement selected.'))
    print(json.dumps(results,indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('command',choices=('freeze','evaluate'));a=p.parse_args()
    freeze() if a.command=='freeze' else evaluate()
