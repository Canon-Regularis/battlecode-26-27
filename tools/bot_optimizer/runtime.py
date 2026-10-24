"""Pinned cambc build/smoke checks; these are NOT equivalence proofs."""

from pathlib import Path
import shutil
import subprocess
import zipfile


def executable(explicit=None):
    candidate = explicit or (str(Path(".venv/bin/cambc").resolve())
                             if Path(".venv/bin/cambc").is_file() else shutil.which("cambc"))
    if not candidate:
        raise ValueError("cambc not found; use --cambc /path/to/cambc")
    result = subprocess.run([candidate, "--version"], capture_output=True, text=True, check=True, timeout=30)
    if not result.stdout.strip() or result.stdout.strip().split()[-1] != "3.0.4":
        raise ValueError(f"Expected cambc 3.0.4, found {result.stdout.strip()!r}")
    return candidate


def run_command(command, timeout=240):
    result = subprocess.run(command, capture_output=True, text=True, timeout=timeout)
    if result.returncode:
        raise ValueError(f"Command failed ({result.returncode}): {' '.join(map(str, command))}\n"
                         f"{result.stdout[-6000:]}\n{result.stderr[-6000:]}")
    return result


def replay_logs(path):
    with zipfile.ZipFile(path) as archive:
        return {name: archive.read(name).decode("utf-8", errors="replace").replace("\0", "")
                for name in archive.namelist() if name.endswith((".stdout", ".stderr"))}


def check_logs(logs):
    failures = [f"{name}: {line}" for name, text in logs.items() for line in text.splitlines()
                if any(marker in line for marker in (
                    "Traceback (most recent call last)", "FATAL ", "bot error:", "panicked at",
                ))]
    if failures:
        raise ValueError("Runtime errors:\n" + "\n".join(failures[:20]))


def verify(output, *, cambc=None, maps=(), rounds=3):
    cli = executable(cambc)
    output = Path(output).resolve()
    run_command([cli, "build", str(output), "--release"])
    checks = {"build": "passed", "smoke": [],
              "note": "Build and smoke checks do not establish behavioural equivalence or fuel savings."}
    for index, game_map in enumerate(maps):
        destination = output / ".cambc" / f"optimizer-smoke-{index}"
        if destination.exists():
            raise ValueError(f"Smoke output already exists: {destination}")
        run_command([cli, "run", str(output), str(output), "--release", "--map", game_map,
                     "--rounds", str(rounds), "--out-dir", str(destination)])
        replays = sorted(destination.glob("*.repl26a"))
        if len(replays) != 1:
            raise ValueError(f"Expected one replay in {destination}, found {len(replays)}")
        check_logs(replay_logs(replays[0]))
        checks["smoke"].append({"map": game_map, "rounds": rounds, "status": "no logged errors",
                                "replay": str(replays[0])})
    return checks
