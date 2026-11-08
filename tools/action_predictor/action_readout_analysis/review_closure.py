"""Bind AB01's fresh review to additive corrections; no model operations."""
from ..audit import immutable_json
from ..data import digest
from ..policy_action_readout.protocol import OUT


def run():
    immutable_json(OUT/'AB01-review-response.json', dict(
        review_sha256=digest(OUT/'AB01-review.json'),
        delegation_sha256=digest(OUT/'AB01-review-delegation.json'),
        launch_sha256=digest(OUT/'AB01-review-delegation-launch.json'),
        reviewed_checkpoint_sha256='fcc2a471d6cb7fc3847df802e978430301d5494c5f335529876959a5ded88fe3',
        correction_sha256=digest(OUT/'AB01-closure-correction.json'),
        responses={'stale_language':'Additive closure supersedes next-arm/control-only text; both arms complete and negative.',
            'augmented_only':'Saved-output correction supplies all144270augmented-only rows and complete category/NLL metrics; no refit or denominator change.',
            'main_bottleneck':'Frozen movement modes miss934/2362even with perfect action choice. Main effort jointly trains actual movement execution and neural duration/state inference against a direct sequence control.',
            'limits':'No information-insufficiency, hidden-intent, robustness, promotion or complete-policy-success claim. Later segment-policy implementation is outside AB01 review scope.'},
        caught_closure_writer_failure='An attempted addition changed the producer hash embedded in an already immutable correction. The rewrite was refused. Original producer bytes restored; separate review-response producer added. No fit or original report changed.',
        reproduction='python -m tools.action_predictor.action_readout_analysis.review_closure',
        correctness_findings_addressed=True, promoted=False, new_fits=0, reserved_opened=0))


if __name__ == '__main__': run()
