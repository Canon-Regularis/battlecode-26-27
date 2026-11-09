"""Fail closed before optimization; verify executed bytes exist in HEAD."""
import hashlib
import subprocess


def committed_sources(root, paths):
    commit = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=root,
                            check=True, capture_output=True, text=True).stdout.strip()
    result = {}
    for path in paths:
        relative = path.relative_to(root).as_posix()
        blob = subprocess.run(['git', 'show', f'{commit}:{relative}'], cwd=root,
                              check=True, capture_output=True).stdout
        actual = path.read_bytes()
        if blob != actual:
            raise RuntimeError(f'Executed source differs from committed bytes: {relative}')
        result[relative] = hashlib.sha256(actual).hexdigest()
    return commit, result


def checked_execution(commands, operation, root):
    """No optimizer/fit callback is reached if any prerequisite command fails."""
    receipts = []
    for command in commands:
        result = subprocess.run(command, cwd=root, check=True, capture_output=True, text=True)
        receipts.append(dict(command=command, returncode=result.returncode,
                             stdout=result.stdout, stderr=result.stderr))
    return operation(receipts)
