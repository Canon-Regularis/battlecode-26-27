"""Pre-final-review inventory including late diagnostics and corrected commands."""
import json
from .protocol import ROOT,WORK,REPORT
from ..audit import immutable_json
from ..data import digest

def run():
    target=REPORT/'X00-evidence-inventory.json';reports={str(p.relative_to(ROOT)):digest(p) for p in REPORT.iterdir() if p.is_file() and p!=target and p.name!='STATUS.md'};sources={str(p.relative_to(ROOT)):digest(p) for p in (ROOT/'tools/action_predictor/movement_experts').glob('*.py')};artifacts={}
    for name in ('S00','X00'):
        for p in (WORK/'runs'/name).iterdir():
            if p.is_file():artifacts[str(p.relative_to(ROOT))]=digest(p)
    commands=['python -m tools.action_predictor.movement_experts.fit S00','python -m tools.action_predictor.movement_experts.roundtrip S00','python -m tools.action_predictor.movement_experts.analysis S00','python -m tools.action_predictor.movement_experts.loss_supplement S00','python -m tools.action_predictor.movement_experts.error_ledger S00','python -m tools.action_predictor.movement_experts.fit X00','python -m tools.action_predictor.movement_experts.roundtrip X00 [RECORDED FAILED PREFLIGHT, do not call a pass]','python -m tools.action_predictor.movement_experts.roundtrip_diagnostic X00','python -m tools.action_predictor.movement_experts.components','python -m tools.action_predictor.movement_experts.analysis X00','python -m tools.action_predictor.movement_experts.loss_supplement X00','python -m tools.action_predictor.movement_experts.error_ledger X00','python -m tools.action_predictor.movement_experts.evidence_inventory']
    immutable_json(target,dict(reports=reports,sources=sources,artifacts=artifacts,commands=commands,fit_execution_commits={n:json.loads((REPORT/f'{n}.json').read_text())['source_commit'] for n in ('S00','X00')},qualification='Snapshot before fresh final review. Existing run directories intentionally reject refits; commands document execution/reproduction in a separate initialized cache, not instructions to rerun old fits. Generic X00 completion recipe is superseded here by the explicitly failed original probability check plus numerical attribution diagnostic. No model/checkpoint/threshold change. Mutable STATUS excluded.',serving_scope='179 raw cases: all predicted types checked, 74 modified movement/blocked command arguments checked; exact raw inputs except128frozencontext rounding. Unchanged argument paths reuse prior G00 evidence. Original2e-5logp check remains failed for blocked conditional at13393, predicted end. SameRAWcontext gives exact headlogp. No all-row raw or complete API/shop guarantee.',budget=dict(allocated=2,completed=2,repeat_seeds=0,extra_fits=0),ward_protocol='User discontinued after3/4 fits; T01 never run; not completed.',source_sha256=digest(__file__),new_fits=0,reserved_opened=0,promoted=False,three_seed_confirmed=False));print('V15 pre-review evidence inventory complete',flush=True)

if __name__=='__main__':run()
