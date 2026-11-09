"""Additive command, parameter, goal-state and regression diagnostics."""
import json
import sys
from pathlib import Path
import numpy as np
from .sequence_data import ROOT, BASE, WORK, REPORT, JOBS
from ..audit import immutable_json
from ..data import digest
from .. import reliable_train as rt
from ..observation_metrics import correctness, group_samples, interval
from ..movement_experts.evaluate import summary, support


def read(path):
    with np.load(path) as z:
        return {k: z[k] for k in z.files}


def readiness_flags(raw, p):
    """Reuse historical partial checks, separate from attempted-move masks."""
    alive = raw['hp_alive']; free = raw['channel'] == 0
    flags, restrictions = raw['flags'], raw['restrictions']
    checks = dict(attack=alive & free & ((flags & 2) != 0) & ((restrictions & 2) == 0),
                  ward=alive & free & (raw['ward_charges'] > 0),
                  submit=alive & free & (raw['gems'] > 0),
                  recall=alive & free, shop=raw['shop'])
    for slot in (0, 1):
        checks[f'cast_{slot}'] = alive & free & raw['ability_ready'][:, slot] & ((flags & 1024) != 0) & ((restrictions & 4) == 0)
    return dict(by_predicted_family={name:dict(assessed=int((p['prediction'] == rt.LABELS.index(name)).sum()),
        flagged=int(((p['prediction'] == rt.LABELS.index(name)) & ~ok).sum())) for name, ok in checks.items()},
        full_engine_legality=None, meaning='Historical partial readiness/resource formulas reused from reliable_train.invalid_rate. Not complete SDK target/range/identity legality. Successful-move and blocked-attempt mask rejections are reported separately, never pooled into an illegal-success rate.')


def freeze():
    immutable_json(REPORT / 'analysis-plan.json', dict(
        purpose='Diagnose learned sequential policy without changing the two-fit design, support, checkpoints, thresholds or seeds.',
        contexts=['natural vs augmented TRAIN', 'DEV original whole groups',
                  'each action', 'move continuation/change/startup', 'true-root gap 1/2-16/>16',
                  'goal-target availability for diagnostic only', 'historical engine (confounded by groups)'],
        goals='Prior entropy/usage and within-row world-goal separation; world-goal expected distance, effective root-gap retention, goal-forecast NLL and support. These measure state behavior, NOT Fish intent or strategic success.',
        comparisons='G00 and available B00/S00/X00; L01 directly vs L00. 2000 paired whole-group bootstrap draws seed20261106, fixed14named-action macro. Alltrue-family vs correctlytyped parameter and joint accuracy separate. Empty denominator null.',
        deployment='Teacher-forced replay filtering after earlier actual Fish commands differs from closed-loop own-action filtering. SDK dispatch tracing is not a match, legality certification or playing-strength evaluation.',
        prospective_interventions='After selected L01, optional fixed-output sensitivity: reset persistent state and zero goal_condition projection independently, without retraining/checkpoint selection. Interpret as dependence under distribution change, not causal identification of Fish intent. Do not automatically run more fits.',
        likelihood='Normalized observed representation, spatial mixture/latent modes marginalized consistently for MAP and likelihood; shop is a marginalized type bucket with unavailable arguments and strict failure.',
        new_fits=0, reserved_opened=0))


def paired_categories(raw, p, reference, mask):
    groups = np.unique(raw['group']); rng = np.random.default_rng(20261106)
    draws = np.stack([np.bincount(rng.integers(len(groups), size=len(groups)), minlength=len(groups)) for _ in range(2000)])
    pc, j = correctness(raw, p); oc, o = correctness(raw, reference)
    def counts(m): return np.array([(m & (raw['group'] == g)).sum() for g in groups])
    def ratio(a, b): return np.divide(a, b, out=np.full(a.shape, np.nan, float), where=b > 0)
    a = group_samples(raw, p, mask, draws, groups)
    b = group_samples(raw, reference, mask, draws, groups)
    result = {'overall': dict(rows=int(mask.sum()), rescues=int((j & ~o & mask).sum()),
        regressions=int((~j & o & mask).sum()),
        paired95={key:interval(a[key] - b[key]) for key in ('joint_accuracy','macro_f1','joint_nll')},
        group_net={str(int(g)):int(((j.astype(np.int64)-o.astype(np.int64))*mask*(raw['group']==g)).sum()) for g in groups})}
    for code, name in enumerate(rt.LABELS):
        m = mask & (raw['y'] == code)
        pt = m & (p['prediction'] == code); ot = m & (reference['prediction'] == code)
        both = pt & ot; n = int(m.sum())
        row = dict(support=n, rescues=int((j & ~o & m).sum()), regressions=int((~j & o & m).sum()),
                   mean_nll_difference=float((p['nll'][m] - reference['nll'][m]).mean()) if n else None,
                   targeting={})
        for key, a, ad, b, bd in (
            ('joint', j & m, m, o & m, m),
            ('all_true_family_parameter', pc & m, m, oc & m, m),
            ('correctly_typed_parameter', j & pt, pt, o & ot, ot),
            ('matched_correctly_typed_parameter', j & both, both, o & both, both)):
            if name not in ('altar', 'attack', 'blocked', 'cast_0', 'cast_1', 'move', 'priority', 'submit', 'teleport', 'ward') and key != 'joint':
                row['targeting'][key] = None; continue
            row['targeting'][key] = dict(new_correct=int(a.sum()), new_support=int(ad.sum()),
                                        reference_correct=int(b.sum()), reference_support=int(bd.sum()),
                                        paired95=interval(ratio(draws @ counts(a), draws @ counts(ad)) - ratio(draws @ counts(b), draws @ counts(bd))))
        sums = np.array([(p['nll'][m & (raw['group'] == g)] - reference['nll'][m & (raw['group'] == g)]).sum() for g in groups])
        row['nll_difference_paired95'] = interval(ratio(draws @ sums, draws @ counts(m)))
        result[name] = row
    return result


def run(identifier):
    freeze(); result = {}; comparisons = {}; bindings = {}
    for split in ('train', 'validation'):
        raw = read(BASE / 'combined-train.npz' if split == 'train' else BASE.parent / 'v4/validation.npz')
        path = WORK / f'runs/{identifier}/{split}-predictions.npz'; p = read(path)
        assert np.isfinite(p['nll']).all() and (p['nll'] >= -1e-5).all()
        np.testing.assert_allclose(p['type_nll'] + p['param_nll'], p['nll'], atol=2e-5, rtol=0)
        gp = WORK / f'runs/{identifier}/{split}-goals.npz'; goals = read(gp)
        target = read(WORK / f'{split}-goals.npz'); seq = read(WORK / f'{split}-sequences.npz')
        gap = np.empty_like(seq['gap']); gap[seq['order']] = seq['gap']
        root_gap = np.rint(np.expm1(gap[:, 0].astype(np.float64) * 8)).astype(np.int64)
        direction = np.load(BASE.parent / f'v7/{split}-direction.npy')
        d = dict(raw=raw, direction=direction,
                 available=np.load(BASE.parent / f'v7/{split}-available.npy'),
                 near=np.load(BASE.parent / f'v7/{split}-near_obstacle.npy'))
        sampling = {'all': np.ones(len(raw['y']), bool)}
        if split == 'train':
            natural_path = BASE.parent / 'v9/frequency/natural-mask.npy'
            assert digest(natural_path) == '09217d8fc3d5673d980c8b8a4434861aa26dddb37e506bbfa22cbaafc0e525bd'
            bindings[str(natural_path.relative_to(ROOT))] = digest(natural_path)
            sampling['natural'] = np.load(natural_path)
        pc, joint = correctness(raw, p)
        contexts = {'move_continue': (raw['y'] == 8) & (direction == 2),
                    'move_change': (raw['y'] == 8) & (direction == 3),
                    'move_startup': (raw['y'] == 8) & (direction == 1),
                    'root_gap_1': root_gap == 1,
                    'root_gap_2_16': (root_gap > 1) & (root_gap <= 16),
                    'root_gap_over16': root_gap > 16,
                    'goal_target_available_diagnostic': target['goal_target_available'],
                    'goal_target_unavailable_diagnostic': ~target['goal_target_available']}
        engine = np.empty(len(joint), np.int8)
        for job in json.loads(JOBS.read_text()):
            if job['split'] == split:
                engine[job['offset']:job['offset'] + job['rows']] = int(job['record']['engine_version'][0])
        contexts.update({f'engine_{v}': engine == v for v in np.unique(engine)})
        summaries = {}
        for name, mask in sampling.items():
            categories = []
            for code, action in enumerate(rt.LABELS):
                m = mask & (raw['y'] == code); typed = m & (p['prediction'] == code); n = int(m.sum())
                categories.append(dict(action=action, support=n,
                    wrong_type=int((m & ~typed).sum()), wrong_argument_after_correct_type=int((typed & ~joint).sum()) if action != 'shop' else None,
                    typed_missing_shop_arguments=int(typed.sum()) if action == 'shop' else 0,
                    observed_nll=float(p['nll'][m].mean()) if n else None,
                    type_nll=float(p['type_nll'][m].mean()) if n else None,
                    parameter_nll=float(p['param_nll'][m].mean()) if n and action != 'shop' else None))
            classified_failures = sum(c['wrong_type'] + (c['wrong_argument_after_correct_type'] or 0) + c['typed_missing_shop_arguments'] for c in categories)
            assert classified_failures == int((mask & ~joint).sum())
            prior = goals['prior'][mask]; entropy = -(prior * np.log(prior.clip(1e-30))).sum(-1)
            geometry_rows = mask & target['position_known']
            worlds = goals['world'][geometry_rows]; separation = np.abs(worlds[:, :, None] - worlds[:, None, :]).max(-1) * 32
            gm = mask & np.isfinite(goals['achievement_nll'])
            g = dict(rows=int(mask.sum()), mean_prior=prior.mean(0).tolist(),
                     prior_argmax_usage=np.bincount(prior.argmax(-1), minlength=4).tolist(),
                     mean_prior_entropy=float(entropy.mean()),
                     known_origin_goal_geometry_support=int(geometry_rows.sum()),
                     median_max_pairwise_goal_tile_distance=float(np.median(separation.max((1, 2)))) if geometry_rows.any() else None,
                     effective_gap_retention_quantiles=np.quantile(goals['retention'][mask], [0, .25, .5, .75, 1]).tolist(),
                     achieved_target_support=int(gm.sum()),
                     achieved_position_nll=float(goals['achievement_nll'][gm].mean()) if gm.any() else None)
            if gm.any():
                predicted = (goals['prior'][gm, :, None] * goals['world'][gm]).sum(1) * 32
                truth = target['achieved_position'][gm] * 32
                hold = target['position'][gm] * 32
                predicted_error = np.abs(predicted - truth).max(-1)
                hold_error = np.abs(hold - truth).max(-1)
                g['achieved_position_diagnostic'] = dict(
                    support=int(gm.sum()),
                    predicted_prior_mean_chebyshev_tile_error=float(predicted_error.mean()),
                    current_position_hold_chebyshev_tile_error=float(hold_error.mean()),
                    predicted_prior_mean_rounded_exact=int((np.rint(predicted) == truth).all(-1).sum()),
                    current_position_hold_exact=int((hold == truth).all(-1).sum()),
                    demonstrated_displacement_quantiles=np.quantile(hold_error, [0, .25, .5, .75, .9, 1]).tolist(),
                    meaning='One prior-weighted predicted waypoint, never best component chosen using future truth. Continuous Gaussian goal-density NLL is separate from command probability and strategic intent.')
            summaries[name] = dict(overall=summary(d, p, mask), category_losses_and_failures=categories,
                                   contexts={k: summary(d, p, mask & m) for k, m in contexts.items()}, goal_behavior=g)
        result[split] = dict(sampling=summaries, movement_support_and_partial_legality=support(d, p),
                            partial_readiness_resource_diagnostic=readiness_flags(raw, p))
        if split == 'train':
            result[split]['natural_sampling_qualification'] = ('Natural membership is identity-verified, but these selected-checkpoint predictions traverse the original augmented actor stream. The extra selected actions affect transition-gap features and, for L01, latent filter updates. Natural-row point scores are in-sample diagnostics, not a matched natural-cadence replay or evidence isolating group shift. Root-gap strata are reported separately; no nonconsecutive rows are stitched.')
        run_metrics = {}
        for width in (2, 4, 8):
            blocks = []
            for a, b in zip(seq['offsets'][:-1], seq['offsets'][1:]):
                ids = seq['order'][a:b]
                cuts = np.r_[0, np.flatnonzero(root_gap[ids][1:] > 1) + 1, len(ids)]
                for left, right in zip(cuts[:-1], cuts[1:]):
                    run = ids[left:right]
                    for at in range(0, len(run) - width + 1, width):
                        blocks.append(run[at:at + width])
            if blocks:
                blocks = np.stack(blocks)
                run_metrics[str(width)] = dict(nonoverlapping_windows=len(blocks),
                    all_commands_exact=int(joint[blocks].all(1).sum()),
                    all_commands_exact_fraction=float(joint[blocks].all(1).mean()),
                    mean_window_observed_nll=float(p['nll'][blocks].sum(1).mean()),
                    support_by_group={str(int(g)):int((raw['group'][blocks[:, 0]] == g).sum()) for g in np.unique(raw['group'])})
            else: run_metrics[str(width)] = dict(nonoverlapping_windows=0, all_commands_exact_fraction=None)
        result[split]['consecutive_root_command_runs'] = dict(windows=run_metrics,
            interpretation='Nonoverlapping windows within genuine consecutive selected own roots, reset at every unobserved action gap/actor boundary. Teacher-forced personal observations/past commands; not autonomous rollouts or strategic-success percentages. All original rows also remain in the full benchmark.')
        bindings[str(path.relative_to(ROOT))] = digest(path); bindings[str(gp.relative_to(ROOT))] = digest(gp)
        if split == 'validation':
            refs = dict(G00=BASE.parent / 'v9/runs/G00/validation-predictions.npz',
                        B00=BASE.parent / 'v13/runs/B00/validation-predictions.npz',
                        S00=BASE.parent / 'v15/runs/S00/validation-predictions.npz',
                        X00=BASE.parent / 'v15/runs/X00/validation-predictions.npz')
            if identifier == 'L01': refs['L00'] = WORK / 'runs/L00/validation-predictions.npz'
            for name, ref in refs.items():
                if ref.exists():
                    reference = read(ref)
                    if 'family_commands' in reference:
                        # B00 stores its selected command coordinate in the
                        # coordinate field. Reconstruct true-family diagnostics
                        # only from its archived all-family conditional modes.
                        reference['coordinate'] = reference['family_commands'][np.arange(len(raw['y'])), raw['y'], 1]
                        reference['priority'] = reference['family_commands'][:, 9, 2]
                    comparisons[name] = paired_categories(raw, p, reference, sampling['all'])
                    bindings[str(ref.relative_to(ROOT))] = digest(ref)
    immutable_json(REPORT / f'{identifier}-analysis.json', dict(
        results=result, category_comparisons=comparisons, bindings=bindings,
        source_sha256=digest(__file__), analysis_plan_sha256=digest(REPORT / 'analysis-plan.json'),
        limitation='In-sample TRAIN; reused five DEV groups/checkpoint selection, not untouched or three-seed evidence. Goal states are learned hypotheses, not identified Fish intent. Complete executable bot and closed-loop playing strength remain unproven.',
        new_fits=0, reserved_opened=0))


if __name__ == '__main__':
    run(sys.argv[1])
