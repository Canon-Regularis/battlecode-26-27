"""Prospective matched action-belief input experiment, no global research cap."""
import json
import numpy as np
from pathlib import Path
from ..audit import immutable_json
from ..data import digest
from ..order_information.anchored import committed_manifest
from ..priority_broad.guard import committed_sources
from ..priority_regularized.safety import dependency_files,reject_optimized_python

ROOT=Path(__file__).resolve().parents[3]
OUT=ROOT/'tools/action_predictor/experiments/v28'
LOCAL=ROOT/'.cambc/action-predictor/v28'
ANCHOR='12e62bd'
SCIENTIFIC='1caf7ff5f38e62e28c8bfbf6cc6521230f6d4eeb'
GROUP_SEED=20261128
SWAP_SEED=20261190
SEED=20261129
ARMS={'AB00':'shuffled_training_inputs','AB01':'real_training_inputs'}
ROWS={'train':433071,'validation':14439}
FEATURES=tuple(['normalized_own_priority_'+str(i) for i in range(39)]+['pair_unavailable','current_scheduled_differ'])


def source_gate():
    reject_optimized_python()
    result=committed_sources(ROOT,dependency_files(ROOT,('tools.action_predictor.policy_action_readout.data',
        'tools.action_predictor.policy_action_readout.fit','tools.action_predictor.policy_action_readout.test_model',
        'tools.action_predictor.policy_action_readout.test_data','tools.action_predictor.policy_action_readout.test_review')))
    from .matched_guard import verify_scientific_contract
    verify_scientific_contract(result[1])
    return result


def inputs():
    completion,bindings=committed_manifest(SCIENTIFIC,'tools/action_predictor/experiments/v27/JP-completion.json')
    allowed={k.replace('\\','/'):v for k,v in completion['bindings'].items()}
    family,more=committed_manifest(SCIENTIFIC,'tools/action_predictor/experiments/v26/family-cache-ready.json');bindings.update(more)
    for split in ROWS:
        allowed.update({k.replace('\\','/'):v for k,v in family['results'][split]['files'].items()})
    for name in ('JP-review.json','JP-review-delegation.json','JP-review-delegation-launch.json','JP-review-request.json','JP-review-response.json'):
        _,more=committed_manifest(ANCHOR,'tools/action_predictor/experiments/v27/'+name);bindings.update(more)
    def bind(relative):
        relative=str(relative).replace('\\','/')
        if relative not in allowed:raise RuntimeError('Unbound retained input: '+relative)
        path=ROOT/relative
        if digest(path)!=allowed[relative]:raise RuntimeError('Retained input changed: '+relative)
        bindings[relative]=allowed[relative]
        return path
    return bind,bindings


def fold(groups,natural):
    unique=np.unique(groups)
    if len(unique)!=94 or len(groups)!=433071 or int(natural.sum())!=288801:raise RuntimeError('Original TRAIN population changed')
    held=np.sort(np.random.default_rng(GROUP_SEED).permutation(unique)[:15])
    return natural&~np.isin(groups,held),natural&np.isin(groups,held),held


def freeze():
    commit,sources=source_gate();bind,bindings=inputs()
    path=bind('.cambc/action-predictor/v5/combined-train.npz')
    with np.load(path) as z:groups=z['group']
    natural=np.load(bind('.cambc/action-predictor/v9/frequency/natural-mask.npy'))
    fit,held,held_groups=fold(groups,natural)
    value=dict(id='AB-marginal-action-belief-priority-input',source_commit=commit,sources=sources,inputs=bindings,
        hypothesis='Direct causal own-priority/history inputs may improve action-family beliefs when fixed current beliefs impose a344/576priority ceiling. Their incremental usefulness is unestablished. No hand strategy or intent label.',
        arms=ARMS,feature_schema=list(FEATURES),
        feature_definition='Existing39P05-normalized PREown/history fields plus two softderivedindicators from the earlier unrunV8C01/C02design: pairunavailable and bothavailable-and-current!=scheduled. Exactint64comparison; no hard action mask. This tests the combined representation package, not the incremental value of any single scalar.',
        architecture='Zero-initialized bias-free Linear(active_features,15), float64, added to frozenL02marginalfamilylogprobabilities then normalized. Common TRAIN-only nonzero-column mask, identical active parameterization. Conditional distributions from JP02 remain frozen, including RC01integers and all spatial families. No latent-component reweighting or upstream/filter/representation update.',
        control='AB00usesonefixed TRAIN-only derangement of the entire input block within group,engine,andowncurrent/scheduled/latest/history16availabilitysignature. Only natural correction-fit rows can donate. AB01usesrealinputs. Both primary inference paths use realcausalinputs. Control retains group/context/marginal correlations and may retain identicalfeaturevectors; it is not information-free. Report raw/featurecorruption and singleton counts.',
        population=dict(original_train=433071,natural_train=288801,dev=14439,train_groups=94,fit_groups=79,
            excluded_groups=held_groups.tolist(),fit_rows=int(fit.sum()),natural_excluded_rows=int(held.sum()),group_seed=GROUP_SEED),
        exposure='Group exclusion applies only to new action-correction optimization. Warm L02/P05/RC01encoders,heads,normalizersandearlierresearchsaw eligibleTRAIN. No untouched-policy claim. Every originalTRAIN/DEVrow remains in assessment; augmented rows are not optimization duplicates or a changed benchmark.',
        sampling='One shuffled pass of natural correction-fit rows per round; both arms same order/seed/budget. No class weighting, negative subsampling, focal loss or current-answer routing.',
        optimization=dict(seed=SEED,swap_seed=SWAP_SEED,batch=256,lr=.001,weight_decay=0.,gradient_clip=5.,
            displacement_penalty=.0001,max_rounds=35,patience=6,min_improvement=.0001),
        loss='Mean normalized observed complete-command NLL plus .0001sum(correctionweights^2). Fixed conditional target logmass contributes to reported loss but no parameter gradients. Missing shop argument likelihood remains absent. All fifteen family probabilities compete; final MAP uses those same probabilities and every fixed conditional mode, never softmax-over-modes/type-first routing.',
        checkpoint='Original unweighted observed joint NLL on all14439DEVrows; improvement.0001,patience6,max35rounds. Epochzero reported notselectable. Preserve every round/rawreadout/failure, no retrospective selection on exactness,thresholdsorheldTRAIN.',
        numerical='Float64 family normalization; prospective2e-5 initial probability/NLL tolerance and zero semantic-command mismatches against JP02 on all original rows. Full corrected family sum error<=1e-12. Frozen spatial conditional arithmetic retains historical tighter failednormalization qualification; no repair claimed.',
        metrics='Complete-command overall/percategory, typePRF/confusion/FPvsjointFP, alltrue-family and typed parameters, category observedNLL, priority conditional/joint/errors andFP, movementcontinue/change/blocked, attack/casttargetguards, naturalfit/excluded/otherTRAINandaugTRAIN, fiveoriginalDEVgroups, paired2000whole-groupresamplesseed20261106includingzerosupportgroups/nulls.',
        allocation='Matchedpair AB00thenAB01, one separately invokedfit each and freshSolxhighreviewaftereach. AB01requires completed freshAB00review and addressed correctness findings; control underperformance alone does not cancel the registered contrast. This is a local experiment allocation, not a limit or stop on autonomous research.',
        exploratory_continuation=dict(net_complete_gain_vs_JP02_minimum=37,net_complete_gain_vs_control_minimum=20,
            priority_joint_gain_vs_JP02_minimum=20,priority_type_FP_increase_vs_JP02_maximum=10,
            mean_NLL_below_both=True,macro_F1_decline_vs_JP02_maximum=.005,
            move_recall_joint_decline_maximum=.005,attack_cast_joint_decline_maximum=.02,
            meaning='All conditions for a promising component signal; distinct from unchanged original success targets. No automatic seedrepeat,promotionorarchitectureexpansion. Failure informs the next distinct hypothesis.'),
        limits='Frozen argument modes still cap priority248/576,ward27/112,blocked22/110,move1428/2362 andcast1 144/243; actionlearningalonecannot certify90%orreachthe1541movementpointtarget. Originalpercategory90%,macro.65,move.6520745131244708,10%lowerstrongestrelevantjointNLL,originaltargetingguardsandthree-seedconsistencyremainbinding/unmet. Same frozen augmented-cadence baseline filter, not natural-cadence or closed-loop policy.',
        safeguards='No reserved partitions, matches, downloads, bot/runtime changes, deployment, PRready/merge/queue. Preserve43DEVshopstrictfailures, sparseuncertainty and entityidentity ambiguity. No new enginequery or extraction.',new_fits_allocated=2,reserved_opened=0)
    path=OUT/'AB-plan.json'
    if path.exists():
        old=json.loads(path.read_text())
        if {k:v for k,v in old.items() if k!='source_commit'}!={k:v for k,v in value.items() if k!='source_commit'}:
            raise RuntimeError('Frozen AB protocol changed; version rather than overwrite')
        return old
    immutable_json(path,value);return value
