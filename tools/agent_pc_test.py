"""Trusted PC-side build/tournament adapter for agent_bridge tester workers."""
import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import zipfile

from agent_bridge import run, save, stop
from party_feature_load import gentle_run

ROOT = Path(__file__).resolve().parents[1]
OPPONENTS = {
    'champion': ROOT / '.cambc/tuning/g07_search.zip',
    'record_guard': ROOT / '.cambc/features/c02_record_guard.zip',
    'phase4': ROOT / '.cambc/tuning/g08_phase4.zip',
    'without_search': ROOT / '.cambc/tuning/g05_without_search.zip',
    'without_team': ROOT / '.cambc/tuning/g05_without_team.zip',
}
MAPS = ['00ambush', '00breadcrumbs', '00lanes', '00packs', '00swirl',
        '01broken-curve', '02guardians', '03colosseum']


def frozen(path):
    with zipfile.ZipFile(path) as archive:
        language = json.loads(archive.read('manifest.json'))['language']
        wasm = archive.read('bot.wasm')
    return dict(path=str(path.resolve()), language=language,
                wasm_sha256=hashlib.sha256(wasm).hexdigest(),
                zip_sha256=hashlib.sha256(path.read_bytes()).hexdigest())


def logged_command(argv, cwd, path, timeout):
    with path.open('w', encoding='utf-8') as log:
        process = subprocess.Popen([str(x) for x in argv], cwd=cwd, stdout=log,
                                   stderr=subprocess.STDOUT, start_new_session=os.name != 'nt')
        try:
            if process.wait(timeout=timeout):
                raise RuntimeError(f'Command failed; see {path}')
        finally:
            # Kill compiler/engine descendants as well on timeout, rather than leaving locks.
            stop(process)


def evaluate(args):
    checkout = args.checkout.resolve()
    output = args.output.resolve()
    local = output.parent / 'tournament'
    local.mkdir(parents=True, exist_ok=False)
    cli = args.cli.resolve()
    if not re.fullmatch(r'pi_[a-z0-9][a-z0-9_-]{0,63}', args.bot):
        raise ValueError('Only bridge candidate bots can be tested by this adapter')
    commit = run(['git', 'rev-parse', 'HEAD'], cwd=checkout).stdout.strip()
    base = run(['git', 'show', '-s', '--format=%P', 'HEAD'], cwd=checkout).stdout.strip()
    maps = sorted(set(args.maps))
    opponents = {name: frozen(OPPONENTS[name]) for name in args.opponents}
    if not maps or not opponents:
        raise ValueError('At least one map and opponent required')
    for name in maps:
        if not re.fullmatch(r'[a-zA-Z0-9_-]+', name) or not (checkout / 'maps' / (name + '.map26a')).is_file():
            raise ValueError('Unknown or invalid map: ' + name)
    cli_hash = hashlib.sha256(cli.read_bytes()).hexdigest()
    with gentle_run(ROOT / '.cambc/features') as settings:
        logged_command([cli, 'build', args.bot, '--release'], checkout, local / 'build.log', 600)
        wasm = checkout / 'bots' / args.bot / '.cambc/build-release/bot-injected.wasm'
        artifact = local / 'candidate.zip'
        with zipfile.ZipFile(artifact, 'w', zipfile.ZIP_DEFLATED) as archive:
            archive.write(wasm, 'bot.wasm')
            archive.writestr('manifest.json', json.dumps(dict(apiVersion=1, status='ready', language='cpp')))
        candidate = frozen(artifact)
        teams = {name: dict(name=name, path=data['path'], language=data['language']) for name, data in opponents.items()}
        teams['candidate'] = dict(name='candidate', path=str(artifact), language='cpp')
        jobs = []
        conditions = []
        for opponent in opponents:
            for name in maps:
                for side in ['teamA', 'teamB']:
                    ident = f'{len(jobs):05d}'
                    a, b = ('candidate', opponent) if side == 'teamA' else (opponent, 'candidate')
                    replay = local / (ident + '.zip')
                    jobs.append(dict(apiVersion=1, id=ident, teamA=teams[a], teamB=teams[b],
                                     map=str(checkout / 'maps' / (name + '.map26a')), replay=str(replay)))
                    conditions.append(dict(opponent=opponent, map=name, side=side))
        manifest = local / 'matches.jsonl'
        manifest.write_text(''.join(json.dumps(job) + '\n' for job in jobs), encoding='utf-8')
        logged_command([cli, 'run-batch', '--jsonl', manifest, '--jobs', str(settings['workers']),
                        '--release', '--log-limit', '200000'], checkout, local / 'events.jsonl', args.match_timeout)
        rows = []
        for job, condition in zip(jobs, conditions):
            with zipfile.ZipFile(job['replay']) as archive:
                raw = local / (job['id'] + '.camstat')
                raw.write_bytes(archive.read('summary.camstat'))
                side = condition['side']
                log_name = 'team-a.stdout' if side == 'teamA' else 'team-b.stdout'
                stdout = archive.read(log_name).replace(b'\0', b'').decode(errors='replace')
            data = json.loads(run([cli, 'summary', raw, '-o', '-'], cwd=checkout).stdout)
            outcome = data['match']['outcome']
            other = 'teamB' if side == 'teamA' else 'teamA'
            totals = {t['team']: int(t['submittedGems']) for t in data['teams']}
            rows.append(dict(**condition,
                             outcome='win' if outcome == side else 'loss' if outcome == other else 'draw',
                             submitted=totals[side], opponent_submitted=totals[other],
                             both_teams_faults=data['diagnostics']['botFaults'],
                             candidate_logged_errors=stdout.count('LP_ERROR'),
                             replay=job['replay'], replay_sha256=hashlib.sha256(Path(job['replay']).read_bytes()).hexdigest(),
                             seed=data['match']['seed']))
        report = dict(bot=args.bot, candidate_commit=commit, parent_commit=base,
                      candidate=candidate, opponents=opponents, cpu_policy=settings,
                      cli_sha256=cli_hash, cli_version=run([cli, '--version'], cwd=checkout).stdout.strip(),
                      map_sha256={name: hashlib.sha256((checkout / 'maps' / (name + '.map26a')).read_bytes()).hexdigest() for name in maps},
                      games=len(rows), outcomes=dict(Counter(r['outcome'] for r in rows)),
                      versus={name: dict(Counter(r['outcome'] for r in rows if r['opponent'] == name)) for name in opponents},
                      both_teams_faults=sum(r['both_teams_faults'] for r in rows),
                      candidate_logged_errors=sum(r['candidate_logged_errors'] for r in rows),
                      matches=rows, decision='Evidence for critic review; no automatic promotion or platform submission.')
        save(output, report)
        print(json.dumps({key: report[key] for key in ['bot', 'candidate_commit', 'games', 'outcomes', 'versus']}, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--checkout', type=Path, required=True)
    parser.add_argument('--bot', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--cli', type=Path, default=ROOT / '.venv/Scripts/cambc.exe')
    parser.add_argument('--maps', nargs='+', default=MAPS)
    parser.add_argument('--opponents', nargs='+', choices=OPPONENTS, default=list(OPPONENTS))
    parser.add_argument('--match-timeout', type=int, default=2400)
    evaluate(parser.parse_args())


if __name__ == '__main__':
    main()
