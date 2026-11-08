"""Predeclared saved-output comparisons including strongest retained controls."""
import json
import numpy as np
from ..audit import immutable_json
from ..data import digest
from ..order_information.anchored import committed_manifest
from ..learned_policy.analysis import paired_categories
from ..movement_experts.evaluate import paired
from ..observation_metrics import correctness
from .data import ROOT, WORK, REPORT

REFERENCE = '01534f48277e671050dfc5e6438710bc128de003'


def read(path):
    with np.load(path) as z: return {k: z[k] for k in z.files}


def freeze():
    bindings = {}; references = {}
    def receipt(relative):
        value, more = committed_manifest(REFERENCE, relative)
        bindings.update(more)
        return value
    original = receipt('tools/action_predictor/experiments/v30/protocol.json')
    bindings.update(original['inputs'])
    h00 = receipt('tools/action_predictor/experiments/v30/H00.json')
    references['H00'] = dict(path='.cambc/action-predictor/v30/runs/H00/validation-predictions.npz',
        sha256={k.replace('\\', '/'): v for k, v in h00['bindings'].items()}['.cambc/action-predictor/v30/runs/H00/validation-predictions.npz'])
    g00 = receipt('tools/action_predictor/experiments/v9/G00.json')
    references['G00'] = dict(path='.cambc/action-predictor/v9/runs/G00/validation-predictions.npz', sha256=g00['predictions_sha256'])
    l02 = receipt('tools/action_predictor/experiments/v16/L02.json')
    references['L02'] = dict(path='.cambc/action-predictor/v16/runs/L02/validation-predictions.npz', sha256=l02['predictions_sha256']['validation'])
    for name in ('AB00', 'AB01'):
        value = receipt('tools/action_predictor/experiments/v28/'+name+'-completion.json')
        key = '.cambc/action-predictor/v28/runs/'+name+'/validation-predictions.npz'
        references[name] = dict(path=key, sha256={k.replace('\\', '/'): v for k, v in value['bindings'].items()}[key])
    normalized = {k.replace('\\', '/'): v for k, v in original['inputs'].items()}
    key = '.cambc/action-predictor/v27/JP02-validation-predictions.npz'
    references['JP02'] = dict(path=key, sha256=normalized[key])
    for ref in references.values():
        if digest(ROOT/ref['path']) != ref['sha256']: raise RuntimeError('Frozen comparison changed')
    immutable_json(REPORT/'H01-matched-analysis-plan.json', dict(references=references,
        bindings=bindings, source_sha256=digest(__file__),
        purpose='Judge selected H01 against direct H00 and retained G00/L02/JP02/AB00/AB01, not only a weaker control.',
        rule='Selected original fullDEVNLLcheckpoint only; identical complete-command and conditional schemas/denominators. No variant selection or new threshold tuning.',
        allocation_clarification='Original24jointmove/12changingdestination exploratory criteria are retained; report BOTH conditional and joint change gains rather than choosing the favorable interpretation. Other original numeric guards and binding targets unchanged. This is not duration-specific attribution or automatic promotion.',
        uncertainty='2000pairedwholegroupdrawsseed20261106, five reusedDEVgroups, exploratory/notselectionadjusted. NaturalTRAIN strata remain in-sample under augmented traversal.',
        new_fits=0, reserved_opened=0))


def run():
    plan_path = REPORT/'H01-matched-analysis-plan.json'; plan = json.loads(plan_path.read_bytes())
    if digest(__file__) != plan['source_sha256']: raise RuntimeError('Planned report producer changed')
    report_path = REPORT/'H01.json'; h = json.loads(report_path.read_bytes())
    selected_path = WORK/'runs/H01/validation-predictions.npz'
    if digest(selected_path) != h['bindings'][str(selected_path.relative_to(ROOT))]:
        raise RuntimeError('Selected predictions changed')
    p = read(selected_path)
    raw_path = ROOT/'.cambc/action-predictor/v4/validation.npz'
    if digest(raw_path) != '01a15e1e10f68922334a5367bb825c8ef9bbe228ae7a9e86e92aae9609b204ed':
        raise RuntimeError('Original DEV changed')
    raw = read(raw_path)
    direction = np.load(ROOT/'.cambc/action-predictor/v7/validation-direction.npy')
    context = dict(raw=raw, direction=direction,
        available=np.load(ROOT/'.cambc/action-predictor/v7/validation-available.npy'),
        near=np.load(ROOT/'.cambc/action-predictor/v7/validation-near_obstacle.npy'))
    comparisons = {}; counts = {}
    def count(forecast):
        parameter, joint = correctness(raw, forecast)
        matrix = np.bincount(raw['y']*15+forecast['prediction'], minlength=225).reshape(15, 15)
        f1 = 2*matrix.diagonal()/np.maximum(matrix.sum(0)+matrix.sum(1), 1)
        result = dict(complete=int(joint.sum()), macro_F1=float(f1[1:].mean()), joint_NLL=float(forecast['nll'].mean()),
            conditional_mode_ceiling_with_fixed_family_conditionals=int((parameter&(raw['y'] != 11)).sum()))
        for key, mask in [('move', raw['y'] == 8), ('change', (raw['y'] == 8)&(direction == 3)),
                          ('continue', (raw['y'] == 8)&(direction == 2))]:
            result[key] = dict(support=int(mask.sum()), joint=int((mask&joint).sum()), conditional=int((mask&parameter).sum()))
        return result
    counts['H01'] = count(p)
    bindings = {str(x.relative_to(ROOT)): digest(x) for x in (report_path, selected_path, raw_path, plan_path,
        ROOT/'tools/action_predictor/segment_policy/matched_report.py')}
    for name, ref in plan['references'].items():
        path = ROOT/ref['path']
        if digest(path) != ref['sha256']: raise RuntimeError('Reference forecast changed')
        reference = read(path); counts[name] = count(reference)
        comparisons[name] = dict(categories=paired_categories(raw, p, reference, np.ones(14439, bool)),
                                contexts=paired(context, p, reference))
        bindings[ref['path']] = ref['sha256']
    component = json.loads((REPORT/'H01-component-analysis.json').read_bytes())
    bindings[str((REPORT/'H01-component-analysis.json').relative_to(ROOT))] = digest(REPORT/'H01-component-analysis.json')
    n = counts['H01']; c = counts['H00']
    numerical = dict(joint_move_gain_at_least24=n['move']['joint']-c['move']['joint'] >= 24,
        joint_change_gain_at_least12=n['change']['joint']-c['change']['joint'] >= 12,
        conditional_change_gain_at_least12=n['change']['conditional']-c['change']['conditional'] >= 12,
        observed_NLL_below_direct=n['joint_NLL'] < c['joint_NLL'],
        continuation_loss_at_most_half_pp=(n['continue']['joint']-c['continue']['joint'])/1198 >= -.005)
    immutable_json(REPORT/'H01-matched-analysis.json', dict(counts=counts, comparisons=comparisons,
        numerical_exploratory_conditions=numerical, component_results=component['results'], bindings=bindings,
        scope='Combined architecture contrast; no isolated duration/grounding/intent claim. Oracle conditional caps hold current family conditionals fixed and are not architecture ceilings. Numerical allocation conditions alone do not establish no other-category regression or original success.',
        new_fits=0, reserved_opened=0, promoted=False))
    lines = ['# H01 corrected neural semi-Markov hierarchy', '',
        f"Selected round{h['selected_round']}of{h['completed_rounds']}; {h['selected_updates']:,}selected/{h['completed_updates']:,}completed updates. Original fullDEVNLLcheckpoint rule, every original TRAIN/DEV row retained. Fresh post-fit review pending; no promotion.", '',
        '| Predictor | Complete /14,439 | Joint move /2,362 | Conditional move | Joint change /1,158 | Joint continuation /1,198 | Macro F1 | Joint NLL |',
        '| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |']
    for name in ('G00', 'L02', 'JP02', 'AB00', 'AB01', 'H00', 'H01'):
        r = counts[name]
        lines.append(f"| {name} | {r['complete']} | {r['move']['joint']} | {r['move']['conditional']} | {r['change']['joint']} | {r['continue']['joint']} | {r['macro_F1']:.6f} | {r['joint_NLL']:.6f} |")
    lines += ['', 'All comparisons retain the original action/parameter definitions. Conditional destinations are recorded-family diagnostics; actual complete commands use predicted families and normalized joint MAP. The JSON includes paired groups, categories, targeting guards, false positives and context losses. Improving only relative to the weaker direct control would not establish improved imitation against stronger retained predictors.', '',
        f"Numerical exploratory conditions versus H00: `{numerical}`. Both conditional and joint change gains are shown; there is no favorable posthoc choice between them. Original category/macro/movement/loss/targeting/three-seed targets remain binding; no robustness or untouched-test claim.", '',
        'The repaired previous-command buffer is written after prediction and cleared at identical gaps. Only transitions/hazards gain21inputs; initial128inputlayer and original weights/RNG are preserved. This compares a combined discrete state/age inference and conditioned-execution policy with continuous recurrence, not isolated duration benefit. DEVselectedruns reach at most15roots, unknown prefixes are explicit, and BPTT detaches every8nodes. State lifetimes do not establish Fish objectives.', '',
        'Component diagnostics distinguish available-mode misses, mixture-shape effects and common-wrong execution limits. A component-mode union is not achieved accuracy or a full mixture ceiling. Frozen common-wrong bounds do not prove observation insufficiency and can change when execution or encoded observations change. State indices have no assigned semantic labels.', '',
        'Natural/augmentation-only TRAIN metrics in H01.json are in-sample row-membership strata under augmented traversal, not held-out policy or natural-cadence evidence. Sequential windows overlap and use earlier recorded Fish actions after occurrence; they are not autonomous execution. Five repeatedly reused DEV groups, one seed, selected checkpoints and engine/group confounding limit inference.', '',
        'All43shop rows remain strict failures; purchase-argument likelihood is absent. Sparse altar/teleport/submit cannot certify reliability. Ambiguous entity identity, full legality and global calibration remain unresolved. Successful-move mask rejection is separate from blocked-attempt rejection. Both reserved75gamepartitions stay sealed, with no matches, downloads, proposed-action simulations or bot/runtime/deployment work.', '',
        'Reproduce saved-output analysis: `python -m tools.action_predictor.segment_policy.component_analysis` then `python -m tools.action_predictor.segment_policy.matched_report`. Producers refuse overwrites; reuse hash-bound artifacts. Fit command is preserved as `python -m tools.action_predictor.segment_policy.hierarchy_fit H01`, executable only under the immutable reviewed amendment and in an unused namespace.']
    output = REPORT/'H01-REPORT.md'
    if output.exists(): raise FileExistsError('Preserve report')
    output.write_text('\n'.join(lines)+'\n', encoding='utf-8')
    bindings[str(output.relative_to(ROOT))] = digest(output)
    immutable_json(REPORT/'H01-completion-supplement.json', dict(bindings=bindings,
        primary_report_sha256=digest(report_path), selected_checkpoint_sha256=h['checkpoint_sha256'],
        primary_execution_source_commit=h['source_commit'], new_fits=0, reserved_opened=0))


if __name__ == '__main__':
    import sys
    freeze() if '--freeze' in sys.argv else run()
