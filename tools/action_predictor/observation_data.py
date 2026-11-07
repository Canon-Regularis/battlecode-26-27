"""Recover real earlier personal observations without changing prediction targets."""
from collections import defaultdict,Counter
from concurrent.futures import ProcessPoolExecutor,as_completed
import gzip
import json
from pathlib import Path
import subprocess
import sys

import numpy as np

from .observation_study import ROOT,WORK,REPORTS,OLD,MORE,source_blocks,log_command
from .more_replays import frozen,sha
from .rich_data import read_turns,history_vector,extra_features
from .data import features,action_name
from .audit import cursor,validate_decision


def encode(observation,supplement,route,round_number):
    a,_=features(observation);b,_=extra_features(observation,supplement,route,round_number)
    return np.concatenate((a,b))


def safe_observation(obs,actor,team,supplement):
    assert obs['perspective']==dict(team=team,champion=actor)
    assert obs['own']['entity']==dict(kind=1,index=actor) and obs['own']['team']==team
    assert obs['own']['known']&1
    dynamic={'position','health','maxHealth','buffs','cooldowns','charges','abilities','abilityProps','attackRange','chebyshevRange','alive'}
    for entity in [obs['own'],*obs['entities']]:
        if not entity['known']&1:assert not dynamic.intersection(entity),'Hidden dynamic information'
    known=obs['own']['known']
    if not known&2:assert not {'gems','items'}.intersection(obs['own'])
    if not known&4:assert not {'roundFlags','channelTimer','channelType'}.intersection(obs['own'])
    if not known&8:assert 'gold' not in supplement['own']


def compact_supplement(row):
    return {key:row[key] for key in ('pre','own','movement','restrictions','can_shop','can_shop_consumables')}


def visible_ids(obs):
    return {(e['entity']['kind'],e['entity']['index']) for e in obs['entities'] if e['known']&1}


def near_obstacle(position,route):
    if position is None:return False
    w,h=route['width'],route['height'];blocked=set(route['blocked'])
    for dy in range(-2,3):
        for dx in range(-2,3):
            x,y=position['x']+dx,position['y']+dy
            if not (0<=x<w and 0<=y<h) or y*w+x in blocked:return True
    return False


def game_job(job):
    record=job['record'];manifest=job['manifest'];work=Path(job['work']);raw=record['raw_sha256']
    directory=WORK/'games'/raw;directory.mkdir(parents=True,exist_ok=True)
    receipt_path=directory/'receipt.json'
    code_hashes={name:sha(Path(__file__).with_name(name)) for name in ('observation_data.py','observation_context.cjs')}
    if receipt_path.exists():
        receipt=json.loads(receipt_path.read_text())
        assert receipt['code_hashes']==code_hashes
        assert all(sha(directory/name)==digest for name,digest in receipt['files'].items())
        return receipt
    shard=Path(job['shard']);assert sha(shard)==job['shard_sha256']
    with np.load(shard) as archive:target={key:archive[key] for key in archive.files}
    source=Path(manifest['source'])/'extracted'/raw
    index=source/'index.jsonl';index_receipt=json.loads((source/'receipt.json').read_text())
    assert sha(index)==index_receipt['files']['index.jsonl']
    turns_index=[json.loads(line) for line in index.open()]
    assert turns_index[-1]['status']=='complete'
    originals=read_turns(manifest,record)
    team=originals[0]['view']['team']
    events=defaultdict(list);by_event={}
    for turn in turns_index:
        if turn.get('record')!='turn':continue
        for root in turn['roots']:
            event=dict(root=root,actor=turn['actor'],turn=turn['id'],round=turn['round'],entry=turn['entry'],occurrence=turn['occurrence'])
            events[turn['actor']].append(event)
            assert root['event'] not in by_event
            by_event[root['event']]=event
    for actor,rows in events.items():
        rows.sort(key=lambda e:cursor(e['root']['event']))
        for ordinal,event in enumerate(rows):event['ordinal']=ordinal
    supplements={};route=None
    for path in [work/'supplement'/raw/'pre.jsonl',work/'augmentation'/raw/'pre.jsonl']:
        if not path.exists():continue
        for line in path.open():
            row=json.loads(line)
            if row['record']=='map':route=row['route']
            elif row['record']=='pre':supplements[row['id']]=compact_supplement(row)
    assert route is not None
    targets=[];cached={};needed=set();counts=Counter()
    for turn in originals:
        for decision in turn['decisions']:
            validate_decision(decision,turn)
            event=by_event[decision['event_cursor']]
            assert event['actor']==turn['actor'] and event['round']==turn['round']
            assert cursor(event['root']['pre'])==cursor(decision['pre_cursor'])
            root_list=events[event['actor']];ordinal=event['ordinal']
            previous=root_list[max(0,ordinal-16):ordinal]
            assert all(cursor(e['root']['event'])<=cursor(decision['pre_cursor'])<cursor(event['root']['event']) for e in previous)
            needed.update(e['root']['event'] for e in previous)
            supplemental=supplements[decision['id']]
            safe_observation(decision['observation'],turn['actor'],team,supplemental)
            current=encode(decision['observation'],supplemental,route,turn['round'])
            row=len(targets)
            assert np.array_equal(current,target['x'][row]),'Current observation encoding differs from frozen M01 input'
            assert target['y'][row]==manifest['labels'].index(action_name(decision['label']))
            assert target['round'][row]==turn['round']
            cached[decision['event_cursor']]=dict(record='history',id=decision['id'],actor=turn['actor'],team=team,
                turn=turn['id'],round=turn['round'],pre=decision['pre_cursor'],event=decision['event_cursor'],
                pre_header=decision['audit']['pre_header'],observation=decision['observation'],supplement=supplemental)
            targets.append((turn,decision,event,previous))
    assert len(targets)==len(target['y'])
    cached_needed=needed.intersection(cached)
    audit_cached=sorted(cached_needed,key=cursor)[:8]
    recover=needed.difference(cached).union(audit_cached)
    query_turns=[]
    for turn in turns_index:
        if turn.get('record')!='turn':continue
        roots=[root for root in turn['roots'] if root['event'] in recover]
        if roots:query_turns.append(dict(id=turn['id'],actor=turn['actor'],entry=turn['entry'],round=turn['round'],roots=roots))
    output=directory/'additional.jsonl.gz';query_path=directory/'query.json'
    old_source=Path(json.loads((ROOT/'.cambc/action-predictor/data/dataset.json').read_text())['source'])
    reader=old_source.parents[2]/'tools/replay_eval';assets=next(old_source.parents[1].glob('asset-cache-5/*/visualiser/assets'))
    raw_path=work/'supplement'/raw/'raw.bin';assert sha(raw_path)==raw
    query=dict(raw=str(raw_path),raw_sha256=raw,team=team,reader=str(reader),assets=str(assets),output=str(output),turns=query_turns)
    frozen(query_path,query)
    additional_receipt=directory/'additional-receipt.json'
    if additional_receipt.exists():
        assert sha(output)==json.loads(additional_receipt.read_text())['sha256']
    elif recover:
        assert not output.exists(),'Incomplete history extraction requires inspection, not silent reuse'
        command=['node',str(Path(__file__).with_name('observation_context.cjs')),str(query_path)]
        log_command(command,purpose='Additional earlier own personal observations; eligible game only',query_sha256=sha(query_path))
        p=subprocess.run(command,capture_output=True,text=True,encoding='utf-8',timeout=600)
        if p.returncode:raise ValueError(f'{raw}: '+p.stderr[-4000:])
        frozen(additional_receipt,dict(sha256=sha(output),query_sha256=sha(query_path),code_hashes=code_hashes))
    recovered={}
    if recover:
        with gzip.open(output,'rt',encoding='utf-8') as stream:
            for line in stream:
                frame=json.loads(line)
                if frame['record']=='complete':footer=frame;continue
                assert frame['event'] in recover and frame['event'] not in recovered
                recovered[frame['event']]=frame
        assert footer['frames']==len(recover)==len(recovered)
    for key in audit_cached:
        assert recovered[key]['observation']==cached[key]['observation'],'Personal snapshot does not reproduce'
        assert recovered[key]['supplement']==cached[key]['supplement'],'Personal supplemental state does not reproduce'
    keys=sorted(needed,key=cursor);local_ids={key:i+1 for i,key in enumerate(keys)}
    frame_features=[np.zeros(target['x'].shape[1],np.float32)];frame_observations={}
    evidence=directory/'frames.jsonl.gz'
    with gzip.open(evidence,'wt',encoding='utf-8') as stream:
        for key in keys:
            event=by_event[key];frame=cached[key] if key in cached else recovered[key]
            assert frame['actor']==event['actor'] and frame['team']==team and frame['turn']==event['turn']
            assert frame['round']==event['round'] and frame['pre']==event['root']['pre']
            assert cursor(frame['pre'])<cursor(frame['event'])
            assert frame['pre_header']['phase']==10 and frame['pre_header']['currentChampion']==frame['actor']
            safe_observation(frame['observation'],frame['actor'],team,frame['supplement'])
            vector=encode(frame['observation'],frame['supplement'],route,frame['round'])
            frame_features.append(vector);frame_observations[key]=frame['observation']
            stream.write(json.dumps(frame|dict(origin='cached' if key in cached else 'recovered'))+'\n')
    n=len(targets);sequence=np.zeros((n,16),np.int32);gaps=np.zeros((n,16,5),np.float32)
    available=np.zeros(n,np.uint8);direction=np.zeros(n,np.uint8);obstacle=np.zeros(n,bool);visible_change=np.zeros(n,np.uint8)
    for i,(turn,decision,event,previous) in enumerate(targets):
        own=decision['observation']['own'];pos=own.get('position');count=len(previous);available[i]=count
        expected=np.zeros((16,len(manifest['labels'])+9),np.float32)
        for j,prior in enumerate(previous,16-count):
            root=prior['root'];step=root['header']['step'];name=root['classification']
            if name=='cast':name=f'cast_{step.get("abilitySlot")}'
            label=manifest['labels'].index(name) if name in manifest['labels'] else 0
            expected[j]=history_vector((cursor(root['event']),label,step,prior['round']),turn['round'],pos,manifest['labels'])
            sequence[i,j]=local_ids[root['event']]
            following=previous[j-(16-count)+1] if j<15 else event
            gap=following['round']-prior['round'];age=turn['round']-prior['round']
            assert gap>=0 and age>=0
            gaps[i,j]=[1,1,min(gap,100)/100,float(following['turn']!=prior['turn']),min(age,100)/100]
        assert np.array_equal(expected,target['history'][i,-16:]),'Prior action sequence differs from retained M01'
        obstacle[i]=near_obstacle(pos,route)
        if previous:
            visible_change[i]=1+int(visible_ids(decision['observation'])!=visible_ids(frame_observations[previous[-1]['root']['event']]))
        if decision['label']['root_class']=='move':
            movement=None
            for earlier in reversed(events[event['actor']][:event['ordinal']]):
                if earlier['root']['header']['step']['kind']==4:movement=earlier['root']['header']['step'];break
            delta=np.array([decision['label']['to'][axis]-decision['label']['from'][axis] for axis in ('x','y')])
            if not delta.any():direction[i]=4
            elif movement is None:direction[i]=1
            else:
                last=np.array([movement['to'][axis]-movement['from'][axis] for axis in ('x','y')])
                direction[i]=2 if np.array_equal(np.sign(delta),np.sign(last)) else 3
        counts['targets_crossing_own_turn_boundary']+=int(any(gaps[i,:,3]))
    arrays=directory/'arrays.npz'
    np.savez_compressed(arrays,observations=np.stack(frame_features),sequence=sequence,gaps=gaps,
                        available=available,direction=direction,near_obstacle=obstacle,visible_change=visible_change)
    files={name:sha(directory/name) for name in ('arrays.npz','frames.jsonl.gz','query.json')}
    if recover:files['additional.jsonl.gz']=sha(output)
    result=dict(raw_sha256=raw,rows=n,frames=len(keys),cached_frames=len(cached_needed),additional_frames=len(needed.difference(cached)),
        audit_cached_frames=len(audit_cached),available_history_counts=dict(Counter(map(int,available))),
        missing_observation_frames=0,chronology_alignment=True,action_history_bitwise_identical=True,
        code_hashes=code_hashes,files=files,shard_sha256=job['shard_sha256'],diagnostics=counts)
    frozen(receipt_path,result)
    return result


def jobs():
    WORK.mkdir(parents=True,exist_ok=True)
    output=WORK/'jobs.json'
    if output.exists():return json.loads(output.read_text())
    blocks=source_blocks();result=[]
    for split,path,selected in [('train',MORE/'combined-train.npz',blocks[:2]),('validation',OLD/'validation.npz',blocks[2:])]:
        with np.load(path) as archive:raw={key:archive[key] for key in ('x','history','y','round','group')}
        offset=0
        for block in selected:
            for record in block['records']:
                hashed=record['raw_sha256'];receipt=json.loads((block['work']/'supplement'/hashed/'receipt.json').read_text())
                count=receipt['decisions']
                if 'augmented_path' in record:count+=record['extra_actions']
                group_offset=len(blocks[0]['groups']) if block['name']=='new_train' else 0
                assert np.all(raw['group'][offset:offset+count]==block['groups'].index(record['group'])+group_offset)
                directory=WORK/'targets';directory.mkdir(exist_ok=True)
                shard=directory/(hashed+'.npz')
                if not shard.exists():np.savez_compressed(shard,**{key:value[offset:offset+count] for key,value in raw.items()})
                result.append(dict(record=record,manifest=block['manifest']|dict(recordings=[]),work=str(block['work']),
                                   split=split,offset=offset,rows=count,shard=str(shard),shard_sha256=sha(shard)))
                offset+=count
        assert offset==len(raw['y'])
    frozen(output,result)
    return result


def prepare(audit=False):
    all_jobs=jobs()
    selected=all_jobs
    if audit:
        selected=[]
        for engine in ('2.0.0','3.0.0'):
            selected.append(next(j for j in all_jobs if j['split']=='train' and j['record']['engine_version']==engine))
    receipts={}
    with ProcessPoolExecutor(max_workers=4) as pool:
        pending={pool.submit(game_job,job):job for job in selected}
        try:
            for i,future in enumerate(as_completed(pending),1):
                job=pending[future];receipt=future.result();receipts[job['record']['raw_sha256']]=receipt
                if i%10==0 or i==len(selected):print('Causal observation history games',i,'/',len(selected),flush=True)
        except Exception as error:
            print('History recovery failed:',repr(error),flush=True)
            for future in pending:future.cancel()
            raise
    if audit:
        frozen(REPORTS/'recovery-audit.json',dict(engines=['2.0.0','3.0.0'],games=receipts,
            passed=True,training_only=True,fits_started=0))
        return
    merge(all_jobs,receipts)


def merge(all_jobs,receipts):
    if (REPORTS/'data-ready.json').exists():return
    total_frames=1+sum(r['frames'] for r in receipts.values());dimensions=253
    table=np.lib.format.open_memmap(WORK/'observations.npy',mode='w+',dtype=np.float32,shape=(total_frames,dimensions));table[0]=0
    outputs={};frame_offset=0
    for split,n in [('train',433071),('validation',14439)]:
        outputs[split]={name:np.lib.format.open_memmap(WORK/(split+'-'+name+'.npy'),mode='w+',dtype=dtype,shape=shape)
            for name,dtype,shape in [('sequence',np.int32,(n,16)),('gaps',np.float32,(n,16,5)),('available',np.uint8,(n,)),
                                   ('direction',np.uint8,(n,)),('near_obstacle',bool,(n,)),('visible_change',np.uint8,(n,))]}
    manifest=[]
    for job in all_jobs:
        raw=job['record']['raw_sha256'];receipt=receipts[raw];path=WORK/'games'/raw/'arrays.npz'
        with np.load(path) as archive:
            count=receipt['frames'];table[frame_offset+1:frame_offset+1+count]=archive['observations'][1:]
            start=job['offset'];stop=start+job['rows'];dest=outputs[job['split']]
            for name in dest:
                value=archive[name]
                if name=='sequence':value=np.where(value>0,value+frame_offset,0)
                dest[name][start:stop]=value
            manifest.append(dict(raw_sha256=raw,split=job['split'],offset=start,rows=job['rows'],frames_start=frame_offset+1,frames=count,
                                 receipt_sha256=sha(WORK/'games'/raw/'receipt.json')))
            frame_offset+=count
    table.flush()
    for split in outputs.values():
        for array in split.values():array.flush()
    files={path.name:sha(path) for path in WORK.glob('*.npy')}
    frozen(WORK/'row-frame-manifest.json',manifest)
    frozen(REPORTS/'data-ready.json',dict(files=files,frames=total_frames-1,train_rows=433071,validation_rows=14439,
        cached_frames=sum(r['cached_frames'] for r in receipts.values()),additional_frames=sum(r['additional_frames'] for r in receipts.values()),
        audit_cached_frames=sum(r['audit_cached_frames'] for r in receipts.values()),missing_observation_frames=0,
        sequence_length=16,frame_features=dimensions,all_target_rows_retained=True,new_reserved_games_opened=0,
        manifest_sha256=sha(WORK/'row-frame-manifest.json'),plan_sha256=sha(REPORTS/'plan.json')))
    print('Observation history data ready:',total_frames-1,'frames, all original target rows retained.',flush=True)


if __name__=='__main__':
    log_command([sys.executable,'-m','tools.action_predictor.observation_data',*sys.argv[1:]],purpose='Causal earlier personal observations; eligible games only')
    prepare('--audit' in sys.argv)
