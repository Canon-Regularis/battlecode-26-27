"""Unchanged complete-command metrics plus goal-pathway movement diagnostics."""
import json
import numpy as np
from .sequence_data import BASE,WORK,REPORT
from .pathway_protocol import LOCAL,OUT,freeze
from .pathway_inputs import CONTRASTS
from .analysis import read,paired_categories,readiness_flags
from ..movement_experts.evaluate import summary,support
from ..observation_metrics import correctness
from ..audit import immutable_json
from ..data import digest


def movement(raw,p,diag,mask):
    ids=np.flatnonzero(mask);target=raw['py'][ids];modes=diag['head_modes'][ids]
    valid=(target>=0)&(target<289);correct=(p['coordinate'][ids]==target)&valid
    typed=p['prediction'][ids]==raw['y'][ids]
    same=(modes==modes[:,:1]).all(-1);common_wrong=same&(modes[:,0]!=target)
    forced=common_wrong|~valid;union=(modes==target[:,None]).any(-1)&valid
    def distribution(a):
        a=np.asarray(a);a=a[np.isfinite(a)]
        return dict(rows=len(a),mean=float(a.mean()) if len(a) else None,
            quantiles=np.quantile(a,[0,.25,.5,.75,.95,1]).tolist() if len(a) else None)
    return dict(rows=len(ids),conditional_correct=int(correct.sum()),joint_correct=int((correct&typed).sum()),
        all_components_same_mode=int(same.sum()),common_wrong_component_mode=int(common_wrong.sum()),
        unrepresentable_recorded_coordinates=int((~valid).sum()),component_mode_union=int(union.sum()),
        typed_destination_errors=int((typed&~correct).sum()),
        typed_errors_with_correct_component_mode=int((typed&~correct&union).sum()),
        typed_errors_without_correct_component_mode=int((typed&~correct&~union).sum()),
        typed_errors_dominated_under_current_reweighting=int((typed&~correct&forced).sum()),
        conservative_conditional_reweighting_ceiling=int((~forced).sum()),
        conditional_probability_of_recorded=distribution(diag['recorded_probability'][ids]),
        recorded_rank=distribution(diag['recorded_rank'][ids][diag['recorded_rank'][ids]>0]),
        conditional_TV_from_original=distribution(diag['conditional_TV'][ids]),
        mean_component_JS=distribution(diag['component_JS'][ids]))


def run():
    freeze();raw=read(BASE.parent/'v4/validation.npz')
    direction=np.load(BASE.parent/'v7/validation-direction.npy')
    q=dict(raw=raw,direction=direction);n=len(raw['y'])
    masks=dict(all=np.ones(n,bool),move=raw['y']==8,blocked=raw['y']==3,
        continuation=(raw['y']==8)&(direction==2),change=(raw['y']==8)&(direction==3),
        startup=(raw['y']==8)&(direction==1),position_known=raw['pos_known'].astype(bool),
        position_unknown=~raw['pos_known'].astype(bool))
    for identifier in ('L01','L02'):
        ready=json.loads((OUT/f'Q01-{identifier}-ready.json').read_text())
        directory=LOCAL/f'Q01/{identifier}'
        baseline=read(directory/'baseline-predictions.npz');results={};bindings={}
        _,baseline_joint=correctness(raw,baseline)
        for label,expected in ready['branches'].items():
            tag=label.replace('/','--');path=directory/f'{tag}-predictions.npz';dp=directory/f'{tag}-diagnostics.npz'
            assert digest(path)==expected['predictions_sha256'] and digest(dp)==expected['diagnostics_sha256']
            p=read(path);diag=read(dp);_,joint=correctness(raw,p)
            assert np.isfinite(p['nll']).all() and (p['nll']>=-1e-5).all()
            np.testing.assert_allclose(p['nll'],p['type_nll']+p['param_nll'],rtol=0,atol=2e-5)
            if label.startswith('fixed/'):
                np.testing.assert_array_equal(diag['prior'],read(directory/'baseline-diagnostics.npz')['prior'])
            categories=summary(q,p,masks['all'])['per_category'];losses={}
            for code,row in enumerate(categories):
                m=raw['y']==code;nrow=int(m.sum())
                losses[row['action']]=dict(rows=nrow,observed_nll=float(p['nll'][m].mean()) if nrow else None,
                    type_nll=float(p['type_nll'][m].mean()) if nrow else None,
                    parameter_nll=float(p['param_nll'][m].mean()) if nrow and row['action']!='shop' else None)
            prior=diag['prior'];entropy=-(prior*np.log(prior.clip(1e-30))).sum(1)
            semantic_changed=p['prediction']!=baseline['prediction']
            same_type=~semantic_changed;spatial=np.isin(p['prediction'],[1,2,3,5,6,8,12,13,14])
            semantic_changed|=same_type&spatial&(p['proposed_coordinate']!=baseline['proposed_coordinate'])
            semantic_changed|=same_type&(p['prediction']==9)&(p['priority']!=baseline['priority'])
            results[label]=dict(overall=summary(q,p,masks['all']),
                contexts={name:summary(q,p,m) for name,m in masks.items() if name!='all'},
                category_losses=losses,
                movement={name:movement(raw,p,diag,masks[name]) for name in ('move','blocked','continuation','change','startup')},
                goal_behavior=dict(mean_prior=prior.mean(0).tolist(),prior_argmax_usage=np.bincount(prior.argmax(1),minlength=4).tolist(),
                    mean_prior_entropy=float(entropy.mean()),effective_retention_quantiles=np.quantile(diag['retention'],[0,.25,.5,.75,.95,1]).tolist()),
                partial_movement_legality=support(q,p),partial_readiness=readiness_flags(raw,p),
                semantic_observed_mode_changes=int(semantic_changed.sum()),
                rescues=int((joint&~baseline_joint).sum()),regressions=int((~joint&baseline_joint).sum()),
                paired_original=paired_categories(raw,p,baseline,masks['all']) if label!='baseline' else None)
            bindings[label]=expected
        immutable_json(OUT/f'Q01-{identifier}-evaluation.json',dict(results=results,bindings=bindings,
            ready_sha256=digest(OUT/f'Q01-{identifier}-ready.json'),protocol_sha256=digest(OUT/'Q01-plan.json'),
            source_sha256=digest(__file__),direction_sha256=digest(BASE.parent/'v7/validation-direction.npy'),
            qualification='All original DEV rows and unchanged metrics. One selected checkpoint per model, five reused groups, exploratory fixed-weight contrasts. Fixed-state branches are shadow diagnostics, refiltered branches use only past evidence but still teacher-forced Fish observations/actions. No replacement variant, threshold, checkpoint or strategy-similarity percentage selected. Current-distribution bounds freeze each branch own state/distributions.',
            new_fits=0,reserved_opened=0,promoted=False))
        print('Q01 evaluated',identifier,{k:(v['overall']['strict_correct'],v['overall']['joint_nll']) for k,v in results.items()},flush=True)


if __name__=='__main__':run()
