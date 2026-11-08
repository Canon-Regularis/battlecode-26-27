"""RC: a separately registered signed-vector learning hypothesis."""
import numpy as np
from pathlib import Path
from ..audit import immutable_json
from ..priority_broad.guard import committed_sources
from ..priority_regularized.safety import dependency_files,reject_optimized_python
from ..order_information.anchored import anchored_inputs
from .model import NAMES

ROOT=Path(__file__).resolve().parents[3]
LOCAL=ROOT/'.cambc/action-predictor/v24'
OUT=ROOT/'tools/action_predictor/experiments/v24'
V23_COMMIT='cf9eff1f3277c0daa5b609186602496d12567bb9'
GROUP_SEED=20261125
SWAP_SEED=20261188
TRAIN_SEED=20261120
STRENGTH=3.029750319831723e-5
UPDATES=2000
ARMS={'RC00':'matched_shuffled_training','RC01':'real_training'}


def fold(groups):
    unique=np.unique(groups)
    if len(unique)!=55:raise RuntimeError('Expected original55broad groups')
    held=np.sort(np.random.default_rng(GROUP_SEED).permutation(unique)[:15])
    fit=~np.isin(groups,held)
    if not fit.any() or fit.all():raise RuntimeError('Invalid correction fold')
    return fit,held


def source_gate():
    reject_optimized_python()
    return committed_sources(ROOT,dependency_files(ROOT,(
        'tools.action_predictor.relational_priority.protocol',
        'tools.action_predictor.relational_priority.data',
        'tools.action_predictor.relational_priority.test_model',
        'tools.action_predictor.relational_priority.test_data')))


def freeze():
    commit,sources=source_gate()
    broad,_,bindings=anchored_inputs();groups=broad['group'].numpy();fit,held=fold(groups)
    plan=dict(id='RC-shared-signed-point-correction',source_commit=commit,sources=sources,inputs=bindings,
        hypothesis='A shared signed candidate-relative correction can use distinctions discarded '
                   'by pooled ANY features and O01 aggregates. This is separately registered '
                   'after OD03 secondary evidence; OD03 primary gate remains failed.',
        arms=ARMS,features=list(NAMES),
        architecture='Freeze original warm P05 core/vocabulary/logistic parameters. Shared signed '
                     'linear correction on every available absolute/residual POINT component logit, '
                     'using that exact integer.24own+48other Boolean relations. No extra hidden '
                     'layer, point vocabulary, selected-competitor routing or intent label. '
                     'Normalize all corrected points with retained full-support logistic fallback; '
                     'duplicate commands marginalize; original global integer MAP/ties retained.',
        active_capacity='Common TRAIN-only support mask: a feature is trainable only if it occurs '
                        'on at least one available point in BOTH real and shuffled optimization '
                        'inputs. Otherwise its weight is fixedzero in both; all72feature definitions '
                        'and all rows retained. No target labels or held values select this mask.',
        population=dict(original_broad_rows=5876,new_fit_rows=int(fit.sum()),new_held_rows=int((~fit).sum()),
            fit_groups=sorted(map(int,np.unique(groups[fit]))),held_groups=held.tolist(),group_seed=GROUP_SEED,
            rule='Shuffle55existingbroadgroup IDs with fixed RNG, hold first15wholegroups; fit40. '
                 'All5876rows retained, original128PC00fit is not a separate optimization population. '
                 'Legacy128-row controls not assessed in this study.'),
        exposure='Fresh group separation for THIS correction fit only. Original frozen encoder/head/'
                 'vocabulary previously saw eligible TRAIN; OD03 also inspected this population. '
                 'Not untouched or confirmatory full-policy generalization. No DEV/reserved data.',
        control='Both arms get identical exact candidate-relative own current/scheduled/latest/'
                'history16 relations. RC00 TRAIN other-unit pairs use one fixed availability-matched '
                'within-group/engine derangement seed20261188. RC01 TRAIN uses real pairs. '
                'Corruption never crosses group or new fit/held membership. Primary evaluation '
                'of BOTH arms always uses REAL personally available PRE inputs; no future donor '
                'is an inference input. Singleton/unchanged-control rows stay explicit.',
        optimization=dict(seed=TRAIN_SEED,updates=UPDATES,endpoint='Fixed2000, no held-based checkpoint selection',
            optimizer='AdamW',lr_first1000=.003,lr_last1000=.001,weight_decay=0,clip_norm=5,
            batch='Full optimization-population mean NLL accumulated through chunks256 before one update',
            regularization='Inherited fixed PC02 lambda*SUM squared new-weight displacement fromzero, '
                           'once per full-population update. Frozen core has no trainable displacement.',
            lambda_value=STRENGTH,assessments=[0,100,500,1000,2000],threads=4),
        metrics='All new fit/held rows: conditional integer exact,NLL,MAE,bounded rank,modeconfidence, '
                'absolute/residual/fallback posterior shares, whole-group paired2000draws seed20261106. '
                'Report real-input TRAIN scores separately from actual fitting-input scores for RC00. '
                'Warm P05 and direct real-versus-control comparisons; fit-seen/unseen integer strata '
                'describe correction exposure only. Calibration is conditional, not global policy.',
        exploratory_allocation_gate=dict(held_exact_gain_over_warm_at_least=.02,
            held_exact_gain_over_matched_control_at_least=.01,
            held_mean_NLL_lower_than_both=True,majority_held_groups_net_positive_over_warm=True,
            meaning='Named exploratory allocation criterion for a subsequent FULL-policy assessment, '
                    'not replacement certification or original success. Report intervals and '
                    'contradictory category limitations; no tuning of strength,split,endpoint,features.'),
        budget='Two matched substantive fits RC00 then RC01, fresh requested Solxhigh review after '
               'EACH. Complete the registered contrast even if control is negative unless '
               'correctness/access/resource blocker intervenes. No automatic extra seeds. '
               'This is a study allocation, not a global research stopping limit.',
        full_policy='Recorded priority family supplied only for this diagnostic. Any policy claim '
                    'requires new fields on EVERYdecision and normalized joint redecoding against '
                    'retained complete predictors, with original per-category/movement/macro/loss/'
                    'targeting guards and three-seed criteria. No promotion here.',
        restrictions='MODELonly; preserve every old artifact; both75gamepartitions sealed; '
                     'no matches/simulations/downloads/bot/runtime/deployment. PR11DRAFTunmerged.',
        new_fits=0,reserved_opened=0)
    immutable_json(OUT/'RC-plan.json',plan)
    return plan


if __name__=='__main__':freeze()
