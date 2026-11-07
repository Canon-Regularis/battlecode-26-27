"""Exact A00 routing-input consistency and independent decoder count checks."""
import hashlib
from collections import Counter
import numpy as np
import torch
from .saved import ROOT,OLD,WORK,REPORT,read,arrays,joint
from .selection import loader,features,group_index,group_mass
from ..algorithmic.study import matches
from ..audit import immutable_json
from ..data import digest

def run():
    immutable_json(REPORT/'S01-plan.json',dict(source_sha256=digest(__file__),purpose='Exactinputconsistencytest forA00routing,notfullpersonalobservationcontradictiontest. Nooptimizer. Newsignature:actualclippednormalized445inputs+availablemask+commandaliaspatternseenbydecoder. Countjointlycorrectexpertroutingoptionswithoutinventedsingleintentlabels. Missing-supportrowsseparate.',scope='All288801identity-certifiednaturalTRAINrows;directindependentDEVcommandgroupcounts. Noapproximate-neighbourmetric,rerunofoldD02audit,rawreplayrecoveryorreservedrows. Near-uniquesignatureswouldnotprovesufficientinformationorlearnability.',new_fits=0))
    raw,c,base,p=loader('validation');p=p['A00'];m=matches(c,raw['y'],raw['py'],raw['priority']);B=joint(raw,base);J=joint(raw,p);w=p['selector_weights'];ties=0;veto=0;strict_top=0
    for i in np.flatnonzero(m.any(1)&~B&~J):
        groups={};correct=set()
        for j,cmd in enumerate(c[i]):
            if cmd[0]<0:continue
            key=tuple(cmd);groups[key]=groups.get(key,0.)+float(w[i,j+1])
            if m[i,j]:correct.add(key)
        winner=max(groups,key=groups.get)
        if winner in correct and w[i,0]>=groups[winner]:
            veto+=1;other=[v for k,v in groups.items() if k not in correct]
            if other and groups[winner]>max(other):strict_top+=1
            else:ties+=1
    assert veto==read(REPORT/'S00-selection.json')['stats']['validation']['A00']['all']['miss_partition']['correct_point_is_top_point_but_fallback_vetoes']
    del raw,c,base,p,m,B,J,w
    raw,c,base,p=loader('train');natural=np.load(OLD/'v9/frequency/natural-mask.npy');ix=np.flatnonzero(natural);c=np.array(c[ix]);raw={k:v[ix] for k,v in raw.items()};base={k:v[ix] for k,v in base.items()};del p
    saved=torch.load(OLD/'v10/runs/A00/round-17.pt',weights_only=False,map_location='cpu');x=features(ix);x-=saved['mean'];x/=saved['std'];np.clip(x,-10,10,out=x);ids,_=group_index(c);m=matches(c,raw['y'],raw['py'],raw['priority']);B=joint(raw,base);bits=np.bitwise_or.reduce(np.where(m,np.left_shift(np.uint64(1),ids.astype(np.uint64)),np.uint64(0)),axis=1);bits|=B.astype(np.uint64)<<np.uint64(31);available=bits!=0
    table={};initial=[]
    for i in range(len(x)):
        if not available[i]:continue
        h=hashlib.blake2b(digest_size=16);h.update(x[i].tobytes());h.update(ids[i].astype(np.uint8).tobytes());key=h.digest();mask=int(bits[i])
        if key not in table:table[key]=[mask,1,None,i];continue
        node=table[key]
        if node[2] is None:node[2]=np.array([(node[0]>>k)&1 for k in range(32)],np.int32)
        node[2]+=np.array([(mask>>k)&1 for k in range(32)],np.int32);node[0]&=mask;node[1]+=1
    repeats=[v for v in table.values() if v[1]>1];unavoidable=sum(v[1]-int(v[2].max()) for v in repeats);intersection_empty=sum(v[0]==0 for v in repeats)
    # Mathematical initialization property, not an initial-fit intervention.
    k=(c[:,:,0]>=0).sum(1);F0=1/(1+k*np.exp(-8));result=dict(source_sha256=digest(__file__),plan_sha256=digest(REPORT/'S01-plan.json'),natural_rows=len(x),available_support_rows=int(available.sum()),missing_support_rows=int((~available).sum()),unique_routing_signatures=len(table),repeated_signature_groups=len(repeats),rows_in_repeats=sum(v[1] for v in repeats),groups_with_empty_intersection_of_correct_routings=intersection_empty,additional_unavoidable_errors_from_exact_routing_input_collisions=unavoidable,interpretation='This is an upper-bound consistencydiagnosticofspecifiedroutinginputsandaliaspattern. Full evidence/intent/policycontradictionsnotestablished. Mostlyuniqueinputsneitherproveinformation sufficiency nor explainremainingrankingerrors.',independent_DEV_veto_check=dict(vetoes=veto,strictly_top_correct_point=strict_top,non_strict_ties_or_no_other_points=ties),initial_fallback_prior=dict(min=float(F0.min()),median=float(np.median(F0)),max=float(F0.max()),formula='1/(1+available_point_slots*exp(-8));biases4/-4',causality='Conservativeinitializationisdemonstrated;noablationestablishesitscausalcontribution.'),new_fits=0,reserved_opened=0)
    immutable_json(REPORT/'S01-routing-inputs.json',result);print(result,flush=True)

if __name__=='__main__':run()
