"""Regression guards for the repaired generator's causal argument contract."""
import copy,unittest
import numpy as np
from .proposal_data import selected_jobs,evidence
from .proposal_generator import generate,SPATIAL

class ProposalRegression(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        turns,cls.supps,cls.route=evidence(selected_jobs('train')[0]);cls.d=turns[0]['decisions'][0]
    def arguments(self):return dict(coordinates={a:144 for a in SPATIAL},priority=-784,prefer_blocked=False)
    def test_priority_and_end_survive_missing_position(self):
        obs=copy.deepcopy(self.d['observation']);obs['own']['position']=None
        out=generate(obs,self.supps[self.d['id']],self.route,np.zeros((32,24)),self.arguments())
        by={p.source:p for p in out['proposals']}
        self.assertEqual(by['priority/P05'].priority,-784);self.assertEqual(by['end'].action,'end')
        self.assertNotIn('priority/zero',by)
    def test_no_both_outcomes_for_one_destination(self):
        out=generate(self.d['observation'],self.supps[self.d['id']],self.route,np.zeros((32,24)),self.arguments());outcomes={}
        for p in out['proposals']:
            if p.action in ('move','blocked'):outcomes.setdefault(p.position,set()).add(p.action)
        self.assertTrue(all(len(v)==1 for v in outcomes.values()))
    def test_priority_placeholder_and_foreign_personal_state_rejected(self):
        args=self.arguments();args['priority']=float(-784)
        with self.assertRaises(ValueError):generate(self.d['observation'],self.supps[self.d['id']],self.route,np.zeros((32,24)),args)
        foreign=dict(pre='0:0',perspective=self.d['observation']['perspective'],availability='personal_api',altar_locks=[])
        with self.assertRaises(ValueError):generate(self.d['observation'],self.supps[self.d['id']],self.route,np.zeros((32,24)),self.arguments(),foreign)

if __name__=='__main__':unittest.main()
