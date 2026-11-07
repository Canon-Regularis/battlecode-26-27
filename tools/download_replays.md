# Bulk replay downloads

From the repository root, sign in once with the official CAMBC CLI, then run:

```powershell
uv run --locked cambc login
uv run --locked python tools/download_replays.py --team "Intercontinental Fish" --limit 100 --workers 4
```

`--team` accepts a full team name (case-insensitive), team UUID, or `me`.
`--map` accepts an exact published map name, a `.map26a` filename, or a platform
map UUID. Names are resolved against the current platform map list.
Omit `--map` (or pass `--all-maps`) to download across **all maps** for the team.
Add `--map 00ambush` to restrict downloads to one map.

**Login is required**, including when downloading another team's public replays.
The official CLI requires a session for both match listing and replay downloads.
Run `uv run --locked cambc login` once and again if your session expires; the script
reuses that session without asking for credentials itself.

Downloads run asynchronously with **4 concurrent workers** by default. Set
`--workers 8` to allow eight concurrent downloads, or `--workers 1` for sequential
downloads. Listing pages also runs off the event loop so existing downloads keep
running while the next page loads. Progress messages appear in completion order;
the manifest retains the platform's listing order. Queued work is bounded by the
worker limit.

When any request receives HTTP 429 (or a rate-limit message), all workers share
one cooldown before starting further CLI requests, including listing pages and
retries. The script honors the reported retry delay, with exponential backoff
and a 5-second fallback when no delay is reported. Further rate-limit responses
can extend the cooldown; they never shorten it. Requests already in flight are
allowed to finish. Worker count stays at the configured limit after the pause.

By default, the script downloads **all finished ranked games across all maps** for the team,
following every page. `--limit 100` selects at most 100 games in the platform's
listing order; omit it or use `--limit 0` for all games. Existing valid files count
toward the limit. Use `--kind unranked`, `--kind tournament`, or `--kind all` to
change the match types.
The limit is a total across all maps, rather than a separate limit per map.

```powershell
# Preview the selection without downloading or writing files.
uv run --locked python tools/download_replays.py --team me --map 00monolith --limit 10 --dry-run

# Choose an output directory, relative to your current directory.
uv run --locked python tools/download_replays.py --team "Intercontinental Fish" --map 00ambush --out replays/fish-ambush
```

Default output is `replays/downloads/TEAM_UUID/MAP_UUID/` under the repository
(or `replays/downloads/TEAM_UUID/all-maps/` when no map filter is used;
the team directory is `me` for that selector). Each game is saved as
`MATCH_UUID.repl26a`, the official ZIP replay bundle, usable with `cambc view`.
`manifest.json` records the current run's selection, match metadata, filenames,
and download statuses/errors. Use separate output directories if you want to
retain separate selection manifests; existing replay files are retained.

Rerun the same command to resume: valid replay bundles are checked and skipped,
and missing or corrupt bundles are downloaded again. Files are validated before
being moved into place; interrupted partial files are retried on the next run.
Individual download failures are recorded and the remaining games continue.
The script exits nonzero on failures. It retries timeouts and temporary HTTP
429/502/503/504 errors, up to three attempts per command, respecting the CLI's
reported retry delay.

To exclude replays you already have by content hash:

```powershell
uv run --locked python tools/download_replays.py --team "Intercontinental Fish" --exclude-hashes hashes.txt
```

The text file must contain one **SHA-256 of the raw `replay.repl26a` payload inside
the ZIP** per line. ZIP-file hashes are different and will not match. Blank lines
and `#` comments are accepted; uppercase hex is accepted. Invalid lines cause an
error before platform requests start. The input file is read without modification.

For each replay, the downloader records `replay_sha256` in `manifest.json` and
maintains a persistent match-ID-to-hash index in `replay-hashes.json` in the output
directory. If a match's indexed hash is excluded, its download is skipped entirely.
For a replay whose hash is unknown, the payload **must first be downloaded to a
temporary file** to calculate its hash. If excluded, the temporary download is
discarded and its hash is indexed so subsequent runs can skip the network request.
Excluded replays report `excluded`, count toward `--limit`, and do not count as
failures. Existing valid files are preserved and report `skipped`. A dry run only
recognizes exclusions already in the hash index; it does not fetch unknown payloads.

To create a compatible text file from a previous run's hash index in PowerShell:

```powershell
$replayIndex = Get-Content replays/fish-ambush/replay-hashes.json -Raw | ConvertFrom-Json
$replayIndex.PSObject.Properties.Value | Sort-Object -Unique | Set-Content hashes.txt -Encoding utf8
```

The script uses the project's `.venv` CAMBC executable, then `cambc` on PATH,
then `uv run --locked`. If needed, pass `--cli C:/path/to/cambc.exe` to select
an installation explicitly. It reuses the CLI's login session.

Offline tests:

```powershell
python -m unittest discover -s tools -p test_download_replays.py
```
