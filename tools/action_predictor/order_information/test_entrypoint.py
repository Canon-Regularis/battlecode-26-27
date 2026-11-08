"""Actual fitting entrypoint must reject coherently forged control inputs."""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
import torch

from .anchored import ROOT
from .data import numeric_mean_inputs


class InformationEntryTests(unittest.TestCase):
    def test_optimized_and_changed_source_real_entrypoint_refuse(self):
        for optimized in (True,False):
            with self.subTest(optimized=optimized),tempfile.TemporaryDirectory() as directory:
                marker=Path(directory)/'optimizer-reached'
                code="import runpy,torch\nfrom pathlib import Path\n"
                code+=f"def forbidden(*a,**k):\n Path({str(marker)!r}).write_text('reached')\n raise RuntimeError('OPTIMIZER_TRIPWIRE')\n"
                code+="torch.optim.AdamW=forbidden\n"
                if not optimized:
                    code+="original=Path.read_bytes\ndef altered(self):\n value=original(self)\n return value+b'\\n# injected' if self.name=='data.py' and self.parent.name=='order_information' else value\nPath.read_bytes=altered\n"
                code+="runpy.run_module('tools.action_predictor.order_information.fit',run_name='__main__')\n"
                result=subprocess.run([sys.executable,*(['-O'] if optimized else []),'-c',code],
                                      cwd=ROOT,capture_output=True,text=True,timeout=30)
                self.assertNotEqual(result.returncode,0)
                self.assertIn('FIT_REQUIRES_ASSERTIONS' if optimized else 'Executed source differs',result.stderr)
                self.assertFalse(marker.exists(),result.stderr)

    def test_real_entrypoint_rejects_coherent_control_forgery_before_optimizer(self):
        with tempfile.TemporaryDirectory() as directory:
            marker=Path(directory)/'optimizer-reached'
            code="""import runpy,torch,json,io,hashlib,numpy as np
from pathlib import Path
root=Path.cwd()
manifest=root/'tools/action_predictor/experiments/v19/PC00-data-ready.json'
archive=root/'.cambc/action-predictor/v19/PC00-cohorts/held_groups.npz'
with np.load(archive) as z: arrays={key:z[key] for key in z.files}
arrays['group']=arrays['group']+10000
buffer=io.BytesIO();np.savez_compressed(buffer,**arrays);new_archive=buffer.getvalue()
altered=json.loads(manifest.read_text());altered['cohorts']['held_groups']['sha256']=hashlib.sha256(new_archive).hexdigest()
new_manifest=json.dumps(altered).encode('utf-8')
original=Path.read_bytes
def read(self):
 if self==manifest:return new_manifest
 if self==archive:return new_archive
 return original(self)
Path.read_bytes=read
def forbidden(*a,**k):
 Path(MARKER).write_text('optimizer reached')
 raise RuntimeError('OPTIMIZER_TRIPWIRE')
torch.optim.AdamW=forbidden
runpy.run_module('tools.action_predictor.order_information.fit',run_name='__main__')
""".replace('MARKER',repr(str(marker)))
            result=subprocess.run([sys.executable,'-c',code],cwd=ROOT,capture_output=True,text=True,timeout=30)
            self.assertNotEqual(result.returncode,0)
            self.assertIn('Anchored input differs',result.stderr)
            self.assertFalse(marker.exists(),result.stderr)

    def test_non_degenerate_numeric_mean_replacement(self):
        x=torch.arange(128,dtype=torch.float32).reshape(4,32)/7
        available=torch.tensor([[1,1,0,1],[1,0,1,0],[0,1,1,1],[0,0,0,0]],dtype=torch.bool)
        references=(np.arange(24,dtype=np.float32).reshape(4,6)+100)/3
        result=numeric_mean_inputs(x,available,references,np.ones(4,bool))
        expected=x.clone()
        for row in range(4):
            for pool in range(4):
                if available[row,pool]:
                    expected[row,pool*8+2:pool*8+8]=torch.tensor(references[pool])
        torch.testing.assert_close(result,expected,rtol=0,atol=0)
        self.assertGreater(int(torch.count_nonzero(result-x)),0)
        torch.testing.assert_close(result[3],x[3],rtol=0,atol=0)
        torch.testing.assert_close(result[:,[0,1,8,9,16,17,24,25]],x[:,[0,1,8,9,16,17,24,25]],rtol=0,atol=0)


if __name__=='__main__':unittest.main()
