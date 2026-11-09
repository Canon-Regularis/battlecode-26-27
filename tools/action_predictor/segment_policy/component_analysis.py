"""New emission/selection diagnostics, with a causal fixed-checkpoint refilter.

No fit, oracle state routing, alternative policy selection or replay operation.
"""
import json
import numpy as np
import torch
from ..audit import immutable_json
from ..data import digest
from ..priority_fit_v3 import load_base
from .. import reliable_train as rt
from .data import ROOT, WORK, REPORT, load, causal_inputs, geometry, targets, chunks
from .history_model import HistorySegmentPolicy
from .inference import take, put


def freeze():
    immutable_json(REPORT/'H01-component-analysis-plan.json', dict(
        question='Do state-conditioned emissions supply useful distinct movement alternatives, and does causal selection recover them?',
        endpoint='Only the original selected H01checkpoint, never a different round or variant',
        scope='All14439originalDEVrows forecast allfourcomponenttype/movement distributions before currentanswerassimilation; all2362truefamilymoves enter diagnostics afterward. Same original direction strata and predicted completecommands. No data deletion.',
        measures=['component-mode union vs actual conditional/joint accuracy', 'common-wrong dominance upperbound with frozen emissions and inputs',
            'correct available mode only in lower conditional-state-weight heads vs mixture failure despite top-weight correct head',
            'component total variation, distinct modes, target rank/probability and continuation/change',
            'primary family-coordinate/type/prior parity'],
        interpretation='Mode union is an oracle diagnostic, not achieved selection accuracy or a general mixture ceiling. Only the common-wrong first-argmax certificate proves impossibility under current nonnegative reweighting. Retraining execution or changing encoded observations can change that bound. Component names have no assumed intent.',
        source_sha256=digest(__file__), new_fits=0, reserved_opened=0))


@torch.no_grad()
def run():
    if digest(__file__) != json.loads((REPORT/'H01-component-analysis-plan.json').read_bytes())['source_sha256']:
        raise RuntimeError('Planned analysis source changed')
    rt.setup(20261130)
    report_path = REPORT/'H01.json'; report = json.loads(report_path.read_bytes())
    checkpoint = WORK/f"runs/H01/round-{report['selected_round']:02d}.pt"
    if digest(checkpoint) != report['checkpoint_sha256']: raise RuntimeError('Selected checkpoint changed')
    teacher, saved = load_base(); model = HistorySegmentPolicy(teacher)
    model.load_state_dict(torch.load(checkpoint, weights_only=False, map_location='cpu')['state']); model.eval()
    d = load('validation', saved); n = len(d['raw']['y'])
    destination = WORK/'H01-component-analysis'; destination.mkdir(parents=True, exist_ok=False)
    raw = {k: np.lib.format.open_memmap(destination/(k+'.npy'), mode='w+', dtype=np.float64, shape=shape)
        for k, shape in dict(logprior=(n, 4), types=(n, 4, 15), movement=(n, 4, 291)).items()}
    for a in raw.values(): a[:] = np.nan
    state = model.empty(32); seen = np.zeros(n, np.uint8)
    for block in chunks(d['sequences']):
        for rows in block:
            active = torch.from_numpy(np.flatnonzero(rows >= 0)); ids = rows[rows >= 0]
            if not len(ids): continue
            step = model.begin(**causal_inputs(d, ids), state=take(state, active)); geo = geometry(d, ids)
            raw['logprior'][ids] = step['logprior'].numpy()
            raw['types'][ids] = model.types(step).numpy()
            raw['movement'][ids] = model.spatial_log_probs(step, **geo, family=torch.full((len(ids),), 8, dtype=torch.long)).numpy()
            # Current command is first consumed AFTER its component forecasts.
            _, post = model.observed(step, **geo, **targets(d, ids))
            state = put(state, active, post); seen[ids] += 1
        for a in raw.values(): a.flush()
    bindings = {str(p.relative_to(ROOT)): digest(p) for p in destination.glob('*.npy')}
    immutable_json(destination/'preserved.json', dict(bindings=bindings, current_answer_in_forecast=False, rows=n))
    if not np.all(seen == 1): raise RuntimeError('Original row accounting changed; outputs preserved')
    actual_dir = WORK/'runs/H01/validation-raw'
    actual = {k: np.load(actual_dir/(k+'.npy'), mmap_mode='r') for k in
        ('prior', 'type_logp', 'family_coordinate', 'prediction', 'conditional_move_target_logp')}
    for k in actual:
        p = actual_dir/(k+'.npy'); expected = report['bindings'][str(p.relative_to(ROOT))]
        if digest(p) != expected: raise RuntimeError('Primary forecasts changed')
        bindings[str(p.relative_to(ROOT))] = expected
    lp = torch.from_numpy(np.array(raw['movement']))
    prior = torch.from_numpy(np.array(raw['logprior']))
    typ = torch.from_numpy(np.array(raw['types']))
    type_marginal = torch.logsumexp(prior[:, :, None]+typ, 1)
    conditional_weight = (prior+typ[:, :, 8]).log_softmax(-1)
    mixture = torch.logsumexp(conditional_weight[:, :, None]+lp, 1)
    modes = lp.argmax(-1).numpy(); winner = mixture.argmax(-1).numpy()
    y = d['raw']['y']; label = d['raw']['py']; move = y == 8
    parity = dict(prior_max_error=float(np.abs(prior.exp().numpy()-actual['prior']).max()),
        type_max_error=float(np.abs(type_marginal.numpy()-actual['type_logp']).max()),
        conditional_mode_mismatches=int((winner != actual['family_coordinate'][:, 8]).sum()),
        target_logp_max_error=float(np.abs(mixture[move, torch.from_numpy(label[move])].numpy()-actual['conditional_move_target_logp'][move]).max()))
    immutable_json(destination/'parity.json', parity)
    if parity['conditional_mode_mismatches'] or max(parity['prior_max_error'], parity['type_max_error'], parity['target_logp_max_error']) > 2e-6:
        raise RuntimeError('Fixed-checkpoint reconstruction mismatch; evidence preserved')
    correct = modes == label[:, None]; available = correct.any(-1)
    conditional_correct = winner == label; typed = actual['prediction'] == 8
    largest = conditional_weight.argmax(-1).numpy(); largest_correct = correct[np.arange(n), largest]
    common_wrong = (modes == modes[:, :1]).all(-1) & ~available
    probabilities = lp.exp().numpy()
    tv = np.max(np.stack([.5*np.abs(probabilities[:, i]-probabilities[:, j]).sum(-1)
        for i in range(4) for j in range(i)]), 0)
    direction = np.load(ROOT/'.cambc/action-predictor/v7/validation-direction.npy')
    results = {}
    for name, mask in [('all_moves', move), ('change', move & (direction == 3)), ('continue', move & (direction == 2))]:
        missed = mask & ~conditional_correct & available
        typed_missed = missed & typed
        results[name] = dict(rows=int(mask.sum()), conditional_correct=int((mask&conditional_correct).sum()),
            complete_correct=int((mask&conditional_correct&typed).sum()), component_mode_oracle=int((mask&available).sum()),
            available_mode_misses=int(missed.sum()), top_weight_correct_but_mixture_wrong=int((missed&largest_correct).sum()),
            correct_mode_only_in_lower_weight_heads=int((missed&~largest_correct).sum()),
            correctly_typed_available_mode_misses=int(typed_missed.sum()),
            typed_top_weight_correct_but_mixture_wrong=int((typed_missed&largest_correct).sum()),
            typed_correct_mode_only_in_lower_weight_heads=int((typed_missed&~largest_correct).sum()),
            common_wrong_modes=int((mask&common_wrong).sum()), frozen_reweighting_upper_bound=int(mask.sum()-(mask&common_wrong).sum()),
            mean_maximum_component_TV=float(tv[mask].mean()),
            mean_distinct_modes=float(np.array([len(np.unique(row)) for row in modes[mask]]).mean()))
    bindings.update({str(p.relative_to(ROOT)): digest(p) for p in (report_path, checkpoint,
        REPORT/'H01-component-analysis-plan.json', ROOT/'tools/action_predictor/segment_policy/component_analysis.py')})
    immutable_json(REPORT/'H01-component-analysis.json', dict(results=results, parity=parity, bindings=bindings,
        scope='New diagnostics from a causal fixed-checkpoint refilter, not an oracle policy, replacement variant or new fit. Component-mode presence is not sufficient for a mixture decision, and absence from every component mode is not alone an impossibility proof. Common-wrong certification fixes emissions/current encoded evidence; it does not constrain retrained models or establish observation insufficiency.',
        new_fits=0, optimizer_updates=0, reserved_opened=0))


if __name__ == '__main__':
    import sys
    freeze() if '--freeze' in sys.argv else run()
