import copy
import unittest
from unittest.mock import patch
from .review_gate import validate,QUESTION


class ReviewContracts(unittest.TestCase):
    def fixture(self):
        expected=dict(checkpoint_sha256='a'*64,protocol_sha256='b'*64,reviewed_sources={'model.py':'c'*64},reviewed_completion_sha256='d'*64,reviewed_report_sha256='e'*64,
            parent_thread_id='parent',child_thread_id='child',reviewed_supplemental_evidence={'diagnosis.json':'5'*64})
        scope=dict(expected,reviewed_commit='f'*40,raw_review_sha256='1'*64,delegation_sha256='2'*64,launch_sha256='4'*64)
        hashes=dict(review_sha256='1'*64,delegation_sha256='2'*64,review_scope_sha256='3'*64,launch_sha256='4'*64)
        response=dict(hashes,reviewed_checkpoint_sha256='a'*64,correctness_findings_addressed=True)
        review=dict(thread=dict(status='completed',model='gpt-6.1-sol',providerInstanceId='codex',relationshipToParent='subagent',runCount=1,latestRunId='run',threadId='child',parentThreadId='parent',activeRunId=None,createdAt='2026-11-08T12:00:00Z'),
            recentRuns=[dict(status='completed',runId='run',model='gpt-6.1-sol',providerInstanceId='codex')],
            items=[dict(type='user_message',status='completed',sourceThreadId='child',runId='run',senderThreadId='parent',createdBy='agent',creationSource='mcp',text=QUESTION+' AB-plan.json '+'a'*64+' '+'f'*40),
                dict(type='assistant_message',status='completed',sourceThreadId='child',runId='run',createdBy='agent',creationSource='provider',text='AB00 '+'f'*40+' checked artifacts. '*50)])
        delegation=dict(status='completed',latestTerminalStatus='completed',hasPendingChildRuns=False,hasPendingQuestion=False,pendingApproval=None,
            childThreadId='child',latestTerminalRunId='run',model='gpt-6.1-sol',providerInstanceId='codex',options=[dict(id='reasoningEffort',value='xhigh')])
        return review,delegation,scope,response,expected,hashes,'2026-11-08T11:00:00+00:00'

    def test_scope_and_freshness_reject_known_loopholes(self):
        args=self.fixture();self.assertTrue(validate(*args))
        for field in ('empty','checkpoint','effort','source','stale','response'):
            a=copy.deepcopy(args)
            if field=='empty':a[0]['items']=[]
            elif field=='checkpoint':a[2]['checkpoint_sha256']='wrong'
            elif field=='effort':a[1]['options'][0]['value']='high'
            elif field=='source':a[2]['reviewed_sources']={}
            elif field=='stale':a[0]['thread']['createdAt']='2026-11-08T10:00:00Z'
            else:a[3]['review_sha256']='wrong'
            with self.subTest(field=field),self.assertRaises(RuntimeError):validate(*a)

    def test_real_entrypoint_stops_before_optimizer_after_review_failure(self):
        from . import fit
        with patch.object(fit,'source_gate',return_value=('source',{})),patch.object(fit,'require_control_review',side_effect=RuntimeError('injected review failure')),patch.object(fit.torch.optim,'AdamW') as optimizer:
            with self.assertRaisesRegex(RuntimeError,'injected review failure'):fit.run('AB01')
            optimizer.assert_not_called()

    def corrupt(self,a,field):
        if field=='parent':a[0]['thread']['parentThreadId']='unrelated'
        elif field=='message_thread':a[0]['items'][-1]['sourceThreadId']='unrelated'
        elif field=='run_provider':a[0]['recentRuns'][0]['providerInstanceId']='another'
        elif field=='active':a[0]['thread']['activeRunId']='other-live-run'
        elif field=='author':a[0]['items'][-1]['createdBy']='user'
        elif field=='final_source':a[0]['items'][-1]['creationSource']='mcp'
        elif field=='request_thread':a[0]['items'][0]['sourceThreadId']='unrelated'
        elif field=='request_author':a[0]['items'][0]['senderThreadId']='unrelated'
        elif field=='supplement':a[2]['reviewed_supplemental_evidence']={}
        else:a[2]['launch_sha256']='wrong'

    def test_new_identity_faults_through_entrypoint_before_optimizer(self):
        from . import fit,review_gate
        for field in ('parent','message_thread','request_thread','run_provider','active','author','final_source','request_author','supplement','launch'):
            a=copy.deepcopy(self.fixture());self.corrupt(a,field)
            records=dict(review=a[0],delegation=a[1],scope=a[2],response=a[3],completion={'bindings':{}})
            with self.subTest(field=field),patch.object(fit,'source_gate',return_value=('source',{})),patch.object(review_gate,'load_review_context',return_value=(records,a[4],a[5],a[6])),patch.object(fit.torch.optim,'AdamW') as optimizer:
                with self.assertRaisesRegex(RuntimeError,'AB00_REVIEW_CONTRACT'):fit.run('AB01')
                optimizer.assert_not_called()

    def test_control_prediction_corruption_rejected_before_optimizer(self):
        from . import fit,review_gate
        a=self.fixture();path=review_gate.LOCAL/'runs/AB00/train-predictions.npz';key=str(path.relative_to(review_gate.ROOT))
        records=dict(review=a[0],delegation=a[1],scope=a[2],response=a[3],completion={'bindings':{key:'expected'}})
        with patch.object(fit,'source_gate',return_value=('source',{})),patch.object(review_gate,'load_review_context',return_value=(records,a[4],a[5],a[6])),patch.object(review_gate,'digest',return_value='corrupt'),patch.object(fit.torch.optim,'AdamW') as optimizer:
            with self.assertRaisesRegex(RuntimeError,'CONTROL_PREDICTIONS_CHANGED_BEFORE_OPTIMIZER'):fit.run('AB01')
            optimizer.assert_not_called()

    def test_committed_science_change_rejected_by_real_source_gate(self):
        from . import fit,protocol,matched_guard
        original=matched_guard.current_bytes
        def forged(name):
            raw=original(name)
            return raw+b'\n# simulated subsequently committed scientific change\n' if name.endswith('/fit.py') else raw
        with patch.object(protocol,'committed_sources',return_value=('later-commit',{})),patch.object(matched_guard,'current_bytes',side_effect=forged),patch.object(fit.torch.optim,'AdamW') as optimizer:
            with self.assertRaisesRegex(RuntimeError,'MATCHED_SCIENCE_CHANGED'):fit.run('AB01')
            optimizer.assert_not_called()


if __name__=='__main__':unittest.main()
