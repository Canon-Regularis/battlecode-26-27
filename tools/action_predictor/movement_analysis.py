"""Complete G00/G01 results and prospective guards, without fitting."""
import csv,json,sys
from pathlib import Path
import numpy as np
from . import reliable_train as rt
from .fundamental_audit import WORK,REPORTS,arrays,log
from .priority_fit_v3 import BASE,VAL,read
from .more_replays import frozen,sha
from .observation_metrics import correctness,interval,ratio

def run(identifier):
    report=read(REPORTS/(identifier+'.json'));directory=WORK/'runs'/identifier;assert sha(directory/'validation-predictions.npz')==report['predictions_sha256'];raw=arrays(VAL);pred=arrays(directory/'validation-predictions.npz');old=arrays(BASE.parent/'v8/runs/P05/validation-predictions.npz');d02=read(REPORTS/'D02.json');base=d02['validation_P05'];parameter,joint=correctness(raw,pred);old_param,old_joint=correctness(raw,old)
    for key in ('prediction','priority','type_nll'):np.testing.assert_array_equal(pred[key],old[key])
    fixed=~np.isin(raw['y'],[8,3])
    for key in ('coordinate','top5','param_nll'):np.testing.assert_array_equal(pred[key][fixed],old[key][fixed])
    typed=raw['y']==pred['prediction'];shop=raw['y']==rt.LABELS.index('shop');failures=dict(wrong_types=int((~typed).sum()),wrong_parameters_after_correct_type=int((typed&~parameter&~shop).sum()),correct_type_missing_shop_arguments=int((typed&shop).sum()),strict_failures=int((~joint).sum()));assert sum(v for k,v in failures.items() if k!='strict_failures')==failures['strict_failures']
    summary=report['validation']['summary'];categories=report['validation']['per_category'];groups=np.unique(raw['group']);rng=np.random.default_rng(20261106);draws=np.stack([np.bincount(rng.integers(0,len(groups),len(groups)),minlength=len(groups)) for _ in range(2000)]);uncertainty={}
    for r in categories:
        if not r['support']:continue
        mask=raw['y']==rt.LABELS.index(r['action']);n=np.array([int((mask&(raw['group']==g)).sum()) for g in groups]);a=np.array([int(joint[mask&(raw['group']==g)].sum()) for g in groups]);b=np.array([int(old_joint[mask&(raw['group']==g)].sum()) for g in groups]);uncertainty[r['action']]=dict(joint_accuracy=interval(ratio(draws@a,draws@n)),joint_gain_vs_P05=interval(ratio(draws@(a-b),draws@n)),groups_with_support=int((n>0).sum()))
    with (REPORTS/(identifier+'-per-category.csv')).open('w',newline='',encoding='utf-8') as f:
        writer=csv.DictWriter(f,fieldnames=list(categories[0]));writer.writeheader();writer.writerows(categories)
    np.savetxt(REPORTS/(identifier+'-confusion.csv'),np.asarray(summary['confusion_matrix']),delimiter=',',fmt='%d',header=','.join(rt.LABELS),comments='')
    references={'P05':base};pred_refs={'P05':old}
    if identifier=='G01':references['G00']=read(REPORTS/'G00.json')['validation'];pred_refs['G00']=arrays(WORK/'runs/G00/validation-predictions.npz')
    guards={};directions=report['validation']['direction_contexts']
    for name,reference in references.items():
        params,complete=correctness(raw,pred_refs[name]);target=[]
        for category in ('attack','cast_0','cast_1'):
            m=raw['y']==rt.LABELS.index(category);target.append(bool(np.array_equal(parameter[m],params[m]) and np.array_equal(joint[m],complete[m])))
        guards[name]=dict(no_strict_regression=summary['strict_full_command_accuracy']>=reference['summary']['strict_full_command_accuracy'],continuation_exact_drop_at_most_half_point=directions['continuing']['parameter_exact']>=reference['direction_contexts']['continuing']['parameter_exact']-.005,direction_change_joint_not_worse=directions['direction_change']['joint_exact']>=reference['direction_contexts']['direction_change']['joint_exact'],attack_cast_parameters_and_joint_unchanged=all(target),lower_joint_nll=summary['joint_nll']<reference['summary']['joint_nll'])
    ward_pred=pred['prediction']==rt.LABELS.index('ward');ward_true=raw['y']==rt.LABELS.index('ward');recall=raw['y']==rt.LABELS.index('recall');ward_tp=int((ward_pred&ward_true).sum());ward_fp=int((ward_pred&~ward_true).sum());ward_j=int(joint[ward_true].sum());ward_count=int(ward_pred.sum());recall_ward=int((ward_pred&recall).sum())
    rare=dict(ward_type_correct=ward_tp,ward_joint_correct=ward_j,ward_type_FP=ward_fp,recall_to_ward=recall_ward,ward_type_precision=ward_tp/ward_count,passed=ward_tp>=35 and ward_j>=7 and ward_fp<=282 and recall_ward<=257 and ward_tp/ward_count>=35/317)
    # Parameter rows use only supported required arguments; missing shop never correct.
    with np.load(BASE/'combined-train.npz') as z:training_y=z['y'];training_priority=z['priority']
    v,c=np.unique(training_priority[training_y==9],return_counts=True);freq=dict(zip(v,c));counts=np.array([freq.get(x,0) for x in raw['priority']]);priority={}
    for name,criterion in [('all',counts>=0),('rare',(counts>0)&(counts<20)),('unseen',counts==0)]:
        mask=(raw['y']==9)&criterion;priority[name]=dict(support=int(mask.sum()),parameter_exact=int(parameter[mask].sum()),joint_correct=int(joint[mask].sum()),parameter_nll=float(pred['param_nll'][mask].mean()) if mask.any() else None)
    trigger=False
    if identifier=='G01':
        trigger=rare['passed'] and all(all(x.values()) for x in guards.values()) and all(summary['parameters']['move']['joint_accuracy']-references[k]['summary']['parameters']['move']['joint_accuracy']>=.05 and report['comparisons'][k]['move_joint_gain']['low']>0 for k in references)
    simple=read(REPORTS.parent/'v4/simple-baselines.json')['validation'];simple_move=max(v['parameters']['move']['exact_accuracy'] for v in simple.values())
    result=dict(report_sha256=sha(REPORTS/(identifier+'.json')),source_sha256=sha(__file__),failure_accounting=failures,prospective_guards=guards,rare_action_protection=rare,priority=priority,category_uncertainty=uncertainty,exploratory_seed_trigger=trigger,seed_trigger_scope='Only after G01; must beat BOTH G00 and P05. No automatic repeats. Warm-start seeds cannot establish independent full-model generalization.',original_targets=dict(macro_f1_at_least_065=summary['macro_f1']>=.65,movement_gain_vs_simple=summary['parameters']['move']['exact_accuracy']-simple_move,movement_gain_at_least_ten_points=summary['parameters']['move']['exact_accuracy']>=simple_move+.10,loss_reduction_vs_P05=1-summary['joint_nll']/base['summary']['joint_nll'],all_category_90_certified=False,three_seed_confirmed=False),legality=report['legality'],reserved_opened=0)
    frozen(REPORTS/(identifier+'-analysis.json'),result);(REPORTS/(identifier+'-analysis-source.txt')).write_bytes(Path(__file__).read_bytes())
    lines=[f'# {identifier}: movement mixture study','',f"Selected epoch{report['best_epoch']} from{len(report['history'])};{report['optimizer_calls']:,} optimizer calls,{report['head_updates']:,} actual updates. Nominal trainable{report['nominal_trainable_parameters']:,}; frozen mixture-model parameters{report['frozen_model_parameters']:,}. Separate unchanged P05 priority head also remains part of the complete predictor.",'','| Model/split | Strict joint | Macro F1 | Observed joint NLL |','|---|---:|---:|---:|']
    for name,m in [('M01 dev',d02['validation_M01']),('P05 dev',base),(identifier+' train',report['train']),(identifier+' dev',report['validation'])]:
        s=m['summary'];lines.append(f"| {name} | {s['strict_full_command_accuracy']:.4%} | {s['macro_f1']:.5f} | {s['joint_nll']:.6f} |")
    lines+=['','| Category | Joint correct/support | Joint accuracy | True-family parameter exact |','|---|---:|---:|---:|']
    for r in categories:
        if not r['support']:continue
        p='unassessed' if r['action']=='shop' else '—' if r['parameter_exact'] is None else f"{r['parameter_exact']:.2%}"
        lines.append(f"| {r['action']} | {r['joint_correct']}/{r['support']} | {r['joint_accuracy']:.2%} | {p} |")
    lines+=['','Parameter accuracy supplies the true family over all recorded rows of that category. Joint requires the predicted type and every exact required argument. Missing purchases remain unassessed strict failures; no-required-parameter rows have no parameter metric. Per-action type PRF and false positives remain in the CSV; type confusion is frozen with the classifier.','',f'Failure accounting: {failures}.','',f'Prospective guards: {guards}. Ward protection: {rare}.','',f'Gate diagnostics: {report["gate"]}.','',f'Original targets: {result["original_targets"]}. No certified replacement; both reserved75-game partitions remain sealed.','', 'Direction contexts and train/development results are complete in the immutable report. Any improvements remain conditional on one warm-start seed and five reused development groups. G00 is an unrestricted control, not evidence that direction specialization helps. G01 must compare directly with G00 after the fresh completed-G00 review.']
    (REPORTS/(identifier+'-REPORT.md')).write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(json.dumps(dict(id=identifier,strict=summary['strict_full_command_accuracy'],move=summary['parameters']['move'],failures=failures,guards=guards)))

if __name__=='__main__':log([sys.executable,'-m','tools.action_predictor.movement_analysis',*sys.argv[1:]]);run(sys.argv[1])
