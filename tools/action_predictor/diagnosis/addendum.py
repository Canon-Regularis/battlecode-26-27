"""R00-R02 review qualifications, matched diagnostics, metadata; no fitting."""
import json
import numpy as np
from .saved import ROOT,OLD,WORK,REPORT,read,arrays,joint,metrics
from ..audit import immutable_json
from ..data import digest
from .. import reliable_train as rt

def mask_counts(raw,pred):
    n=len(raw['y']);separated={};any_movement=np.zeros(n,bool)
    for code,name in ((8,'successful_move_forecast'),(3,'blocked_attempt_forecast')):
        rows=np.flatnonzero(pred['prediction']==code);c=pred['proposed_coordinate'][rows];known=(c>=0)&(c<289);reject=np.ones(len(rows),bool);reject[known]=~raw['move_mask'][rows[known],c[known]];any_movement[rows[reject]]=True;separated[name]=dict(forecasts=len(rows),mask_rejections=int(reject.sum()))
    # Legacy total is a partial flag count, not a full legality rate. Its other
    # checks are disjoint by forecast type from the two movement branches.
    legacy=rt.invalid_rate(raw,pred);separated['other_readiness_flags']=legacy['invalid']-int(any_movement.sum());separated['legacy_total_flagged']=legacy['invalid'];separated['meaning']='Blockedmaskrejectioncanbeacorrectoutcomeforecast;neverinterpretthesumasillegalsuccessfulmoves.Fullenginelegalityunassessed.'
    return separated

def run():
    directory=WORK/'R02-capacity';indices=arrays(directory/'row-indices.npz');parts={};rawsets={};pred={};path=OLD/'v5/combined-train.npz'
    with np.load(path) as z:
        for s,idx in indices.items():rawsets[s]={k:z[k][idx] for k in z.files if k not in ('grid','x','history','valid')}
    for s in indices:pred[s]=arrays(directory/f'{s}-predictions.npz');parts[s]=mask_counts(rawsets[s],pred[s])
    # Matched common-class report supplements, never replaces, every full-set row.
    common=set(np.unique(rawsets['fit']['y']))&set(np.unique(rawsets['seen_group']['y']))&set(np.unique(rawsets['held_group']['y']));matched={}
    for s,r in rawsets.items():
        w=np.zeros(len(r['y']))
        for k in common:w[r['y']==k]=1/int((r['y']==k).sum())
        matched[s]=dict(full_rows=len(w),excluded_for_this_diagnostic=int((w==0).sum()),common_actions=[rt.LABELS[k] for k in sorted(common)],equal_action_weight_metrics=metrics(r,pred[s],w>0,w))
    # Independent family accounting for fitted failures; no unused arguments used.
    r=rawsets['fit'];j=joint(r,pred['fit']);fit_failures={name:int(((r['y']==code)&~j).sum()) for code,name in enumerate(rt.LABELS)}
    movement_rows=[json.loads(line) for line in (WORK/'R01-row-diagnostics.jsonl').open()];proxy={}
    for name,mask in [('all',lambda r:True),('change',lambda r:r['direction']==3)]:
        rs=[r for r in movement_rows if r['split']=='validation' and mask(r)];a='nearest_camp/field/yx';b='past5_goal/field/yx';both=[r for r in rs if r['forecasts'][a]['available'] and r['forecasts'][b]['available']];new=[r for r in rs if not r['forecasts'][a]['available'] and r['forecasts'][b]['available']];lost=[r for r in rs if r['forecasts'][a]['available'] and not r['forecasts'][b]['available']]
        proxy[name]=dict(rows=len(rs),shared_rows=len(both),nearest_camp_correct_shared=sum(r['forecasts'][a]['correct'] for r in both),past5_correct_shared=sum(r['forecasts'][b]['correct'] for r in both),newly_available_rows=len(new),newly_available_correct=sum(r['forecasts'][b]['correct'] for r in new),lost_availability_rows=len(lost),lost_correct=sum(r['forecasts'][a]['correct'] for r in lost),qualification='Even sharedrowgainmixesobjectivechoiceandhistory;notmatchedpersistenceintervention.Currentgoallocationsusedagainstpastmoves,nothistoricalpersistentgoalidentity.')
    jobs=read(OLD/'v7/jobs.json');metadata={}
    for split in ('train','validation'):
        selected=[j for j in jobs if j['split']==split];metadata[split]={}
        for version in ('2.0.0','3.0.0'):
            js=[j for j in selected if j['record']['engine_version']==version];metadata[split][version]=dict(games=len(js),groups=len({j['record']['group'] for j in js}),rows=sum(j['rows'] for j in js))
    recordfields=sorted(set().union(*(set(j['record']) for j in jobs)));assert not any('policy' in k.lower() or 'bot_hash' in k.lower() for k in recordfields)
    immutable_json(REPORT/'R02-review-addendum.json',dict(source_sha256=digest(__file__),review_sha256=digest(REPORT/'R02-review.md'),supersedes='R02trace.observable_invalid_commands islegacy partialflag count;use separatedforecastmask/readinesscountsbelow,notanillegalcommandrate. Originalstrictpredictionsandalltracevaluespreserved.',R02_mask_readiness_flags=parts,R02_fitted_failure_counts=fit_failures,R02_matched_common_class_diagnostic=matched,R01_proxy_availability_decomposition=proxy,engine_metadata=metadata,eligible_record_fields=recordfields,policy_version_status='EngineversionisnotFishbinary/policyversion. Eligiblejobrecords lackpolicybinaryfingerprint;engine3DEVgamesonegroup. Policyvariationandfullevidencecontradictorylabelsunresolved. ReuseD02existingcollisioncounts,notrepeatlargeunchangedaudit.',bindings={p.name:digest(p) for p in (REPORT/'R00-saved.json',REPORT/'R01-movement.json',REPORT/'R02-plan.json',REPORT/'R02-capacity.json')},new_fits=0,reserved_opened=0))
    print(json.dumps(dict(flags=parts,fit_failures=fit_failures,persistence_proxy=proxy,engine_metadata=metadata),indent=2))

if __name__=='__main__':run()
