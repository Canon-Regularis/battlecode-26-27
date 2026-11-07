"""U00: trace unsupported DEV commands and the exact natural-TRAIN rescue set."""
import json
from collections import Counter
from pathlib import Path
import numpy as np
from .saved import ROOT,OLD,WORK,REPORT,read,arrays,joint
from .selection import group_index,group_mass
from ..algorithmic.study import matches
from ..rich_data import read_turns
from ..audit import immutable_json,validate_decision
from ..data import digest,action_name
from ..targets import OFFSETS
from .. import reliable_train as rt

def basic(split):
    path=OLD/('v5/combined-train.npz' if split=='train' else 'v4/validation.npz');raw=arrays(path,['y','py','priority','group','pos_known','move_mask','flags','ability_mask','ward_charges']);c=np.load(OLD/f'v10/{split}-candidates.npy',mmap_mode='r');base=arrays(OLD/f'v9/runs/G00/{split}-predictions.npz');p=arrays(OLD/f'v10/runs/A00/{split}-predictions.npz');return raw,c,base,p

def conditional_parameter(raw,base):
    # This is an explicitly oracle-conditioned metric of the retained G00 heads,
    # not an A00 command, inference input or current-answer router.
    result=np.ones(len(raw['y']),bool);sp=raw['py']>=0;result[sp]=(raw['py'][sp]<289)&(base['coordinate'][sp]==raw['py'][sp]);pr=raw['y']==9;result[pr]=base['priority'][pr]==raw['priority'][pr];result[raw['y']==11]=False
    return result

def target_exclusion(d,slot):
    obs=d['observation'];own=obs['own'];pos=own.get('position');target=d['label']['to']
    if pos is None:return 'missing_position_global_abstention'
    props={} if slot<0 else (own.get('abilityProps') or [{},{}])[slot];mask=3 if slot<0 else props.get('target',0);radius=own.get('attackRange',0) if slot<0 else props.get('range',0);eligible=[];same=[]
    for e in [own,*obs['entities']]:
        if e is not own and not (e.get('known',0)&1 and e.get('position') and e.get('health',0)>0):continue
        q=e.get('position')
        if q!=target:continue
        bit=1 if e['entity']['kind']==2 else 8 if e['entity']==own['entity'] else 4 if e['team']==own['team'] else 2
        if bit&mask:
            same.append(e)
            if max(abs(q['x']-pos['x']),abs(q['y']-pos['y']))<=radius:eligible.append(e)
    if mask==16:return 'ground_only_target_mode_not_implemented'
    if eligible:return 'eligible_target_not_chosen_by_near_hp_fraction_ranks'
    if same:return 'target_excluded_by_declared_range_filter'
    if mask&16:return 'ground_capable_target_not_in_compatible_unit_proposals'
    return 'no_compatible_living_personally_visible_entity_at_recorded_target'

def run():
    immutable_json(REPORT/'U00-plan.json',dict(source_sha256=digest(__file__),purpose='Explain exact1301A00hard-supportDEVmisses and13.2%naturalTRAINrescuecapture. No fit,newlibrary,promoteddecoder orreservedaccess.',part1='UsefrozenC00bothlibraries,G00hardforecastanddiagnosticonlytrue-familyG00argumentheads. ScorealloriginalDEV;readPREonlyfor1301selectedmissingrowsfrom25eligiblegames.Nooriginalshopargumentsaccessed/inferred. ExistingR01relationshipsetsreused.',part2='UseexactnaturalTRAINrescuepopulation Lcorrect/G00wrong;separatecorrectpoint-topfallbackveto,wrongfamilyrankingandwrongwithin-familyparameters. ForcedpointdecodingisnewNOFIT diagnosticnotpromotion. Compareallaugmented/natural/augmentation-onlyexposureandanalyticlossbiasgradients.',limits='Primitivegeneratorrestrictionsaremechanisms,notFishintentlabels. ConditionalheadsuccessdoesnotmakethecommandavailabletoA00. Exposure/gradientsalonecannotprovewhylearningstalls. KeepalloldresultsandoriginalDEVdenominators. No newoptimizersteps.'))
    raw,allc,base,p=basic('validation');c=allc[:,1];M=matches(c,raw['y'],raw['py'],raw['priority']);L=M.any(1);B=joint(raw,base);missing=~L&~B;assert missing.sum()==1301 and not joint(raw,p)[missing].any();param=conditional_parameter(raw,base);typed=base['prediction']==raw['y'];family_emitted=(c[:,:,0]==raw['y'][:,None]).any(1)
    rowinfo={int(i):dict(index=int(i),action=rt.LABELS[raw['y'][i]],G00_type_correct=bool(typed[i]),oracle_G00_conditional_parameter_correct=bool(param[i]),point_true_family_present=bool(family_emitted[i])) for i in np.flatnonzero(missing)}
    per={}
    for code,name in enumerate(rt.LABELS):
        m=missing&(raw['y']==code)
        if not m.any():continue
        per[name]=dict(rows=int(m.sum()),no_true_family_in_point_or_G00_forecast=int((m&~family_emitted&~typed).sum()),true_family_emitted_but_wrong_parameter=int((m&(family_emitted|typed)).sum()),oracle_conditional_parameter_correct_but_wrong_G00_type=int((m&param&~typed).sum()),G00_type_correct_but_parameter_wrong=int((m&typed&~param).sum()),G00_type_and_parameter_both_wrong=int((m&~typed&~param).sum()))
    movement={r['index']:r for r in (json.loads(line) for line in (WORK/'R01-row-diagnostics.jsonl').open()) if r['split']=='validation'};jobs=[j for j in read(OLD/'v7/jobs.json') if j['split']=='validation'];mechanisms=Counter();details={};bindings=[]
    for job in jobs:
        selected=set(rowinfo)&set(range(job['offset'],job['offset']+job['rows']))
        if not selected:continue
        local=0
        for t in read_turns(job['manifest'],job['record']):
            for d in t['decisions']:
                idx=job['offset']+local;local+=1
                if idx not in selected:continue
                validate_decision(d,t);name=action_name(d['label']);assert name==rowinfo[idx]['action'];info=rowinfo[idx];pos=d['observation']['own'].get('position');reason=''
                if name=='priority':reason='priority_proposal_only_zero' if pos else 'missing_position_global_abstention';info['recorded_value_zero']=bool(raw['priority'][idx]==0)
                elif name=='move':reason=movement[idx]['relationship'];info['G00_true_family_argument_correct']=bool(param[idx])
                elif name=='blocked':reason='no_blocked_outcome_generator';info['empty_movement_mask']=bool(not raw['move_mask'][idx].any());info['move_flag_unavailable']=bool((raw['flags'][idx]&1)==0)
                elif name=='ward':
                    r=int(np.abs(OFFSETS[raw['py'][idx]]).max()) if 0<=raw['py'][idx]<289 else None;info['target_chebyshev_offset']=r;info['ward_charges']=int(raw['ward_charges'][idx]);reason='ward_range2_absent_from_self_or_bank_step1' if r==2 else 'ward_direction_not_self_or_one_step_toward_bank'
                elif name in ('attack','cast_0','cast_1'):
                    reason=target_exclusion(d,-1 if name=='attack' else int(name[-1]));info['target_mask']=3 if name=='attack' else int(raw['ability_mask'][idx,int(name[-1])])
                elif name=='shop':reason='original_item_count_arguments_unavailable_strict_failure'
                elif name in ('altar','teleport'):reason='action_family_has_no_point_generator'
                else:raise AssertionError(name)
                info['primitive_reason']=reason;mechanisms[name+'/'+reason]+=1
        assert local==job['rows'];bindings.append(dict(raw=job['record']['raw_sha256'],source=job['record'].get('augmented_sha256',job['record']['turns_sha256'])))
    field=matches(allc[:,0],raw['y'],raw['py'],raw['priority']).any(1);alternatives={'C00_terrain_library':int((missing&field).sum())}
    for name,version in [('M01','v5'),('P05','v8'),('G01','v9')]:alternatives[name]=int((missing&joint(raw,arrays(OLD/f'{version}/runs/{name}/validation-predictions.npz'))).sum())
    kinds={name:dict(Counter(v['primitive_reason'] for v in rowinfo.values() if v['action']==name)) for name in per};blocked=[r for r in rowinfo.values() if r['action']=='blocked'];wards=[r for r in rowinfo.values() if r['action']=='ward'];casts=[r for r in rowinfo.values() if r['action']=='cast_1']
    dev=dict(rows=14439,missing=1301,per_family=per,primitive_reasons=kinds,blocked_context=dict(rows=len(blocked),empty_mask=sum(r['empty_movement_mask'] for r in blocked),move_flag_unavailable=sum(r['move_flag_unavailable'] for r in blocked)),ward_context=dict(rows=len(wards),offset_distribution=dict(Counter(r['target_chebyshev_offset'] for r in wards)),charges_distribution=dict(Counter(r['ward_charges'] for r in wards))),cast1_masks=dict(Counter(r['target_mask'] for r in casts)),other_existing_predictions_correct_on_missing=alternatives,conditional_argument_overlay_total=int((missing&param&~typed).sum()),limits='Otherpreviouspredictions/conditionalheadvaluesareORACLEdiagnostics,notavailableA00commands.No neworacleinferenceor expandedlibraryaccuracyclaim.')
    # Natural TRAIN rescue opportunities, rather than the broader available-error set.
    trainraw,tc,base,p=basic('train');c=tc[:,1];natural=np.load(OLD/'v9/frequency/natural-mask.npy');M=matches(c,trainraw['y'],trainraw['py'],trainraw['priority']);L=M.any(1);B=joint(trainraw,base);J=joint(trainraw,p);w=p['selector_weights'];ids,reps=group_index(c);G=group_mass(w,ids);row=np.arange(len(c));best=G.argmax(1);pointcorrect=M[row,reps[row,best]];F=w[:,0];family_by_group=c[row[:,None],reps,0];familymass=np.where(family_by_group==trainraw['y'][:,None],G,-1);within=familymass.argmax(1);within_correct=M[row,reps[row,within]];R=natural&L&~B;miss=R&~J
    partition=dict(rescued=int((R&J).sum()),correct_point_top_but_fallback_veto=int((miss&pointcorrect).sum()),wrong_global_point_rank_but_correct_within_true_family=int((miss&~pointcorrect&within_correct).sum()),wrong_within_true_family_parameter_rank=int((miss&~pointcorrect&~within_correct).sum()));assert sum(partition.values())==int(R.sum())==28903
    original_parts=dict(correct_top_fallback=int((miss&pointcorrect).sum()),wrong_top_fallback=int((miss&~pointcorrect&(F>=G.max(1))).sum()),wrong_top_point_selected=int((miss&~pointcorrect&(F<G.max(1))).sum()))
    # No-fit forced-point control diagnoses why simply turning off fallback fails.
    anypoint=(c[:,:,0]>=0).any(1);forced=np.where(anypoint,pointcorrect,B);force=dict(rows=int(natural.sum()),correct=int((forced&natural).sum()),accuracy=float(forced[natural].mean()),fixes_A00_errors=int((natural&forced&~J).sum()),regresses_A00_correct=int((natural&~forced&J).sum()),rescuable_errors_fixed=int((R&forced).sum()),not_promoted=True)
    q=np.exp(-base['nll'].astype(float));P=(w[:,1:]*M).sum(1);mixture=P+F*q;grad=F-np.divide(F*q,mixture,out=np.zeros_like(P),where=mixture>0);exposure={}
    for name,mask in [('all_augmented_TRAIN',np.ones(len(L),bool)),('natural',natural),('augmentation_only',~natural)]:
        populations={'both_G00_and_point_correct':mask&B&L,'rescuable_G00_error':mask&~B&L,'only_G00_hard_command_correct':mask&B&~L,'neither_hard_option_correct':mask&~B&~L};exposure[name]={}
        for stratum,m in populations.items():exposure[name][stratum]=dict(rows=int(m.sum()),fraction=float(m.sum()/mask.sum()),mean_fallback_logit_derivative=float(grad[m].mean()) if m.any() else None,contribution_to_overall_fallback_bias_derivative=float(grad[m].sum()/len(L)))
    byfamily={}
    for code,name in enumerate(rt.LABELS):
        m=R&(trainraw['y']==code)
        if m.any():byfamily[name]=dict(opportunities=int(m.sum()),rescued=int((m&J).sum()),correct_global_point_rank=int((m&pointcorrect).sum()),correct_point_vetoed=int((m&~J&pointcorrect).sum()),wrong_global_type_rank_but_correct_within_family=int((m&~J&~pointcorrect&within_correct).sum()),wrong_within_family_parameter_rank=int((m&~J&~pointcorrect&~within_correct).sum()))
    train=dict(opportunities=int(R.sum()),partition=partition,original_router_partition=original_parts,per_family=byfamily,forced_point_decoder=force,optimizer_exposure=exposure,interpretation='Analyticgradientnegative=>descentincreasesfallbacklogit;positive=>decreasesit. UncoveredrowsmustuseG00distributionfornonzero likelihood,evenwhenitshardforecastiswrong. This is structuralpressure,notproofsampling/optimizercausedrankingfailure. Known-familydiagnosticusesrecordedfamilyonlytoaudit,notforecast.')
    witnesses=WORK/'U00-missing-witnesses.jsonl';assert not witnesses.exists();witnesses.write_text(''.join(json.dumps(rowinfo[i])+'\n' for i in sorted(rowinfo)),encoding='utf-8')
    immutable_json(REPORT/'U00-support-rescue.json',dict(plan_sha256=digest(REPORT/'U00-plan.json'),source_sha256=digest(__file__),DEV=dev,natural_TRAIN=train,PRE_sources=bindings,witnesses_sha256=digest(witnesses),old_S00_receipt_sha256=digest(REPORT/'S00-completion.json'),new_fits=0,reserved_opened=0,original_checkpoints_unchanged=True))
    print(json.dumps(dict(DEV=dev,TRAIN=train),indent=2),flush=True)

if __name__=='__main__':run()
