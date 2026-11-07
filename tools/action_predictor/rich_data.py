"""V4 preparation from frozen PRE evidence and strictly earlier own actions."""
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import Counter, defaultdict
import hashlib
import json
import math
from pathlib import Path
import subprocess
import zipfile

import numpy as np

from .audit import immutable_json, validate_decision, cursor
from .benchmark import REPORTS, WORK
from .data import action_name, digest, features
from .targets import OFFSETS, point

SPATIAL = ['move','blocked','attack','cast_0','cast_1','ward','submit','altar','teleport']


def load_manifest():
    path=Path('.cambc/action-predictor/data/dataset.json')
    benchmark=json.loads((REPORTS/'benchmark.json').read_text())
    if digest(path)!=benchmark['original_dataset_sha256']:
        raise ValueError('Frozen benchmark membership changed')
    return json.loads(path.read_text())


def read_turns(manifest, record):
    path=Path(record['augmented_path']) if 'augmented_path' in record else Path(manifest['source'])/'extracted'/record['raw_sha256']/'turns.jsonl'
    if digest(path)!=record.get('augmented_sha256',record['turns_sha256']):
        raise ValueError('Original turns changed')
    turns=[]
    for line in path.open(encoding='utf-8'):
        t=json.loads(line)
        if t.get('record')=='turn' and t.get('complete') and not t.get('diagnostic_only') and t['view']['team_id']==manifest['fish_team_id'] and t['decisions']:
            if not any(d['label']['root_class'] in ('unknown','error','rollover','resign') for d in t['decisions']):
                turns.append(t)
    return turns


def supplement_one(manifest, record, originals):
    directory=WORK/'supplement'/record['raw_sha256']
    directory.mkdir(parents=True,exist_ok=True)
    output=directory/'pre.jsonl'
    receipt=directory/'receipt.json'
    code=digest(Path(__file__).with_name('supplement.cjs'))
    if receipt.exists():
        saved=json.loads(receipt.read_text())
        if saved['code']!=code or digest(output)!=saved['sha256']:
            raise ValueError('Cached supplement changed')
        return record['match']
    source=Path(manifest['source'])
    reader=Path(manifest['reader_root']) if 'reader_root' in manifest else source.parents[2]/'tools/replay_eval'
    alias=originals[record['raw_sha256']]['aliases'][0]
    with zipfile.ZipFile(alias['path']) as z:
        payload=z.read('replay.repl26a')
    if hashlib.sha256(payload).hexdigest()!=record['raw_sha256']:
        raise ValueError('Actual replay payload differs')
    (directory/'raw.bin').write_bytes(payload)
    turns=read_turns(manifest,record)
    q=dict(raw=str((directory/'raw.bin').resolve()),raw_sha256=record['raw_sha256'],reader=str(reader),
           assets=manifest['assets_root'] if 'assets_root' in manifest else str(next(source.parents[1].glob('asset-cache-5/*/visualiser/assets'))),
           output=str(output.resolve()),turns=[dict(entry=t['entry'],actor=t['actor'],team=t['view']['team'],roots=t['roots']) for t in turns])
    (directory/'query.json').write_text(json.dumps(q))
    if output.exists():
        output.unlink()  # Only this task's incomplete output, with no completion receipt.
    result=subprocess.run(['node',str(Path(__file__).with_name('supplement.cjs')),str(directory/'query.json')],capture_output=True,text=True,timeout=300)
    if result.returncode:
        raise ValueError(result.stderr[-3000:])
    footer=json.loads(output.read_text().splitlines()[-1])
    if footer!={'record':'complete','decisions':sum(len(t['decisions']) for t in turns)}:
        raise ValueError('Incomplete supplemental evidence')
    immutable_json(receipt,dict(code=code,sha256=digest(output),raw_sha256=record['raw_sha256'],decisions=footer['decisions']))
    return record['match']


def extract(splits=('train','validation')):
    m=load_manifest()
    frozen=json.loads((Path(m['source'])/'frozen.json').read_text())
    originals={r['raw_sha256']:r for r in frozen['recordings']}
    selected=[r for r in m['recordings'] if r['split'] in splits]
    seen=set()
    for r in m['recordings']:
        if r['raw_sha256'] in seen:
            raise ValueError('Duplicate payload membership')
        seen.add(r['raw_sha256'])
    with ThreadPoolExecutor(max_workers=2) as pool:
        jobs=[pool.submit(supplement_one,m,r,originals) for r in selected]
        for i,future in enumerate(as_completed(jobs),1):
            future.result()
            if i%10==0 or i==len(jobs):
                print(f'Supplemental PRE {i}/{len(jobs)}',flush=True)


def historical_actions(source, record, labels):
    """Index all recorded own roots; sampled turns are never treated as adjacent."""
    path=source/'extracted'/record['raw_sha256']/'index.jsonl'
    receipt=json.loads((path.parent/'receipt.json').read_text())
    if digest(path)!=receipt['files']['index.jsonl']:
        raise ValueError('Full root index changed')
    events=defaultdict(list)
    for line in path.open(encoding='utf-8'):
        t=json.loads(line)
        if t.get('record')!='turn':
            continue
        for r in t['roots']:
            h=r['header'];s=h['step'];name=r['classification']
            if name=='cast':
                name=f'cast_{s.get("abilitySlot")}'
            events[t['actor']].append((cursor(r['event']),labels.index(name) if name in labels else 0,s,t['round']))
    for actor in events:
        events[actor].sort(key=lambda e:e[0])
    return events


def history_vector(event, current_round, pos, labels):
    _,kind,s,round_number=event
    x=np.zeros(len(labels)+9,dtype=np.float32)
    x[kind]=1
    x[len(labels)]=min(max(current_round-round_number,0),100)/100
    if point(pos):
        if point(s.get('to')):
            x[len(labels)+1:len(labels)+3]=[(s['to']['x']-pos['x'])/32,(s['to']['y']-pos['y'])/32]
        if point(s.get('from')) and s['kind'] in (4,23):
            x[len(labels)+3:len(labels)+5]=[(s['to']['x']-s['from']['x'])/8,(s['to']['y']-s['from']['y'])/8]
    x[len(labels)+5]=float(s['kind']==4)
    x[len(labels)+6]=float(s['kind']==5)
    x[len(labels)+7]=float(s['kind']==6)
    x[len(labels)+8]=1
    return x


def extra_features(obs, supplemental, route, round_number):
    own=obs['own'];pos=own.get('position');s=supplemental
    values=[float(point(pos)),math.log1p(max(0,s['own'].get('gold',0))),
            float('gold' in s['own']),own.get('maxHealth',0)/2000,
            own.get('health',0)/2000,round_number/1000,
            float(s['can_shop']),float(s['can_shop_consumables']),len(s['movement'])/100]
    names=['position_known','log_gold','gold_known','max_hp','hp','round','shop','consumable_shop','movement_options']
    for k in ('strength','focus'):
        stat=s['own'].get(k,{})
        for part in ('base','items','bonus','effective'):
            values.append(stat.get(part,0)/100 if isinstance(stat,dict) else 0)
            names.append(k+'_'+part)
    for k in ('charges','rechargeTimer'):
        values.append(s['own'].get('ward',{}).get(k,0)/10);names.append('ward_'+k)
    for i in range(4):
        values.append(float(bool(s['restrictions']&(1<<i))));names.append('restriction_'+str(i))
    for i in range(4):
        a=s['own'].get('consumables',[])
        values.append(a[i]/10 if i<len(a) else 0);names.append('consumable_'+str(i))
    if point(pos):
        w,h=route['width'],route['height']
        values += [pos['x']/w,pos['y']/h,w/64,h/64]
    else:
        values += [0,0,route['width']/64,route['height']/64]
    names += ['relative_map_x','relative_map_y','map_width','map_height']
    for slot in range(2):
        p=(own.get('abilityProps') or [{},{}])[slot]
        for key in ('range','radius','modifier','duration','stunDuration','target','attributes','cooldown'):
            values.append(p.get(key,0)/10);names.append(f'ability_{slot}_{key}')
    for name,points in [('altar',route['altars'])]:
        points=sorted(points,key=lambda p:max(abs(p['x']-pos['x']),abs(p['y']-pos['y']))) if point(pos) else []
        for i in range(3):
            p=points[i] if i<len(points) else None
            values += [(p['x']-pos['x'])/32,(p['y']-pos['y'])/32] if p else [0,0]
            names += [f'{name}_{i}_dx',f'{name}_{i}_dy']
    return np.asarray(values,dtype=np.float32),names


def candidate_grid(obs,supp,route,last_move):
    """Candidate encodings use public geometry and personal PRE entities only."""
    pos=obs['own'].get('position');grid=np.zeros((289,20),dtype=np.float32)
    grid[:,:2]=OFFSETS/8;grid[:,2]=np.abs(OFFSETS).max(1)/8
    if not point(pos):
        return grid,np.zeros(289,dtype=bool),np.zeros(289,dtype=bool)
    coords=OFFSETS+np.array([pos['x'],pos['y']]);w,h=route['width'],route['height']
    valid=(coords[:,0]>=0)&(coords[:,0]<w)&(coords[:,1]>=0)&(coords[:,1]<h)
    blocked=set(route['blocked']);movements={(p['x'],p['y']) for p in supp['movement']}
    grid[:,3]=valid
    grid[:,4]=[int(y*w+x in blocked) for x,y in coords]
    move=np.array([tuple(p) in movements for p in coords])
    grid[:,5]=move
    enemyspawn=route['spawns'][1-obs['own']['team']]
    grid[:,6]=[(enemyspawn['minX']<=x<enemyspawn['maxX'] and enemyspawn['minY']<=y<enemyspawn['maxY']) for x,y in coords]
    visible=[e for e in obs['entities'] if e.get('known',0)&1 and point(e.get('position')) and e.get('health',0)>0]
    for cat in range(3):
        units=[e for e in visible if (2 if e['entity']['kind']==2 else int(e['team']==obs['own']['team']))==cat]
        if units:
            points=np.array([[e['position']['x'],e['position']['y']] for e in units])
            dist=np.abs(coords[:,None,:]-points[None,:,:]).max(-1)
            grid[:,7+cat]=np.minimum(dist.min(-1),64)/32
            grid[:,10+cat]=(dist==0).sum(-1)
            hp=np.array([e['health']/max(e.get('maxHealth',1),1) for e in units])
            grid[:,13+cat]=((dist==0)*hp).sum(-1)
    if route['altars']:
        altars=np.array([[p['x'],p['y']] for p in route['altars']])
        grid[:,16]=np.abs(coords[:,None]-altars[None]).max(-1).min(-1)/32
    grid[:,17]=(OFFSETS==0).all(-1)
    if last_move is not None:
        grid[:,18]=(OFFSETS==last_move).all(-1)
        grid[:,19]=np.abs(OFFSETS-last_move).max(-1)/8
    return grid,valid,move


def build(splits=('train','validation'),augment=False):
    m=load_manifest();labels=m['labels'];source=Path(m['source'])
    if augment:
        additions=json.loads((WORK/'augmentation.json').read_text())
        m['recordings']=[r|additions[r['raw_sha256']] if r['raw_sha256'] in additions else r for r in m['recordings']]
    groups=sorted({r['group'] for r in m['recordings']});group_ids={g:i for i,g in enumerate(groups)}
    for split in splits:
        output_name=split+'-aug' if augment else split
        output=WORK/f'{output_name}.npz'
        if output.exists():
            receipt=json.loads((WORK/f'{output_name}-data.json').read_text())
            if digest(output)!=receipt['sha256']:
                raise ValueError('Prepared data changed')
            continue
        rows=defaultdict(list);quality=Counter();feature_names=None
        for r in [r for r in m['recordings'] if r['split']==split]:
            directory=WORK/'supplement'/r['raw_sha256']
            evidence=[json.loads(l) for l in (directory/'pre.jsonl').open()]
            route=evidence[0]['route'];supplements={s['id']:s for s in evidence if s['record']=='pre'}
            if augment:
                extra=WORK/'augmentation'/r['raw_sha256']/'pre.jsonl'
                if extra.exists():
                    supplements.update({s['id']:s for s in map(json.loads,extra.open()) if s['record']=='pre'})
            turns=read_turns(m,r);histories=historical_actions(source,r,labels)
            for t in turns:
                for d in t['decisions']:
                    validate_decision(d,t);supp=supplements[d['id']]
                    if supp['pre']!=d['pre_cursor']:
                        raise ValueError('Supplement PRE mismatch')
                    for key in ('position','health','maxHealth','items','gems','channelType','channelTimer','roundFlags'):
                        if key in supp['own'] and supp['own'][key]!=d['observation']['own'].get(key):
                            raise ValueError('Fresh snapshot differs from original PRE')
                    obs=d['observation'];name=action_name(d['label']);y=labels.index(name) if name in labels else 0
                    past=[e for e in histories[t['actor']] if e[0]<=cursor(d['pre_cursor'])]
                    if past and past[-1][0]>=cursor(d['event_cursor']):
                        raise ValueError('Future action leaked into history')
                    history=np.zeros((32,len(labels)+9),dtype=np.float32)
                    for i,event in enumerate(past[-32:]):
                        history[32-min(len(past),32)+i]=history_vector(event,t['round'],obs['own'].get('position'),labels)
                    movements=[e for e in past if e[2]['kind']==4]
                    last_move=None
                    if movements:
                        s=movements[-1][2];last_move=np.array([s['to']['x']-s['from']['x'],s['to']['y']-s['from']['y']])
                    basic,basic_names=features(obs);extra,extra_names=extra_features(obs,supp,route,t['round'])
                    grid,valid,move=candidate_grid(obs,supp,route,last_move)
                    py=-1;pos=obs['own'].get('position');target=d['label'].get('to')
                    if name in SPATIAL:
                        py=290
                        if point(pos) and point(target):
                            delta=np.array([target['x']-pos['x'],target['y']-pos['y']])
                            py=(int(delta[1])+8)*17+int(delta[0])+8 if np.abs(delta).max()<=8 else 289
                    priority=float(d['audit']['header']['step']['priority']) if name=='priority' else 0.
                    # Histories remain separate; stateless models receive neither history nor last-move candidate channels.
                    rows['x'].append(np.concatenate([basic,extra]));rows['history'].append(history)
                    rows['grid'].append(grid.astype(np.float16));rows['valid'].append(valid);rows['move_mask'].append(move)
                    rows['y'].append(y);rows['py'].append(py);rows['priority'].append(priority)
                    rows['group'].append(group_ids[r['group']]);rows['round'].append(t['round'])
                    rows['flags'].append(obs['own'].get('roundFlags',0));rows['restrictions'].append(supp['restrictions'])
                    rows['pos_known'].append(point(pos));rows['hp_alive'].append(obs['own'].get('alive',False))
                    rows['attack_range'].append(obs['own'].get('attackRange',0));rows['channel'].append(obs['own'].get('channelType',0))
                    rows['shop'].append(supp['can_shop'] or supp['can_shop_consumables'])
                    rows['ability_ready'].append([bool(p.get('type')) and obs['own'].get('cooldowns',[1,1])[i]==0 and (not p.get('maxCharges') or obs['own'].get('charges',[0,0])[i]>0) for i,p in enumerate(obs['own'].get('abilityProps',[{},{}]))])
                    rows['ability_range'].append([p.get('range',0) for p in obs['own'].get('abilityProps',[{},{}])])
                    rows['ability_mask'].append([p.get('target',0) for p in obs['own'].get('abilityProps',[{},{}])])
                    rows['gems'].append(obs['own'].get('gems',0));rows['ward_charges'].append(supp['own'].get('ward',{}).get('charges',0))
                    quality[name]+=1;quality['unsupported_coordinate']+=int(py>=289)
                    quality['unidentifiable_shop_arguments']+=int(name=='shop')
                    feature_names=basic_names+extra_names
            print(f'Encoded {split}: {r["match"]}',flush=True)
        arrays={k:np.stack(v) for k,v in rows.items()}
        np.savez_compressed(output,**arrays)
        immutable_json(WORK/f'{output_name}-data.json',dict(sha256=digest(output),rows=len(arrays['y']),quality=quality,
                        supplement_code_sha256=digest(Path(__file__).with_name('supplement.cjs')),
                        feature_names=feature_names,basic_features=200,labels=labels,groups=groups))
        print(f'{split}: {len(arrays["y"])} actions',flush=True)


if __name__=='__main__':
    import sys
    splits=('test',) if '--test' in sys.argv else ('train','validation')
    if '--test' in sys.argv and not (REPORTS/'final-candidate-lock.json').exists():
        raise ValueError('Final candidates must be locked before opening test PRE evidence')
    WORK.mkdir(parents=True,exist_ok=True)
    extract(splits)
    build(splits)
