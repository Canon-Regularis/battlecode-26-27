"""Real entrypoint refuses source/data/review faults before any optimizer."""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from .protocol import ROOT


class EntrypointContracts(unittest.TestCase):
    def tripwire(self,kind):
        with tempfile.TemporaryDirectory() as directory:
            marker=Path(directory)/'optimizer-reached'
            code="import runpy,torch,json,io,hashlib,numpy as np,sys\nfrom pathlib import Path\nroot=Path.cwd()\n"
            code+=f"def forbidden(*a,**k):\n Path({str(marker)!r}).write_text('reached')\n raise RuntimeError('OPTIMIZER_TRIPWIRE')\ntorch.optim.AdamW=forbidden\n"
            # Failure probes remain valid after either real run directory exists.
            # Every probe must still fail before prerequisites/optimization.
            code+="original_exists=Path.exists\ndef empty_runs(self):\n return False if self.parent.name=='runs' and self.parent.parent.name=='v24' and self.name in ('RC00','RC01') else original_exists(self)\nPath.exists=empty_runs\n"
            if kind=='source':
                code+="original=Path.read_bytes\ndef altered(self):\n value=original(self)\n return value+b'\\n# injected' if self.name=='model.py' and self.parent.name=='relational_priority' else value\nPath.read_bytes=altered\n"
            elif kind=='data':
                code+="""manifest=root/'tools/action_predictor/experiments/v24/RC-data-ready.json'
metadata=root/'.cambc/action-predictor/v24/data/metadata.npz'
with np.load(metadata) as z:arrays={key:z[key] for key in z.files}
arrays['fit_mask']=~arrays['fit_mask']
buffer=io.BytesIO();np.savez_compressed(buffer,**arrays);forged=buffer.getvalue()
altered=json.loads(manifest.read_text());key=next(k for k in altered['files'] if k.endswith('metadata.npz'))
altered['files'][key]=hashlib.sha256(forged).hexdigest();forged_manifest=json.dumps(altered).encode()
original=Path.read_bytes
def read(self):
 if self==manifest:return forged_manifest
 if self==metadata:return forged
 return original(self)
Path.read_bytes=read
"""
            elif kind=='review':
                code+="original=Path.is_file\ndef exists(self):\n return False if self.name=='RC00-review.json' else original(self)\nPath.is_file=exists\n"
            code+=f"sys.argv=['correction-fit',{'RC01' if kind=='review' else 'RC00'!r}]\n"
            code+="runpy.run_module('tools.action_predictor.relational_priority.fit',run_name='__main__')\n"
            result=subprocess.run([sys.executable,*(['-O'] if kind=='optimized' else []),'-c',code],
                                  cwd=ROOT,capture_output=True,text=True,timeout=30)
            self.assertNotEqual(result.returncode,0,result.stdout)
            self.assertFalse(marker.exists(),result.stderr)
            return result.stderr

    def test_optimized_python_refused(self):
        self.assertIn('FIT_REQUIRES_ASSERTIONS',self.tripwire('optimized'))

    def test_modified_source_refused(self):
        self.assertIn('Executed source differs',self.tripwire('source'))

    def test_coherent_metadata_and_manifest_forgery_refused(self):
        self.assertIn('Anchored manifest differs',self.tripwire('data'))

    def test_treatment_requires_completed_fresh_control_review(self):
        self.assertIn('RC01_REQUIRES_COMPLETED_CONTROL_REVIEW',self.tripwire('review'))


if __name__=='__main__':unittest.main()
