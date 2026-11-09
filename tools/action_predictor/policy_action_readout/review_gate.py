"""Fresh completed control-review provenance, not a certification of review depth."""
from datetime import datetime
import subprocess
from ..data import digest
from ..order_information.anchored import committed_manifest
from .protocol import ROOT,OUT,LOCAL

QUESTION='Read my thread and find all the errors my model has now made and how we could improve all of it substantially'
PARENT='mcp:launch:c4185c930eca174d8d1afc1306852295d17ffddccc8ef520a6713bb41d411891'


def validate(review,delegation,scope,response,expected,hashes,committed_at):
    def require(value,why):
        if not value:raise RuntimeError('AB00_REVIEW_CONTRACT: '+why)
    thread=review['thread'];runs=review['recentRuns'];items=review['items']
    require(thread['status']=='completed' and thread['model']=='gpt-6.1-sol' and thread['providerInstanceId']=='codex','model/completion')
    require(thread['relationshipToParent']=='subagent' and thread['runCount']==1,'fresh child')
    require(thread['parentThreadId']==expected['parent_thread_id'] and thread['threadId']==expected['child_thread_id'],'parent/child identity')
    require(thread['activeRunId'] is None,'active run contradicts completed review')
    require(len(runs)==1 and runs[0]['status']=='completed' and runs[0]['runId']==thread['latestRunId'] and runs[0]['model']=='gpt-6.1-sol' and runs[0]['providerInstanceId']=='codex','terminal run')
    require(delegation['status']=='completed' and delegation['childThreadId']==thread['threadId'] and delegation['latestTerminalRunId']==thread['latestRunId'],'delegation identity')
    require(delegation.get('latestTerminalStatus')=='completed' and delegation.get('hasPendingChildRuns') is False and delegation.get('hasPendingQuestion') is False and delegation.get('pendingApproval') is None,'delegation still active/pending')
    require(delegation['model']=='gpt-6.1-sol' and delegation['providerInstanceId']=='codex' and dict((x['id'],x['value']) for x in delegation['options']).get('reasoningEffort')=='xhigh','requested effort')
    requests=[i['text'] for i in items if i['type']=='user_message' and i.get('text')]
    finals=[i['text'] for i in items if i['type']=='assistant_message' and i['status']=='completed' and i['runId']==thread['latestRunId'] and i.get('text')]
    require(bool(requests) and bool(finals),'empty review')
    require(all(i.get('sourceThreadId')==thread['threadId'] and i.get('runId')==thread['latestRunId'] for i in items),'message source/run identity')
    request_items=[i for i in items if i['type']=='user_message' and i.get('text')]
    final_items=[i for i in items if i['type']=='assistant_message' and i.get('text')]
    require(request_items[0].get('senderThreadId')==thread['parentThreadId'] and request_items[0].get('createdBy')=='agent' and request_items[0].get('creationSource')=='mcp','request author/source')
    require(request_items[0].get('status')=='completed' and final_items[-1].get('status')=='completed','message completion')
    require(final_items[-1].get('createdBy')=='agent' and final_items[-1].get('creationSource')=='provider' and final_items[-1].get('senderThreadId') in (None,thread['threadId']),'reviewer author/source')
    require(QUESTION in requests[0] and len(finals[-1])>500 and 'AB00' in finals[-1],'substantive control review')
    for key in ('checkpoint_sha256','protocol_sha256','reviewed_sources','reviewed_completion_sha256','reviewed_report_sha256',
        'parent_thread_id','child_thread_id','reviewed_supplemental_evidence'):
        require(scope.get(key)==expected[key],'scope '+key)
    require(expected['checkpoint_sha256'] in requests[0] and 'AB-plan.json' in requests[0],'original request checkpoint/protocol')
    require(scope['reviewed_commit'] in requests[0] and scope['reviewed_commit'] in finals[-1],'reviewed commit')
    require(datetime.fromisoformat(thread['createdAt'].replace('Z','+00:00'))>datetime.fromisoformat(committed_at),'stale review')
    for key in ('review_sha256','delegation_sha256','review_scope_sha256'):
        require(response.get(key)==hashes[key],'response '+key)
    require(scope.get('raw_review_sha256')==hashes['review_sha256'] and scope.get('delegation_sha256')==hashes['delegation_sha256'],'scope record identity')
    require(scope.get('launch_sha256')==hashes['launch_sha256'],'actual launch identity')
    require(response.get('reviewed_checkpoint_sha256')==expected['checkpoint_sha256'] and response.get('correctness_findings_addressed') is True,'response checkpoint/findings')
    return True


def load_review_context():
    commit=subprocess.run(['git','rev-parse','HEAD'],cwd=ROOT,check=True,capture_output=True,text=True).stdout.strip()
    records={}
    for key,name in (('review','AB00-review.json'),('delegation','AB00-review-delegation.json'),('launch','AB00-review-delegation-launch.json'),('scope','AB00-review-scope.json'),
        ('response','AB00-review-response.json'),('report','AB00.json'),('completion','AB00-completion.json')):
        records[key],_=committed_manifest(commit,'tools/action_predictor/experiments/v28/'+name)
    checkpoint=digest(LOCAL/'runs/AB00/model.pt')
    expected=dict(checkpoint_sha256=checkpoint,protocol_sha256=digest(OUT/'AB-plan.json'),reviewed_sources=records['report']['sources'],
        reviewed_completion_sha256=digest(OUT/'AB00-completion.json'),reviewed_report_sha256=digest(OUT/'AB00.json'),
        parent_thread_id=PARENT,child_thread_id=records['launch']['childThreadId'],
        reviewed_supplemental_evidence={name:digest(OUT/name) for name in ('AB00-REPORT.md','AB00-fitting-diagnosis.json','AB00-completion-supplement.json')})
    if checkpoint!=records['completion']['checkpoint_sha256']:raise RuntimeError('Control checkpoint changed')
    hashes={key:digest(OUT/name) for key,name in (('review_sha256','AB00-review.json'),('delegation_sha256','AB00-review-delegation.json'),('review_scope_sha256','AB00-review-scope.json'),('launch_sha256','AB00-review-delegation-launch.json'))}
    reviewed=records['scope']['reviewed_commit']
    for name in ('AB-plan.json','AB-data-ready.json','AB00.json','AB00-completion.json','AB00-REPORT.md','AB00-fitting-diagnosis.json','AB00-completion-supplement.json'):
        verify_reviewed_artifact(reviewed,name)
    committed_at=subprocess.run(['git','show','-s','--format=%cI',reviewed],cwd=ROOT,check=True,capture_output=True,text=True).stdout.strip()
    return records,expected,hashes,committed_at


def verify_reviewed_artifact(commit,name):
    # Supplemental scope includes Markdown, not only JSON manifests.
    relative='tools/action_predictor/experiments/v28/'+name
    blob=subprocess.run(['git','show',commit+':'+relative],cwd=ROOT,check=True,capture_output=True).stdout
    if (OUT/name).read_bytes()!=blob:raise RuntimeError('Reviewed artifact differs from scientific commit: '+name)
    return True


def verify_control_predictions(completion):
    for split in ('train','validation'):
        path=LOCAL/'runs/AB00'/f'{split}-predictions.npz';key=str(path.relative_to(ROOT))
        if digest(path)!=completion['bindings'][key]:raise RuntimeError('CONTROL_PREDICTIONS_CHANGED_BEFORE_OPTIMIZER: '+split)


def require_control_review():
    records,expected,hashes,committed_at=load_review_context()
    validate(records['review'],records['delegation'],records['scope'],records['response'],expected,hashes,committed_at)
    verify_control_predictions(records['completion'])
    return records['completion']
