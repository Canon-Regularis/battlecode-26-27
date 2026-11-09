import unittest
import torch
from . import goal_execution_fit as fit


class Tests(unittest.TestCase):
    def test_diagnostic_goals_do_not_count_as_causal_target(self):
        torch.manual_seed(2)
        rows=[dict(key=f'{split}-{h}',position=0,split=split,horizon=h,label=1,far=True) for split in ('fit','evaluation') for h in (2,4,8)]
        logits=torch.zeros(6,9);logits[:,1]=4
        bank=dict(context=torch.zeros(6,704),goal=torch.zeros(6,9,8),baseline=logits,support=torch.ones(6,9,dtype=torch.bool),labels=torch.ones(6,dtype=torch.long),routed=torch.ones(6,dtype=torch.long))
        causal=[dict(split=split,label=1,active=False,direct=1,routed=1,direct_nll=.1,predictions=dict(control=1,goal=1),nll=dict(control=.1,goal=.1)) for split in ('fit','evaluation')]
        nets={a:fit.new(a,dict(seed=66001)) for a in fit.ARMS};r=fit.summaries(nets,bank,rows,causal)
        self.assertEqual(r['diagnostic']['evaluation']['goal']['correct'],3);self.assertFalse(r['target_met']);self.assertFalse(r['all_checks_pass'])
        routing=r['diagnostic']['evaluation']['routing'];self.assertNotIn('nll_sum',routing);self.assertNotIn('losses',routing)
        for h in routing['horizons'].values():self.assertNotIn('nll_sum',h)


if __name__=='__main__':unittest.main()
