"""Prospective matched-readout protocol; continuing research has no global cap."""
import json
from pathlib import Path
from ..learned_policy.sequence_data import ROOT, BASE, WORK as V16, REPORT as V16_REPORT
from ..audit import immutable_json
from ..data import digest

LOCAL = BASE.parent / 'v18'
OUT = ROOT / 'tools/action_predictor/experiments/v18'
V17 = OUT.parent / 'v17'
SEED = 20261114
ARMS = {'U00': False, 'U01': True}


def freeze():
    directory = Path(__file__).parent
    names = ('__init__.py', 'protocol.py', 'model.py', 'cache.py', 'data.py',
             'inference.py', 'fit.py', 'preflight.py', 'evaluate.py', 'test_model.py')
    sources = {name: digest(directory / name) for name in names}
    info = json.loads((V16_REPORT / 'L02.json').read_text())
    checkpoint = V16 / f"runs/L02/round-{info['selected_round']:02d}.pt"
    assert digest(checkpoint) == info['checkpoint_sha256']
    bindings = {str(checkpoint.relative_to(ROOT)): info['checkpoint_sha256']}
    for p in (V16_REPORT / 'policy-input-bindings.json', V16_REPORT / 'L02-completion.json', V16_REPORT / 'L02.json',
              V17 / 'Q01-L02-reference.json', V17 / 'Q01-review-response.json'):
        bindings[str(p.relative_to(ROOT))] = digest(p)
    for name in ('model.py', 'data.py', 'inference.py', 'pathway_reference.py', 'pathway_inputs.py'):
        p = directory.parent / 'learned_policy' / name
        bindings[str(p.relative_to(ROOT))] = digest(p)
    for name in ('reliable_model.py', 'reliable_train.py', 'movement_experts/evaluate.py',
                 'observation_metrics.py', 'learned_policy/analysis.py'):
        p = directory.parent / name
        bindings[str(p.relative_to(ROOT))] = digest(p)
    natural = BASE.parent / 'v9/frequency/natural-mask.npy'
    assert digest(natural) == '09217d8fc3d5673d980c8b8a4434861aa26dddb37e506bbfa22cbaafc0e525bd'
    bindings[str(natural.relative_to(ROOT))] = digest(natural)
    plan = dict(id='V18-frozen-upstream-readout', arms=ARMS, seed=SEED,
        upstream='One fixed L02 selected checkpoint. All forecaster, representations, latent context, '
                 'prior and posterior filtering remain common and frozen. Cache each PRE before '
                 'assimilating that recorded action. No future-position supervision or answer enters '
                 'the readout inputs. Filtering uses the frozen baseline likelihood, not trained readouts.',
        contrast='U00 replaces only projection relative-world geometry with the defined per-component '
                 'natural TRAIN mean, zero when current position unknown. U01 retains dynamic causal '
                 'predicted geometry. Current predicted uncertainty/availability, latent contexts, '
                 'bias and every other input are identical. Other geometry pathways remain common.',
        architecture='No new scorer. Copies of the existing action/query/candidate/family/offset/special '
                     'heads and five-channel goal_condition projection. Initialization weights exactly '
                     'identical between arms; only dynamic flag differs. All other weights frozen.',
        objective='Original unweighted observed complete-command marginalized NLL, no auxiliary loss '
                  'because upstream is fixed. Duplicate latent explanations marginalized, joint MAP '
                  'uses original GoalPolicy.decode. Shop argument likelihood absent, strict failure.',
        training=dict(lr=.0003, weight_decay=.01, clip=5, max_rounds=35, patience=6,
                      min_improvement=.0001, checkpoint='Original full14439DEV command NLL',
                      order='Same seeded original sequence chunks,32actors x8selectednodes; flatten '
                            'real rows into one readout update. No upstream BPTT or sampled adjacency.',
                      epochs='Every433071TRAIN row once per round; augmented and natural-membership '
                             'scores separate. Same maximum allowance/rng/order in both arms.'),
        allocation='Two matched fits in this diagnostic study, fresh Sol xhigh after EACH fit. '
                   'No repeats/promotion without prospective new budget and meaningful category benefit. '
                   'This is no global research stopping rule. Complete matched contrast even if control '
                   'alone is negative unless a correctness/access/resource blocker appears.',
        metrics=['strict complete commands and every category PRF/confusion/type and joint FP',
                 'observed command/type/argument NLL with absent shop argument likelihood explicit',
                 'all-true-family versus correctly typed parameters, matched targeting regressions',
                 'move/blocked continuation/change/startup, history/position availability',
                 'true destination rank/probability, component diversity/common-wrong bound',
                 'augmented/natural TRAIN, DEV,2000paired whole-group draws seed20261106',
                 'direct U01-U00 plus retained L02/L01/B00/G00 complete-predictor comparisons'],
        continuation='Exploratory allocation criterion, separate from original success targets: dynamic '
                     'versus mean must lower DEV command NLL and conditional change NLL, gain at least '
                     '.01 absolute conditional change accuracy with no joint-change loss, no continuation '
                     'conditional drop beyond .005, no overall strict-count loss and no attack/cast '
                     'conditional targeting drop beyond original .02 guard. Report all differences '
                     'regardless; one seed cannot certify robustness. Original goals remain binding. This comparison '
                     'does not recover intent or certify a fully retrained persistent policy. TRAIN-only '
                     'benefit suggests transfer failure; neither benefit leaves forecasts/optimization '
                     'and executor limitations unresolved. No retrospective thresholds/checkpoint choice.',
        original_targets=dict(each_supported_category_joint=.90, macro_F1=.65,
                              movement_joint=.6520745131244708, target_regression_max=.02,
                              NLL='10% lower than strongest relevant baseline', seeds=3),
        constraints='Both75-game reservations sealed; all originalDEV rows; no matches, downloads, '
                    'bot/runtime work or deployment. PR11DRAFT/open/unmerged/noauto-merge/queue. '
                    'Sparse categories, identity ambiguity, full legality/calibration remain uncertified.',
        sources=sources, bindings=bindings, new_fits=0, reserved_opened=0)
    immutable_json(OUT / 'protocol.json', plan)
    return plan


if __name__ == '__main__':
    freeze()
