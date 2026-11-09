"""Document actual-head fitting, pre-exposed controls and execution provenance."""
import json
import subprocess
from pathlib import Path
from .protocol import ROOT,LOCAL,OUT
from ..audit import immutable_json
from ..data import digest


def run():
    info=json.loads((OUT/'PC00.json').read_text());analysis=json.loads((OUT/'PC00-analysis.json').read_text())
    first,last=info['trace'][0]['cohorts'],info['trace'][-1]['cohorts']
    lines=['# PC00: actual P05 can fit128priority examples; fine-tuning harms controls','',
        'One conditional value-head capacity diagnostic uses the actual retained P05 architecture, '
        'warm weights, normalized frozen M01 contexts,39recovered causal priority channels and exact '
        'int64 anchors. No action selector or full-policy model is replaced.', '',
        '| Cohort | Exact initially | Exact final | NLL initially | NLL final |',
        '| --- | ---: | ---: | ---: | ---: |']
    for name in first:
        lines.append(f"| {name} | {first[name]['exact']}/{first[name]['rows']} | "
                     f"{last[name]['exact']}/{last[name]['rows']} | {first[name]['mean_NLL']:.6f} | {last[name]['mean_NLL']:.6f} |")
    lines += ['', 'All128fitted integers are correct by update100 and remain correct at the fixed '
        'final update2000. This meets the declared small-set capacity gate. It demonstrates fitting '
        'these examples with this actual head/input setup, not general recoverability, learning '
        'Fish intent or the original category goal.', '',
        'Controls are disjoint from the new head optimization. Same-fit-group controls draw from '
        'groups actually represented by fit rows; held-group controls use disjoint groups. However '
        'the frozen M01 encoder, normalization, vocabulary/counts AND warm P05 head previously saw '
        'eligible TRAIN including these controls. Their deterioration is not untouched full-policy '
        'generalization evidence. Local fine-tuning can forget prior knowledge.', '',
        'The supplemental post-fit label-coverage strata retain all128rows per cohort and separate '
        'targets with absolute/residual explanation labels present versus absent in the new microfit. '
        'Coverage shifts and forgetting limit causal attribution of control decline. See analysis; '
        'no subset or earlier checkpoint is substituted for the declared final result.', '',
        'Target rank is among distinct existing point/fallback-mode candidates, not all integers. '
        'Absolute/residual/fallback credits marginalize equivalent probability explanations; they '
        'are not unique true algorithms or intent labels. Every target is in the existing absolute '
        'vocabulary. No new values/library expansion or missing-label deletion.', '',
        'R02’s3/128 came from a different single-logistic head and representation. This is not a '
        'controlled architecture comparison against R02. The optimizer/presentation and warm-start '
        'also differ. P05’s original full-data selected modes remain the benchmark comparison.', '',
        '**Execution provenance:** the fit ran after a source-archive assertion made the intended '
        'commit step fail. The parent failed to gate the later tool call on that failure. Therefore '
        f"recorded execution commit `{info['source_commit']}` does not contain PC00 source. The "
        'protocol/source hashes were frozen before optimization and match the preserved exact '
        'executed-source bundle and subsequent source commit. Checkpoint commit fields are not '
        'rewritten, and the fit is not rerun. See PC00-execution-provenance.json. A separate earlier '
        'synthetic availability-fixture failure and newline reconstruction failure are preserved.', '',
        'All207816head parameters are trainable and optimizer membership is checked explicitly. '
        'First-update parameter/output gradient norms, all five assessment checkpoints, raw outputs '
        'and probabilities are retained. The final2000step checkpoint is fixed, with no DEV lookup, '
        'early stopping or retrospective selection. Two focused measurement tests pass. Extraction '
        'and causal integer recovery reuse prior immutable evidence; no repeated495game audit.', '',
        'Only conditional integer diagnostics are reported: action type is supplied as priority. '
        'There is no deployable joint accuracy or full-policy improvement claim. Any later policy '
        'comparison must re-decode normalized joint probabilities because new integer probabilities '
        'can change the winning action family. Original benchmark/success targets remain binding.', '',
        'Both75game reservations stay sealed. No DEV payload is consumed by this probe. No matches, '
        'downloads, bot/runtime work or deployment. No promotion or robustness claim. Fresh Solxhigh '
        'review follows, then research continues from evidence.', '']
    report=OUT/'PC00-REPORT.md';assert not report.exists();report.write_text('\n'.join(lines))
    files=list((LOCAL/'runs/PC00').glob('*'))+list((LOCAL/'PC00-cohorts').glob('*'))
    files+=list((LOCAL/'PC00-executed-sources').glob('*'))+list((LOCAL/'unit-failure').glob('*'))
    files+=list(Path(__file__).parent.glob('*.py'))
    files+=[p for p in OUT.glob('PC00*') if p.name!='PC00-completion.json']
    ready=json.loads((OUT/'PC00-data-ready.json').read_text())
    files+=[ROOT/name for name in ready['bindings']]
    immutable_json(OUT/'PC00-completion.json',dict(
        execution_git_head=info['source_commit'],sources_uncommitted_at_execution=True,
        source_preservation_commit='f55ec55',
        inventory_commit=subprocess.run(['git','rev-parse','HEAD'],capture_output=True,text=True,check=True).stdout.strip(),
        fixed_final_step=2000,bindings={str(p.relative_to(ROOT)):digest(p) for p in sorted(set(files))},
        commands=['.venv-action-predictor/Scripts/python.exe -m tools.action_predictor.priority_capacity.'+name
                  for name in ('protocol','data','fit','analyze','report')],
        tests='.venv-action-predictor/Scripts/python.exe -m unittest tools.action_predictor.priority_capacity.test_measurement',
        qualification='Producers refuse existing attempts. Do not rerun fitting or overwrite sources/receipts. '
                      'Execution provenance incident remains explicit; source hashes match the pre-fit protocol. '
                      'No full-policy evaluation, promotion or untouched group generalization.',
        new_fits=0,reserved_opened=0,promoted=False))


if __name__=='__main__':run()
