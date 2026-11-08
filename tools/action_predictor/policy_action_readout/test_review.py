import copy
import unittest
from unittest.mock import patch
from .review_gate import validate,QUESTION


class ReviewContracts(unittest.TestCase):
    def fixture(self):
        expected=dict(checkpoint_sha256='a'*64,protocol_sha256='b'*64,reviewed_sources={'model.py':'c'*64},reviewed_completion_sha256='d'*64,reviewed_report_sha256='e'*64)
        scope=dict(expected,reviewed_commit='f'*40,raw_review_sha256='1'*64,delegation_sha256='2'*64)
        hashes=dict(review_sha256='1'*64,delegation_sha256='2'*64,review_scope_sha256='3'*64)
        response=dict(hashes,reviewed_checkpoint_sha256='a'*64,correctness_findings_addressed=True)
        review=dict(thread=dict(status='completed',model='gpt-6.1-sol',providerInstanceId='codex',relationshipToParent='subagent',runCount=1,latestRunId='run',threadId='child',createdAt='2026-11-08T12:00:00Z'),
            recentRuns=[dict(status='completed',runId='run',model='gpt-6.1-sol')],
            items=[dict(type='user_message',text=QUESTION+' AB-plan.json '+'a'*64+' '+'f'*40),
                dict(type='assistant_message',status='completed',runId='run',text='AB00 '+'f'*40+' checked artifacts. '*50)])
        delegation=dict(status='completed',childThreadId='child',latestTerminalRunId='run',model='gpt-6.1-sol',providerInstanceId='codex',options=[dict(id='reasoningEffort',value='xhigh')])
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


if __name__=='__main__':unittest.main()
