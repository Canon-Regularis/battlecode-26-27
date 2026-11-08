"""Exercise real entrypoint failures and archival without optimizer updates."""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
import torch

from .safety import ROOT,dependency_files,archive_then_measure


class SafetyTests(unittest.TestCase):
    def tripwire_run(self,optimized=False,mutated=None):
        with tempfile.TemporaryDirectory() as directory:
            marker=Path(directory)/'optimizer-reached'
            prefix=("import runpy,torch; from pathlib import Path\n"
                "def forbidden(*a,**k):\n"
                f" Path({str(marker)!r}).write_text('optimizer reached')\n"
                " raise RuntimeError('OPTIMIZER_TRIPWIRE')\n"
                "torch.optim.AdamW=forbidden\n")
            if mutated:
                target=str((ROOT/mutated).resolve())
                prefix+=("original=Path.read_bytes\n"
                    "def altered(self):\n"
                    " value=original(self)\n"
                    f" return value+b'\\n# injected source mismatch' if str(self.resolve())=={target!r} else value\n"
                    "Path.read_bytes=altered\n")
            code=prefix+"runpy.run_module('tools.action_predictor.priority_regularized.experiment',run_name='__main__')\n"
            command=[sys.executable]+(['-O'] if optimized else [])+['-c',code]
            env=os.environ.copy()
            result=subprocess.run(command,cwd=ROOT,capture_output=True,text=True,env=env,timeout=30)
            self.assertNotEqual(result.returncode,0,result.stdout)
            self.assertFalse(marker.exists(),result.stderr)
            return result

    def test_static_closure_contains_previous_omissions_and_tests(self):
        paths={p.relative_to(ROOT).as_posix() for p in dependency_files()}
        self.assertIn('tools/action_predictor/priority_capacity/protocol.py',paths)
        self.assertIn('tools/action_predictor/priority_capacity/test_measurement.py',paths)
        self.assertIn('tools/action_predictor/priority_regularized/test_safety.py',paths)

    def test_real_optimized_entrypoint_refuses_before_optimizer(self):
        result=self.tripwire_run(optimized=True)
        self.assertIn('FIT_REQUIRES_ASSERTIONS',result.stderr)

    def test_real_entrypoint_rejects_each_previously_omitted_source(self):
        for target in ('tools/action_predictor/priority_capacity/protocol.py',
                       'tools/action_predictor/priority_capacity/test_measurement.py'):
            with self.subTest(target=target):
                result=self.tripwire_run(mutated=target)
                self.assertIn('Executed source differs from committed bytes: '+target,result.stderr)

    def test_raw_survives_injected_measurement_exception(self):
        raw=np.array([[1.,2.],[3.,4.]],dtype=np.float32)
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'raw.npy'
            def failed(saved):
                np.testing.assert_array_equal(saved,raw)
                raise RuntimeError('injected measurement failure')
            with self.assertRaisesRegex(RuntimeError,'injected measurement failure'):
                archive_then_measure(raw,path,failed)
            np.testing.assert_array_equal(np.load(path),raw)

    def test_penalty_gradient_is_exact_sum_not_mean(self):
        from .experiment import displacement_penalty
        parameter=torch.tensor([2.,-3.],requires_grad=True)
        warm=torch.tensor([1.,1.])
        loss=displacement_penalty([parameter],[warm],.2)
        loss.backward()
        torch.testing.assert_close(parameter.grad,torch.tensor([.4,-1.6]))
        self.assertAlmostEqual(float(loss.detach()),3.4)
        torch.testing.assert_close(warm,torch.tensor([1.,1.]))


if __name__=='__main__':
    unittest.main()
