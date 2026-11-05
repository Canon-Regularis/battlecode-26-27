"""Git mailbox for a Pi coding worker and a PC testing worker. No hosted CI."""
import argparse
from contextlib import contextmanager
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import signal
import socket
import subprocess
import tempfile
import time
import uuid

REF = 'refs/heads/agent-mailbox-v1'
SHA = re.compile(r'^[0-9a-f]{40}$')
ID = re.compile(r'^[a-z0-9][a-z0-9_-]{0,63}$')


def run(argv, cwd=None, data=None, env=None, check=True):
    result = subprocess.run([str(x) for x in argv], cwd=cwd, input=data,
                            capture_output=True, text=True, encoding='utf-8', env=env, timeout=120)
    if check and result.returncode:
        raise RuntimeError(f'{argv[0]} failed: {result.stderr.strip()}')
    return result


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')
    temporary.replace(path)


@contextmanager
def file_lock(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a+b') as handle:
        if handle.tell() == 0:
            handle.write(b'0')
            handle.flush()
        handle.seek(0)
        if os.name == 'nt':
            import msvcrt
            while True:
                try:
                    msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                    break
                except OSError:
                    time.sleep(.1)
        else:
            import fcntl
            fcntl.flock(handle, fcntl.LOCK_EX)
        try:
            yield
        finally:
            handle.seek(0)
            if os.name == 'nt':
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle, fcntl.LOCK_UN)


class Mailbox:
    """Single remote branch, compare-and-swap updates, expiring worker leases."""
    def __init__(self, remote, state):
        self.state = Path(state).resolve()
        self.gitdir = self.state / 'mailbox.git'
        self.remote = remote
        self.state.mkdir(parents=True, exist_ok=True)
        with file_lock(self.state / 'mailbox.lock'):
            if not self.gitdir.exists():
                run(['git', 'init', '--bare', self.gitdir])
                self.git('remote', 'add', 'origin', remote)
            if self.git('remote', 'get-url', 'origin') != remote:
                raise ValueError('State directory belongs to another remote')

    def git(self, *args, data=None, env=None, check=True):
        return run(['git', '--git-dir', self.gitdir, *args], data=data,
                   env=env, check=check).stdout.strip()

    def head(self):
        found = run(['git', '--git-dir', self.gitdir, 'ls-remote', '--exit-code', 'origin', REF], check=False)
        if found.returncode == 2:
            return None
        if found.returncode:
            raise RuntimeError('Cannot read mailbox remote: ' + found.stderr.strip())
        self.git('fetch', '--no-tags', 'origin', REF)
        return self.git('rev-parse', 'FETCH_HEAD')

    def read(self, head, job_id):
        if not ID.fullmatch(job_id):
            raise ValueError('Invalid job identifier')
        if head is None:
            return None
        result = run(['git', '--git-dir', self.gitdir, 'show', f'{head}:jobs/{job_id}.json'], check=False)
        return json.loads(result.stdout) if result.returncode == 0 else None

    def jobs(self):
        with file_lock(self.state / 'mailbox.lock'):
            head = self.head()
            if head is None:
                return []
            paths = self.git('ls-tree', '-r', '--name-only', head, 'jobs/').splitlines()
            return [self.read(head, Path(p).stem) for p in paths if p.endswith('.json')]

    def update(self, job_id, transform):
        with file_lock(self.state / 'mailbox.lock'):
            for attempt in range(8):
                head = self.head()
                value = transform(self.read(head, job_id))
                value['updated_at'] = time.time()
                with tempfile.TemporaryDirectory(dir=self.state) as temporary:
                    env = dict(os.environ, GIT_INDEX_FILE=str(Path(temporary) / 'index'),
                               GIT_AUTHOR_NAME='Battlecode agent bridge', GIT_AUTHOR_EMAIL='bridge@localhost',
                               GIT_COMMITTER_NAME='Battlecode agent bridge', GIT_COMMITTER_EMAIL='bridge@localhost')
                    self.git('read-tree', head if head else '--empty', env=env)
                    blob = self.git('hash-object', '-w', '--stdin', data=json.dumps(value, indent=2) + '\n')
                    self.git('update-index', '--add', '--cacheinfo', '100644', blob, f'jobs/{job_id}.json', env=env)
                    tree = self.git('write-tree', env=env)
                    parents = ['-p', head] if head else []
                    commit = self.git('commit-tree', tree, *parents, data=f'Update job {job_id}\n', env=env)
                # An exact lease also protects the initial creation from a competing root commit.
                lease = f'--force-with-lease={REF}:{head or ""}'
                pushed = run(['git', '--git-dir', self.gitdir, 'push', lease, 'origin', f'{commit}:{REF}'], check=False)
                if pushed.returncode == 0:
                    return value
                if not any(x in pushed.stderr.lower() for x in ['stale info', 'fetch first', 'rejected', 'cannot lock ref']):
                    raise RuntimeError('Mailbox push failed: ' + pushed.stderr.strip())
                time.sleep(.1 * (attempt + 1))
            raise RuntimeError('Mailbox busy; retry later')

    def submit(self, task):
        def create(current):
            if current is not None:
                raise ValueError('Job already exists')
            return dict(task, status='queued', created_at=time.time())
        return self.update(task['id'], create)

    def claim(self, job_id, role, worker, ttl=900):
        waiting, running = ('queued', 'coding') if role == 'coder' else ('ready', 'testing')
        token = secrets.token_hex(16)
        def change(job):
            if job is None or not (job['status'] == waiting or
                                   job['status'] == running and job['lease']['expires_at'] < time.time()):
                raise ValueError('Job is not available for this worker')
            job.update(status=running, lease=dict(token=token, worker=worker, expires_at=time.time() + ttl))
            return job
        return self.update(job_id, change)

    def finish(self, job_id, token, status, payload=None, ttl=900):
        def change(job):
            if (job is None or job.get('lease', {}).get('token') != token or
                    job['lease']['expires_at'] < time.time() or job['status'] not in ('coding', 'testing')):
                raise ValueError('Worker lease expired or was replaced')
            allowed = {'coding': {'coding', 'ready', 'coding_failed'},
                       'testing': {'testing', 'done', 'testing_failed'}}
            if job.get('kind') == 'ping':
                allowed['coding'].add('done')
            if status not in allowed[job['status']]:
                raise ValueError('Invalid job transition')
            job.update(payload or {})
            job['status'] = status
            if status in ('coding', 'testing'):
                job['lease']['expires_at'] = time.time() + ttl
            else:
                job.pop('lease')
            return job
        return self.update(job_id, change)


def stop(process):
    if process.poll() is not None:
        return
    if os.name == 'nt':
        subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'], capture_output=True)
    else:
        os.killpg(process.pid, signal.SIGKILL)
    process.wait()


def execute(argv, cwd, log, mailbox, job, timeout, prompt=None):
    """Lease heartbeat while the child runs; timeout stops this child's process tree."""
    token = job['lease']['token']
    deadline = time.monotonic() + timeout
    next_heartbeat = time.monotonic() + 60
    with log.open('w', encoding='utf-8') as output, tempfile.TemporaryFile(mode='w+', encoding='utf-8') as stdin:
        if prompt:
            stdin.write(prompt)
            stdin.seek(0)
        process = subprocess.Popen(argv, cwd=cwd, stdin=stdin, stdout=output,
                                   stderr=subprocess.STDOUT, start_new_session=os.name != 'nt')
        try:
            while process.poll() is None:
                if time.monotonic() >= deadline:
                    raise TimeoutError('Worker command exceeded its time limit')
                if time.monotonic() >= next_heartbeat:
                    mailbox.finish(job['id'], token, job['status'])
                    next_heartbeat = time.monotonic() + 60
                time.sleep(.25)
            if process.returncode:
                raise RuntimeError(f'Worker command exited {process.returncode}; see {log}')
        finally:
            stop(process)


def checkout(mailbox, job, role):
    if (not ID.fullmatch(job['id']) or not ID.fullmatch(job['base_bot']) or
            not SHA.fullmatch(job['base_commit']) or job['candidate_bot'] != 'pi_' + job['id']):
        raise ValueError('Malformed job identity or base commit')
    attempt = job['lease']['token'][:12]
    path = mailbox.state / 'checkouts' / f'{job["id"]}-{role}-{attempt}'
    path.parent.mkdir(parents=True, exist_ok=True)
    run(['git', 'clone', '--no-checkout', mailbox.remote, path])
    if role == 'coder':
        commit = job['base_commit']
        branch = f'pi/{job["id"]}/{attempt}'
        run(['git', 'fetch', 'origin', commit], cwd=path)
        run(['git', 'checkout', '-b', branch, 'FETCH_HEAD'], cwd=path)
        return path, branch
    commit = job['candidate_commit']
    branch = job['candidate_branch']
    if not SHA.fullmatch(commit) or not re.fullmatch(r'pi/' + re.escape(job['id']) + r'/[0-9a-f]{12}', branch):
        raise ValueError('Invalid candidate branch or commit')
    remote_sha = run(['git', 'ls-remote', 'origin', 'refs/heads/' + branch], cwd=path).stdout.split()
    if not remote_sha or remote_sha[0] != commit:
        raise ValueError('Candidate branch no longer matches the recorded commit')
    run(['git', 'fetch', 'origin', branch], cwd=path)
    run(['git', 'checkout', '--detach', commit], cwd=path)
    if run(['git', 'rev-parse', 'HEAD'], cwd=path).stdout.strip() != commit:
        raise ValueError('Checkout identity mismatch')
    return path, branch


def implement(mailbox, job, args, logs):
    path, branch = checkout(mailbox, job, 'coder')
    bot = job['candidate_bot']
    source = path / 'bots' / job['base_bot']
    target = path / 'bots' / bot
    if not source.is_dir() or target.exists():
        raise ValueError('Base bot missing from committed snapshot, or candidate already exists')
    shutil.copytree(source, target, ignore=shutil.ignore_patterns('.cambc', 'build', 'target', '__pycache__'))
    prompt = f'''Implement this Battlecode experiment in C++.
Base commit: {job['base_commit']}. Candidate: bots/{bot}/.
The bridge has cloned {job['base_bot']} into that directory.
Change only files inside bots/{bot}/. Preserve the existing pathfinding unless the task explicitly changes it.
Read the relevant strategy documents and SDK in this checkout. Make one coherent, testable change.
Run focused checks available on the Pi; large tournaments run on the PC.
Leave a report in bots/{bot}/IMPLEMENTATION.md describing the hypothesis, actual changes,
checks performed, and any gaps. Leave changes uncommitted; the bridge commits and pushes them.
Keep all other bots, SDK files, repository tools and settings unchanged.
Task:
{job['instructions']}
'''
    codex = shutil.which(args.codex)
    if not codex:
        raise ValueError('Codex executable not found; install and authenticate it on the Pi')
    execute([codex, 'exec', '--sandbox', 'workspace-write', '--json', '--color', 'never', '-'],
            path, logs / 'codex.jsonl', mailbox, job, args.timeout, prompt)
    # Include both committed and uncommitted changes, including untracked files.
    run(['git', 'add', '-A'], cwd=path)
    changed = run(['git', 'diff', '--cached', '--name-only', job['base_commit']], cwd=path).stdout.splitlines()
    prefix = f'bots/{bot}/'
    if not changed or any(not name.startswith(prefix) for name in changed):
        raise ValueError('Agent changed files outside the candidate bot; branch was not pushed')
    # Reject symlinks/submodules: code and build inputs stay inside the candidate checkout.
    entries = run(['git', 'ls-files', '--stage', '--', prefix], cwd=path).stdout.splitlines()
    if any(entry.startswith(('120000 ', '160000 ')) for entry in entries):
        raise ValueError('Candidate contains a symlink or submodule')
    mailbox.finish(job['id'], job['lease']['token'], 'coding')
    staged = run(['git', 'diff', '--cached', '--quiet'], cwd=path, check=False)
    if staged.returncode:
        run(['git', 'commit', '-m', f'Implement experiment {job["id"]}'], cwd=path)
    commit = run(['git', 'rev-parse', 'HEAD'], cwd=path).stdout.strip()
    run(['git', 'merge-base', '--is-ancestor', job['base_commit'], commit], cwd=path)
    run(['git', 'push', 'origin', f'HEAD:refs/heads/{branch}'], cwd=path)
    report = (target / 'IMPLEMENTATION.md').read_text(encoding='utf-8')[:24000] if (target / 'IMPLEMENTATION.md').exists() else 'Agent produced no implementation report.'
    return dict(candidate_commit=commit, candidate_branch=branch, implementation_report=report)


def test_candidate(mailbox, job, args, logs):
    command_text = (args.test_command_file.read_text(encoding='utf-8-sig')
                    if getattr(args, 'test_command_file', None) else args.test_command)
    if not command_text:
        raise ValueError('Tester requires a locally configured --test-command JSON argv array')
    command = json.loads(command_text)
    if not isinstance(command, list) or not command or not all(isinstance(x, str) for x in command):
        raise ValueError('--test-command must be a JSON string array')
    path, _ = checkout(mailbox, job, 'tester')
    output = logs / 'test-result.json'
    replacements = {'{checkout}': str(path), '{bot}': job['candidate_bot'], '{output}': str(output)}
    for key, value in replacements.items():
        command = [part.replace(key, value) for part in command]
    execute(command, path, logs / 'test.log', mailbox, job, args.timeout)
    report = json.loads(output.read_text(encoding='utf-8'))
    if report.get('candidate_commit') != job['candidate_commit'] or report.get('bot') != job['candidate_bot']:
        raise ValueError('Test report does not identify the requested commit and bot')
    if output.stat().st_size > 256000:
        raise ValueError('Keep test reports under 256 KB; replay archives stay on the PC')
    return dict(test_report=report)


def worker(mailbox, args):
    # One local worker per role; leases also prevent cross-machine duplication.
    with file_lock(mailbox.state / (args.role + '.lock')):
        while True:
            if (mailbox.state / 'STOP').exists():
                print('STOP file present; worker stopped', flush=True)
                return
            available = ('queued', 'coding') if args.role == 'coder' else ('ready', 'testing')
            for job in sorted(mailbox.jobs(), key=lambda x: x['created_at']):
                if job['status'] not in available:
                    continue
                if job['status'] == available[1] and job['lease']['expires_at'] >= time.time():
                    continue
                try:
                    job = mailbox.claim(job['id'], args.role, args.name)
                except ValueError:
                    continue
                logs = mailbox.state / 'logs' / f'{job["id"]}-{job["lease"]["token"][:12]}'
                logs.mkdir(parents=True, exist_ok=False)
                print(f'{args.role}: {job["id"]}; logs: {logs}', flush=True)
                try:
                    if job.get('kind') == 'ping':
                        result = dict(worker_reply=dict(name=args.name, host=socket.gethostname(), received_at=time.time()))
                        status = 'done'
                    else:
                        result = implement(mailbox, job, args, logs) if args.role == 'coder' else test_candidate(mailbox, job, args, logs)
                        status = 'ready' if args.role == 'coder' else 'done'
                    mailbox.finish(job['id'], job['lease']['token'], status, result)
                except Exception as error:
                    save(logs / 'failure.json', {'error': str(error)})
                    try:
                        mailbox.finish(job['id'], job['lease']['token'], args.role.replace('coder', 'coding').replace('tester', 'testing') + '_failed', {'error': str(error)[:8000]})
                    except Exception:
                        pass  # Expired/replaced workers cannot overwrite a newer attempt.
                    print(f'FAILED {job["id"]}: {error}', flush=True)
                if args.once:
                    return
            if args.once:
                print('No available job', flush=True)
                return
            time.sleep(args.poll)


def snapshot(args):
    """Commit selected working files with a temporary index; leave user index alone."""
    root = Path(args.repo).resolve()
    run(['git', 'check-ref-format', 'refs/heads/' + args.branch])
    if not args.branch.startswith('bridge/'):
        raise ValueError('Snapshots must use a bridge/ branch')
    for item in args.paths:
        path = (root / item).resolve()
        if not path.is_relative_to(root) or path == root or '.git' in path.relative_to(root).parts:
            raise ValueError('Snapshot paths must be specific paths inside the repository')
    parent = run(['git', 'rev-parse', 'HEAD'], cwd=root).stdout.strip()
    with tempfile.TemporaryDirectory() as temporary:
        env = dict(os.environ, GIT_INDEX_FILE=str(Path(temporary) / 'index'))
        run(['git', 'read-tree', parent], cwd=root, env=env)
        run(['git', 'add', '--', *args.paths], cwd=root, env=env)
        tree = run(['git', 'write-tree'], cwd=root, env=env).stdout.strip()
        commit = run(['git', 'commit-tree', tree, '-p', parent], cwd=root, env=env,
                     data='Snapshot selected files for Pi experiments\n').stdout.strip()
    # Creation only: never replace an existing branch.
    run(['git', 'update-ref', 'refs/heads/' + args.branch, commit, '0' * 40], cwd=root)
    if args.push:
        run(['git', 'push', 'origin', f'{commit}:refs/heads/{args.branch}'], cwd=root)
    print(json.dumps(dict(branch=args.branch, commit=commit, pushed=args.push), indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--remote', help='Git URL or local bare repository; uses origin if omitted')
    parser.add_argument('--state', default='.cambc/agent-bridge')
    sub = parser.add_subparsers(dest='command', required=True)
    submit = sub.add_parser('submit')
    submit.add_argument('--id', default=None)
    submit.add_argument('--base', required=True, help='Exact 40-character pushed base commit')
    submit.add_argument('--base-bot', default='leader_party_tuned')
    submit.add_argument('--instructions', type=Path, required=True)
    sub.add_parser('status')
    ping = sub.add_parser('ping', help='Check worker receipt without a model call or code changes')
    ping.add_argument('--id', default=None)
    show = sub.add_parser('show');show.add_argument('id')
    work = sub.add_parser('work')
    work.add_argument('--role', choices=['coder', 'tester'], required=True)
    work.add_argument('--name', required=True)
    work.add_argument('--once', action='store_true')
    work.add_argument('--poll', type=int, default=60)
    work.add_argument('--timeout', type=int, default=3600)
    work.add_argument('--codex', default='codex')
    work.add_argument('--test-command', help='Local JSON argv array with {checkout}, {bot}, {output} placeholders')
    work.add_argument('--test-command-file', type=Path, help='Local file containing the trusted test command argv')
    snap = sub.add_parser('snapshot')
    snap.add_argument('--repo', default='.')
    snap.add_argument('--branch', required=True)
    snap.add_argument('--push', action='store_true')
    snap.add_argument('paths', nargs='+')
    args = parser.parse_args()
    if args.command == 'snapshot':
        snapshot(args)
        return
    remote = args.remote or run(['git', 'remote', 'get-url', 'origin']).stdout.strip()
    mailbox = Mailbox(remote, args.state)
    if args.command == 'submit':
        job_id = args.id or 'job-' + uuid.uuid4().hex[:12]
        if not ID.fullmatch(job_id) or not SHA.fullmatch(args.base) or not ID.fullmatch(args.base_bot):
            raise ValueError('Invalid job ID, base bot name, or exact base commit')
        task = dict(id=job_id, base_commit=args.base, base_bot=args.base_bot,
                    candidate_bot='pi_' + job_id, instructions=args.instructions.read_text(encoding='utf-8'))
        print(json.dumps(mailbox.submit(task), indent=2))
    elif args.command == 'ping':
        job_id = args.id or 'ping-' + uuid.uuid4().hex[:12]
        if not ID.fullmatch(job_id):
            raise ValueError('Invalid ping identifier')
        print(json.dumps(mailbox.submit(dict(id=job_id, kind='ping')), indent=2))
    elif args.command == 'status':
        print(json.dumps([{k: j[k] for k in ('id', 'status', 'updated_at')} for j in mailbox.jobs()], indent=2))
    elif args.command == 'show':
        with file_lock(mailbox.state / 'mailbox.lock'):
            print(json.dumps(mailbox.read(mailbox.head(), args.id), indent=2))
    else:
        if args.poll < 5 or args.timeout < 1:
            raise ValueError('Poll must be at least 5 seconds; timeout must be positive')
        worker(mailbox, args)


if __name__ == '__main__':
    main()
