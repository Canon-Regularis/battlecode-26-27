"""Personally visible entity tokens, without entity IDs or a nearest-k cutoff."""
import numpy as np
import torch
from .data import number

def token(entity,own,is_self=False):
    pos=entity.get('position');origin=own.get('position');known_pos=bool(pos and origin)
    dx=number(pos['x'])-number(origin['x']) if known_pos else 0.;dy=number(pos['y'])-number(origin['y']) if known_pos else 0.
    kind=entity['entity']['kind'];category=0 if is_self else 3 if kind==2 else 1 if entity.get('team')==own.get('team') else 2
    typ=int(entity.get('type',-1));values=[float(category==i) for i in range(4)]
    values += [float(typ==i) for i in range(16)]+[typ/16,float(typ<0 or typ>=16)]
    values += [float(known_pos),dx/32,dy/32,max(abs(dx),abs(dy))/32,number(entity.get('health'))/max(number(entity.get('maxHealth')),1),number(entity.get('health'))/2000,number(entity.get('maxHealth'))/2000,
               float(entity.get('alive',number(entity.get('health'))>0)),number(entity.get('attackRange'))/10,float(bool(entity.get('chebyshevRange')))]
    for slot in range(2):
        abilities=entity.get('abilities') or [];props=entity.get('abilityProps') or [];cd=entity.get('cooldowns') or [];charges=entity.get('charges') or []
        p=props[slot] if slot<len(props) else {};ability=int(abilities[slot]) if slot<len(abilities) else -1
        values += [float(slot<len(abilities)),ability/32,number(cd[slot])/10 if slot<len(cd) else 0.,number(charges[slot])/10 if slot<len(charges) else 0.]
        values += [float(p.get('type')==i) for i in range(8)]
        bits=int(p.get('target',0));values += [float(bool(bits&(1<<i))) for i in range(5)]
        values += [number(p.get(k))/10 for k in ('cooldown','maxCharges','range','radius','stunDuration')]
        values += [float(bool(p.get('enhancedAuto'))),number(p.get('attributes'))/16,number(p.get('modifier'))/16]
    buffs=entity.get('buffs') or []
    for kind in range(8):
        selected=[b for b in buffs if b.get('type')==kind]
        values += [len(selected)/8,max([number(b.get('timer')) for b in selected],default=0)/100,sum(number(b.get('magnitude')) for b in selected)/2000]
    unknown=[b for b in buffs if b.get('type') not in range(8)]
    values += [len(unknown)/8,sum(number(b.get('type')) for b in unknown)/16,max([number(b.get('timer')) for b in unknown],default=0)/100,sum(number(b.get('magnitude')) for b in unknown)/2000]
    values += [float(k in entity) for k in ('health','maxHealth','alive','buffs','abilities','abilityProps','cooldowns','charges','attackRange')]
    result=np.asarray(values,dtype=np.float16);assert np.isfinite(result).all()
    return result

def encode_entities(observation):
    own=observation['own'];assert own.get('known',0)&1
    entities=[token(own,own,True)]
    for entity in observation.get('entities',[]):
        if entity.get('known',0)&1 and entity['entity']['kind'] in (1,2):entities.append(token(entity,own))
    return np.stack(entities)

class EntityBank:
    def __init__(self,directory,split,dimension):
        self.offsets=np.load(directory/(split+'-offsets.npy'),mmap_mode='r')
        self.values=np.memmap(directory/(split+'-entities.f16'),dtype=np.float16,mode='r').reshape(-1,dimension)
        assert self.offsets[0]==0 and self.offsets[-1]==len(self.values) and (np.diff(self.offsets)>0).all()

    def batch(self,indices):
        indices=np.asarray(indices);lengths=self.offsets[indices+1]-self.offsets[indices];maximum=int(lengths.max())
        result=np.zeros((len(indices),maximum,self.values.shape[1]),np.float32);mask=np.zeros((len(indices),maximum),bool)
        for i,index in enumerate(indices):
            a,b=self.offsets[index:index+2];result[i,:b-a]=self.values[a:b];mask[i,:b-a]=True
        return torch.from_numpy(result),torch.from_numpy(mask)
