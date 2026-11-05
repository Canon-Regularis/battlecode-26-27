# Pi coding agent and PC tester

The Pi runs Codex CLI; the Windows PC builds and tests its candidates. A dedicated `agent-mailbox-v1` Git branch carries jobs, implementation reports and test summaries. Candidate code goes to `pi/<job>/<attempt>`. GitHub is Git transport only: no Actions, webhooks, inbound ports or shared credentials between machines.

This chat can submit instructions and read results while active. Continuous strategic analysis needs a separate critic process with its own model access; this implementation does not pretend that a closed chat stays running. The initial workflow is human/chat-directed experiments, automated implementation, automated testing, then critic review and another explicit job. It neither merges candidates nor changes the website submission automatically.

## How a job runs

1. Submit a hypothesis with an exact pushed base commit and base bot name.
2. The Pi claims a lease and creates a fresh checkout. It copies the base bot into `bots/pi_<job>/` and runs Codex there.
3. The bridge verifies that the agent changed only that candidate directory, commits it, and pushes a unique branch. Changes elsewhere fail the job before pushing.
4. The PC claims the ready candidate, verifies the remote branch SHA, and builds that exact commit in a fresh checkout. The trusted local adapter runs paired matches against five frozen top-bot artifacts. Eight maps give 80 games by default.
5. The compact report returns through the mailbox; logs and replays remain on the worker machine. Ask this chat to inspect the job, propose a follow-up or expand testing.

Workers heartbeat once per minute. An interrupted worker's 15-minute lease can be reclaimed; an old attempt cannot publish results over a new one. Failed jobs remain visible instead of being silently retried and spending more model usage. Submit a new job ID for a deliberate retry. Checkouts and logs are preserved for diagnosis; prune them separately after review.

## Pi prerequisites

Use 64-bit Raspberry Pi OS (`uname -m` should report `aarch64`) and Python 3.10+ for the bridge. The PC remains the C++/CAMBC testing machine; the Pi does not need CAMBC's compiler assets. Codex CLI's installed package includes a Linux ARM64 build. These instructions were checked against CLI 0.166.0; Pi installation and authentication still need an actual Pi smoke test.

Install Git, Python, a supported Node.js/npm and GitHub CLI using your OS's packages. Install Codex as your normal user, for example:

```bash
npm install --prefix "$HOME/.local" -g @openai/codex@0.166.0
export PATH="$HOME/.local/bin:$PATH"
codex --version
codex login --device-auth
codex login status
gh auth login --git-protocol https --web
gh auth setup-git
git config --global user.name "Pi coding agent"
git config --global user.email "YOUR_GIT_EMAIL"
```

Authenticate interactively on the Pi using its own account/session. If device authentication is unavailable for your account, use the authentication method supported by your Codex account. Never put authentication tokens in job instructions or commits. Model usage follows that account's subscription/API limits; no model is selected or billed by this bridge independently of Codex configuration.

Once the bridge files have been pushed to a bootstrap branch:

```bash
git clone --branch bridge/pi-bootstrap https://github.com/Canon-Regularis/battlecode-26-27.git "$HOME/battlecode-26-27"
cd "$HOME/battlecode-26-27"
python3 tools/agent_bridge.py --state "$HOME/.local/state/battlecode-agent" status
python3 tools/agent_bridge.py --state "$HOME/.local/state/battlecode-agent" work --role coder --name pi5 --once
```

The first `status` prints an empty list until a job is submitted. `--once` processes at most one job and exits. Run the first real coding job this way before enabling the service.

## Publish a selected bootstrap snapshot from the PC

The current workspace has unrelated changes and untracked bot sources. The snapshot command uses a temporary Git index: it leaves the current branch, normal staging area and unrelated working files alone. It starts at HEAD and overlays only the listed paths. HEAD's historical files remain part of that snapshot; it is not a commit of the recent folder cleanup.

Review the files, then create/push the dedicated bootstrap branch:

```powershell
.venv/Scripts/python.exe tools/agent_bridge.py snapshot --branch bridge/pi-bootstrap --push bots/leader_party_tuned bots/lp_feature_c02_record_guard tools/agent_bridge.py tools/agent_pc_test.py tools/party_feature_load.py tools/start_agent_tester.ps1 tools/pi-coder.service.example tools/tests/test_agent_bridge.py docs/pi_agent_bridge.md
```

The command prints the exact base commit. Keep it for submission. Existing snapshot branches are never overwritten; choose a new `bridge/` name for an updated snapshot. The Pi needs the matching branch name in its clone command. Git authentication must work on both machines. No push or persistent service was started when these files were authored.

## Submit a coding job from this PC

Write the implementation request to a UTF-8 text file. Give one hypothesis, expected behaviour, relevant replay evidence and a measurable acceptance criterion. Example:

```text
Investigate bank stalls caused by a selectable but unreachable altar approach.
Clone the baseline strategy; preserve Subhan pathfinding and current tuning.
Implement bounded, reason-coded banking recovery without enabling team rallies.
Add focused checks proving eventual productive progress in the blocking scenario.
Document any scenario that remains unverified; do not claim a win-rate improvement.
```

```powershell
.venv/Scripts/python.exe tools/agent_bridge.py submit --id bank-progress-01 --base EXACT_40_CHARACTER_PUSHED_COMMIT --base-bot leader_party_tuned --instructions .cambc/bank-task.txt
.venv/Scripts/python.exe tools/agent_bridge.py status
.venv/Scripts/python.exe tools/agent_bridge.py show bank-progress-01
```

Use `--base-bot lp_feature_c02_record_guard` to start from the selected combined challenger instead; the snapshot must contain that bot. Subsequent jobs can start from a previous candidate's commit and bot name. The whole loop is directed through these commands, so this chat can issue implementation tasks and inspect results without controlling the Pi desktop.

## Run the PC tester

The five frozen opponent ZIPs must already exist under this PC's `.cambc/tuning` and `.cambc/features` directories. The adapter deliberately uses these local frozen artifacts, not newly compiled opponents. It records their hashes, the candidate SHA/WASM, map hashes, CLI identity, both spawn sides, faults, logged errors and replay hashes.

```powershell
& tools/start_agent_tester.ps1 -Once
# After the first successful round trip, keep polling:
& tools/start_agent_tester.ps1
```

The runner reserves one physical core, uses the other permitted logical processors and BelowNormal priority. It shares the feature-suite lock with the existing experiments. Default matches use platform-normal fuel. Small-screen wins are evidence for expanding a tournament, not an automatic promotion gate. To change maps/opponents, configure the local adapter command using `agent_pc_test.py --help`; jobs never supply shell commands to the PC.

## Keep the Pi worker running

After a successful real smoke test, copy `tools/pi-coder.service.example` to `~/.config/systemd/user/battlecode-coder.service`, adjusting its checkout path if needed. Then:

```bash
systemctl --user daemon-reload
systemctl --user enable --now battlecode-coder
journalctl --user -u battlecode-coder -f
```

To run after logout, your administrator may need to enable user lingering (`loginctl enable-linger YOUR_USERNAME`). No service is installed automatically. Use `systemctl --user stop battlecode-coder` to stop the Pi worker. Stop the PC worker with Ctrl+C. A `STOP` file in either worker's state directory prevents it claiming another job; remove it to resume. It does not interrupt the current job. Each command also has a one-hour default timeout.

## Checks and next stages

```powershell
.venv/Scripts/python.exe -m unittest discover -s tools/tests -p test_agent_bridge.py -v
```

The local tests exercise two independent mailbox clients, concurrent submissions, lease exclusion/recovery, stale-result rejection, an isolated candidate push/test/result round trip, out-of-scope rejection, and snapshot isolation. Fake coding/testing processes avoid spending tokens or running tournaments. An actual Pi/PC smoke test is still required to validate Linux sandbox support, authentication, ARM64 Codex execution and real CAMBC builds end to end.

An unattended critic and online challenge automation are follow-up integrations. The portal supports 50 unrated challenges/hour according to the user; that limit should become a shared rate limiter when challenge scheduling is implemented. The bridge currently submits no online challenges.
