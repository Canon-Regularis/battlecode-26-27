"""Reproducible concise paired-study interpretation from retained reports."""
import json
from .protocol import OUT
from ..audit import immutable_json
from ..data import digest


def run():
    paths = {key: OUT / name for key, name in dict(
        control='U00-evaluation-v2.json', dynamic='U01-evaluation-v2.json',
        diagnosis='U01-diagnosis-v2.json', sensitivity='U01-sensitivity.json',
        allocation='U01-allocation.json', pair='U01-pair-contract.json').items()}
    data = {key: json.loads(path.read_text()) for key, path in paths.items()}
    summaries, failures = {}, {}
    for name, key in [('U00', 'control'), ('U01', 'dynamic')]:
        score = data[key]['results']['validation']['all']
        categories = score['per_category']
        shop = next(row for row in categories if row['action'] == 'shop')
        typed = sum(row['type_TP'] for row in categories)
        failure = dict(wrong_types=score['rows'] - typed,
                       wrong_arguments_after_correct_type=typed - score['strict_correct'] - shop['type_TP'],
                       correctly_typed_unavailable_shop_arguments=shop['type_TP'])
        assert sum(failure.values()) == score['rows'] - score['strict_correct']
        failures[name] = failure
        summaries[name] = {key: score[key] for key in ('strict_correct', 'joint_accuracy', 'joint_nll', 'macro_f1')}
    paired = data['dynamic']['comparisons']['U00']['categories']['overall']
    sensitivity = data['sensitivity']
    result = dict(DEV=summaries, failure_partition=failures,
        dynamic_minus_mean=paired,
        sampling_comparisons=data['diagnosis']['results'],
        allocation=data['allocation'],
        fixed_weight_sensitivity=dict(semantic_mode_changes=sensitivity['semantic_mode_changes'],
            strict_correct=sensitivity['results']['all']['strict_correct'],
            NLL=sensitivity['results']['all']['joint_nll'],
            rescues=sensitivity['paired']['overall']['rescues'],
            regressions=sensitivity['paired']['overall']['regressions'],
            unknown_position_semantic_changes=sensitivity['unknown_position_semantic_changes']),
        ranked_findings=[
            'Demonstrated configuration limits: fixed P05 integer modes109/576, shop arguments unavailable, '
            'and U01 common-wrong movement bound1518/2362 below1541 point target under frozen distributions/state.',
            'No meaningful benefit from the tested dynamic projection channel in the matched frozen-upstream '
            'readout experiment. Small aggregate NLL difference has a paired interval spanning zero; '
            'exact DEV direction changes and complete commands do not improve.',
            'Small TRAIN gains do not transfer to DEV in this comparison. This does not isolate group '
            'shift, optimization, redundant information or forecaster quality.',
            'Fixed-weight mean replacement changes24command modes but has8rescues/8regressions. '
            'Dependence is measurable; useful strategic-goal conditioning is not established.',
            'Representation/history sufficiency, latent strategy identity, goal-proxy quality and '
            'policy-version inconsistencies remain unresolved. No hidden-intent or irreducibility claim.'
        ],
        next='Fresh independent Solxhigh challenge before choosing a distinct next experiment. '
             'No promotion/repeated seeds or more current-geometry/retention variants justified here.',
        bindings={str(path): digest(path) for path in paths.values()}, source_sha256=digest(__file__),
        new_fits=0, reserved_opened=0, promoted=False, three_seed_confirmed=False)
    immutable_json(OUT / 'U01-study-summary.json', result)
    print(json.dumps(dict(DEV=summaries, failure_partition=failures,
                         dynamic_minus_mean=paired, fixed_weight_sensitivity=result['fixed_weight_sensitivity']), indent=2))


if __name__ == '__main__':
    run()
