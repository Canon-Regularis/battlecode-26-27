"""Forward component-execution diagnostic, not an oracle deployable policy."""
import json
import sys
from pathlib import Path
import numpy as np
import torch
from .sequence_data import BASE, WORK, REPORT
from .model import GoalPolicy
from .data import load, chunks, causal_inputs, geometry, targets
from .inference import select_state
from ..priority_fit_v3 import load_base
from ..data import digest
from ..audit import immutable_json


def plan():
    immutable_json(REPORT / 'component-execution-plan.json', dict(
        purpose='LP-01: compare diversity of execution, not just separation of predicted waypoints.',
        scope='L00 review-driven diagnostic; identical procedure prospective for uncompleted L01. All original DEV move/blocked rows and identity-verified natural TRAIN move/blocked rows; causal state traverses full original streams.',
        metrics='Per-component conditional modes, union, mode agreement, actual mixture mode, typed failures with/without correct component modes, mixture successes outside all modes, conditional-goal weight entropy and component Jensen-Shannon divergence.',
        interpretation='Current component-mode union is an oracle diagnostic, NOT achieved accuracy, full distribution support or an architecture ceiling. Mixture MAP can lie outside component modes. Recorded family/answer enters conditional diagnosis and only postprediction filter update, never goal proposal.',
        no_selection='Do not choose checkpoints, thresholds, seeds or intervention by these diagnostics.',
        source_sha256=digest(__file__), new_fits=0, reserved_opened=0))


@torch.no_grad()
def run(identifier, split):
    plan(); torch.set_num_threads(2)
    info = json.loads((REPORT / f'{identifier}.json').read_text())
    checkpoint = WORK / f"runs/{identifier}/round-{info['selected_round']:02d}.pt"
    assert digest(checkpoint) == info['checkpoint_sha256']
    teacher, saved = load_base(); statefile = torch.load(checkpoint, weights_only=False)
    model = GoalPolicy(teacher, statefile['persistent']); model.load_state_dict(statefile['state']); model.eval()
    d = load(split, saved); raw = d['raw']; n = len(raw['y'])
    with np.load(WORK / f'runs/{identifier}/{split}-predictions.npz') as z:
        forecast = {k:z[k] for k in ('prediction','coordinate')}
    eligible = np.isin(raw['y'], [3,8])
    natural_path = BASE.parent / 'v9/frequency/natural-mask.npy'
    if split == 'train':
        assert digest(natural_path) == '09217d8fc3d5673d980c8b8a4434861aa26dddb37e506bbfa22cbaafc0e525bd'
        eligible &= np.load(natural_path)
    ids = np.flatnonzero(eligible); inverse = np.full(n, -1, np.int32); inverse[ids] = np.arange(len(ids))
    modes = np.full((len(ids),4), -1, np.int64); mixture = np.full(len(ids), -1, np.int64)
    weights = np.zeros((len(ids),4), np.float32); js = np.zeros(len(ids), np.float64)
    state = model.empty(32); seen = np.zeros(n, np.uint8)
    for rows in chunks(d['sequences']):
        for row in rows:
            valid = row >= 0; ix = np.maximum(row, 0); mask = torch.from_numpy(valid)
            step = model.begin(**causal_inputs(d,ix), state=state); geo = geometry(d,ix)
            diagnostic = valid & eligible[ix]
            if diagnostic.any():
                sub = {k:v[diagnostic] for k,v in step.items()}
                sg = {k:v[diagnostic] for k,v in geo.items()}
                family = torch.from_numpy(raw['y'][ix[diagnostic]]).long()
                lp = model.spatial_log_probs(sub, **sg, family=family)
                typ = model.types(sub)[torch.arange(len(family)), :, family]
                logweight = (sub['logprior'] + typ).log_softmax(-1)
                mix = torch.logsumexp(logweight[:,:,None] + lp, 1)
                at = inverse[ix[diagnostic]]
                modes[at] = lp.argmax(-1).numpy(); mixture[at] = mix.argmax(-1).numpy(); weights[at] = logweight.exp().numpy()
                middle = torch.logsumexp(lp.double(),1) - np.log(4)
                js[at] = (.25 * (lp.double().exp() * (lp.double()-middle[:,None])).sum((1,2))).numpy()
            target = targets(d,ix)
            _, post = model.observed(step, **geo, **{k:target[k] for k in ('y','py','priority_parameter_nll')})
            state = select_state(state,post,mask); seen[row[valid]] += 1
    assert np.all(seen == 1)
    np.testing.assert_array_equal(mixture, forecast['coordinate'][ids])
    target = raw['py'][ids]; correct = (mixture == target) & (target < 289)
    component_correct = (modes == target[:,None]) & (target[:,None] < 289)
    union = component_correct.any(-1); typed = forecast['prediction'][ids] == raw['y'][ids]
    direction = np.load(BASE.parent / f'v7/{split}-direction.npy')[ids]
    contexts = dict(all=np.ones(len(ids),bool), move=raw['y'][ids]==8, blocked=raw['y'][ids]==3,
                    continuation=(raw['y'][ids]==8)&(direction==2), change=(raw['y'][ids]==8)&(direction==3))
    result = {}
    for name, m in contexts.items():
        result[name] = dict(rows=int(m.sum()), all_components_same_mode=int((m & (modes==modes[:,:1]).all(-1)).sum()),
            component_mode_exact=component_correct[m].sum(0).tolist(), mode_union_exact=int((m&union).sum()),
            mixture_conditional_exact=int((m&correct).sum()), mixture_joint_exact=int((m&correct&typed).sum()),
            typed_destination_failures=int((m&typed&~correct).sum()),
            typed_failures_with_correct_component_mode=int((m&typed&~correct&union).sum()),
            typed_failures_without_correct_component_mode=int((m&typed&~correct&~union).sum()),
            mode_union_missed_by_mixture=int((m&union&~correct).sum()),
            mixture_correct_outside_modes=int((m&correct&~union).sum()),
            mean_component_JS_divergence=float(js[m].mean()) if m.any() else None,
            mean_goal_given_family_weights=weights[m].mean(0).tolist() if m.any() else None)
    path = WORK / f'runs/{identifier}/{split}-components.npz'
    assert not path.exists(), 'Preserve existing component diagnostic'
    np.savez_compressed(path,index=ids,head_modes=modes,mixture_mode=mixture,family_goal_weights=weights,JS_divergence=js)
    immutable_json(REPORT / f'{identifier}-{split}-components.json',dict(
        results=result, artifact_sha256=digest(path), checkpoint_sha256=digest(checkpoint),
        forecast_sha256=digest(WORK/f'runs/{identifier}/{split}-predictions.npz'),
        input_receipt_sha256=digest(REPORT/'policy-input-bindings.json'),
        natural_mask_sha256=digest(natural_path) if split=='train' else None,
        direction_sha256=digest(BASE.parent/f'v7/{split}-direction.npy'),
        plan_sha256=digest(REPORT/'component-execution-plan.json'), source_sha256=digest(__file__),
        qualification='Conditional family supplied only for diagnosis, not deployable routing. Natural TRAIN rows are from augmented filter traversal and in-sample. Oracle mode coverage is not a configuration support ceiling.',
        new_fits=0, reserved_opened=0))
    print(identifier, split, result, flush=True)


if __name__ == '__main__': run(*sys.argv[1:])
