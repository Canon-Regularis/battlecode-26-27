"""Ten-run development controller; selection reads validation results only."""
import json

from .audit import immutable_json
from .benchmark import REPORTS, WORK
from .data import digest
from .reliable_train import fit, load_data

DESIGNS=[
    dict(id='E01',name='stateless-basic',history=0,rich=False,spatial=False,balance=0.,augment=False),
    dict(id='E02',name='stateless-rich-spatial',history=0,rich=True,spatial=True,balance=0.,augment=False),
    dict(id='E03',name='gru-rich-history4',history=4,rich=True,spatial=True,balance=0.,augment=False),
    dict(id='E04',name='gru-rich-history16',history=16,rich=True,spatial=True,balance=.5,augment=False),
    dict(id='E05',name='stateless-rich-rare-training',history=0,rich=True,spatial=True,balance=.5,augment=True),
    dict(id='E06',name='gru-rich-rare-training',history=16,rich=True,spatial=True,balance=.5,augment=True)]


def freeze_designs():
    immutable_json(REPORTS/'experiment-designs.json',dict(designs=DESIGNS,
        remaining_runs=['E07 best GRU seed27','E08 best GRU seed28','E09 best stateless seed27','E10 best stateless seed28'],
        amended_before_any_training=True,
        reason='Data-quality audit found only five sampled training teleports and ten altar actions, despite additional recorded rare actions in full indexes. Use paired augmented/stateless fits and three seeds for both final configurations within ten experiments.',
        augmentation='At most 64 extra complete rare-action turns per TRAIN game; select deterministically from existing full indexes, exclude original sampled turns, leave validation and test unchanged.',
        selection='Original metric targets, groups and test remain unchanged. Select checkpoints by validation observed joint NLL and configurations by count of proposed targets met then joint NLL.',
        limits='History4 versus history16 also changes class balancing; this combined experiment does not isolate those two effects.',
        benchmark_sha256=digest(REPORTS/'benchmark.json')))


def references(infos,simple):
    baselines={**{k:v for k,v in simple.items()},**{c['config']['id']:c['validation'] for c in infos if not c['config']['history']}}
    bestloss=min(baselines,key=lambda n:baselines[n]['joint_nll'])
    bestmove=max(simple,key=lambda n:simple[n]['parameters']['move']['exact_accuracy'])
    target={name:max(baselines,key=lambda n:baselines[n]['parameters'][name]['exact_accuracy']) for name in ('attack','cast_0','cast_1')}
    return dict(loss=bestloss,movement=bestmove,targeting=target),baselines


def gates(report,ref,baselines):
    move_gain=report['parameters']['move']['exact_accuracy']-baselines[ref['movement']]['parameters']['move']['exact_accuracy']
    reduction=1-report['joint_nll']/baselines[ref['loss']]['joint_nll']
    drops={n:baselines[r]['parameters'][n]['exact_accuracy']-report['parameters'][n]['exact_accuracy'] for n,r in ref['targeting'].items()}
    passed=dict(macro_f1=report['macro_f1']>=.65,movement=move_gain>=.10,joint_loss=reduction>=.10,
                targeting=all(d<=.02 for d in drops.values()))
    return dict(passed=passed,passed_count=sum(passed.values()),movement_gain=move_gain,
                joint_loss_reduction=reduction,targeting_drops=drops)


def run():
    freeze_designs()
    train=load_data('train');val=load_data('validation');aug=None;infos=[]
    simple=json.loads((REPORTS/'simple-baselines.json').read_text())['validation']
    for config in DESIGNS:
        if config['id'] in ('E05','E06'):
            config=config|dict(constrain=True)
        path=REPORTS/f'{config["id"]}.json'
        if path.exists():
            info=json.loads(path.read_text())
            if digest(WORK/'runs'/config['id']/'model.pt')!=info['checkpoint_sha256']:
                raise ValueError('Saved experiment changed')
        else:
            if config['augment'] and aug is None:aug=load_data('train-aug')
            info=fit(config,26,aug if config['augment'] else train,val)
        infos.append(info)
    extra=REPORTS/'additional-simple-baselines.json'
    if extra.exists():simple|=json.loads(extra.read_text())['validation']
    ref,base=references(infos,simple)
    eligible=[i for i in infos if i['config']['history']]
    ranked=sorted(eligible,key=lambda i:(-gates(i['validation'],ref,base)['passed_count'],i['validation']['joint_nll']))
    winner=ranked[0]
    stateless=min([i for i in infos if not i['config']['history']],key=lambda i:i['validation']['joint_nll'])
    immutable_json(REPORTS/'selection-lock.json',dict(winner=winner['config'],stateless=stateless['config'],references=ref,
        checkpoints={i['config']['id']:i['checkpoint_sha256'] for i in infos},
        validation_gates={i['config']['id']:gates(i['validation'],ref,base) for i in eligible},
        policy='No test data read. Configurations chosen once from seed26 validation; repetitions cannot change selection.'))
    for identifier,seed,original in [('E07',27,winner),('E08',28,winner),('E09',27,stateless),('E10',28,stateless)]:
        path=REPORTS/f'{identifier}.json'
        if path.exists():continue
        config=original['config']|dict(id=identifier,repeats=original['config']['id'])
        if config['augment'] and aug is None:aug=load_data('train-aug')
        fit(config,seed,aug if config['augment'] else train,val)
    immutable_json(REPORTS/'final-candidate-lock.json',dict(
        selection_sha256=digest(REPORTS/'selection-lock.json'),
        checkpoints={p.stem:json.loads(p.read_text())['checkpoint_sha256'] for p in REPORTS.glob('E[0-9][0-9].json')},
        experiment_count=len(list(REPORTS.glob('E[0-9][0-9].json'))),
        status='Fitting complete; final test may now be encoded/evaluated without changing selection.'))


if __name__=='__main__':
    import sys
    freeze_designs() if '--freeze-only' in sys.argv else run()
