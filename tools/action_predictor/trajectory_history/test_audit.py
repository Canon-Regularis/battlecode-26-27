import copy
import unittest
from .audit import label, window_counts


def example():
    own = dict(entity=dict(kind=1, index=4), team=1, position=dict(x=5, y=6))
    turn = dict(actor=4, round=9)
    root = dict(pre='3:4', event='4:0', header=dict(phase=10, currentChampion=4, round=9,
        step=dict(kind=4, actor=own['entity'], to=dict(x=6, y=6), **{'from': own['position']})))
    frame = dict(actor=4, pre='3:4', round=9, observation=dict(own=own),
        pre_header=dict(phase=10, currentChampion=4, team=1))
    return turn, root, frame


class CacheAuditTests(unittest.TestCase):
    def test_recorded_move_and_shop_semantics(self):
        t, r, f = example()
        self.assertEqual(label(t, r, f)['destination'], dict(x=6, y=6))
        r['header']['step']['kind'] = 13
        self.assertFalse(label(t, r, f)['complete_arguments'])

    def test_actor_future_and_team_rejected(self):
        for mutate in (lambda r, f: f.update(actor=3),
                       lambda r, f: r.update(event='3:4'),
                       lambda r, f: f['pre_header'].update(team=0),
                       lambda r, f: r['header']['step'].update(actor=dict(kind=1, index=2))):
            t, r, f = example(); mutate(r, f)
            with self.assertRaises(ValueError): label(t, r, f)

    def test_missing_destination_priority_and_wrong_origin_rejected(self):
        t, r, f = example()
        r['header']['step']['to'] = None
        with self.assertRaises(ValueError): label(t, r, f)
        t, r, f = example(); r['header']['step']['from'] = dict(x=9, y=9)
        with self.assertRaises(ValueError): label(t, r, f)
        r['header']['step']['kind'] = 9
        with self.assertRaises(ValueError): label(t, r, f)

    def test_nonoverlap_round_spanning_and_gaps(self):
        stream = [(i, i//12) for i in range(70)]
        result = window_counts([stream])['32']
        self.assertEqual(result, dict(windows=2, across_rounds=2, roots=64))
        self.assertEqual(window_counts([stream[:20], stream[21:40]])['32']['windows'], 0)
        bad = copy.deepcopy(stream); bad[10] = (20, 0)
        with self.assertRaises(ValueError): window_counts([bad])


if __name__ == '__main__': unittest.main()
