"""Complete-command/category/sequence metrics from preserved causal forecasts."""
import numpy as np
from .data import BASE, WORK, diagnostic_data
from ..movement_experts.evaluate import summary, support, masks, paired
from ..learned_policy.analysis import paired_categories, readiness_flags
from ..observation_metrics import correctness


def read(path):
    with np.load(path) as z: return {k: z[k] for k in z.files}


def consecutive_windows(d, p, length):
    _, correct = correctness(d['raw'], p)
    gap = np.rint(np.expm1(d['transition_gap'][:, 0].astype(np.float64)*8)).astype(np.int64)
    total = exact = 0
    groups = {}
    for sequence in d['sequences']:
        for i in range(length-1, len(sequence)):
            rows = sequence[i-length+1:i+1]
            if not np.all(gap[rows[1:]] == 1): continue
            good = bool(correct[rows].all())
            total += 1; exact += good
            group = str(int(d['raw']['group'][rows[-1]]))
            counts = groups.setdefault(group, [0, 0]); counts[0] += 1; counts[1] += good
    return dict(windows=total, exact=exact, accuracy=exact/total if total else None, groups=groups,
                meaning='Overlapping genuine consecutive own-root windows, teacher-forced past actions; not autonomous rollouts or independent samples')


def assess(arm, data, forecasts):
    results = {}; comparisons = {}
    natural = np.load(BASE.parent/'v9/frequency/natural-mask.npy')
    for split, d in data.items():
        q = diagnostic_data(d, split); raw = d['raw']; p = forecasts[split]
        sampling = {'all': np.ones(len(raw['y']), bool)}
        if split == 'train': sampling.update(natural=natural, augmented_only=~natural)
        out = {}
        pc, joint = correctness(raw, p)
        for name, selected in sampling.items():
            overall = summary(q, p, selected)
            for code, row in enumerate(overall['per_category']):
                m = selected & (raw['y'] == code)
                for key in ('nll', 'type_nll', 'param_nll'):
                    row[key] = float(p[key][m].mean()) if m.any() and not (key == 'param_nll' and code == 11) else None
            out[name] = dict(overall=overall, contexts={k: summary(q, p, selected&m) for k, m in masks(q).items()})
        typed = p['prediction'] == raw['y']; shop = raw['y'] == 11
        out['failures'] = dict(wrong_type=int((~typed).sum()), wrong_arguments_after_correct_type=int((typed&~joint&~shop).sum()),
            typed_shop_unavailable=int((typed&shop).sum()))
        out['partial_legality'] = support(q, p)
        out['partial_readiness'] = readiness_flags(raw, p)
        move = raw['y'] == 8
        modes = np.asarray(p['component_move_modes'])
        available = (modes == raw['py'][:, None]).any(1)
        common_wrong = (modes == modes[:, :1]).all(1) & ~available
        out['execution'] = {}
        for name, m in [('all_moves', move), ('change', move & (q['direction'] == 3)),
                        ('continue', move & (q['direction'] == 2))]:
            typed_miss = m & typed & ~joint
            conditional = pc & m
            out['execution'][name] = dict(rows=int(m.sum()), conditional_exact=int(conditional.sum()), joint_exact=int((joint&m).sum()),
                component_mode_oracle=int((available&m).sum()), available_mode_not_selected=int((available&~pc&m).sum()),
                correctly_typed_available_mode_misses=int((typed_miss&available).sum()),
                correctly_typed_no_component_mode=int((typed_miss&~available).sum()),
                common_wrong_modes=int((common_wrong&m).sum()), conditional_reweight_upper_bound=int(m.sum()-(common_wrong&m).sum()),
                mean_target_rank=float(p['move_target_rank'][m].mean()) if m.any() else None,
                conditional_nll=float(-p['conditional_move_target_logp'][m].mean()) if m.any() else None,
                mean_distinct_component_modes=float(np.array([len(np.unique(v)) for v in modes[m]]).mean()) if m.any() else None)
        out['memory'] = dict(reset_rows=int(p['reset'].sum()), mean_prior=np.asarray(p['prior']).mean(0).tolist(),
            mean_prior_entropy=float(-(p['prior']*np.log(np.maximum(p['prior'], 1e-300))).sum(1).mean()),
            note='State usage/diversity does not establish objective identity or useful strategy; duration/age saved separately when applicable')
        if 'expected_age' in p:
            out['memory'].update(mean_state_conditional_age=p['expected_age'].mean(0).tolist(),
                mean_state_conditional_termination=p['termination_probability'].mean(0).tolist())
        out['sequential'] = {str(k): consecutive_windows(d, p, k) for k in (2, 4, 8)}
        results[split] = out
        if split == 'validation':
            refs = {'G00': d['baseline'], 'L02': read(BASE.parent/f'v16/runs/L02/{split}-predictions.npz'),
                    'JP02': read(BASE.parent/f'v27/JP02-{split}-predictions.npz')}
            if arm == 'H01': refs['H00'] = read(WORK/f'runs/H00/{split}-predictions.npz')
            comparisons = {k: dict(categories=paired_categories(raw, p, o, sampling['all']),
                contexts=paired(q, p, o)) for k, o in refs.items()}
    return results, comparisons
