"""Prospective Q01 controlled attribution; no optimizer or replacement selection."""
import json
from pathlib import Path
from .sequence_data import ROOT, WORK, REPORT
from .pathway_inputs import CONTRASTS
from ..audit import immutable_json
from ..data import digest

LOCAL=ROOT/'.cambc/action-predictor/v17'
OUT=ROOT/'tools/action_predictor/experiments/v17'


def freeze():
    OUT.mkdir(exist_ok=True);LOCAL.mkdir(exist_ok=True)
    names=('pathway_inputs.py','pathway_protocol.py','pathway_reference.py','pathway_study.py','pathway_evaluate.py','test_pathway_inputs.py')
    sources={name:digest(Path(__file__).parent/name) for name in names}
    original=json.loads((REPORT/'policy-design.json').read_text())
    core={name:digest(Path(__file__).parent/name) for name in ('model.py','data.py','inference.py')}
    for name,value in core.items():assert value==original['sources'][name],name
    upstream={name:digest(ROOT/'tools/action_predictor'/name) for name in
        ('reliable_model.py','reliable_train.py','priority_fit_v3.py','entity_set.py',
         'observation_metrics.py','movement_experts/evaluate.py','learned_policy/public_inputs.py')}
    bindings={}
    for identifier in ('L01','L02'):
        info=json.loads((REPORT/f'{identifier}.json').read_text())
        path=WORK/f"runs/{identifier}/round-{info['selected_round']:02d}.pt"
        assert digest(path)==info['checkpoint_sha256']
        bindings[identifier]=dict(checkpoint_sha256=info['checkpoint_sha256'],selected_round=info['selected_round'],
            train_predictions_sha256=info['predictions_sha256']['train'],validation_predictions_sha256=info['predictions_sha256']['validation'])
    plan=dict(id='Q01-TRAIN-mean-goal-projection-attribution',models=['L01','L02'],new_training_fits=0,
        purpose='Test incremental dependence/usefulness of variable goal projection channels versus constant offsets, anchored to demonstrated execution collapse. No new architecture, optimizer, checkpoint or policy promotion.',
        controls='Original retained L01/L02 checkpoints and their unchanged decoder, all original14439DEV rows; baseline reproduction before interpreting contrasts.',
        contrasts=list(CONTRASTS),
        reference='Use all288801 identity-verified natural TRAIN rows during original augmented causal traversal. Per-model/per-latent-component means, no action-label or future-target conditioning. Geometry mean among current-position-known rows, zero geometry kept when position unknown. Logscale means stratified by current-position availability. Availability channel uses unconditional TRAIN mean; only its linear projection contribution is neutralized, never real flags/masks. Each centered contribution has zero TRAIN mean up to declared floating precision.',
        mean_preservation='Keep goal_condition.bias in every mean contrast and preserve the TRAIN mean projected offset. bias_off and full projection_off are separate non-mean-preserving calibration/pathway controls, not interchangeable with mean contrasts.',
        inference_modes={'fixed':'Each contrast changes only current readout from original baseline step/prior/world/history. All shadow posterior updates discarded. These are fixed-state diagnostics, not an autonomous/refiltered policy.',
            'refilter':'Each contrast has its own forward filter. Predict before reading current answer; after action occurs assimilate that actual recorded action under the contrast likelihood. All current/past personal observations and true gaps retained. No future state, smoothing, oracle type routing or game simulation.'},
        data='Existing eligible TRAIN/DEV caches only. No replay extraction/download/495-game audit. Future achieved positions/availability never used for references, selection, forecasting or filter updates.',
        metrics=['Full complete-command exactness, action macroF1/confusion/false positives and observed joint NLL; same original helpers/denominators',
            'Per-category joint/type/all-true-family/correctly-typed parameters and NLL; paired2000 whole-group draws seed20261106 versus corresponding original model',
            'Movement continuation/change/startup; recorded-destination probability and first-argmax-tie rank; TV versus original readout',
            'Component conditional modes, union, current common-wrong dominance bounds, goal weights/diversity; distinguish fixed states from changed causal filter histories',
            'Unknown-position/context support, partial readiness and successful-move versus blocked-attempt mask rejection separately'],
        TRAIN_limit='Full original TRAIN baselines retained; TRAIN-derived references and Q00 bounded development sensitivity are not full TRAIN counterfactual-policy scores. Do not claim a matched TRAIN/DEV generalization effect for all contrasts.',
        numerical_contract='Unchanged original model/decoder sources. Baseline integer/semantic prediction arrays exact; observed NLL/type/parameter arithmetic absolute discrepancy<=2e-5, retaining historical failed all-bucket absolute-log check as failed. Mean projected offset discrepancy<=1e-6. All model weights fingerprint-identical before/after. Identity contrast must preserve forward/state.',
        interpretation='Fixed-weight pathway dependence is not information sufficiency, strategic intent, proof of retraining benefit or all-goal-path removal. Five repeatedly reused DEV groups, selected checkpoints, exploratory contrasts; no variant/threshold selected as a replacement and no robustness claim.',
        continuation='Fresh requested Sol6.1xhigh review after complete study. Address findings, continue to the next distinct evidence-driven model experiment automatically; no overall research cap under current user authority.',
        scope='Model-only. Both75-game reserved partitions sealed, no matches/proposed-action game simulations/downloads/bot/runtime/native/SDK/export/deployment. Shops unavailable strict failures; sparse categories/identity/full legality uncertified. PR11 draft/open/unmerged/no-auto-merge/queue.',
        sources=sources,core_model_sources=core,upstream_sources=upstream,model_bindings=bindings,input_receipt_sha256=digest(REPORT/'policy-input-bindings.json'),
        prior_review_sha256=digest(REPORT/'L02-review-response.json'),new_fits=0,reserved_opened=0)
    immutable_json(OUT/'Q01-plan.json',plan)
    return plan


if __name__=='__main__':freeze()
