"""Local bare-repository tests: no GitHub calls, model calls or tournaments."""
import argparse
import hashlib
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import zipfile
from contextlib import nullcontext
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import agent_bridge as bridge
import agent_pc_test as adapter


class BridgeTests(unittest.TestCase):
    def setUp(self):
        scratch = Path(__file__).resolve().parents[2] / '.cambc/bridge-tests'
        scratch.mkdir(parents=True, exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(dir=scratch)
        self.root = Path(self.temporary.name)
        self.remote = self.root / 'remote.git'
        self.seed = self.root / 'seed'
        bridge.run(['git', 'init', '--bare', self.remote])
        bridge.run(['git', 'init', self.seed])
        bridge.run(['git', 'config', 'user.name', 'Test'], cwd=self.seed)
        bridge.run(['git', 'config', 'user.email', 'test@localhost'], cwd=self.seed)
        bot = self.seed / 'bots/leader_party_tuned/src'
        bot.mkdir(parents=True)
        (bot / 'bot.cpp').write_text('int original = 1;\n')
        (self.seed / 'README.md').write_text('base\n')
        bridge.run(['git', 'add', '.'], cwd=self.seed)
        bridge.run(['git', 'commit', '-m', 'seed'], cwd=self.seed)
        bridge.run(['git', 'branch', '-M', 'main'], cwd=self.seed)
        bridge.run(['git', 'remote', 'add', 'origin', self.remote], cwd=self.seed)
        bridge.run(['git', 'push', 'origin', 'main'], cwd=self.seed)
        bridge.run(['git', '--git-dir', self.remote, 'symbolic-ref', 'HEAD', 'refs/heads/main'])
        self.base = bridge.run(['git', 'rev-parse', 'HEAD'], cwd=self.seed).stdout.strip()
        self.pc = bridge.Mailbox(str(self.remote), self.root / 'pc')
        self.pi = bridge.Mailbox(str(self.remote), self.root / 'pi')

    def tearDown(self):
        # Windows Git creates read-only loose objects in clones.
        import shutil
        def writable(function, path, error):
            os.chmod(path, 0o700)
            function(path)
        shutil.rmtree(self.root, onerror=writable)
        self.temporary.cleanup()

    def submit(self, name='experiment'):
        return self.pc.submit(dict(id=name, base_commit=self.base, base_bot='leader_party_tuned',
                                   candidate_bot='pi_' + name, instructions='Improve banking progress.'))

    def job(self, name='experiment'):
        return next(j for j in self.pc.jobs() if j['id'] == name)

    def test_two_machines_do_not_lose_concurrent_submissions(self):
        def submit(pair):
            mailbox, name = pair
            return mailbox.submit(dict(id=name))
        with ThreadPoolExecutor(max_workers=2) as pool:
            list(pool.map(submit, [(self.pc, 'one'), (self.pi, 'two')]))
        self.assertEqual({j['id'] for j in self.pc.jobs()}, {'one', 'two'})

    def test_claim_exclusion_and_stale_worker_cannot_publish(self):
        self.submit()
        old = self.pi.claim('experiment', 'coder', 'pi')
        with self.assertRaises(ValueError):
            self.pc.claim('experiment', 'coder', 'second')
        with patch.object(bridge.time, 'time', return_value=old['lease']['expires_at'] + 1):
            replacement = self.pc.claim('experiment', 'coder', 'replacement')
            with self.assertRaises(ValueError):
                self.pi.finish('experiment', old['lease']['token'], 'ready')
            self.pc.finish('experiment', replacement['lease']['token'], 'ready', {'candidate_commit': self.base})
        self.assertEqual(self.job()['status'], 'ready')

    def test_state_machine_rejects_skipping_testing(self):
        self.submit()
        job = self.pi.claim('experiment', 'coder', 'pi')
        with self.assertRaises(ValueError):
            self.pi.finish('experiment', job['lease']['token'], 'done')

    def test_coder_push_and_pc_test_round_trip(self):
        self.submit()
        args = argparse.Namespace(role='coder', name='pi', once=True, poll=5, timeout=30, codex=sys.executable)
        def agent(argv, cwd, log, mailbox, job, timeout, prompt=None):
            (cwd / 'bots' / job['candidate_bot'] / 'src/bot.cpp').write_text('int improved = 2;\n')
            (cwd / 'bots' / job['candidate_bot'] / 'IMPLEMENTATION.md').write_text('Changed banking; test on PC.\n')
        with patch.object(bridge, 'execute', side_effect=agent):
            bridge.worker(self.pi, args)
        ready = self.job()
        self.assertEqual(ready['status'], 'ready')
        self.assertNotEqual(ready['candidate_commit'], self.base)
        tester = self.root / 'fake_test.py'
        tester.write_text('import json,pathlib,subprocess,sys\n'
                          'commit=subprocess.check_output(["git","rev-parse","HEAD"],cwd=sys.argv[1],text=True).strip()\n'
                          'pathlib.Path(sys.argv[3]).write_text(json.dumps(dict(candidate_commit=commit,bot=sys.argv[2],games=2,outcomes={"win":1,"loss":1})))\n')
        args.role = 'tester'
        args.name = 'pc'
        args.test_command = json.dumps([sys.executable, str(tester), '{checkout}', '{bot}', '{output}'])
        bridge.worker(self.pc, args)
        done = self.job()
        self.assertEqual(done['status'], 'done')
        self.assertEqual(done['test_report']['candidate_commit'], ready['candidate_commit'])
        self.assertEqual(done['test_report']['games'], 2)
        self.assertEqual((self.seed / 'bots/leader_party_tuned/src/bot.cpp').read_text(), 'int original = 1;\n')

    def test_out_of_scope_agent_change_fails_without_pushing_candidate(self):
        self.submit()
        args = argparse.Namespace(role='coder', name='pi', once=True, poll=5, timeout=30, codex=sys.executable)
        def agent(argv, cwd, *unused):
            (cwd / 'README.md').write_text('unrelated change')
        with patch.object(bridge, 'execute', side_effect=agent):
            bridge.worker(self.pi, args)
        self.assertEqual(self.job()['status'], 'coding_failed')
        refs = bridge.run(['git', '--git-dir', self.remote, 'for-each-ref', '--format=%(refname)', 'refs/heads/pi/']).stdout
        self.assertEqual(refs, '')

    def test_snapshot_preserves_index_and_unrelated_working_files(self):
        (self.seed / 'README.md').write_text('staged unrelated\n')
        bridge.run(['git', 'add', 'README.md'], cwd=self.seed)
        before = bridge.run(['git', 'write-tree'], cwd=self.seed).stdout
        selected = self.seed / 'bots/leader_party_tuned/src/bot.cpp'
        selected.write_text('int snapshot = 3;\n')
        args = argparse.Namespace(repo=str(self.seed), branch='bridge/test', paths=['bots/leader_party_tuned'], push=False)
        bridge.snapshot(args)
        self.assertEqual(before, bridge.run(['git', 'write-tree'], cwd=self.seed).stdout)
        self.assertEqual(bridge.run(['git', 'show', 'bridge/test:README.md'], cwd=self.seed).stdout, 'base\n')
        self.assertEqual(bridge.run(['git', 'show', 'bridge/test:bots/leader_party_tuned/src/bot.cpp'], cwd=self.seed).stdout, 'int snapshot = 3;\n')
        self.assertEqual(bridge.run(['git', 'rev-parse', 'HEAD'], cwd=self.seed).stdout.strip(), self.base)

    def test_pc_adapter_counts_candidate_side_and_records_artifact_identity(self):
        maps = self.seed / 'maps'
        maps.mkdir()
        for name in ['one', 'two']:
            (maps / (name + '.map26a')).write_bytes(name.encode())
        cli = self.root / 'fake-cli'
        cli.write_bytes(b'fake engine')
        opponent = self.root / 'opponent.zip'
        with zipfile.ZipFile(opponent, 'w') as z:
            z.writestr('bot.wasm', b'fixed opponent')
            z.writestr('manifest.json', '{"language":"cpp"}')
        args = argparse.Namespace(checkout=self.seed, output=self.root / 'result/report.json', cli=cli,
                                  bot='pi_experiment', maps=['one', 'two'], opponents=['champion'], match_timeout=60)
        def command(argv, cwd, path, timeout):
            if argv[1] == 'build':
                wasm = cwd / 'bots/pi_experiment/.cambc/build-release/bot-injected.wasm'
                wasm.parent.mkdir(parents=True)
                wasm.write_bytes(b'candidate wasm')
            else:
                manifest = Path(argv[argv.index('--jsonl') + 1])
                for line in manifest.read_text().splitlines():
                    job = json.loads(line)
                    with zipfile.ZipFile(job['replay'], 'w') as z:
                        z.writestr('summary.camstat', job['id'])
                        z.writestr('team-a.stdout', 'LP_ERROR' if job['id'] == '00002' else '')
                        z.writestr('team-b.stdout', '')
        original_run = bridge.run
        def summary(argv, **kwargs):
            if argv[0] != cli:
                return original_run(argv, **kwargs)
            if argv[1] == '--version':
                return subprocess.CompletedProcess(argv, 0, stdout='CAMBC 4.0.0', stderr='')
            index = int(Path(argv[2]).stem)
            result = dict(match=dict(outcome=['teamA', 'teamB', 'teamB', 'draw'][index], seed=index),
                          teams=[dict(team='teamA', submittedGems=10), dict(team='teamB', submittedGems=20)],
                          diagnostics=dict(botFaults=0))
            return subprocess.CompletedProcess(argv, 0, stdout=json.dumps(result), stderr='')
        with patch.object(adapter, 'OPPONENTS', {'champion': opponent}), \
                patch.object(adapter, 'gentle_run', return_value=nullcontext({'workers': 2})), \
                patch.object(adapter, 'logged_command', side_effect=command), \
                patch.object(adapter, 'run', side_effect=summary):
            adapter.evaluate(args)
        report = json.loads(args.output.read_text())
        self.assertEqual(report['candidate_commit'], self.base)
        self.assertEqual(report['outcomes'], {'win': 2, 'loss': 1, 'draw': 1})
        self.assertEqual(report['candidate_logged_errors'], 1)
        self.assertEqual(len(report['matches']), 4)
        self.assertEqual(report['candidate']['wasm_sha256'], hashlib.sha256(b'candidate wasm').hexdigest())


if __name__ == '__main__':
    unittest.main()
