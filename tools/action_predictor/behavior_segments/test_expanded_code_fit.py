import unittest
from .expanded_code_fit import partition_indices


class ExpandedCodeFitTests(unittest.TestCase):
    def test_all_held_game_extras_excluded_from_training(self):
        ids=[dict(group=f'g{g}',fold=g,canonical=i==0) for g in range(4) for i in range(5)]
        train,held=partition_indices(ids,2)
        self.assertEqual(len(train),15);self.assertEqual(held.tolist(),[10])
        self.assertFalse(any(ids[i]['group']=='g2' for i in train))
        ids[0]['group']='g2'
        with self.assertRaises(ValueError):partition_indices(ids,2)


if __name__=='__main__':unittest.main()
