"""Mandatory pre-fit checks and archive-before-measurement primitives."""
import ast
import importlib.util
import subprocess
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
ROOTS = ('tools.action_predictor.priority_regularized.experiment',
         'tools.action_predictor.priority_regularized.test_safety',
         'tools.action_predictor.priority_capacity.test_measurement')


def reject_optimized_python():
    if not __debug__ or sys.flags.optimize:
        raise RuntimeError('FIT_REQUIRES_ASSERTIONS: optimized Python is prohibited')


def dependency_files(root=ROOT, roots=ROOTS):
    """Static project-import closure, including nested imports and test roots.

    External packages are environment dependencies. Explicit roots cover the
    unittest modules loaded by name. Module initializers are also included.
    """
    def locate(name):
        base = root.joinpath(*name.split('.'))
        for path in (base.with_suffix('.py'), base/'__init__.py'):
            if path.is_file():
                return path
        return None
    pending=list(roots)
    visited=set()
    result=set()
    while pending:
        name=pending.pop()
        if name in visited:
            continue
        visited.add(name)
        path=locate(name)
        if path is None:
            continue  # Imported function/constant rather than a module.
        result.add(path)
        parts=name.split('.')
        for i in range(1,len(parts)):
            initializer=root.joinpath(*parts[:i])/'__init__.py'
            if initializer.is_file():
                result.add(initializer)
                pending.append('.'.join(parts[:i]))
        package=name if path.name=='__init__.py' else name.rsplit('.',1)[0]
        for node in ast.walk(ast.parse(path.read_text(encoding='utf-8-sig'),filename=str(path))):
            if isinstance(node,ast.Import):
                pending.extend(alias.name for alias in node.names)
            elif isinstance(node,ast.ImportFrom):
                base=importlib.util.resolve_name('.'*node.level+(node.module or ''),package) if node.level else node.module
                if base:
                    pending.append(base)
                    pending.extend(base+'.'+alias.name for alias in node.names if alias.name!='*')
    return sorted(result)


def committed_closure():
    reject_optimized_python()
    from ..priority_broad.guard import committed_sources
    paths=dependency_files()
    # committed_sources is itself executable and must be bound too.
    extra=ROOT/'tools/action_predictor/priority_broad/guard.py'
    if extra not in paths:
        paths.append(extra)
    return committed_sources(ROOT,paths)


def archive_then_measure(raw,path,measurement):
    """The complete cohort raw archive exists before any scoring callback."""
    path=Path(path)
    if path.exists():
        raise FileExistsError(f'Preserve raw archive: {path}')
    path.parent.mkdir(parents=True,exist_ok=True)
    np.save(path,np.asarray(raw))
    return measurement(np.load(path,mmap_mode='r'))
