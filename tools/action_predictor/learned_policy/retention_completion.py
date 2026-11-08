"""Immutable L02 model-only reproduction inventory, excluding paused bot work."""
import json
import subprocess
from pathlib import Path
from .sequence_data import ROOT, WORK, REPORT
from ..audit import immutable_json
from ..data import digest


def run():
    info=json.loads((REPORT/'L02.json').read_text())
    protocol=json.loads((REPORT/'L02-protocol.json').read_text())
    source=Path(__file__).parent
    for name,h in protocol['sources'].items():assert digest(source/name)==h,name
    original=json.loads((REPORT/'policy-design.json').read_text())
    for name,h in original['sources'].items():assert digest(source/name)==h,name
    files=list((WORK/'runs/L02').glob('round-*.pt'))
    files.extend((WORK/'runs/L02').glob('*.npz'))
    files.extend((WORK/'natural-evaluation/L02').glob('*.npz'))
    files.extend((WORK/'runs/L01').glob('*-direct-memory.npz'))
    files.extend(p for p in REPORT.glob('L02*') if p.name!='L02-completion.json')
    files.extend(REPORT.glob('L01-*-direct-memory.json'))
    files.extend(REPORT/name for name in ('L01-review-response-v2.json','continuation-authority.json','policy-design.json','policy-input-bindings.json',
        'L01.json','L01-model-completion-v2.json','L01-REPORT.md','L01-analysis.json','L01-natural-cadence.json',
        'component-execution-plan.json','natural-cadence-evaluation-plan.json','analysis-plan.json'))
    files.extend(source.glob('retention_*.py'))
    files.extend((source/'completion_sources').glob('retention_memory_*.py'))
    files.extend(source/name for name in ('model.py','data.py','inference.py','fit.py','analysis.py','components.py',
        'dominance_bounds.py','natural_evaluation.py','matched_movement.py','current_oracles.py'))
    files.extend(WORK/f'runs/L01/{split}-predictions.npz' for split in ('train','validation'))
    files.append(WORK/f"runs/L01/round-{json.loads((REPORT/'L01.json').read_text())['selected_round']:02d}.pt")
    commands=['retention_preflight','retention_fit L02','analysis L02','matched_movement L02','retention_evaluate',
        'components L02 train','components L02 validation','dominance_bounds L02 train','dominance_bounds L02 validation',
        'natural_evaluation L02','retention_memory L01 train','retention_memory L01 validation',
        'retention_memory L02 train','retention_memory L02 validation','current_oracles L02','retention_report','retention_completion']
    immutable_json(REPORT/'L02-completion.json',dict(
        fit_source_commit=info['source_commit'],inventory_commit=subprocess.run(['git','rev-parse','HEAD'],cwd=ROOT,capture_output=True,text=True,check=True).stdout.strip(),
        protocol_sha256=digest(REPORT/'L02-protocol.json'),checkpoint_sha256=info['checkpoint_sha256'],
        selected_round=info['selected_round'],selected_updates=info['selected_updates'],completed_updates=info['completed_updates'],
        bindings={str(p.relative_to(ROOT)):digest(p) for p in sorted(set(files))},
        commands=['.venv-action-predictor/Scripts/python.exe -m tools.action_predictor.learned_policy.'+c for c in commands],
        reproduction='Training/diagnostic producers refuse existing output directories/receipts. Do not rerun fits or overwrite artifacts. All original L00/L01 sources, reports, checkpoints and predictions preserved.',
        timing_scope='Fit seconds excludes loading; includes optimizer rounds, DEV scoring, final full inference, serialization and evaluation. Additional direct-memory L01 diagnostics overlapped training, so no isolated speed comparison is claimed.',
        treatment='Only direct retention.weight/bias derivatives from auxiliary removed through entire unroll. Other parameters retain original combined loss gradient; clipping/AdamW and all forward/evaluation code unchanged. Indirect auxiliary effects through representations remain.',
        scope='Model training/evaluation only. Paused bot/native artifacts excluded; no matches/downloads/reserved access. Shops remain unavailable strict failures; observed likelihood omits their argument loss. Sparse categories, entity ambiguity and incomplete legality remain uncertified.',
        new_fits=0,reserved_opened=0,promoted=False,three_seed_confirmed=False))


if __name__=='__main__':run()
