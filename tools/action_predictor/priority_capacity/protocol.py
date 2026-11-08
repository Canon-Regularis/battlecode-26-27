"""Prospective small-set capacity protocol; original benchmark unchanged."""
from pathlib import Path
from ..audit import immutable_json
from ..data import digest

ROOT = Path(__file__).resolve().parents[3]
OLD = ROOT / '.cambc/action-predictor'
LOCAL = OLD / 'v19'
OUT = ROOT / 'tools/action_predictor/experiments/v19'
SEED = 20261120


def freeze():
    source = Path(__file__).parent
    names = ('__init__.py', 'protocol.py', 'data.py', 'measurement.py', 'fit.py', 'test_measurement.py')
    plan = dict(id='PC00-actual-P05-capacity', new_fits_allocated=1,
        purpose='Can the actual P05 value model fit a fixed small diverse set, and what happens '
                'on controls held out from this new optimization? No new architecture or full-policy promotion.',
        model='Warm-start the retained selected P05 absolute/residual/logistic mixture, with all '
              'linear weight/bias parameters trainable. Frozen M01 contexts, existing39causal '
              'priority channels, original normalization and exact int64 anchor inputs. Original '
              'P05 probability arithmetic and integer MAP. No current/future argument input.',
        cohort='Fit: the128natural-TRAIN priority rows in frozen R02 fit indices. Same-fit-group '
               'control:128other natural priority rows from groups actually represented in those128, '
               'fixed seed20261120, excluding fit rows. Held-group control:128priority rows from '
               'R02 held_group indices, whose groups are disjoint from fit. Freeze row identities '
               'and support before optimization. This conditional diagnostic does not drop any '
               'row or category from the original benchmark.',
        exposure='Encoder, normalization, vocabulary/prior counts AND warm P05 head previously saw '
                 'eligible TRAIN including control rows/groups. Controls are held out ONLY from '
                 'new head optimization; not untouched full-policy/group generalization evidence.',
        training=dict(seed=SEED, updates=2000, full_fit_batch=128, optimizer='AdamW',
                      lr_first1000=.003, lr_last1000=.001, weight_decay=0, gradient_clip=5,
                      loss='Mean normalized conditional integer NLL over all128fit rows per update. '
                           'Different presentation/optimization from original full-data P05; capacity '
                           'probe, not an isolated causal comparison to that training protocol.'),
        assessment_steps=[0,100,500,1000,2000], checkpoint='Fixed final2000; assessments descriptive only. '
                    'No DEV lookups/selection, early stopping, threshold tuning or promotion. '
                    'Original full-DEV .0001/pat6/max35 rule remains unchanged for benchmark fits.',
        metrics=['Exact integers, mean NLL and integer MAE/quantiles on fit and both controls',
                 'Rank among DISTINCT existing point/fallback-mode candidates, explicitly not full-Z rank',
                 'Posterior absolute/residual/fallback shares of recorded-target probability; '
                 'equivalent explanations marginalized, no true-intent labels',
                 'Support/availability and trainable-parameter/optimizer/gradient checks'],
        preflight='Before optimizer: exact integer-mode parity with retained G00/P05 TRAIN arguments '
                  'and conditional-NLL difference<=2e-5 on all384cohort rows. Save raw outputs/checkpoint '
                  'before checks. Reuse approved extraction evidence; no repeated495game audit.',
        diagnostic_fit_gate=dict(exact_at_least=.95, mean_NLL_at_most=.25,
             qualification='Named finite-budget capacity criterion, not original success. Passing '
                           'demonstrates small-set fitting only; failing does not prove a hard capacity '
                           'limit or information insufficiency. Inspect support/gradients/optimization.'),
        continuation='Fresh Solxhigh after this fit. If fitting succeeds but controls deteriorate, '
                     'investigate representation/transfer and prior exposure. No architecture change '
                     'or repeated seed automatically follows. Continuing research has no global cap.',
        integration='No complete-policy replacement in this diagnostic. Any later comparison must '
                    'recompute normalized joint action/parameter probabilities and predicted families; '
                    'cannot merely swap integers while inheriting old hard action choices.',
        constraints='EligibleTRAINonly. Both75game reservations sealed, DEVunopened by this probe. '
                    'No matches/downloads/bot/runtime work/deployment. Original datasets, folds, '
                    'checkpoints and all category/likelihood/three-seed targets preserved.',
        sources={name:digest(source/name) for name in names},
        dependencies={name:digest(source.parent/name) for name in (
            'priority_residual_modes.py','priority_modes.py','priority_head.py','priority_fit_v3.py')},
        new_fits=0, reserved_opened=0)
    immutable_json(OUT/'PC00-plan.json', plan)
    return plan


if __name__ == '__main__':
    freeze()
