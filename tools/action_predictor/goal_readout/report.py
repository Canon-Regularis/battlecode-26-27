"""Concise interpretation of a saved readout fit; no variant selection."""
import argparse
import json
from .protocol import OUT, ARMS, V16_REPORT
from ..audit import immutable_json
from ..data import digest


def run(identifier):
    info = json.loads((OUT / f'{identifier}.json').read_text())
    evidence = json.loads((OUT / f'{identifier}-evaluation.json').read_text())
    old = json.loads((V16_REPORT / 'L02.json').read_text())
    current = evidence['results']['validation']['all']
    baseline = old['results']['validation']['all']
    lines = [f'# {identifier}: frozen-upstream execution readout', '',
        ('Dynamic causal predicted geometry.' if ARMS[identifier] else 'TRAIN-mean geometry control.'),
        'One shared frozen L02 checkpoint supplies forecasts, latent representations, priors and '
        'baseline causal filtering. Only existing execution heads and the conditioning projection '
        'are trained. This changes several training freedoms versus L02; only the matched U01-U00 '
        'comparison isolates the named geometry-input treatment.', '',
        '| Original DEV measure | L02 | '+identifier+' |', '| --- | ---: | ---: |']
    for label, key, fmt in [('Complete commands /14,439', 'strict_correct', 'd'),
                            ('Complete-command accuracy', 'joint_accuracy', '.6f'),
                            ('Action macro F1', 'macro_f1', '.6f'),
                            ('Observed joint NLL', 'joint_nll', '.6f')]:
        lines.append(f'| {label} | {baseline[key]:{fmt}} | {current[key]:{fmt}} |')
    oldcats = {row['action']: row for row in baseline['per_category']}
    lines += ['', '| Category | Joint L02 | Joint '+identifier+' | Conditional parameter | Type TP / FP |',
              '| --- | ---: | ---: | ---: | ---: |']
    for row in current['per_category']:
        n = row['support']
        parameter = row['all_true_family_parameter_accuracy']
        text = f'{parameter:.4f}' if parameter is not None else 'unavailable/not applicable'
        lines.append(f"| {row['action']} | {oldcats[row['action']]['joint_correct']}/{n} | "
                     f"{row['joint_correct']}/{n} | {text} | {row['type_TP']} / {row['type_FP']} |")
    lines += ['', '| Sampling | Complete / rows | NLL | Change conditional / joint | Continue conditional / joint |',
              '| --- | ---: | ---: | ---: | ---: |']
    for split, sample in [('train', 'all'), ('train', 'natural'), ('validation', 'all')]:
        value = evidence['results'][split][sample]
        change, continuing = [value['movement_contexts'][key] for key in ('change', 'continue')]
        lines.append(f"| {split}/{sample} | {value['strict_correct']}/{value['rows']} | {value['joint_nll']:.6f} | "
                     f"{change['conditional_correct']} / {change['joint_correct']} of {change['rows']} | "
                     f"{continuing['conditional_correct']} / {continuing['joint_correct']} of {continuing['rows']} |")
    lines += ['', 'Conditional metrics supply the recorded family only after forecasting for diagnosis. '
        'Complete predictions use predicted action types and the original probability-consistent joint MAP. '
        'Component-mode union/common-wrong bounds are frozen-distribution diagnostics, not achieved '
        'selector accuracy or architecture/data ceilings.', '',
        'Natural TRAIN figures use identity-verified membership with the common augmented-traversal '
        'filtering cadence. They remain in-sample and do not isolate group shift. No sampled rows are '
        'stitched as adjacent observations. Current recorded actions enter the frozen filter only after '
        'their PRE features have been cached; the trained readout never changes that filter.', '',
        f"Selected round {info['selected_round']} of {len(info['trace'])}; updates "
        f"{info['selected_updates']} selected / {info['completed_updates']} completed. Original "
        '.0001 NLL improvement, patience6, max35. Every attempted round and final archive retained. '
        f"Trainable/readout parameters {info['trainable_parameters']}, resident model parameters "
        f"{info['resident_parameters']}; serving additionally requires the frozen upstream policy. "
        'No total production latency or architecture-efficiency claim.', '',
        'The evaluation includes paired overall/category/targeting/context differences against L02, '
        'L01, B00 and G00; U01 additionally compares directly with U00. Accuracy intervals use fraction '
        'differences, macro F1 score differences, and NLL nats per recorded decision. All are conditional '
        'on selected checkpoints and five repeatedly reused DEV groups, not untouched, selection-adjusted '
        'or three-seed evidence.', '',
        'This diagnostic tests incremental utility of the named predicted-geometry channel under a '
        'fixed upstream model. Other paths still carry geometry and history. Positive results cannot '
        'identify Fish intent; negative results cannot reject strategic objectives or prove observation '
        'insufficiency. Fixed P05 priority modes and missing purchase arguments remain configuration '
        'limits that readout training cannot remove.', '',
        'Original category90%, macro.65, movement.6520745131244708, likelihood/targeting and three-seed '
        'targets remain binding. No promotion or robust improvement is claimed. All43DEV shops are '
        'unassessed strict failures; purchase-argument likelihood is absent. Sparse categories, entity '
        'identity and full legality/calibration remain uncertified. Successful-move mask rejections '
        'remain separate from blocked-attempt mask diagnostics.', '',
        'Model research only. Both75-game reservations remain sealed. No matches, replay downloads, '
        'bot/runtime changes or deployment. PR11DRAFT/open/unmerged/no-auto-merge/queue. Fresh Sol '
        'xhigh review follows this fit; matched continuation is separately recorded.', '']
    path = OUT / f'{identifier}-REPORT.md'
    assert not path.exists(), 'Preserve reports'
    path.write_text('\n'.join(lines))
    immutable_json(OUT / f'{identifier}-report-receipt.json', dict(report_sha256=digest(path),
        fit_sha256=digest(OUT / f'{identifier}.json'),
        evaluation_sha256=digest(OUT / f'{identifier}-evaluation.json'),
        source_sha256=digest(__file__), new_fits=0, reserved_opened=0))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('identifier', choices=ARMS)
    run(parser.parse_args().identifier)
