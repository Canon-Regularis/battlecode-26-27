"""Summarize the predeclared retention-gradient intervention from saved results."""
import json
from .sequence_data import REPORT


def run():
    def read(name):return json.loads((REPORT/name).read_text())
    a,b=read('L01.json'),read('L02.json')
    comparison=read('L02-L01-comparison.json')['results']['validation']['L02_minus_L01']
    c=comparison['overall'];metrics=[a['results']['validation']['all'],b['results']['validation']['all']]
    categories=[{r['action']:r for r in m['per_category']} for m in metrics]
    memories=[read(f'{n}-validation-direct-memory.json')['results']['all'] for n in ('L01','L02')]
    components=[read(f'{n}-validation-components.json')['results'] for n in ('L01','L02')]
    bound=[read(f'{n}-validation-dominance-bound.json')['results']['move'] for n in ('L01','L02')]
    movement=[read(f'{n}-matched-movement.json')['results']['validation'][n] for n in ('L01','L02')]
    path=REPORT/'L02-REPORT.md';assert not path.exists()
    lines=['# L02: command-only retention gradients versus L01','',
        'One additional user-authorized fit isolates direct auxiliary derivatives on the retention mechanism. Model training and evaluation only; bot work remains paused. This is a controlled seed-specific training intervention, not proof of Fish intent.','',
        'Architecture, data, warm initialization/seed, decoder, evaluation functions, AdamW, global clipping and checkpoint rule are unchanged. Both retention weights and bias receive command-only gradients through the entire eight-node unroll. Every other parameter receives the original command plus .05 future-position auxiliary gradient. No gate activation is detached; auxiliary gradients still flow to other intended components. Shared clipping and learned representations leave indirect interactions possible.','',
        '| Original DEV measure | L01 | L02 |','| --- | ---: | ---: |']
    for label,key,fmt in [('Complete commands /14,439','strict_correct','d'),('Complete-command accuracy','joint_accuracy','.6f'),('Action macro F1','macro_f1','.6f'),('Observed joint NLL','joint_nll','.6f')]:
        lines.append(f"| {label} | {metrics[0][key]:{fmt}} | {metrics[1][key]:{fmt}} |")
    for family in ('move','blocked','attack','cast_0','cast_1','priority','recall','ward'):
        lines.append(f"| Complete {family} | {categories[0][family]['joint_correct']}/{categories[0][family]['support']} | {categories[1][family]['joint_correct']}/{categories[1][family]['support']} |")
    lines+=['',f"L02 rescues {c['rescues']} and regresses {c['regressions']} commands versus L01. Group net differences: `{c['group_net']}`."]
    for label,key in [('Accuracy','joint_accuracy'),('Macro F1','macro_f1'),('Observed NLL','joint_nll')]:
        ci=c['paired95'][key];lines.append(f"{label} difference paired 95% interval: {ci['low']:.8f} to {ci['high']:.8f} (accuracy in fractions).")
    lines+=['','Intervals use the same2,000 whole-group draws, seed20261106. They are conditional on selected checkpoints and five reused DEV groups, not untouched or three-seed evidence.','',
        '| Movement diagnostic | L01 | L02 |','| --- | ---: | ---: |']
    for context in ('continuation','change','startup'):
        for key in ('conditional_exact','joint_exact'):
            lines.append(f"| {context} {key} | {movement[0][context][key]}/{movement[0][context]['rows']} | {movement[1][context][key]}/{movement[1][context]['rows']} |")
    lines+=['','True-family destination metrics are conditional diagnostics. Complete predictions use predicted actions and the unchanged probability-consistent joint decoder.','',
        '| Retention/execution diagnostic | L01 | L02 |','| --- | ---: | ---: |']
    for label,key in [('Direct per-root gate median','direct_per_root_gate_quantiles'),('Effective gap-retention median','effective_retention_quantiles'),('Forward decay-age feature median','exact_decay_age_feature_quantiles')]:
        lines.append(f"| {label} | {memories[0][key][2]:.6f} | {memories[1][key][2]:.6f} |")
    for label,key in [('Common component destination on moves','all_components_same_mode'),('Component-mode oracle coverage','mode_union_exact'),('Conditional destination exactness','mixture_conditional_exact')]:
        lines.append(f"| {label} | {components[0]['move'][key]}/2,362 | {components[1]['move'][key]}/2,362 |")
    lines.append(f"| Current-reweighting conservative conditional ceiling | {bound[0]['conservative_conditional_ceiling_under_current_reweighting']}/2,362 | {bound[1]['conservative_conditional_ceiling_under_current_reweighting']}/2,362 |")
    lines+=['','Direct gates are measured before effective-retention underflow. Decay age is the exact forward decay feature, not the lifetime of all recurrent information: known world coordinates may be held unchanged without current position, and past information also reaches new forecasts through attention. Component-mode coverage is an oracle diagnostic; the dominance ceiling holds component distributions/past state fixed. Neither is achieved strategy accuracy or an architecture/data ceiling.','',
        'The full TRAIN/DEV tables, conditional versus correctly typed targeting, confusion/false positives, category NLL, root-gap/engine contexts and paired targeting comparisons are in L02-analysis.json and L02-L01-comparison.json. Original augmented traversal and identity-verified natural membership are distinct from the supplemental natural-cadence evaluation. All TRAIN figures remain in-sample.','',
        f"Selected round {b['selected_round']} of {len(b['trace'])}, selected updates {b['selected_updates']}, completed updates {b['completed_updates']}; original NLL improvement .0001/patience6/max35. Source commit `{b['source_commit']}`. All attempted rounds/checkpoints and final predictions preserved. No additional fit, repeat seed or alternative checkpoint selected. Fresh Sol6.1xhigh review required. No promotion or robustness claim. Original category/macro/movement/NLL/targeting/three-seed objectives remain binding. See the result interpretation addendum for the measured conclusion.",'',
        'Both75-game reservations remain sealed. Every43DEV shop remains an unassessed strict failure and purchase-argument likelihood is absent. Altar/teleport/submit support cannot certify reliability. Coordinate agreement retains entity-identity ambiguity. Successful-move mask rejection and blocked-attempt outcome diagnostics are separate; full legality/calibration remain unassessed. No matches, replay downloads, playing-bot changes, native/runtime work or deployment occurred.','']
    path.write_text('\n'.join(lines))


if __name__=='__main__':run()
