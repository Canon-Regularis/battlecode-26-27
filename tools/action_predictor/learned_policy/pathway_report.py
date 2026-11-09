"""Immutable prose/compact table from Q01's preserved measurement artifacts."""
import json
import numpy as np
from .pathway_protocol import LOCAL,OUT
from .pathway_inputs import CONTRASTS
from .analysis import read
from .model import SPATIAL
from ..audit import immutable_json
from ..data import digest


def equal_mode(a,b):
    same=a['prediction']==b['prediction'];spatial=np.isin(a['prediction'],SPATIAL)
    return same&(~spatial|(a['proposed_coordinate']==b['proposed_coordinate']))&((a['prediction']!=9)|(a['priority']==b['priority']))


def run():
    text=['# Q01: variable waypoint projection has little measured influence','',
        'This frozen-checkpoint study separates geometry, predicted log scale, availability and constant offsets. It trains no model. All original14,439 DEV rows are retained, with predicted action choices for complete commands. Fixed-state shadow readouts and separately causal-refiltered variants are distinct diagnostics, not autonomous playing-strength evaluations.','',
        '**Numerical qualification:** the original2e-6 conditional-normalization criterion FAILED for both models. It remains failed. The first producer asserted before saving arrays, so its in-memory forecasts were lost; source/protocol/references/failure traces were preserved. Versioned recovery retained every primary forecast before checks and used independent float64 arithmetic to diagnose the issue. No primary probabilities, decoder, models, inputs, rows or benchmark success targets were changed.','',
        'References come only from all288,801 identity-verified natural TRAIN rows under original augmented traversal. Means are per model/component. Geometry stays zero without current position; log-scale references are stratified by current-position availability; the availability mean alters only its projection contribution, not real flags/masks. Learned bias remains in mean contrasts. These contrasts retain mean offsets and availability-dependent reference structure; they do not remove all goal information or every goal pathway.','']
    compact={};differences={}
    for identifier in ('L01','L02'):
        evaluation=json.loads((OUT/f'Q01-{identifier}-evaluation-v2.json').read_text());results=evaluation['results'];base=results['baseline']
        ref=json.loads((OUT/f'Q01-{identifier}-reference.json').read_text());numeric=json.loads((OUT/f'Q01-{identifier}-numerical-cases.json').read_text())
        text.extend([f'## {identifier}','',
            f"Reference mean-projection discrepancy: {ref['max_mean_projection_difference']:.3g}. Baseline integer arrays match the original archive exactly. All weights remain unchanged.",'',
            '| Readout | Complete | Mode changes | Rescues/regressions | NLL difference | Move conditional/joint | Change joint | Common-wrong moves |',
            '| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |'])
        compact[identifier]={};differences[identifier]={}
        for label,row in results.items():
            m=row['movement']['move'];ch=row['movement']['change'];o=row['overall'];delta=o['joint_nll']-base['overall']['joint_nll']
            text.append(f"| {label} | {o['strict_correct']} | {row['semantic_observed_mode_changes']} | {row['rescues']}/{row['regressions']} | {delta:+.8f} | {m['conditional_correct']}/{m['joint_correct']} | {ch['joint_correct']} | {m['common_wrong_component_mode']} |")
            compact[identifier][label]=dict(complete=o['strict_correct'],macro_f1=o['macro_f1'],joint_nll=o['joint_nll'],
                mode_changes=row['semantic_observed_mode_changes'],rescues=row['rescues'],regressions=row['regressions'],
                move_conditional=m['conditional_correct'],move_joint=m['joint_correct'],change_joint=ch['joint_correct'],
                component_mode_union=m['component_mode_union'],common_wrong=m['common_wrong_component_mode'],
                current_reweighting_bound=m['conservative_conditional_reweighting_ceiling'],
                conditional_move_TV_mean=m['conditional_TV_from_original']['mean'],
                paired_overall=None if label=='baseline' else row['paired_original']['overall']['paired95'])
        for c in CONTRASTS:
            a=read(LOCAL/f'Q01-v2/{identifier}/fixed--{c}-predictions.npz')
            b=read(LOCAL/f'Q01-v2/{identifier}/refilter--{c}-predictions.npz')
            differences[identifier][c]=int((~equal_mode(a,b)).sum())
        text.extend(['',f"Fixed versus refiltered observed-mode differences: `{differences[identifier]}`.",'',
            f"Independent float64 worst-case batches: {numeric['cases_checked']} (duplicates across scopes possible), {numeric['semantic_MAP_mismatches_valid']} semantic MAP mismatches; maximum observed-NLL discrepancy {numeric['max_NLL_discrepancy_valid']:.3g}. This is a bounded arithmetic check, not a full independent causal filter.",''])
    text.extend(['## What this establishes','',
        'Geometry mean replacement changes only3/6 observed command modes in L01/L02; their correct movement counts remain1,372/1,365 and conditional destinations1,437/1,428. Mean conditional-movement TV is about.000371/.001366. This is weak current dependence, not literally zero probability influence or proof that better goal information could not help. Geometry may also be represented redundantly in other pathways.','',
        'Replacing all tested projection variations with their defined TRAIN references changes12/21 modes, net complete commands-1/+3. Removing learned bias alone changes38/33 modes, net-6/-2; removing the entire projection changes228/223 fixed-state modes, net-30/-10. These nonlinear contrasts are not additive causal fractions: do not attribute a percentage of the effect to bias, calibration or geometry. They support the importance of mean/pathway contributions while providing little evidence that variable waypoint geometry currently steers execution successfully.','',
        'Component distributions remain the dominant demonstrated movement limitation. Geometry neutralization leaves current mode unions and common-wrong counts nearly unchanged. Current reweighting bounds freeze each branch distributions and past state; they are oracle diagnostics, not achieved accuracy or architecture/data ceilings. Conditional movement supplies the recorded family only after forecasting for diagnosis. All primary complete-command predictions use predicted families and their actual required parameters.','',
        'The original normalization failures were not caused solely by padding: maxima also occur on valid decisions. Worst rows are recorded/predicted end actions, with hypothetical movement type log probability around-36.39/-34.44. Float32 subtraction in the derived conditional representation exhibits cancellation. Independent normalized float64 conditional mixtures have sum errors below1.6e-15, zero conditional-mode discrepancies across checked real move/blocked distributions, and maximum observed-family NLL discrepancy below1.2e-6. Worst full-batch complete-MAP checks also agree. This supports the primary counts within the older meaningful-NLL numerical contract, while the original tighter normalization criterion still fails. It is not evidence that this small numerical discrepancy explains the large imitation errors.','',
        'Every correctly typed spatial diagnostic coordinate matches the actual selected argument across all26 branches. No dominated/common-wrong component row is simultaneously marked primary-correct. The artifact-contract and numerical-case receipts retain the checks and qualifications.','',
        'Per-category PRF/confusion/false positives, all-true-family and correctly-typed parameters, category losses, unknown-position contexts, continuation/change metrics, target probability/rank, partial readiness and paired2,000 whole-group intervals are in the evaluation JSONs. All five DEV groups have been repeatedly reused after checkpoint selection; intervals are not untouched, multiplicity/selection adjusted or three-seed evidence. No contrast is selected as a replacement policy. Full counterfactual TRAIN scores were not computed, so this does not isolate a TRAIN/DEV generalization effect.','',
        '## Next question','',
        'A justified training hypothesis is whether dynamic learned-goal geometry becomes useful when supplied directly to candidate-conditioned execution, compared with an identical-capacity/head/initialization control receiving TRAIN-mean geometry. That would test the demonstrated weak injection path rather than another retention or auxiliary-weight variation. It must preserve causal goal inference, learn scores from demonstrations, avoid hand-designed strategies, retain probability-consistent decoding and original regression guards, and be registered/reviewed independently. It is proposed, not implemented or fitted; the fresh review should challenge it against target-quality and representation alternatives.','',
        'This study does not identify Fish intent, show observation sufficiency or certify learned strategic persistence. Future-position supervision may be an imperfect objective proxy; no contradiction or irreducibility is proven. Original category/macro/movement/NLL/targeting/three-seed goals remain unmet. All43DEV shops remain unavailable strict failures with absent argument likelihood. Sparse altar/teleport/submit, entity identity and full legality/calibration remain uncertified. Successful-move mask rejection and blocked-attempt diagnostics are separate.','',
        'Research continues automatically after fresh Sol6.1xhigh review and justified corrections. No optimizer, matches, replay downloads, reserved-partition access, playing-bot/runtime work or deployment occurred. Both75-game reservations remain sealed; PR11 staysDRAFT/open/unmerged/no-auto-merge/queue.',''])
    path=OUT/'Q01-REPORT.md';assert not path.exists();path.write_text('\n'.join(text))
    immutable_json(OUT/'Q01-summary.json',dict(results=compact,fixed_vs_refiltered_mode_differences=differences,
        source_sha256=digest(__file__),report_sha256=digest(path),
        evaluation_sha256={n:digest(OUT/f'Q01-{n}-evaluation-v2.json') for n in ('L01','L02')},
        new_fits=0,reserved_opened=0,promoted=False))


if __name__=='__main__':run()
