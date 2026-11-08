"""Fresh completed control-review provenance, not a certification of review depth."""
from datetime import datetime
import subprocess
from ..data import digest
from ..order_information.anchored import committed_manifest
from .protocol import ROOT,OUT,LOCAL

QUESTION='Read my thread and find all the errors my model has now made and how we could improve all of it substantially'


def validate(review,delegation,scope,response,expected,hashes,committed_at):
    def require(value,why):
        if not value:raise RuntimeError('AB00_REVIEW_CONTRACT: '+why)
    thread=review['thread'];runs=review['recentRuns'];items=review['items']
    require(thread['status']=='completed' and thread['model']=='gpt-6.1-sol' and thread['providerInstanceId']=='codex','model/completion')
    require(thread['relationshipToParent']=='subagent' and thread['runCount']==1,'fresh child')
    require(len(runs)==1 and runs[0]['status']=='completed' and runs[0]['runId']==thread['latestRunId'] and runs[0]['model']=='gpt-6.1-sol','terminal run')
    require(delegation['status']=='completed' and delegation['childThreadId']==thread['threadId'] and delegation['latestTerminalRunId']==thread['latestRunId'],'delegation identity')
    require(delegation['model']=='gpt-6.1-sol' and delegation['providerInstanceId']=='codex' and dict((x['id'],x['value']) for x in delegation['options']).get('reasoningEffort')=='xhigh','requested effort')
    requests=[i['text'] for i in items if i['type']=='user_message' and i.get('text')]
    finals=[i['text'] for i in items if i['type']=='assistant_message' and i['status']=='completed' and i['runId']==thread['latestRunId'] and i.get('text')]
    require(bool(requests) and bool(finals),'empty review')
    require(QUESTION in requests[0] and len(finals[-1])>500 and 'AB00' in finals[-1],'substantive control review')
    for key in ('checkpoint_sha256','protocol_sha256','reviewed_sources','reviewed_completion_sha256','reviewed_report_sha256'):
        require(scope.get(key)==expected[key],'scope '+key)
    require(expected['checkpoint_sha256'] in requests[0] and 'AB-plan.json' in requests[0],'original request checkpoint/protocol')
    require(scope['reviewed_commit'] in requests[0] and scope['reviewed_commit'] in finals[-1],'reviewed commit')
    require(datetime.fromisoformat(thread['createdAt'].replace('Z','+00:00'))>datetime.fromisoformat(committed_at),'stale review')
    for key in ('review_sha256','delegation_sha256','review_scope_sha256'):
        require(response.get(key)==hashes[key],'response '+key)
    require(scope.get('raw_review_sha256')==hashes['review_sha256'] and scope.get('delegation_sha256')==hashes['delegation_sha256'],'scope record identity')
    require(response.get('reviewed_checkpoint_sha256')==expected['checkpoint_sha256'] and response.get('correctness_findings_addressed') is True,'response checkpoint/findings')
    return True


def require_control_review():
    commit=subprocess.run(['git','rev-parse','HEAD'],cwd=ROOT,check=True,capture_output=True,text=True).stdout.strip()
    records={}
    for key,name in (('review','AB00-review.json'),('delegation','AB00-review-delegation.json'),('scope','AB00-review-scope.json'),
        ('response','AB00-review-response.json'),('report','AB00.json'),('completion','AB00-completion.json')):
        records[key],_=committed_manifest(commit,'tools/action_predictor/experiments/v28/'+name)
    checkpoint=digest(LOCAL/'runs/AB00/model.pt')
    expected=dict(checkpoint_sha256=checkpoint,protocol_sha256=digest(OUT/'AB-plan.json'),reviewed_sources=records['report']['sources'],
        reviewed_completion_sha256=digest(OUT/'AB00-completion.json'),reviewed_report_sha256=digest(OUT/'AB00.json'))
    if checkpoint!=records['completion']['checkpoint_sha256']:raise RuntimeError('Control checkpoint changed')
    hashes={key:digest(OUT/name) for key,name in (('review_sha256','AB00-review.json'),('delegation_sha256','AB00-review-delegation.json'),('review_scope_sha256','AB00-review-scope.json'))}
    reviewed=records['scope']['reviewed_commit']
    for name in ('AB-plan.json','AB00.json','AB00-completion.json'):
        committed_manifest(reviewed,'tools/action_predictor/experiments/v28/'+name)
    committed_at=subprocess.run(['git','show','-s','--format=%cI',reviewed],cwd=ROOT,check=True,capture_output=True,text=True).stdout.strip()
    validate(records['review'],records['delegation'],records['scope'],records['response'],expected,hashes,committed_at)
    return records['completion']
