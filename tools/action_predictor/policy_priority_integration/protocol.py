"""Prospective all-decision field recovery and no-fit joint comparison."""
from pathlib import Path
from ..audit import immutable_json
from ..data import digest
from ..order_information.anchored import committed_manifest
from ..priority_broad.guard import committed_sources
from ..priority_regularized.safety import dependency_files,reject_optimized_python

ROOT=Path(__file__).resolve().parents[3]
OUT=ROOT/'tools/action_predictor/experiments/v27'
LOCAL=ROOT/'.cambc/action-predictor/v27'
ANCHOR='bcfc9949271de9baf9f1d10b815658e1e8eb423d'
JOBS_SHA='80c61417faed19ebcb8f8f59db35ba0588d7862ff68dfa3eff58f7de4aab14ba'
ROWS={'train':433071,'validation':14439}
ARMS={'JP00':'P05','JP01':'RC00','JP02':'RC01','JP03':'P03'}


def inputs():
    receipts={};bindings={}
    for name,path in (
        ('priority','tools/action_predictor/experiments/v8/priority-data-ready.json'),
        ('contexts','tools/action_predictor/experiments/v8/priority-context-ready-v3.json'),
        ('P05','tools/action_predictor/experiments/v8/P05.json'),
        ('P03','tools/action_predictor/experiments/v8/P03.json'),
        ('absolute_vocabulary','tools/action_predictor/experiments/v8/priority-absolute-modes-vocabulary.json'),
        ('residual_vocabulary','tools/action_predictor/experiments/v8/priority-residual-modes-vocabulary.json'),
        ('L02','tools/action_predictor/experiments/v16/L02.json'),
        ('policy_inputs','tools/action_predictor/experiments/v16/policy-input-bindings.json'),
        ('RC00','tools/action_predictor/experiments/v24/RC00.json'),
        ('RC01','tools/action_predictor/experiments/v24/RC01.json'),
        ('RC_protocol','tools/action_predictor/experiments/v24/RC-plan.json'),
        ('review','tools/action_predictor/experiments/v24/RC01-review.json'),
        ('review_response','tools/action_predictor/experiments/v24/RC01-review-response.json'),
        ('old_fields','tools/action_predictor/experiments/v23/order-cache-ready.json'),
        ('family_cache','tools/action_predictor/experiments/v26/family-cache-ready.json')):
        value,more=committed_manifest(ANCHOR,path);receipts[name]=value;bindings.update(more)
    jobs=ROOT/'.cambc/action-predictor/v7/jobs.json'
    if digest(jobs)!=JOBS_SHA:raise RuntimeError('Canonical eligible job table changed')
    bindings[str(jobs.relative_to(ROOT))]=JOBS_SHA
    for split,expected in receipts['priority']['files'].items():
        path=ROOT/f'.cambc/action-predictor/v8/priority-{split}.npz'
        if digest(path)!=expected:raise RuntimeError('Causal own-priority cache changed')
        bindings[str(path.relative_to(ROOT))]=expected
    for name in ('P05','P03'):
        path=ROOT/f'.cambc/action-predictor/v8/runs/{name}/model.pt'
        if digest(path)!=receipts[name]['checkpoint_sha256']:raise RuntimeError('Frozen head changed: '+name)
        bindings[str(path.relative_to(ROOT))]=digest(path)
    for name in ('RC00','RC01'):
        path=LOCAL.parent/f'v24/runs/{name}/step-2000.pt'
        key=str(path.relative_to(ROOT))
        if digest(path)!=receipts[name]['bindings'][key]:raise RuntimeError('Frozen correction changed: '+name)
        bindings[key]=digest(path)
    path=LOCAL.parent/f"v16/runs/L02/round-{receipts['L02']['selected_round']:02d}.pt"
    if digest(path)!=receipts['L02']['checkpoint_sha256']:raise RuntimeError('Frozen policy changed')
    bindings[str(path.relative_to(ROOT))]=digest(path)
    runtime,more=committed_manifest(ANCHOR,'tools/action_predictor/experiments/v7/execution-lock.json');bindings.update(more)
    runtime=dict(runtime['runtime_assets'])
    # Reader code is independently pinned by a hash-valid earlier scoped query,
    # rather than accepting its current bytes as a new reference.
    import json
    raw=sorted(receipts['old_fields']['receipts'])[0]
    directory=LOCAL.parent/'v23/games'/raw
    rp=directory/'receipt.json';qp=directory/'query.json'
    if digest(rp)!=receipts['old_fields']['receipts'][raw]:raise RuntimeError('Reader reference receipt changed')
    old=json.loads(rp.read_text())
    if digest(qp)!=old['query_sha256']:raise RuntimeError('Reader reference query changed')
    query=json.loads(qp.read_text())
    readers={name:value for name,value in query['bindings'].items() if Path(name).name in ('micro_playback.cjs','playback.cjs')}
    if len(readers)!=2:raise RuntimeError('Missing independently bound reader code')
    runtime.update(readers)
    for p in (rp,qp):bindings[str(p)]=digest(p)
    for name,expected in runtime.items():
        if digest(Path(name))!=expected:raise RuntimeError('Pinned historical runtime changed: '+name)
        bindings[name]=expected
    receipts['runtime']=runtime
    return receipts,bindings


def source_gate():
    reject_optimized_python()
    paths=dependency_files(ROOT,('tools.action_predictor.policy_priority_integration.recover',
                                'tools.action_predictor.policy_priority_integration.test_recover'))
    paths += [Path(__file__).with_name(n) for n in ('capture.cjs','test_capture.cjs')]
    paths += [ROOT/'tools/action_predictor/order_information'/n for n in ('getter.cjs','test_getter.cjs')]
    return committed_sources(ROOT,paths)


def freeze():
    commit,sources=source_gate();receipts,bindings=inputs()
    value=dict(id='JP-frozen-full-policy-priority-integration',source_commit=commit,sources=sources,inputs=bindings,
        arms=ARMS,rows=ROWS,policy='Selected L02 weights, causal upstream/filter, other conditional heads and normalized joint MAP frozen. Only the priority conditional distribution changes. P03 is an additional retained reference, not an active-capacity matched arm.',
        data='Required personally scoped current/scheduled other-champion priorities on EVERY original TRAIN/DEV decision, exactint64, roles, paired availability. Reuse approved6132TRAINgetter records by exactPRE identity; all remaining eligible roots recovered read-only. No recorded-family routing or row dropping.',
        semantics='Pinned historical engine2/3 and scoped GetPriority ABI; unknown getter97 remains unavailable, no hidden-state feature. Current own API values/masks must match immutable V8 controls. Header actor/round/phase checked on every new query. Snapshot/getter equality checked when available; bounded deep nonmutation checks first/middle/lastnewroot pergame reuse established ABI evidence.',
        recovery='At most4workers. Existing recorded MAIN timeline restoration only, no actions/matches/downloads/bot changes. Save raw query results before validation, preserve failed/partial jobs, reuse only hash-valid completed receipts. Do not rerun the unchanged495game priority-chain audit.',
        inference='Forecast all arms and save predictions before current answers. Same15family joint MAP; no type-first veto, no softmax over mode scores. Match JP00 to retainedL02 before scoring treatment. Exactint64own/history anchors and every-family forecasts; no arbitrary destination/command enumeration.',
        metrics='All original rows; augmented and natural-membership TRAIN separately, originalDEV whole5groups. Strict complete commands, per-category joint/typePRF/confusion/typeFPvsjointFP, alltrue-family and correctlytyped arguments, priorityrare/unseen/errors, movementcontinue/change/blocked, fallbackmass/credits, observedjointNLL, partiallegality with blocked attempts separate. Shop arguments absent from likelihood and all43strict failures; sparsecategories uncertified.',
        comparisons='Primary JP02vsJP00 andJP02vsJP01; retainedP03 JP03 reference plus G00/B00/L02. 2000pairedwhole-group resamples seed20261106 using all originalgroups, emptydenominators null. Distinguish parameter corrections, type changes caused by joint competition and semantic commands using required arguments only.',
        limits='Frozen baseline augmented traversal cadence, not new persistent-goal learning or closed-loop execution. New fields do not certify observationsufficient or Fishintent. Originalper-category90%,macro.65,movement.6520745131244708,10%lowerrelevantjointNLL,targetingregressionmax.02 and3seed requirements unchanged/unmet. No model selection/calibration/threshold/checkpoint refit or automaticpromotion.',
        decisions='If conditionalgains do not reachcompletecommands, diagnose typebelief/falsepositives and distribution competition before any new fit. If they transfer, retain useful component but address certified representation limits next. Any null-parity/correctness failure stops assessment and preserves outputs; no criterion relaxation.',
        review='Fresh Solxhigh review after completed substantive comparison, exact requestedquestion. No new training fits in this experiment.',
        new_fits=0,optimizer_updates=0,reserved_opened=0)
    path=OUT/'JP-plan.json'
    if path.exists():
        import json
        old=json.loads(path.read_text())
        if {k:v for k,v in old.items() if k!='source_commit'}!={k:v for k,v in value.items() if k!='source_commit'}:
            raise RuntimeError('Frozen integration plan changed; preserve/version rather than overwrite')
        return old,receipts,bindings
    immutable_json(path,value)
    return value,receipts,bindings
