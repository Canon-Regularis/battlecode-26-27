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
            review_fault=kind.startswith('review_')
            code+=f"sys.argv=['correction-fit',{'RC01' if kind=='review' or review_fault else 'RC00'!r}]\n"
            if review_fault:
                code+="from tools.action_predictor.relational_priority import fit as f\noriginal_manifest=f.committed_manifest\n"
                code+=f"fault={kind!r}\n"
                code+="""def forged_manifest(commit,path):
 value,bindings=original_manifest(commit,path)
 if str(path).endswith('RC00-review.json'):
  if fault=='review_empty':value['items']=[]
  if fault=='review_wrong_checkpoint':value['items'][0]['text']=value['items'][0]['text'].replace('e1e46cab0a343e1b65dd96eb3b9fc59a9d61d2da71439815b142aa9f8181006a','0'*64)
  if fault=='review_stale':value['thread']['createdAt']='2000-01-01T00:00:00Z'
 if str(path).endswith('RC00-review-delegation.json') and fault=='review_effort':value['options']=[{'id':'reasoningEffort','value':'high'}]
 if str(path).endswith('RC00-review-scope.json') and fault=='review_sources':value['reviewed_sources']={}
 if str(path).endswith('RC00-review-response.json') and fault=='review_response':value['review_sha256']='0'*64
 return value,bindings
f.committed_manifest=forged_manifest
f.main()
"""
            else:code+="runpy.run_module('tools.action_predictor.relational_priority.fit',run_name='__main__')\n"
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

    def test_actual_treatment_entrypoint_rejects_inadequate_review_before_optimizer(self):
        for kind,reason in (('review_empty','empty review'),('review_wrong_checkpoint','review checkpoint'),
                            ('review_stale','predates'),('review_effort','effort'),
                            ('review_sources','execution sources'),('review_response','response binding')):
            with self.subTest(kind=kind):
                self.assertIn('RC00_REVIEW_CONTRACT: '+reason,self.tripwire(kind))


if __name__=='__main__':unittest.main()
