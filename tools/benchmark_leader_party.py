"""Reproducible CAMBC artifact benchmark; no source edits or network access.

Pack: python tools/benchmark_leader_party.py pack NAME PATH --language cpp
Run:  python tools/benchmark_leader_party.py run LABEL A.zip B.zip
Maps have fixed seeds in this CLI. Repeats measure reproducibility, not new seeds.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / '.venv/Scripts/cambc.exe'
MAPS = ['00ambush', '00expanse', '00interlock', '00lanes', '00monolith', '00packs']


def pack(name, wasm, language):
    data = Path(wasm).read_bytes()
    target = ROOT / '.cambc' / (name + '.zip')
    with zipfile.ZipFile(target, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr('bot.wasm', data)
        z.writestr('manifest.json', json.dumps(dict(apiVersion=1, status='ready', language=language)))
    print(json.dumps(dict(artifact=str(target), sha256=hashlib.sha256(data).hexdigest())))


def run(args):
    def team(path):
        with zipfile.ZipFile(path) as z:
            language=json.loads(z.read('manifest.json'))['language']
        return dict(name=Path(path).stem,path=str(Path(path).resolve()),language=language)
    out = ROOT / 'replays/leader-party' / args.label
    out.mkdir(parents=True, exist_ok=True)
    jobs = []
    for repeat in range(args.repeat):
        for m in args.maps:
            for swap in range(2):
                ident = f'{m}-{repeat}-{swap}'
                a, b = (args.b, args.a) if swap else (args.a, args.b)
                jobs.append(dict(apiVersion=1, id=ident,
                    teamA=team(a), teamB=team(b),
                    map=str(ROOT / 'maps' / (m+'.map26a')), replay=str(out / (ident+'.zip'))))
    jobpath = ROOT / '.cambc' / (args.label+'.jsonl')
    jobpath.write_text(''.join(json.dumps(j)+'\n' for j in jobs))
    if not args.summarize:
        with (ROOT / '.cambc' / (args.label+'-events.jsonl')).open('w') as events:
            subprocess.run([str(CLI), 'run-batch', '--jsonl', str(jobpath), '--jobs', str(args.jobs),
                            '--release', '--log-limit', '200000'], cwd=ROOT, stdout=events, check=True)
    rows = []
    for j in jobs:
        m, repeat, swap = j['id'].rsplit('-', 2)
        ours = 'teamB' if int(swap) else 'teamA'
        theirs = 'teamA' if int(swap) else 'teamB'
        with zipfile.ZipFile(j['replay']) as z:
            raw = ROOT / '.cambc' / (args.label+'-summary.camstat')
            raw.write_bytes(z.read('summary.camstat'))
            d = json.loads(subprocess.check_output([str(CLI), 'summary', str(raw), '-o', '-'], cwd=ROOT))
            log = z.read('team-b.stdout' if int(swap) else 'team-a.stdout').replace(b'\0', b'').decode(errors='replace')
        scores = {t['team']: int(t['submittedGems']) for t in d['teams']}
        champs = [c for c in d['champions'] if c['team']==ours]
        def entries(kind):
            return [e for series in d['events'] if series['owner'].get('team')==ours
                    and series['kind']==kind for e in series['entries']]
        first = [e['timestamp']['round'] for e in entries('gemSubmission')]
        row = dict(map=m, repeat=int(repeat), side=ours, ours=scores[ours], theirs=scores[theirs],
                   won=d['match']['outcome']==ours, rounds=d['match']['roundsStarted'],
                   seed=d['match']['seed'], faults=d['diagnostics']['botFaults'],
                   errors=log.count('LP_ERROR'), first_tribute=min(first, default=None),
                   tributes=len(first), gem_claims=sum(int(e['value'])>0 for e in entries('gemCollection')),
                   lost_gems=sum(int(e['value']) for e in entries('gemLoss')),
                   fuel_pauses=len(entries('fuelExhausted')),
                   deaths=sum(int(c['metrics']['deaths']) for c in champs),
                   earned_gold=sum(int(c['metrics']['earnedGold']) for c in champs),
                   spent_gold=sum(int(c['metrics']['spentGold']) for c in champs),
                   telemetry=[line for line in log.splitlines() if line.startswith('LP ')][-5:],
                   replay=str(Path(j['replay']).relative_to(ROOT)))
        rows.append(row)
        print(f"{m} {ours}: {row['ours']}-{row['theirs']} errors={row['errors']} faults={row['faults']}", flush=True)
    result = dict(label=args.label, wins=sum(r['won'] for r in rows), games=len(rows),
                  artifacts={str(Path(p)):hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in [args.a,args.b]},
                  matches=rows)
    (ROOT / '.cambc' / (args.label+'-results.json')).write_text(json.dumps(result, indent=2))
    print(f"Wins: {result['wins']}/{len(rows)}")
    if args.require_scoring:
        assert all(r['ours']>0 for r in rows), 'regression: zero scoring on a covered map'
    assert all(not r['faults'][r['side']] and not r['errors'] for r in rows), 'bot faults/unexpected API errors'


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('pack'); p.add_argument('name'); p.add_argument('wasm'); p.add_argument('--language', default='cpp')
    p = sub.add_parser('run'); p.add_argument('label'); p.add_argument('a'); p.add_argument('b')
    p.add_argument('--maps', nargs='+', default=MAPS); p.add_argument('--repeat', type=int, default=1)
    p.add_argument('--jobs', type=int, default=3); p.add_argument('--require-scoring', action='store_true')
    p.add_argument('--summarize', action='store_true', help='Only summarize existing replay bundles')
    args = parser.parse_args()
    if args.command=='pack': pack(args.name,args.wasm,args.language)
    else: run(args)
