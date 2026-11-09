"""Bind a completed, substantive fresh review to its actual reviewed artifacts."""
from datetime import datetime
import subprocess

from ..data import digest
from ..order_information.anchored import committed_manifest
from .protocol import ROOT,OUT,LOCAL

QUESTION='Read my thread and find all the errors my model has now made and how we could improve all of it substantially'


def check_review(review,delegation,scope,response,control,completion):
    def require(ok,reason):
        if not ok:raise RuntimeError('RC00_REVIEW_CONTRACT: '+reason)
    thread=review['thread'];runs=review['recentRuns'];items=review['items']
    require(thread['status']=='completed' and thread['model']=='gpt-6.1-sol' and thread['providerInstanceId']=='codex','model or completion')
    require(thread['relationshipToParent']=='subagent' and thread['runCount']==1,'review must be a fresh child')
    require(len(runs)==1 and runs[0]['status']=='completed' and runs[0]['runId']==thread['latestRunId'],'terminal run identity')
    require(delegation['status']=='completed' and delegation['childThreadId']==thread['threadId'] and
            delegation['latestTerminalRunId']==thread['latestRunId'],'delegation identity')
    require(delegation['model']=='gpt-6.1-sol' and delegation['providerInstanceId']=='codex' and
            dict((x['id'],x['value']) for x in delegation['options']).get('reasoningEffort')=='xhigh','requested effort')
    requests=[x for x in items if x['type']=='user_message' and x.get('text')]
    finals=[x for x in items if x['type']=='assistant_message' and x['status']=='completed' and
            x['runId']==thread['latestRunId'] and x.get('text')]
    require(bool(requests) and bool(finals),'empty review messages')
    request=requests[0]['text'];final=finals[-1]['text']
    require(QUESTION in request and len(final)>500 and 'RC00' in final and
            str(len(completion['bindings'])) in final and 'binding' in final,'substantive scoped result')
    checkpoint=digest(LOCAL/'runs/RC00/step-2000.pt');protocol=digest(OUT/'RC-plan.json')
    require(scope['checkpoint_sha256']==checkpoint and checkpoint in request,'review checkpoint')
    require(scope['protocol_sha256']==protocol and 'RC-plan.json' in request,'review protocol')
    require(scope['reviewed_sources']==control['sources'],'reviewed execution sources')
    require(scope['reviewed_completion_sha256']==digest(OUT/'RC00-completion.json') and
            scope['reviewed_report_sha256']==digest(OUT/'RC00.json'),'reviewed report inventory')
    reviewed=scope['reviewed_commit']
    require(reviewed in request and reviewed in final,'reviewed commit in original review record')
    # The reviewed commit must already contain these exact artifacts, before review creation.
    for name in ('RC-plan.json','RC00.json','RC00-completion.json'):
        committed_manifest(reviewed,'tools/action_predictor/experiments/v24/'+name)
    committed_at=subprocess.run(['git','show','-s','--format=%cI',reviewed],cwd=ROOT,check=True,capture_output=True,text=True).stdout.strip()
    require(datetime.fromisoformat(thread['createdAt'].replace('Z','+00:00'))>
            datetime.fromisoformat(committed_at),'review predates completed evidence')
    require(runs[0]['model']=='gpt-6.1-sol' and runs[0]['providerInstanceId']=='codex','actual run model')
    require(response['reviewed_checkpoint_sha256']==checkpoint,'response checkpoint')
    for field,name in (('review_sha256','RC00-review.json'),('delegation_sha256','RC00-review-delegation.json'),
                       ('review_scope_sha256','RC00-review-scope.json')):
        require(response[field]==digest(OUT/name),'response binding: '+field)
    require(scope['raw_review_sha256']==digest(OUT/'RC00-review.json') and
            scope['delegation_sha256']==digest(OUT/'RC00-review-delegation.json'),'scope record identity')
    # This enforces consistency and provenance, not the truth or depth of human-language review.
    return True
