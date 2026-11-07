"""Ward-specific PRE features. No current answer, IDs or hidden entity state."""
import numpy as np
from ..algorithmic.library import xy,dist
from ..observation_data import compact_supplement

OFFSETS=np.array([(x,y) for y in range(-2,3) for x in range(-2,3)],np.int64)
INDICES=(OFFSETS[:,1]+8)*17+OFFSETS[:,0]+8
SCALARS=('charges','recharge','alive','position','channel','ward_flag','restr_move','restr_attack','restr_cast','hp_frac','gems','ward_state_available','own_wards','ally_wards','enemy_wards','ally_controls','enemy_controls','visible_allies','visible_enemies','visible_camps','ally_within2','enemy_within2','camp_within2','ally_within6','enemy_within6','camp_within6','own_ward_dx','own_ward_dy','own_ward_radius','own_ward_permanent','ally_ward_disabled_fraction','prior_ward_available','prior_ward_age','prior_ward_dx','prior_ward_dy','prior_move_available','prior_move_dx','prior_move_dy')
EXTRA=33+len(SCALARS);GLOBAL=128+445+EXTRA;TILE=36

def build(obs,supp,route,history,personal=None):
    s=compact_supplement(supp);own=obs['own'];pos=own.get('position');p=xy(pos) if pos else None;known=personal is not None
    if known:
        assert personal['pre']==s['pre'] and personal['perspective']==obs['perspective'] and personal['availability']=='personal_api'
        assert personal['resources']==s['own']['ward']
    wards=personal['wards'] if known else [];ally=[w for w in wards if w['team']==own['team'] and w['kind']==3];enemy=[w for w in wards if w['team']!=own['team'] and w['kind']==3];ac=[w for w in wards if w['team']==own['team'] and w['kind']==4];ec=[w for w in wards if w['team']!=own['team'] and w['kind']==4];mine=[w for w in ally if w['own']]
    visible=[e for e in obs['entities'] if e.get('known',0)&1 and e.get('position') and e.get('health',0)>0];allies=[e for e in visible if e['entity']['kind']==1 and e['team']==own['team']];enemies=[e for e in visible if e['entity']['kind']==1 and e['team']!=own['team']];camps=[e for e in visible if e['entity']['kind']==2]
    one=np.zeros(33,np.float32);one[min(32,max(0,int(own['type'])))]=1
    near=lambda es,r:sum(dist(p,xy(e['position']))<=r for e in es) if p else 0
    nearest=min(mine,key=lambda e:(dist(p,xy(e['position'])),e['position']['y'],e['position']['x']),default=None) if p else None
    pastward=np.flatnonzero(history[:,14]>0);pastmove=np.flatnonzero(history[:,8]>0);hw=history[pastward[-1]] if len(pastward) else np.zeros(24);hm=history[pastmove[-1]] if len(pastmove) else np.zeros(24)
    values=[s['own'].get('ward',{}).get('charges',0)/3,s['own'].get('ward',{}).get('rechargeTimer',0)/10,own.get('alive',False),p is not None,own.get('channelType',0)/5,bool(own.get('roundFlags',0)&16),bool(s['restrictions']&1),bool(s['restrictions']&2),bool(s['restrictions']&4),own.get('health',0)/max(1,own.get('maxHealth',1)),own.get('gems',0)/100,known,len(mine)/5,len(ally)/10,len(enemy)/10,len(ac)/10,len(ec)/10,len(allies)/5,len(enemies)/5,len(camps)/20,*[near(es,r)/10 for r in (2,6) for es in (allies,enemies,camps)],(nearest['position']['x']-p[0])/32 if nearest else 0,(nearest['position']['y']-p[1])/32 if nearest else 0,nearest['radius']/10 if nearest else 0,bool(nearest and nearest['timer']<0),sum(w['disabled'] for w in ally)/max(1,len(ally)),bool(len(pastward)),hw[15],hw[16],hw[17],bool(len(pastmove)),hm[18],hm[19]]
    assert len(values)==len(SCALARS);extra=np.r_[one,np.asarray(values,np.float32)].astype(np.float32);tiles=np.zeros((25,16),np.float16);mask=np.zeros(25,bool)
    if p is None:return extra,tiles,mask
    candidates=set(map(xy,personal['candidates'])) if known else set()
    pools=(allies,enemies,camps,mine,ally,enemy,ac,ec)
    for k,delta in enumerate(OFFSETS):
        q=(p[0]+int(delta[0]),p[1]+int(delta[1]));mask[k]=q in candidates
        distances=[min((dist(q,xy(e['position'])) for e in es),default=16)/16 if (j<3 or known) else 0 for j,es in enumerate(pools)]
        counts=[sum(dist(q,xy(e['position']))<=3 for e in es)/10 for es in (allies,enemies,camps)]
        # Coverage is a geometric upper bound, not a LOS or hidden-state claim.
        coverage=[sum(not w['disabled'] and dist(q,xy(w['position']))<=w['radius'] for w in es)/10 for es in (ally,ac)]
        occupied=[any(xy(w['position'])==q for w in es) for es in (ally,enemy)]
        tiles[k]=[*distances,*counts,*coverage,*occupied,known]
    return extra,tiles,mask
