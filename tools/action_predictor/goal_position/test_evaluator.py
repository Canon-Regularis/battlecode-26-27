import unittest
from .evaluator import astar, infer_goal, score_goal


class GoalEvaluatorTests(unittest.TestCase):
    def fixture(self):
        actor={'kind':1,'index':0}; roots=[];frames={}
        for i in range(5):
            event=f'{i+1}:0';p={'x':i,'y':1}
            roots.append(dict(event=event,family='move' if i<4 else 'attack',
                step=dict(actor=actor,phase=10,**{'from':p,'to':{'x':i+1,'y':1}})))
            frames[event]=dict(observation=dict(own=dict(entity=actor,position=p)),
                               supplement=dict(movement=[{'x':1,'y':1}]))
        return roots,frames

    def test_first_interaction_goal_is_approach_not_attack_target(self):
        roots,frames=self.fixture();goal,reason=infer_goal(roots,0,frames)
        self.assertEqual(reason,'available');self.assertEqual(goal['goal'],[4,1])
        self.assertEqual(goal['movement_steps'],4)
        self.assertNotEqual(goal['goal'],list(goal['anchor_target'].values()))

    def test_near_interaction_is_not_skipped(self):
        roots,frames=self.fixture();roots[1]['family']='attack'
        self.assertEqual(infer_goal(roots,0,frames)[1],'first_interaction_too_near')

    def test_missing_anchor_and_discontinuity_censored(self):
        roots,frames=self.fixture();del frames['5:0']
        self.assertEqual(infer_goal(roots,0,frames)[1],'anchor_frame_missing')
        roots,frames=self.fixture();roots[2]['step']['from']['x']=8
        self.assertEqual(infer_goal(roots,0,frames)[1],'position_discontinuity')

    def test_recall_and_horizon_censored(self):
        roots,frames=self.fixture();roots[2]['family']='recall'
        self.assertEqual(infer_goal(roots,0,frames)[1],'uncancelled_recall')
        roots,frames=self.fixture()
        self.assertEqual(infer_goal(roots,0,frames,maximum_roots=2)[1],'horizon_exhausted')

    def test_cancelled_recall_preserves_continuous_path(self):
        roots,frames=self.fixture()
        actor=roots[0]['step']['actor']
        roots[0]['event']='0:0';frames['0:0']=frames.pop('1:0')
        roots[1:1]=[dict(event='0:1',family='recall',step=dict(actor=actor,phase=10)),
                    dict(event='0:2',family='cancel',step=dict(actor=actor,phase=10))]
        goal,reason=infer_goal(roots,0,frames)
        self.assertEqual(reason,'available');self.assertEqual(goal['goal'],[4,1])
        roots[3]['step']['from']={'x':9,'y':9}
        self.assertEqual(infer_goal(roots,0,frames)[1],'position_discontinuity')

    def test_astar_detours_and_respects_first_mask(self):
        route=dict(width=5,height=5,blocked=[2,7,12,17])
        path=astar(route,(0,0),(4,0),{(0,1)})
        self.assertEqual(path[1],(0,1));self.assertEqual(path[-1],(4,0))
        self.assertTrue(all(y*5+x not in route['blocked'] for x,y in path))
        self.assertIsNone(astar(route,(0,0),(4,0),set()))
        self.assertIsNone(astar(route,(0,0),(2,0)))

    def test_oracle_is_separate_from_label(self):
        roots,frames=self.fixture();goal,_=infer_goal(roots,0,frames)
        score=score_goal(dict(width=6,height=3,blocked=[]),frames['1:0'],goal)
        self.assertTrue(score['oracle_optimal_step']);self.assertEqual(score['goal_distance'],4)
        self.assertEqual(score['path_excess'],0)


if __name__=='__main__':unittest.main()
