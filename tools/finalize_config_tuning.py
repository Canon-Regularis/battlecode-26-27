"""Validate and promote the measured combined configuration; preserve all clones.

Run native, select, legacy, promote, audit after tune_all_settings.py pool.
Selection is frozen before the reserved legacy-map robustness check.
"""
import argparse
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
import hashlib
import os
from pathlib import Path
import py_compile
import re
import shutil
import subprocess
import time
import zipfile

import tune_leader_party as t
import tune_all_settings as sweep


def native(prefixes=('g05_', 'g06_', 'g06e_', 'g07_', 'g08_', 'g09_'), receipt='combined-refinement-native.json'):
    registry = t.read(t.STORE / 'generations.json')
    names = [n for n in registry if n.startswith(prefixes)]

    def check(name):
        src = t.ROOT / 'bots' / registry[name]['bot']
        out = t.LOCAL / (name + '-native.exe')
        result = subprocess.run(['g++', '-std=c++20', '-O2', '-Wall', '-Wextra',
            '-I', str(src / 'src'), str(src / 'tests/decisions.cpp'),
            str(src / 'src/state_machine.cpp'), '-o', str(out)], capture_output=True, text=True)
        assert result.returncode == 0, (name, result.stderr)
        result = subprocess.run([str(out)], capture_output=True, text=True)
        assert result.returncode == 0, (name, result.stdout, result.stderr)
        return dict(name=name, status='pass', output=result.stdout.strip())

    with ThreadPoolExecutor(max_workers=2) as executor:
        checks = list(executor.map(check, names))
    t.save(t.STORE / receipt, dict(status='complete', checks=checks))
    print('PASS native scenarios:', len(checks), flush=True)


def select():
    labels = ['complete-tuning-published-pool', 'complete-tuning-opponent-pool', 'complete-tuning-ancestry']
    ranks = {label: sweep.ranking(label) for label in labels}
    if (t.STORE / 'generation08-targeted-design.json').exists():
        extra_labels = ['targeted-tuning-published-pool', 'targeted-tuning-opponent-pool', 'targeted-tuning-ancestry']
        while not all((t.STORE / (label + '.json')).exists() and
                t.read(t.STORE / (label + '.json')).get('status') == 'complete' for label in extra_labels):
            time.sleep(10)
        for label, extra in zip(labels, extra_labels):
            ranks[label].update(sweep.ranking(extra))
    common, wider, ancestry = [ranks[label] for label in labels]
    eligible = [n for n in common if all(not ranks[label][n]['faults'] for label in labels)]
    ordered = sorted(eligible, key=lambda n: (common[n]['wins'], wider[n]['wins'],
        ancestry[n]['wins'] / ancestry[n]['games'], common[n]['margin']), reverse=True)
    assert ordered, 'No fault-free candidate'
    winner = ordered[0]
    # Inform the near-tie interpretation without changing the frozen wins-first policy.
    if len(ordered) > 1:
        finalists = ordered[:2]
        sweep.freeze('complete-tuning-head-to-head-freeze.json', dict(candidates=finalists,
            policy='Compare the two highest common-opponent win counts directly on all 86 published maps, both sides. Diagnostic near-tie evidence; preserve the predeclared common-opponent wins-first selection policy.'))
        splits = t.read(t.STORE / 'experiment.json')['splits']
        sweep.run('complete-tuning-final-head-to-head', finalists[:1], 'broad', finalists[1:],
            splits['train'] + splits['validation'] + splits['holdout'])
        head = t.read(t.STORE / 'complete-tuning-final-head-to-head.json')
        assert all(not any(row['faults'].values()) for row in head['matches']), 'Head-to-head VM fault'
    registry = t.read(t.STORE / 'generations.json')
    sweep.freeze('complete-tuning-selection.json', dict(generation=winner,
        policy='Highest measured common-opponent wins on all 86 published maps, zero candidate VM faults in all three final matrices. Wider-opponent wins, ancestry win rate and common-opponent margin break exact win-count ties. Frozen before reserved legacy maps; no global-optimum claim.',
        ranking=ordered, matrices=ranks, selected_profile=registry[winner]))
    print('SELECTED', winner, flush=True)


def legacy():
    winner = t.read(t.STORE / 'complete-tuning-selection.json')['generation']
    maps = t.read(t.STORE / 'continuation-legacy-freeze.json')['maps']
    sweep.run('complete-tuning-legacy-robustness', list(dict.fromkeys([winner, 'g02_bank35'])),
        'broad', maps=maps)


def promote():
    choice = t.read(t.STORE / 'complete-tuning-selection.json')
    winner = choice['generation']
    legacy_result = sweep.ranking('complete-tuning-legacy-robustness')[winner]
    assert not legacy_result['faults'], 'Reserved maps exposed a VM fault; investigate before promotion'
    entry = t.read(t.STORE / 'generations.json')[winner]
    src = t.ROOT / 'bots' / entry['bot']
    target = t.ROOT / 'bots/leader_party_tuned'
    shutil.copyfile(src / 'src/config.h', target / 'src/config.h')
    shutil.copyfile(src / 'tests/decisions.cpp', target / 'tests/decisions.cpp')
    for rel, digest in entry['source_sha256'].items():
        assert hashlib.sha256((target / rel).read_bytes()).hexdigest() == digest, rel
    env = {**os.environ, 'CMAKE_BUILD_PARALLEL_LEVEL': '2'}
    for release in [True, False]:
        with (t.LOCAL / f'complete-champion-{release}-build.log').open('w') as log:
            subprocess.run([str(t.CLI), 'build', target.name] + (['--release'] if release else []),
                cwd=t.ROOT, env=env, stdout=log, stderr=subprocess.STDOUT, check=True)
    subprocess.run(['powershell', '-NoProfile', '-File', str(target / 'tests/run.ps1')],
        cwd=t.ROOT, check=True)
    assert hashlib.sha256((target / '.cambc/build-release/bot-injected.wasm').read_bytes()).hexdigest() == entry['wasm_sha256']
    t.save(t.STORE / 'champion.json', dict(generation=winner, bot=target.name,
        config={**t.DEFAULTS, **entry['config']}, source_sha256=entry['source_sha256'],
        wasm_sha256=entry['wasm_sha256'], selection=choice['policy'],
        final_matrix_ranking=choice['ranking'], legacy_robustness=legacy_result))
    print('PROMOTED', winner, entry['wasm_sha256'], flush=True)


def audit():
    sweep.coverage()
    registry = t.read(t.STORE / 'generations.json')
    base = registry['g00']['source_sha256']
    for name, entry in registry.items():
        for rel, digest in entry['source_sha256'].items():
            assert hashlib.sha256((t.ROOT / 'bots' / entry['bot'] / rel).read_bytes()).hexdigest() == digest, (name, rel)
            if Path(rel).name != 'config.h':
                assert digest == base[rel], (name, rel)
        with zipfile.ZipFile(t.artifact(name)) as archive:
            assert hashlib.sha256(archive.read('bot.wasm')).hexdigest() == entry['wasm_sha256']
    original = t.read(t.ROOT / 'docs/strategy/leader_party/evaluation/2026-11-04/subhan/original-source-sha256.json')
    for rel, digest in original.items():
        assert hashlib.sha256((t.ROOT / rel).read_bytes()).hexdigest() == digest, rel
    oriented = {}; unique = {}; conflicts = []; digests = {}; faults = defaultdict(int)
    reports = 0
    for path in t.STORE.glob('*.json'):
        data = t.read(path)
        if not isinstance(data, dict) or 'status' not in data or 'matches' not in data:
            continue
        assert data['status'] == 'complete', path
        reports += 1
        for row in data['matches']:
            key = (row['candidate'], row['opponent'], row['map'], row['side'])
            if key in oriented:
                assert oriented[key] == row, (path, key)
            oriented[key] = row
    for row in oriented.values():
        a, b = (row['candidate'], row['opponent']) if row['side'] == 'teamA' else (row['opponent'], row['candidate'])
        for name in [a, b]:
            if name not in digests:
                with zipfile.ZipFile(t.artifact(name)) as archive:
                    digests[name] = hashlib.sha256(archive.read('bot.wasm')).hexdigest()
        map_digest = hashlib.sha256((t.ROOT / 'maps' / (row['map'] + '.map26a')).read_bytes()).hexdigest()
        key = (map_digest, row['seed'], digests[a], digests[b])
        scores = (row['ours'], row['theirs']) if row['side'] == 'teamA' else (row['theirs'], row['ours'])
        if key in unique and unique[key] != scores:
            conflicts.append(dict(map=row['map'], first=unique[key], repeated=scores))
        unique[key] = scores
        faults[row['candidate']] += row['faults'][row['side']]
    assert not conflicts, conflicts
    champion = t.read(t.STORE / 'champion.json')
    target = t.ROOT / 'bots' / champion['bot']
    for rel, digest in champion['source_sha256'].items():
        assert hashlib.sha256((target / rel).read_bytes()).hexdigest() == digest, rel
    assert hashlib.sha256((target / '.cambc/build-release/bot-injected.wasm').read_bytes()).hexdigest() == champion['wasm_sha256']
    assert not faults[champion['generation']], 'Champion has recorded VM faults'
    for filename in ['tune_leader_party.py', 'tune_all_settings.py', 'finalize_config_tuning.py']:
        py_compile.compile(str(t.ROOT / 'tools' / filename), doraise=True)
    documents = [t.ROOT / 'README.md', *t.ROOT.glob('docs/**/*.md'),
        target / 'README.md', *[t.ROOT / 'bots' / entry['bot'] / 'README.md' for entry in registry.values()]]
    for path in documents:
        for link in re.findall(r'\]\(([^)]+)\)', path.read_text(encoding='utf-8-sig')):
            if '://' in link or link.startswith(('#', 'mailto:')) or ' ' in link:
                continue
            assert (path.parent / link.split('#')[0]).exists(), (path, link)
    changed = subprocess.check_output(['git', 'ls-files', '--others', '--modified',
        '--exclude-standard', '-z'], cwd=t.ROOT).decode().split('\0')
    for relative in filter(None, changed):
        path = t.ROOT / relative
        if not path.is_file():
            continue
        try:
            lines = path.read_text(encoding='utf-8-sig').splitlines()
        except UnicodeError:
            continue
        assert all(line.rstrip() == line for line in lines), 'Trailing whitespace: ' + relative
    stats = dict(status='complete', profiles=len(registry), original_files_preserved=len(original),
        complete_match_reports=reports, oriented_evaluation_rows=len(oriented),
        completed_replay_files=len({r['replay'] for r in oriented.values()}),
        unique_wasm_map_seed_conditions=len(unique), determinism_conflicts=conflicts,
        candidate_faults=dict(faults), champion=champion['generation'],
        policy='Unique conditions use ordered team WASM hashes, map bytes and actual CLI seed; artifact aliases, cached stages and mirrored views do not add independent evidence. LP_ERROR entries are bounded log observations, not exact total action errors.')
    t.save(t.STORE / 'complete-tuning-audit.json', stats)
    print('PASS audit:', len(registry), 'profiles;', len(unique), 'unique conditions', flush=True)


def report():
    champion = t.read(t.STORE / 'champion.json')
    name = champion['generation']; cfg = champion['config']
    audit_result = t.read(t.STORE / 'complete-tuning-audit.json')
    coverage = t.read(t.STORE / 'all-settings-coverage.json')
    matrices = {label: t.read(t.STORE / (label + '-ranking.json')) for label in
        ['complete-tuning-published-pool', 'complete-tuning-opponent-pool',
         'complete-tuning-ancestry', 'complete-tuning-legacy-robustness']}
    for label in ['published-pool', 'opponent-pool', 'ancestry']:
        extra = t.STORE / ('targeted-tuning-' + label + '-ranking.json')
        if extra.exists():
            matrices['complete-tuning-' + label] += t.read(extra)
            matrices['complete-tuning-' + label].sort(key=lambda row: (row['wins'], row['margin']), reverse=True)
    common = next(r for r in matrices['complete-tuning-published-pool'] if r['name'] == name)
    wider = next(r for r in matrices['complete-tuning-opponent-pool'] if r['name'] == name)
    legacy_result = next(r for r in matrices['complete-tuning-legacy-robustness'] if r['name'] == name)
    head = t.read(t.STORE / 'complete-tuning-final-head-to-head-ranking.json')[0]
    runner_up = t.read(t.STORE / 'complete-tuning-head-to-head-freeze.json')['candidates'][1]

    def record(row):
        return f"{row['wins']}–{row['games'] - row['wins']}"

    def write(path, content):
        path.write_text(content, encoding='utf-8', newline='\n')

    docs = t.ROOT / 'docs/strategy/leader_party'
    evidence = 'evaluation/2026-11-04/tuning/'
    intro = (f"The preferred bot is `leader_party_tuned`, matching frozen **`{name}`**. "
        'It combines the selected settings in one C++ bot using Subhan’s camp-loop planner. '
        'Original bots and every tuning generation remain intact.\n\n')
    report_text = '# Complete configuration tuning\n\n' + intro
    report_text += (f"All **31 configuration fields** received explicit probes across two full sweeps and "
        f"combined-profile tests. The registry preserves **{audit_result['profiles']} profiles**. "
        'Thirty fields affect gameplay; `attacks` is unused and both values compile to identical WASM. '
        'Keeping a default is a measured outcome, not an omitted stat.\n\n'
        f"The full experiment contains **{audit_result['completed_replay_files']:,} completed replay files**, "
        f"representing **{audit_result['unique_wasm_map_seed_conditions']:,} distinct ordered WASM/map/seed conditions**. "
        'Cached conditions, artifact aliases and mirrored result views do not add independent evidence. '
        'Repeated deterministic scores agree.\n\n'
        '## Final comparisons\n\n'
        '| Frozen profile | Published maps, three opponents | Wider 15-bot suite | Ancestry suite |\n'
        '| --- | ---: | ---: | ---: |\n')
    for row in matrices['complete-tuning-published-pool']:
        other = [next(r for r in matrices[label] if r['name'] == row['name'])
            for label in ['complete-tuning-opponent-pool', 'complete-tuning-ancestry']]
        report_text += f"| `{row['name']}` | {record(row)} | {record(other[0])} | {record(other[1])} |\n"
    report_text += ('\nPublished comparison: all 86 published maps, both sides, against untuned Subhan, '
        'D1 and gold_diamond (516 conditions/profile). The wider suite uses all 15 pre-existing '
        'opponent artifacts on six maps, both sides (180/profile); it is reported separately '
        'to avoid overweighting weaker bots. Ancestry games compare the surviving profiles '
        'to earlier G1/G2/G3 and G5 generations on 18 validation maps; self-games are skipped.\n\n'
        '| Final bot opponent | Wins–losses |\n| --- | ---: |\n')
    for opponent, row in common['versus'].items():
        report_text += f'| `{opponent}` | {record(row)} |\n'
    report_text += (f"\nThe closest full-pool contender is `{runner_up}`. The selected bot’s "
        f"direct record against it on the same 86 maps is **{record(head)}**. "
        'This diagnostic does not replace the predeclared common-opponent wins-first policy; '
        'a one-game full-pool gap is a near tie, not decisive superiority.\n')
    wider_rows = []
    for label in ['complete-tuning-opponent-pool', 'targeted-tuning-opponent-pool']:
        path = t.STORE / (label + '.json')
        if path.exists():
            wider_rows += [r for r in t.read(path)['matches'] if r['candidate'] == name and r['result'] != 'win']
    if wider_rows:
        inventory = t.read(t.STORE / 'opponent-pool.json')
        report_text += '\nWider-suite losses remain visible:\n\n| Opponent | Map / our side | Gems |\n| --- | --- | ---: |\n'
        for row in wider_rows:
            report_text += f"| `{inventory[row['opponent']]['name']}` | `{row['map']}` / {row['side']} | {row['ours']}–{row['theirs']} |\n"
    report_text += (f"\nThe final configuration was frozen before the nine reserved legacy maps. "
        f"Its separate legacy robustness record is **{record(legacy_result)}**; "
        'these map files differ from the published map pool. They are a robustness check, '
        'not random future-map confirmation.\n\n'
        '## One combined configuration\n\n'
        '| Compile-time field | Final value | Continuation probe values |\n'
        '| --- | ---: | --- |\n')
    for key in t.DEFAULTS:
        values = sorted({p['value'] for p in coverage['inventory'][key]['probes']})
        report_text += f"| `{key}` | `{cfg[key]}` | {', '.join('`' + str(v) + '`' for v in values)} |\n"
    report_text += ('\nProtocol lifetime/lease probes explicitly enable coordination; those settings are '
        'dormant when it is disabled. Search serialization allows at most five camps and three '
        'reported routes. The four-altar default is not a packet cap: eight/sixteen altars, '
        '48 candidates, beam widths up to 32 and expansion limits up to 20,000 were tested.\n\n'
        '## Method and limits\n\n'
        'The first pass tuned banking/recovery and a few search choices. The continuation '
        'screened independent lower/upper probes for every active field, expanded the best '
        'probe for every field to 17 training maps (including losing probes), then tested '
        'positive-setting combinations, whole-family combinations, feature flips and '
        'leave-one-family-out ablations. Shortlists used 18 separate validation maps. '
        'A second full sweep refined the best combined parent, tested legal zero/endpoints '
        'and repeated combination/validation before the final common-opponent matrix. '
        'Six final targeted profiles checked the strongest validated planner-start boundary '
        'and its interactions with competition penalty and retry timing; the best two joined '
        'the identical final matrices without changing the earlier frozen receipts. '
        'Executable hashes deduplicate finalist aliases. The final selection uses common-opponent '
        'wins with zero VM faults; wider and ancestry results break exact ties.\n\n'
        'Published maps were reused adaptively. Fixed seeds are deterministic. These results '
        'identify the strongest measured configuration in this experiment; they cannot prove '
        'a global optimum or future ladder performance. Native scenarios cover configured '
        'banking, task expiry and protocol timing, not every possible gameplay situation.\n\n'
        f"The final published matrix recorded **{common['faults']} candidate VM faults** and "
        f"**{common['errors']:,} bounded `LP_ERROR` log entries**. Nonfatal action errors remain; "
        'truncated logs do not measure exact total action errors. Original gameplay source '
        'hashes and all frozen clone source/artifact hashes are checked. Generated gameplay '
        'source differs only in `config.h`. Normal/release builds and native scenarios pass; '
        'the promoted release WASM exactly matches the selected artifact.\n\n'
        f"In **{common['zero_score']}** final published conditions both teams submitted zero gems; "
        'their outcomes still follow the engine’s gold/kills tie-break rules. Such wins count '
        'toward match performance but do not demonstrate successful banking.\n\n'
        '## Evidence and reproduction\n\n'
        f"- [Selection and complete final matrices]({evidence}complete-tuning-selection.json)\n"
        f"- [Champion configuration and hashes]({evidence}champion.json)\n"
        f"- [All generations]({evidence}generations.json)\n"
        f"- [Per-field coverage]({evidence}all-settings-coverage.json)\n"
        f"- [Deduplicated audit]({evidence}complete-tuning-audit.json)\n"
        f"- [Reserved-map results]({evidence}complete-tuning-legacy-robustness.json)\n"
        f"- [Native checks for combined/refined profiles]({evidence}combined-refinement-native.json)\n"
        f"- [Final targeted design]({evidence}generation08-targeted-design.json)\n"
        f"- [Final targeted native checks]({evidence}generation08-native.json)\n"
        '- [First-pass history](config_tuning_first_pass.md)\n\n'
        '```powershell\nuv run --locked cambc build leader_party_tuned --release\n'
        '& bots/leader_party_tuned/tests/run.ps1\n```\n\n'
        'Use `tools/tune_leader_party.py` to preserve/build clones and resume match matrices, '
        '`tools/tune_all_settings.py` for the frozen two-sweep sequence and '
        '`tools/finalize_config_tuning.py` for validation/promotion/auditing. '
        'Large builds and replays remain ignored locally. No platform submission changed.\n')
    write(docs / 'config_tuning_all_stats.md', report_text)
    history = docs / 'config_tuning_first_pass.md'
    if not history.exists():
        old = (docs / 'config_tuning.md').read_text(encoding='utf-8')
        old = re.sub(r'> Tuning continues:.*?\n\n',
            '> Historical first pass. The [complete tuning report](config_tuning_all_stats.md) supersedes this recommendation.\n\n', old, count=1, flags=re.S)
        write(history, old.replace('# Configuration tuning: preferred profile', '# Initial configuration tuning: historical G2 result', 1))
    write(docs / 'config_tuning.md', '# Configuration tuning\n\n' + intro +
        f"The final bot scored **{record(common)}** against untuned Subhan, D1 and gold_diamond "
        f"across all 86 published maps, and **{record(wider)}** in the separate wider suite.\n\n"
        'See the [complete tuning report](config_tuning_all_stats.md) for all settings, generation '
        'comparisons, methodology, evidence and limitations. [Initial G2 results](config_tuning_first_pass.md) '
        'remain as history.\n')
    bot_readme = '# Combined tuned leader-party bot\n\n' + intro
    bot_readme += f"Bank at **{cfg['bank_bag']} gems / {cfg['bag_age']} rounds**. "
    bot_readme += f"Use beam width **{cfg['loop_beam']}**, native field admission **{cfg['field_admission']:,}** "
    bot_readme += f"and fuel reserve **{cfg['reserve']:,}**. All selected settings live together in `src/config.h`.\n\n"
    bot_readme += ('```powershell\nuv run --locked cambc build leader_party_tuned --release\n'
        '& bots/leader_party_tuned/tests/run.ps1\n```\n\n'
        'See the [complete strategy and evaluation](../../docs/strategy/leader_party/config_tuning_all_stats.md). '
        'No platform submission changed.\n')
    write(t.ROOT / 'bots/leader_party_tuned/README.md', bot_readme)
    for path, start, replacement in [
        (t.ROOT / 'README.md', 'The preferred C++ bot is ',
         f"The preferred C++ bot is [leader_party_tuned](bots/leader_party_tuned/README.md), the combined "
         f"configuration champion `{name}` after two full configurable-stat sweeps. It won **{record(common)}** "
         'on 86 published maps against untuned Subhan, D1 and gold_diamond. See the '
         '[complete tuning report](docs/strategy/leader_party/config_tuning_all_stats.md) and '
         '[current strategy](docs/strategy/leader_party/README.md). Build with '
         '`uv run --locked cambc build leader_party_tuned --release`; native tests run with '
         '`& bots/leader_party_tuned/tests/run.ps1`.'),
        (docs / 'README.md', 'The preferred bot is ',
         f"The preferred bot is [leader_party_tuned](../../../bots/leader_party_tuned/README.md), "
         f"matching frozen `{name}` and built against CAMBC 4.0.0. Its combined configuration "
         f"won **{record(common)}** across 86 published maps against three common opponents. "
         'See [complete configuration tuning](config_tuning_all_stats.md) for all values, '
         'generation comparisons and measured limits.')]:
        content = path.read_text(encoding='utf-8')
        content, count = re.subn(re.escape(start) + r'[^\n]+', lambda m: replacement, content, count=1)
        assert count == 1, path
        content = content.replace('Both Subhan-based bots follow eligible planned camp loops after their first two equipment phases, with the original selector as fallback.',
            f"The untuned Subhan bot follows eligible planned camp loops after two equipment phases; the tuned bot starts after {cfg['loop_phase']}. Both retain the original selector as fallback.")
        write(path, content)
    config_doc = '# Release configuration\n\n' + intro
    config_doc += '| Compile-time field | Value |\n| --- | ---: |\n'
    config_doc += ''.join(f'| `{key}` | `{value}` |\n' for key, value in cfg.items())
    config_doc += ('\nSettings are compiled into the bot. The unused `attacks` field has no callers. '
        'Protocol lifetimes matter only with coordination enabled. Movement still uses the existing '
        'native distance fields; Subhan’s planner selects camp loops. See the '
        '[full evaluation](config_tuning_all_stats.md) for measured ranges and limitations.\n')
    write(docs / 'config.md', config_doc)
    wards = docs / 'strategies/ward_placing.md'
    content = wards.read_text(encoding='utf-8')
    content = content.replace('Enabled in the release,',
        ('Enabled' if cfg['wards'] else 'Disabled') + ' in the tuned release; retained in the untuned baseline,')
    write(wards, content)
    route = docs / 'strategies/route_planning.md'
    content = route.read_text(encoding='utf-8')
    content = re.sub(r"Both use Subhan's draft-time camp-loop search after[^.]+\.",
        f"Both precompute Subhan's camp loops at draft time; the untuned bot starts following them after two equipment phases and the tuned profile after {cfg['loop_phase']}.", content, count=1)
    content = content.replace('for the tuned banking/recovery values.', 'for the complete combined configuration.')
    write(route, content)
    combat = docs / 'combat.md'
    content = combat.read_text(encoding='utf-8')
    content = content.replace('The preferred `leader_party_tuned` keeps the combat policy and keeps the configured 55% HP floor for optional wards, matching the untuned bots.',
        f"The preferred `leader_party_tuned` retains the combat policy. Optional wards are {'enabled' if cfg['wards'] else 'disabled'} in its combined configuration; the retained ward code uses the configured recovery-clear HP floor.")
    write(combat, content)
    write(t.STORE / 'README.md', '# Complete configuration tuning evidence\n\n' + intro +
        f"The experiment preserves {audit_result['profiles']} profiles and covers all 31 fields. "
        'See the [complete report](../../../config_tuning_all_stats.md).\n\n'
        '- [Final choice and matrices](complete-tuning-selection.json)\n'
        '- [Promoted configuration and hashes](champion.json)\n'
        '- [All generations](generations.json)\n'
        '- [Coverage](all-settings-coverage.json)\n'
        '- [Source, artifact and deterministic-repeat audit](complete-tuning-audit.json)\n'
        '- [Reserved legacy maps](complete-tuning-legacy-robustness.json)\n'
        '- [Original G2 champion receipt](champion-first-pass.json)\n\n'
        'All stage receipts remain here. Builds and replay ZIPs are ignored locally; '
        'stage totals overlap and must not be added as independent games. No platform submission changed.\n')
    publication = t.STORE / 'publication.json'
    if publication.exists():
        version = t.read(publication)['version']
        for path, relative in [
            (t.ROOT / 'README.md', 'docs/strategy/leader_party/evaluation/2026-11-04/tuning/publication.json'),
            (t.ROOT / 'bots/leader_party_tuned/README.md', '../../docs/strategy/leader_party/evaluation/2026-11-04/tuning/publication.json'),
            (docs / 'README.md', evidence + 'publication.json'),
            (docs / 'config_tuning_all_stats.md', evidence + 'publication.json'),
            (t.STORE / 'README.md', 'publication.json')]:
            content = path.read_text(encoding='utf-8')
            replacement = f'The tuned bot was subsequently submitted to CAMBC as version {version}; see the [publication receipt]({relative}).'
            for old in ['No platform submission changed.', 'Platform submission was not changed by these experiments.',
                    'The platform submission was not changed by these experiments.']:
                content = content.replace(old, replacement)
            write(path, content)
    print('Updated current bot documentation', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=['native', 'select', 'legacy', 'promote', 'audit', 'report'])
    globals()[parser.parse_args().phase]()
