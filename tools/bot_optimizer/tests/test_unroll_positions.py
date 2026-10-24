import ast
import copy
import unittest
from unittest.mock import patch

from tools.bot_optimizer import Options, optimize_source
from tools.bot_optimizer.unroll_positions import UnrollPositions, safe_breaks
from tools.bot_optimizer.tests.test_width_dispatch import SOURCE
from tools.bot_optimizer.tests.test_specialization import execute


class UnrollPositionTests(unittest.TestCase):
    def test_actual_source_control_flow_and_boundary_widths(self):
        for length in (0, 1, 2, 11, 12):
            text = SOURCE.replace('[tuple([0, 0]), tuple([0])]', f'[tuple({[0]*length!r})]')
            compiled = optimize_source(text)
            self.assertEqual(sum(c.pass_name == 'insertion-unroll-positions' for c in compiled.changes),11)
            original,optimized = execute(text),execute(compiled.source)
            for case in original['CASES']:
                self.assertEqual(original[case](),optimized[case](),(length,case))
        for disabled in ('insertion-unroll-positions','insertion-direct-routes','insertion-width-dispatch'):
            compiled = optimize_source(SOURCE, Options(disabled=frozenset({disabled})))
            self.assertFalse(any(c.pass_name == 'insertion-unroll-positions' for c in compiled.changes))

    def test_missing_proofs_changed_controls_and_growth_budget(self):
        captured=[]
        def capture(pass_,tree):
            captured.append(copy.deepcopy(tree))
            return tree
        with patch('tools.bot_optimizer.compiler.UnrollPositions.apply',capture):
            optimize_source(SOURCE)
        original,=captured
        for mutation in ('proof','halt','break','position','size','growth'):
            tree=copy.deepcopy(original)
            loops=[n for n in ast.walk(tree) if getattr(n,'_bcopt_direct_positions',None)]
            for loop in loops:
                width,size=loop._bcopt_direct_positions
                if mutation=='proof':
                    del loop._bcopt_direct_positions
                elif mutation=='halt':
                    del loop._bcopt_fused_halt
                elif mutation=='break':
                    loop.body.insert(0,ast.Break())
                elif mutation in {'position','size'}:
                    variable=loop.target.id if mutation=='position' else size
                    loop.body.append(ast.parse(f'{variable}=1').body[0])
                else:
                    loop.body.extend(ast.Pass() for _ in range(40000))
            transform=UnrollPositions(Options())
            transform.apply(tree)
            self.assertFalse(transform.changes,mutation)
        self.assertFalse(safe_breaks(ast.parse('try:\n    pass\nexcept Exception:\n    break').body,'halt'))
        self.assertFalse(safe_breaks(ast.parse('for x in ():\n    pass\nelse:\n    break').body,'halt'))
        self.assertTrue(safe_breaks(ast.parse('for x in ():\n    break').body,'halt'))


if __name__=='__main__':
    unittest.main()
