"""Replay personal PRE stream through complete offline entity predictor."""
from collections import defaultdict
import gzip,json,sys
from pathlib import Path
import numpy as np
import torch
from . import reliable_train as rt
from .fundamental_audit import ROOT,WORK,REPORTS,dependencies,arrays,log
from .priority_fit_v3 import BASE,VAL,read,context_directory
from .priority_residual_fit import VOCAB
from .entity_experiment import validated_inputs,source_hashes
from .entity_predictor import EntityPredictor
from .entity_cache import DIRECTORY
from .entity_set import EntityBank
from .more_replays import frozen,sha
from .rich_data import read_turns,SPATIAL
from .observation_data import compact_supplement
from .priority_head import flatten
from .action_priority_head import classifier_features
from .audit import cursor

@torch.no_grad()
def run(identifier):
    dependencies();validated_inputs();rt.setup(26)
    info=read(REPORTS/(identifier+'.json'));plan=read(REPORTS/(identifier+'-plan.json'))
    assert sha(REPORTS/(identifier+'-plan.json'))==info['plan_sha256']
    assert source_hashes()==plan['source_hashes']
    directory=WORK/'runs'/identifier;checkpoint=directory/'model.pt';assert sha(checkpoint)==info['checkpoint_sha256']
    assert sha(directory/'validation-predictions.npz')==info['predictions_sha256']
    stored=arrays(directory/'validation-predictions.npz');saved=torch.load(checkpoint,weights_only=True,map_location='cpu');raw=arrays(VAL)
    data,_=rt.model_data(raw,read(ROOT/'tools/action_predictor/experiments/v5/M01.json')['config'],(saved['mean'],saved['std']))
    priority=arrays(BASE.parent/'v8/priority-validation.npz');values=torch.from_numpy(priority['values']);extra=torch.from_numpy((flatten(priority['values'],priority['history']).astype(np.float32)-saved['priority_mean'].numpy())/saved['priority_std'].numpy())
    features=classifier_features(extra,values);bank=EntityBank(DIRECTORY,'validation',saved['config']['dimension']);norm=context_directory()/'extra-normalization.npz';vocab=read(VOCAB)
    legacy=BASE.parent/'v8';cases=0;forced=0;maximum=0.;jobs=[j for j in read(BASE.parent/'v7/jobs.json') if j['split']=='validation']
    for job in jobs:
        digest=job['record']['raw_sha256'];events=defaultdict(list)
        with (Path(job['manifest']['source'])/'extracted'/digest/'index.jsonl').open() as stream:
            for line in stream:
                turn=json.loads(line)
                if turn.get('record')=='turn':
                    for root in turn['roots']:events[turn['actor']].append((root,turn['round']))
        for roots in events.values():roots.sort(key=lambda p:cursor(p[0]['event']))
        states={}
        with gzip.open(legacy/'priority'/digest/'pre.jsonl.gz','rt') as stream:
            for line in stream:
                row=json.loads(line)
                if row['record']=='priority_pre':states[row['event']]=row
        route=None;supplements={}
        with (Path(job['work'])/'supplement'/digest/'pre.jsonl').open() as stream:
            for line in stream:
                row=json.loads(line)
                if row['record']=='map':route=row['route']
                elif row['record']=='pre':supplements[row['id']]=compact_supplement(row)
        targets=[(t,d) for t in read_turns(job['manifest'],job['record']) for d in t['decisions']]
        for local in sorted({0,len(targets)//2,len(targets)-1}):
            turn,decision=targets[local];idx=job['offset']+local
            predictor=EntityPredictor(BASE/'runs/M01/model.pt',norm,vocab,legacy/'runs/P05/model.pt',checkpoint,info['checkpoint_sha256'],actor=turn['actor'])
            for root,round_number in events[turn['actor']]:
                if cursor(root['event'])>cursor(decision['pre_cursor']):break
                predictor.observe(root['event'],root['header']['step'],round_number)
            args=(decision['observation'],supplements[decision['id']],route,turn['round'],decision['pre_cursor'],states[decision['event_cursor']]);actual=predictor.inputs(*args)
            entities,mask=bank.batch(np.array([idx]));expected=dict(x=data['x'][idx:idx+1],history=data['history'][idx:idx+1],grid=data['grid'][idx:idx+1].float(),valid=data['valid'][idx:idx+1],rules=data['rules'][idx:idx+1],extra=extra[idx:idx+1],priority_values=values[idx:idx+1],classifier_features=features[idx:idx+1],entities=entities,entity_mask=mask)
            for key in expected:assert torch.equal(actual[key],expected[key]),(idx,key)
            output=predictor.distributions(actual);reference=predictor.distributions(expected)
            for key in ('action','coordinate','priority_raw'):maximum=max(maximum,float((output[key]-reference[key]).abs().max()))
            forecast=predictor.predict(*args);assert forecast['action']==rt.LABELS[int(stored['prediction'][idx])]
            assert int(predictor.head.integer(output['priority_raw'],actual['priority_values'])[0])==int(stored['priority'][idx])
            assert int(output['coordinate'].argmax(-1))==int(stored['proposed_coordinate'][idx])
            # All families are checked explicitly, with no recorded family as an input.
            for name in SPATIAL:
                family=torch.tensor([rt.LABELS.index(name)])
                p=predictor.network.parameter_logits(output['movement'],output['context'],actual['grid'],actual['valid'],family,actual['rules']).softmax(-1)
                branch=predictor.network.student if name in ('move','blocked') else predictor.network.teacher
                context=output['movement'] if name in ('move','blocked') else output['context']
                q=branch.parameter_logits(context,actual['grid'],actual['valid'],family,actual['rules']).softmax(-1)
                maximum=max(maximum,float((p-q).abs().max()));forced+=1
            cases+=1
    assert maximum<=2e-6
    sources={str(Path(__file__).resolve()):sha(__file__),str(Path(__file__).with_name('entity_predictor.py').resolve()):sha(Path(__file__).with_name('entity_predictor.py'))}
    for path,digest in sources.items():(REPORTS/(identifier+'-'+digest+'-'+Path(path).name+'.txt')).write_bytes(Path(path).read_bytes())
    frozen(REPORTS/(identifier+'-causal-inference-roundtrip.json'),dict(report_sha256=sha(REPORTS/(identifier+'.json')),checkpoint_sha256=info['checkpoint_sha256'],source_hashes=sources,cases=cases,games=len(jobs),forced_spatial_families=forced,maximum_probability_or_raw_error=maximum,tolerance=2e-6,all_inputs_exact=True,scope='Full earlier-own action stream, exact PRE scalars, raw personal observation and public map -> all model inputs -> complete predicted family routed command. First/middle/last target per game, no correctness selection. No current target used as input.',new_fits=0,reserved_opened=0))
    print('Full causal entity inference roundtrip passed',cases,'targets;',forced,'family routes; max error',maximum)

if __name__=='__main__':log([sys.executable,'-m','tools.action_predictor.entity_roundtrip',*sys.argv[1:]]);run(sys.argv[1])
