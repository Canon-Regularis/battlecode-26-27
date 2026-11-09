"""Report the fixed no-fit OD03 assessment; never select a replacement rule."""
import json
from pathlib import Path
import numpy as np
from ..audit import immutable_json
from ..data import digest
from .data import ROOT,OUT,LOCAL


def run():
    path=OUT/'OD03.json';report=json.loads(path.read_text())
    plan_path=OUT/'OD03-plan.json';plan=json.loads(plan_path.read_text())
    bindings={**report['inputs_and_outputs'],**report['sources']}
    with np.load(LOCAL/'relation-discrimination-v3/raw-contrasts.npz') as z:
        target=np.array(z['actual_target_features']);alternative=np.array(z['actual_alternative_features'])
        own_target=np.array(z['own_target']);own_alternative=np.array(z['own_alternative'])
    primary=report['results']['all']['features']['ANY_unguarded_other_relation']
    note=OUT/'OD03-REPORT.md'
    if note.exists():raise FileExistsError(note)
    lines=['# OD03: exact scheduling relations versus matched row swaps','',
        '**The predeclared pooled information gate fails. No predictor or rule is selected.** '
        'This is a no-fit TRAIN diagnostic, not achieved command accuracy or a policy comparison.','',
        'The actual recorded-minus-competing-integer pooled relation contrast is '
        f"{primary['actual_pair_contrast']:.6f}; mean matched-swap contrast is "
        f"{primary['mean_swapped_pair_contrast']:.6f}. The incremental contrast is "
        f"{primary['incremental_contrast']:.6f}, paired whole-group interval "
        f"`{primary['paired_whole_group_interval']}`. Positive groups: "
        f"{primary['positive_groups']}/55. The own-relation-neither stratum also has a negative "
        'point contrast. Passing the majority-group condition alone does not pass the gate.','',
        f"Gate checks: `{report['primary_gate']}`.",'',
        'Every one of the 5,876 fitting targets is already supported by P05 points. For each row, '
        'the comparison integer is the warm head\'s highest-probability distinct alternative in its '
        'existing point/fallback-mode command set, with original smaller-integer tie breaking. '
        'On warm errors this is its actual command; on warm successes it is its strongest alternative. '
        'Recorded labels define diagnostic pairs, never an inference router or a claimed intent label.','',
        'The study keeps each other unit\'s exact current/scheduled pair, role and availability. '
        'It tests 24 fixed sign/offset relations and the same 24 guarded by that unit\'s observed '
        'current/scheduled difference. Own comparisons cover current, scheduled, latest previous '
        'argument and any of the previous16 argument slots, with exact values and masks.','',
        'The 64 controls permute complete other-unit priority pairs within group, engine and '
        'identical role/availability-signature blocks. Own evidence, candidate pairs and labels '
        'stay fixed. Raw other-value marginals and per-row availability/counts are preserved. '
        f"There are {report['swapping']['blocks']} blocks, "
        f"{report['swapping']['singleton_rows']} singleton rows and "
        f"{report['swapping']['swappable_rows']} swappable rows. Numeric evidence actually changes on "
        f"{report['swapping']['effective_changed_rows_range']} rows across controls. All rows remain "
        'in the primary denominator; availability and own-neither strata are additional diagnostics.','',
        'A row swap is artificial diagnostic corruption, potentially using a later TRAIN row. '
        'It is never inference, a legal game trajectory, or an exchangeable temporal randomization. '
        'No proposed action is executed. Group intervals are exploratory on in-sample TRAIN '
        'contrasts, not untouched-policy confidence or adjusted per-feature tests.','',
        'The individual relations below were all declared before assessment. Opposing positive and '
        'negative contrasts can cancel in their pooled union. Their exploratory differences therefore '
        'do not rescue the failed primary gate, but the pooled failure also cannot establish that '
        'every relation is uninformative. No best relation, threshold or replacement command is selected.','',
        '| Fixed relation | Target matches | Alternative matches | Actual−swapped pair contrast | Paired group interval |',
        '| --- | ---: | ---: | ---: | --- |']
    names=list(report['results']['all']['features'])[1:]
    for column,name in enumerate(names):
        v=report['results']['all']['features'][name]
        lo,hi=v['paired_whole_group_interval']
        lines.append(f"| {name} | {int(target[:,column].sum())} | {int(alternative[:,column].sum())} | "
                     f"{v['incremental_contrast']:.6f} | [{lo:.6f}, {hi:.6f}] |")
    lines+=['','| Stratum | Rows | Pooled actual−swapped contrast | Paired group interval |',
            '| --- | ---: | ---: | --- |']
    for name,row in report['results'].items():
        v=row['features']['ANY_unguarded_other_relation']
        lines.append(f"| {name} | {row['rows']} | {v['incremental_contrast']:.6f} | "
                     f"{v['paired_whole_group_interval']} |")
    lines+=['',
        f"Own simple-relation pooled pair contrast is {report['own_relation_pair_contrast']:.6f}; "
        f"own target-only matches {(own_target.any(-1)&~own_alternative.any(-1)).sum()}, "
        f"alternative-only matches {(~own_target.any(-1)&own_alternative.any(-1)).sum()}. "
        'These summaries do not control for every own-state interaction or establish conditional '
        'independence. Alternatives were chosen by the original warm model, which already uses '
        'own-priority/history evidence; this is an incremental discrimination diagnostic.','',
        'Two prerequisite failures are preserved. OD01 assumed the PC02 completion inventory '
        'contained P05 metadata entries; OD02 assumed the broad cohort contained a baseline forecast. '
        'Both stopped before scheduling-relation assessment, with no fitting or new queries. '
        'The OD02 candidate arrays computed before failure were not retained; no byte-identity '
        'claim to them is made. OD03 independently anchors the missing metadata, binds the original '
        'prediction archive, verifies cohort schema and preserves candidate pairs before semantic '
        'checks. Raw contrasts are archived before reporting and uncertainty calculations.','',
        'The exact-integer/pairing and permutation tests pass. Sources were committed before '
        f"execution at `{report['source_commit']}`. O01\'s fresh review motivated this study; "
        'its verdict does not independently review these later results. A new challenge follows.','',
        'No information-sufficiency, hidden-intent, complete-command, policy-quality or robustness '
        'claim follows. All original targets remain unmet; shops and sparse/identity/legality '
        'limitations remain. Both reservations are sealed. No DEV assessment, new replay queries, '
        'optimizer updates, matches, downloads, bot/runtime work or deployment.','',
        'Reproduce only into absent immutable destinations: '
        '`python -m tools.action_predictor.order_information.relation_discrimination_v3`, then '
        '`python -m tools.action_predictor.order_information.discrimination_report`. Earlier '
        'versions intentionally retain their prerequisite failures; do not rerun them.','']
    note.write_text('\n'.join(lines),encoding='utf-8')
    for p in (path,plan_path,note,Path(__file__),OUT/'OD01-plan.json',OUT/'OD01-prerequisite-failure.json',
              OUT/'OD02-plan.json',OUT/'OD02-prerequisite-failure.json',OUT/'O01-review.json',OUT/'O01-review-response.json'):
        bindings[str(p.relative_to(ROOT))]=digest(p)
    for relative,value in bindings.items():
        if digest(ROOT/relative)!=value:raise RuntimeError('Completion mismatch: '+relative)
    immutable_json(OUT/'OD03-completion.json',dict(bindings=bindings,source_commit=report['source_commit'],
        report_source_sha256=digest(__file__),primary_gate_passed=report['exploratory_information_gate_passed'],
        new_fits=0,new_engine_queries=0,reserved_opened=0,policy_replaced=False,
        commands=['python -m unittest tools.action_predictor.order_information.test_discrimination_v3',
                  'python -m tools.action_predictor.order_information.relation_discrimination_v3',
                  'python -m tools.action_predictor.order_information.discrimination_report']))
    print('Preserved OD03 report and',len(bindings),'bindings.',flush=True)


if __name__=='__main__':run()
