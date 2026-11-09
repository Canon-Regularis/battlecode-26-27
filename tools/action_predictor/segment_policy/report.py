"""Additive saved-output report; no fitting or checkpoint reselection."""
import json
from pathlib import Path
import numpy as np
from ..audit import immutable_json
from ..data import digest
from ..learned_policy.analysis import paired_categories
from .data import ROOT, BASE, WORK, REPORT


def read(path):
    with np.load(path) as z: return {k: z[k] for k in z.files}


def run():
    path = REPORT/'H00.json'
    report = json.loads(path.read_text())
    raw = read(BASE.parent/'v4/validation.npz')
    selected_path = WORK/'runs/H00/validation-predictions.npz'
    selected = read(selected_path)
    initial_path = WORK/'runs/H00/initial-validation-diagnostic/predictions.npz'
    initial = read(initial_path)
    value = paired_categories(raw, selected, initial, np.ones(14439, bool))
    immutable_json(REPORT/'H00-initial-comparison.json', dict(comparison=value,
        scope='Saved selected checkpoint versus registered nonselectable roundzero, not a new model or retrospective endpoint choice. Both use causal direct recurrence and the same normalized joint decoder; this does not isolate memory benefit from other trained paths.',
        bindings={str(p.relative_to(ROOT)): digest(p) for p in (path, selected_path, initial_path, Path(__file__))},
        new_fits=0, reserved_opened=0))
    r = report['results']['validation']; overall = r['all']['overall']
    categories = {v['action']: v for v in overall['per_category']}
    lines = ['# H00 direct sequence control: negative against JP02', '',
        f"Selected round{report['selected_round']}of{report['completed_rounds']}; {report['selected_updates']:,}selected/{report['completed_updates']:,}completed updates. All433071TRAIN and14439DEV decisions retained. Fresh independent review pending; no promotion or repeat seeds.", '',
        '| Policy | Complete DEV /14,439 | Joint movement /2,362 | Conditional movement | Macro F1 | Joint NLL |',
        '| --- | ---: | ---: | ---: | ---: | ---: |',
        '| G00 | 11,510 | 1,318 | 1,434 | 0.632394 | 0.726556 |',
        '| JP02 | 12,137 | 1,364 | 1,428 | 0.620048 | 0.629052 |',
        f"| H00 | {overall['strict_correct']:,} | 1,322 | 1,406 | {overall['macro_f1']:.6f} | {overall['joint_nll']:.6f} |", '',
        'H00 loses46complete commands against JP02 through135rescues/181regressions. The exploratory paired whole-group accuracy interval is−0.552to−0.080percentagepoints; NLL worsens by0.00913with interval+0.00289to+0.01658. Five reused DEV groups and selected checkpoints limit inference; these are not selection-adjusted or untouched evidence.', '',
        'Movement changes gain8joint commands (272→280), but continuation loses50 (1089→1039). Conditional changes gain15(304→319); conditional continuation loses37(1121→1084). Thus this direct configuration repeats an unfavorable continuation/change tradeoff. It does not establish a cause in capacity, optimization, representation or observation sufficiency.', '',
        'Of1040wrong movement commands,196have wrong types and844have wrong destinations after correct typing. Every recorded movement destination remains in the retained window/map/success mask. Conditional target rank averages1.96overall and2.78onchanges, but favorable bounded ranks are not exact accuracy. No missing movement vocabulary explanation is established.', '',
        'Against G00 the net581command gain includes531recalls; the stronger JP02 comparison is negative. Priority exact integers remain the same248/576RC01modes: H00 did not train a new integer model. Attack conditional correctness remains943/985 andcast0remains193/213. Cast1falls146→141/243againstG00, slightly exceeding the original0.02conditional-targeting regression guard. All binding category/macro/movement/likelihood/three-seed requirements remain unmet.', '',
        '| Category | Support | Complete correct | Type TP | Type FP | Conditional argument exact |',
        '| --- | ---: | ---: | ---: | ---: | ---: |']
    for name, row in categories.items():
        if name == '<unknown>': continue
        conditional = row['all_true_family_parameter_accuracy']
        conditional = '—' if conditional is None else f'{conditional:.4f}'
        lines.append(f"| {name} | {row['support']} | {row['joint_correct']} | {row['type_TP']} | {row['type_FP']} | {conditional} |")
    lines += ['', 'TRAIN complete counts:344783/433071all,248962/288801natural-membership,95821/144270augmentation-only. These membership strata use augmented traversal and are not matched natural-cadence or held-out policy evaluations. Natural-TRAIN changing destinations are6818/22279andcontinuation23971/25918; fitting and transfer must remain separate.', '',
        'Sequential diagnostics count only genuinely consecutive own-root windows:6868/10496two-command,1795/4250four-command and49/194eight-command windows exactly correct. Windows overlap and earlier recorded actions are teacher-forced; these are not autonomous rollouts or playing-strength measurements.', '',
        'Partial movement-mask checks flag0successful-move predictions and40blocked-attempt predictions. Blocked rejection is not an illegal successful move. Full legality and global calibration remain unassessed. Every43shop row remains a strict failure with purchase-argument likelihood absent. Altar/teleport/submit remain sparse/uncertified; coordinate agreement retains entity-identity ambiguity.', '',
        'Before any hierarchy fit, resolve the effective input asymmetry: direct recurrence explicitly stores earlier integer arguments; the original H01 prototype shares a fixed priority likelihood across states, so that integer information cancels from its posterior. The no-update input-contract probe establishes this mechanism but not its contribution to Fish errors. H01 is unrun; this direct result cannot certify an unchanged hierarchy contrast.', '',
        'The exact sampler reconstruction matches all12RNGstates and20910updates. Only6–16batches per round contain fewer than64rows (157–409rows); the last128updates span77–87groups. Group mean loss coefficients can be nonuniform, but this does not show a dominant tail-group explanation, especially under clipping/Adam. The Windows path-string hash error is corrected additively inH00-sampler-provenance-correction.json; schedules and measurements are unchanged.', '',
        'The measured1863.74seconds begin after setup and include optimization, DEV passes, final inference/serialization/assessment and concurrent diagnostic contention. This is not pure optimization, total experiment preparation or serving latency.', '',
        'Existing personally observed identity inputs and longer cached sequences are opportunities for a later grounded-objective study, not part of H00 and not learned intent. Both reserved75-game partitions remain sealed. No matches, new replay queries/downloads, bot/runtime work or deployment occurred.', '',
        'Reproduce: `python -m tools.action_predictor.segment_policy.fit H00` only in a fresh unused run namespace under the preserved protocol; never overwrite the existing run. Saved-output report: `python -m tools.action_predictor.segment_policy.report`.']
    output = REPORT/'H00-REPORT.md'
    if output.exists(): raise FileExistsError('Preserve report')
    output.write_text('\n'.join(lines)+'\n', encoding='utf-8')
    inventory = {str(p.relative_to(ROOT)): digest(p) for p in (path, output, Path(__file__),
        REPORT/'H00-initial-diagnostic.json', REPORT/'H00-initial-comparison.json',
        REPORT/'H00-sampler-diagnostic.json', REPORT/'H00-sampler-provenance-correction.json',
        REPORT/'prior-command-information-probe.json', REPORT/'protocol.json')}
    for p in (WORK/'sampler-diagnostic').glob('*.npz'): inventory[str(p.relative_to(ROOT))] = digest(p)
    immutable_json(REPORT/'H00-completion-supplement.json', dict(bindings=inventory,
        primary_report_sha256=digest(path), checkpoint_sha256=report['checkpoint_sha256'],
        execution_source_commit=report['source_commit'], new_fits=0, reserved_opened=0,
        reproduction=['python -m tools.action_predictor.segment_policy.initial_diagnostic',
            'python -m tools.action_predictor.segment_policy.input_contract_probe',
            'python -m tools.action_predictor.segment_policy.sampler_diagnostic',
            'python -m tools.action_predictor.segment_policy.report'],
        warning='Producers preserve existing outputs and refuse overwrites. Reuse bound artifacts; rerun in a separately versioned namespace only when new evidence requires it. Sampler source-field correction has its exact saved arithmetic command/provenance in the parent thread.'))


if __name__ == '__main__': run()
