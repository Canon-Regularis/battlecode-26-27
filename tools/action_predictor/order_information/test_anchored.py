"""Self-consistent altered manifest/archive must fail independent anchors."""
import copy
import hashlib
import io
import json
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

from .anchored import ROOT,anchored_inputs,verify_membership


class AnchoredInputTests(unittest.TestCase):
    def test_changed_control_plus_matching_changed_manifest_rejected_before_callback(self):
        manifest=ROOT/'tools/action_predictor/experiments/v19/PC00-data-ready.json'
        archive=ROOT/'.cambc/action-predictor/v19/PC00-cohorts/held_groups.npz'
        with np.load(archive) as z:
            arrays={key:z[key] for key in z.files}
        arrays['group']=arrays['group']+10000
        buffer=io.BytesIO()
        np.savez_compressed(buffer,**arrays)
        forged_archive=buffer.getvalue()
        forged=json.loads(manifest.read_text())
        forged['cohorts']['held_groups']['sha256']=hashlib.sha256(forged_archive).hexdigest()
        forged_manifest=json.dumps(forged).encode('utf-8')
        actual=Path.read_bytes
        def read(path):
            if path==archive:return forged_archive
            if path==manifest:return forged_manifest
            return actual(path)
        reached=[]
        with patch.object(Path,'read_bytes',read):
            with self.assertRaisesRegex(RuntimeError,'Anchored input differs'):
                anchored_inputs()
                reached.append('optimizer callback')
        self.assertEqual(reached,[])

    def test_explicit_membership_rechecks_reject_control_in_training(self):
        fit,controls,_=anchored_inputs()
        bad=copy.deepcopy(fit)
        bad['index'][0]=controls['same_fit_groups']['index'][0]
        with self.assertRaises(RuntimeError):
            verify_membership(bad,controls)


if __name__=='__main__':
    unittest.main()
