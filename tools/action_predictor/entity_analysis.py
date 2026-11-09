"""Complete-command reports for V9 pilots; no fitting or checkpoint selection."""
import argparse,csv,json,sys
from pathlib import Path
import numpy as np
from .fundamental_audit import REPORTS,WORK,arrays
from .more_replays import sha,frozen
from .priority_fit_v3 import BASE,VAL,read
from .observation_metrics import correctness
from . import reliable_train as rt

def run(identifier):
    report=read(REPORTS/(identifier+'.json'));old=read(REPORTS/'D02.json');val=report['validation'];train=report['train'];s=val['summary'];baseline=old['validation_P05']['summary']
    plan=read(REPORTS/(identifier+'-plan.json'))
    for path,digest in plan['source_hashes'].items():assert sha(path)==digest
    directory=WORK/'runs'/identifier
    assert sha(directory/'model.pt')==report['checkpoint_sha256'] and sha(directory/'validation-predictions.npz')==report['predictions_sha256']
    raw=arrays(VAL);pred=arrays(directory/'validation-predictions.npz');parameter,joint=correctness(raw,pred)
    wrongtype=raw['y']!=pred['prediction'];shop=(raw['y']==rt.LABELS.index('shop'))&~wrongtype
    accounting=dict(wrong_types=int(wrongtype.sum()),wrong_parameters_after_correct_type=int((~wrongtype&~parameter&~shop).sum()),correctly_typed_shops_unassessed=int(shop.sum()),strict_failures=int((~joint).sum()))
    assert sum(v for k,v in accounting.items() if k!='strict_failures')==accounting['strict_failures']
    rows=[]
    for row in val['per_category']:
        row=dict(row);j=row['joint_correct'];guess=j+row['joint_FP'];n=row['support'];row.update(joint_precision=j/guess if guess else 0.,joint_recall=j/n if n else None,joint_f1=2*j/(guess+n) if guess+n else 0.)
        rows.append(row)
    with (REPORTS/(identifier+'-per-category.csv')).open('w',newline='',encoding='utf-8') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    matrix=np.asarray(s['confusion_matrix']);np.savetxt(REPORTS/(identifier+'-confusion.csv'),matrix,delimiter=',',fmt='%d',header=','.join(rt.LABELS),comments='')
    target=report['targeting_changes']['P05'];ward=next(r for r in rows if r['action']=='ward');guards=dict(no_overall_joint_regression=s['strict_full_command_accuracy']>=baseline['strict_full_command_accuracy'],macro_drop_at_most_one_point=s['macro_f1']>=baseline['macro_f1']-.01,attack_ability_joint_drop_at_most_two_points=all(target[k]['joint_change']>=-.02 for k in ('attack','cast_0','cast_1')),attack_ability_parameter_guard=all(target[k]['parameter_change']>=-.02 for k in ('attack','cast_0','cast_1')),ward_type_correct_at_least_35=int(matrix[rt.LABELS.index('ward'),rt.LABELS.index('ward')])>=35,ward_joint_at_least_seven=ward['joint_correct']>=7)
    # Original requested benchmarks remain separate from the exploratory allocation gate.
    loss=s['joint_nll'];references=dict(M01=old['validation_M01']['summary']['joint_nll'],P05=baseline['joint_nll'],A01_strongest_simple=.779097620010376)
    simple_path=REPORTS.parent/'v4/simple-baselines.json';simple=read(simple_path)['validation'];movement_reference=max(x['parameters']['move']['exact_accuracy'] for x in simple.values())
    original=dict(macro_f1_at_least_065=s['macro_f1']>=.65,movement_simple_reference=movement_reference,movement_reference_sha256=sha(simple_path),movement_exact_gain=s['parameters']['move']['exact_accuracy']-movement_reference,movement_gain_at_least_ten_points=s['parameters']['move']['exact_accuracy']>=movement_reference+.10,ten_percent_lower_loss={k:loss<=.9*v for k,v in references.items()},per_category_90_point_estimate={r['action']:bool(r['joint_accuracy'] is not None and r['joint_accuracy']>=.9) for r in rows if r['support']},three_seed_certified=False,rare_categories_certified=False,missing_purchase_arguments_assessed=False)
    gain=s['strict_full_command_accuracy']-baseline['strict_full_command_accuracy'];move=target['move']['joint_change'];interval=report['comparisons']['P05']
    # Store the exact preregistered expression; uncertainty keys are retained verbatim.
    from .observation_metrics import interval as bounds,ratio
    groups=np.unique(raw['group']);rng=np.random.default_rng(20261106);draws=np.stack([np.bincount(rng.integers(0,len(groups),len(groups)),minlength=len(groups)) for _ in range(2000)])
    prior=arrays(BASE.parent/'v8/runs/P05/validation-predictions.npz');_,old_joint=correctness(raw,prior);category_uncertainty={}
    for r in rows:
        if not r['support']:continue
        mask=raw['y']==rt.LABELS.index(r['action']);n=np.array([int((mask&(raw['group']==g)).sum()) for g in groups]);a=np.array([int(joint[mask&(raw['group']==g)].sum()) for g in groups]);b=np.array([int(old_joint[mask&(raw['group']==g)].sum()) for g in groups]);den=draws@n
        category_uncertainty[r['action']]=dict(joint_accuracy=bounds(ratio(draws@a,den)),joint_gain_over_P05=bounds(ratio(draws@(a-b),den)),groups_with_support=int((n>0).sum()))
    original_regressions=all(guards[k] for k in ('attack_ability_parameter_guard',))
    seed_trigger=all(guards.values()) and original_regressions and ((gain>=.02 and interval['joint_accuracy_gain']['low']>0) or (move>=.05 and interval['move_joint_gain']['low']>0))
    result=dict(report_sha256=sha(REPORTS/(identifier+'.json')),source_sha256=sha(__file__),accounting=accounting,guards=guards,original_targets=original,exploratory_seed_allocation_trigger=seed_trigger,strict_gain=gain,move_joint_gain=move,paired_intervals=interval,category_uncertainty=category_uncertainty,interpretation='E00 is redesigned zero-entity control; E01 is the matched input treatment. Improvements versus M01/P05 bundle classifier/GRU/movement retraining, separate fusions and common recovered priority channels. Entity attribution requires E01 minus E00. One head/representation warm-start seed is not three independent full-model seeds.',reserved_opened=0)
    frozen(REPORTS/(identifier+'-analysis.json'),result)
    lines=[f'# {identifier}: full predictor pilot','',f"Selected epoch {report['best_epoch']} by the frozen observed-joint-NLL rule; {len(report['history'])} completed epochs, {report['optimizer_calls']:,} optimizer steps. {report['trainable_parameters']:,} trainable and {report['frozen_parameters']:,} frozen parameters. No reserved partitions opened.",'','| Model / split | Strict complete-command accuracy | Macro F1 | Observed joint NLL |','|---|---:|---:|---:|']
    for name,metric in [('M01 dev',old['validation_M01']),('P05 dev',old['validation_P05']),(identifier+' train',train),(identifier+' dev',val)]:
        x=metric['summary'];lines.append(f"| {name} | {x['strict_full_command_accuracy']:.4%} | {x['macro_f1']:.5f} | {x['joint_nll']:.6f} |")
    lines += ['', '| Category | Joint correct / support | Joint accuracy | True-family parameter exact | Type P / R / F1 |','|---|---:|---:|---:|---|']
    for r in rows:
        if not r['support']:continue
        param='unassessed' if r['action']=='shop' else '—' if r['parameter_exact'] is None else f"{r['parameter_exact']:.2%}"
        lines.append(f"| {r['action']} | {r['joint_correct']}/{r['support']} | {r['joint_accuracy']:.2%} | {param} | {r['type_precision']:.2%} / {r['type_recall']:.2%} / {r['type_f1']:.2%} |")
    lines += ['', 'True-family parameter accuracy uses every recorded row in the category, including misclassified rows. Joint correctness requires the predicted type and all exact required parameters. Type PRF describes action names; the CSV also reports complete-command PRF and false positives. Runtime coordinates route by the predicted family; correctly typed spatial rows are checked against that route.', '', 'Movement contexts (recorded direction labels are evaluation evidence, never inference inputs):']
    for split,metric in [('TRAIN',train),('DEV',val)]:
        for name,r in metric['direction_contexts'].items():
            if r['support']:lines.append(f"- {split} {name}: support {r['support']}, destination exact {r['parameter_exact']:.2%}, joint {r['joint_exact']:.2%}.")
    lines += ['', 'Priority value distributions are frozen P05; new action decisions can change priority joint correctness. Rare/unseen strata, train versus development, losses, top-k movement, destination errors and targeting deltas are retained in the immutable fit report. All 43 shop rows remain unassessed strict failures. Two altar/teleport examples cannot certify reliability.', '', f'Failure accounting: {accounting}.', '', f'Regression checks: {guards}.', '', f'Paired whole-group intervals: {interval}. Five reused groups, conditional on checkpoint selection; no independent-seed or untouched-test confirmation.', '', result['interpretation'], '', 'The 90% exact joint objective in every adequately supported category remains unmet. No below-target candidate is promoted as a certified replacement. Preserve P05/M01 and all failed studies.']
    (REPORTS/(identifier+'-REPORT.md')).write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(json.dumps(dict(id=identifier,best_epoch=report['best_epoch'],strict=s['strict_full_command_accuracy'],macro=s['macro_f1'],loss=s['joint_nll'],accounting=accounting,guards=guards)))

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('identifier',choices=['E00','E01']);run(parser.parse_args().identifier)
