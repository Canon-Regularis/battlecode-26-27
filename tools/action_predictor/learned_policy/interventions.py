"""Fixed-checkpoint forward sensitivity, not new fits or checkpoint candidates."""
import copy
import json
import sys
import numpy as np
import torch
from .sequence_data import BASE, WORK, REPORT
from .model import GoalPolicy
from .data import load
from .inference import infer
from ..priority_fit_v3 import load_base
from ..movement_experts.evaluate import summary, paired
from ..audit import immutable_json
from ..data import digest


def plan():
    immutable_json(REPORT / 'L01-sensitivity-plan.json', dict(
        origin='Frozen analysis-plan.json controls, made precise after LP-03; registered while L01 training, before selected L01 evaluation.',
        treatments=dict(
            waypoint_uncertainty_projection_off='Zero goal_condition.weight AND bias. Removes the predicted relative-waypoint/logscale/availability projection only. Latent goal embeddings, goal-conditioned entity attention, proposals and goal mixture remain.',
            persistent_goal_state_reset='Set persistent=False at inference: reset remembered goal belief/world/soft age at each sampled decision. Original bounded action/observation histories, latent embeddings, current goal forecasts and goal-conditioned execution remain.'),
        evaluation='Selected frozen L01 checkpoint only; independently re-filter actual earlier recorded actions forward under each intervention, then decode same normalized distribution. All original DEV rows; compare L01 and L00/G00. No future smoothing, optimizer, threshold/checkpoint selection or model promotion.',
        interpretation='Sensitivity to these particular pathways under an inference-time distribution change, not causal identification of Fish intent, all-goal removal, matched retraining or autonomous rollout strength.',
        source_sha256=digest(__file__), new_fits=0, reserved_opened=0))


def run():
    plan(); torch.set_num_threads(4)
    info = json.loads((REPORT/'L01.json').read_text())
    path = WORK/f"runs/L01/round-{info['selected_round']:02d}.pt"
    assert digest(path) == info['checkpoint_sha256']
    teacher, saved = load_base(); checkpoint = torch.load(path, weights_only=False)
    base = GoalPolicy(teacher, True); base.load_state_dict(checkpoint['state']); base.eval()
    d = load('validation', saved)
    references = {}
    for identifier, p in [('L01',WORK/'runs/L01/validation-predictions.npz'),
                           ('L00',WORK/'runs/L00/validation-predictions.npz'),
                           ('G00',BASE.parent/'v9/runs/G00/validation-predictions.npz')]:
        with np.load(p) as z: references[identifier] = {k:z[k] for k in z.files}
    q = dict(raw=d['raw'],direction=np.load(BASE.parent/'v7/validation-direction.npy'),
             available=np.load(BASE.parent/'v7/validation-available.npy'),
             near=np.load(BASE.parent/'v7/validation-near_obstacle.npy'))
    for name in ('waypoint_uncertainty_projection_off','persistent_goal_state_reset'):
        model = copy.deepcopy(base)
        if name == 'waypoint_uncertainty_projection_off':
            with torch.no_grad(): model.goal_condition.weight.zero_(); model.goal_condition.bias.zero_()
        else: model.persistent = False
        forecast, goals = infer(model,d)
        directory = WORK/f'interventions/L01/{name}'
        assert not directory.exists(), 'Retain completed sensitivity result'
        directory.mkdir(parents=True)
        np.savez_compressed(directory/'validation-predictions.npz',**forecast)
        np.savez_compressed(directory/'validation-goals.npz',**goals)
        immutable_json(REPORT/f'L01-{name}.json',dict(
            summary=summary(q,forecast,np.ones(len(d['raw']['y']),bool)),
            comparisons={k:paired(q,forecast,v) for k,v in references.items()},
            checkpoint_sha256=digest(path),
            predictions_sha256=digest(directory/'validation-predictions.npz'),
            goals_sha256=digest(directory/'validation-goals.npz'),
            source_sha256=digest(__file__),plan_sha256=digest(REPORT/'L01-sensitivity-plan.json'),
            new_fits=0,reserved_opened=0,promoted=False))
        print('Sensitivity completed',name,flush=True)


if __name__ == '__main__':
    if sys.argv[1:] == ['plan']: plan()
    else: run()
