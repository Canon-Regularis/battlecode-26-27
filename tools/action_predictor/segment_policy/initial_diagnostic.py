"""Registered round-zero diagnostic; never a selectable checkpoint."""
import json
import subprocess
import numpy as np
import torch
from ..audit import immutable_json
from ..data import digest
from ..priority_fit_v3 import load_base
from ..movement_experts.evaluate import summary, masks
from .data import ROOT, WORK, REPORT, load, diagnostic_data
from .model import SegmentPolicy
from .inference import infer


def run():
    torch.set_num_threads(1)
    torch.use_deterministic_algorithms(True)
    plan = json.loads((REPORT/'protocol.json').read_text())
    for name in ('model.py', 'filter.py', 'inference.py', 'data.py'):
        key = 'tools/action_predictor/segment_policy/'+name
        if digest(ROOT/key) != plan['sources'][key]: raise RuntimeError('Frozen executable changed')
    source = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=ROOT, check=True, capture_output=True, text=True).stdout.strip()
    path = WORK/'runs/H00/initial.pt'
    saved = torch.load(path, weights_only=False, map_location='cpu')
    teacher, normalizer = load_base()
    model = SegmentPolicy(teacher, False)
    model.load_state_dict(saved['state'])
    d = load('validation', normalizer)
    directory = WORK/'runs/H00/initial-validation-diagnostic'
    forecast = infer(model, d, directory, decode=True)
    archive = directory/'predictions.npz'
    np.savez_compressed(archive, **forecast)
    q = diagnostic_data(d, 'validation')
    overall = summary(q, forecast, np.ones(14439, bool))
    for code, row in enumerate(overall['per_category']):
        m = d['raw']['y'] == code
        row['joint_NLL'] = float(forecast['nll'][m].mean()) if m.any() else None
    immutable_json(REPORT/'H00-initial-diagnostic.json', dict(
        overall=overall, contexts={k: summary(q, forecast, m) for k, m in masks(q).items()},
        source_commit=source, source_sha256=digest(__file__), checkpoint_sha256=digest(path),
        predictions_sha256=digest(archive), protocol_sha256=digest(REPORT/'protocol.json'),
        fit_source_commit=saved['source_commit'], inference_threads=1,
        scope='Registered round-zero diagnostic only; not a checkpoint candidate. Random newly introduced recurrent weights can affect forecasts after the first command even though all common tensors start from M01. Same causal predict-then-assimilate pipeline; all14439DEV rows. Never selected or substituted for a treatment.',
        cost='Runs concurrently with H00 optimization; measured H00 wall time includes resource sharing and is not pure optimizer cost.',
        new_fits=0, optimizer_updates=0, reserved_opened=0))


if __name__ == '__main__': run()
