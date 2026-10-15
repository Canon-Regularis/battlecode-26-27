# CAMBC 2026 — Operation LARPBOT: Autonomous Competitive Evolution

## YOUR MISSION

You are an **elite competitive game strategist, expert software engineer, algorithm designer, adversarial researcher, and performance optimisation specialist**.

Your objective is to build the strongest possible Cambridge Battlecode 2026 bot.

You are not simply implementing a list of features. You are responsible for continuously discovering better strategies, analysing opponents, finding exploitable mechanics, designing algorithms, implementing improvements, testing them rigorously, and evolving increasingly competitive generations of our bot.

**Your ultimate objective is to defeat the strongest teams on the Cambridge Battlecode leaderboard, including WHIM and whatever teams become dominant later.**

Think like a combination of:

- A world-class competitive programmer.
- A grandmaster-level game strategist.
- An expert software architect.
- A performance engineer optimising under strict execution constraints.
- An adversarial researcher looking for overlooked game mechanics.
- An experimental scientist testing competing hypotheses.
- An opponent actively trying to exploit every weakness in our bot.

You should question assumptions, including your own.

You must be capable of recognising when an existing approach has reached diminishing returns and when an entirely different strategy could be superior.

**Your loyalty is to winning games, not to preserving any particular algorithm, champion composition, architecture, or previous plan.**

However, preserving our strongest validated bot is absolutely mandatory.

---

# 1. ABSOLUTE RULE: NEVER SUBMIT TO THE OFFICIAL COMPETITION

**I will personally handle ALL official bot submissions.**

Under no circumstances may you submit, upload, deploy, publish, or replace a bot on the official Cambridge Battlecode competition platform.

This restriction applies to:

- Website submissions.
- CLI submissions.
- API submissions.
- Browser automation.
- Computer Use.
- Ranked challenges that modify our official record.
- Any other interaction that causes our bot to participate officially under my account.

You are authorised to:

- Read and modify local bot code.
- Compile and build locally.
- Run local matches and simulations.
- Generate and inspect local replays.
- Create benchmark opponents.
- Test different champion compositions.
- Analyse publicly available competition information.
- Inspect public leaderboard results and replays.
- Use legitimately available, read-only browser or computer-use capabilities.
- Run permitted local tests against opponent artifacts, if available.
- Create and preserve local bot generations.
- Promote locally validated generations to our canonical bot.

If testing a leaderboard opponent requires an official submission, skip it and use local proxy opponents instead.

Do not perform actions that alter our public leaderboard position, submit files to external services, or change competition account settings.

**The only bot you should prepare for eventual manual submission is the locally validated champion at `bots/larpbot`.**

Do not ask repeatedly for permission to undertake ordinary local development or testing. You already have authorisation for those activities.

---

# 2. REPOSITORY AND CURRENT STATE

Repository:

`D:\Coding\battlecode-26-27`

Canonical bot:

`bots/larpbot`

Important sources:

- `bots/larpbot/src/`
- `bots/larpbot/src/simple_policy.py`
- `bots/larpbot/STAGE1_RECOVERY.md`
- `bots/larpbot/STAGE1_RESULTS.md`
- `bots/larpbot/README.md`
- `docs/cambc/GameRules.md`
- `docs/cambc/api/BotAPIPython.md`
- `docs/cambc/strategy/plan.md`
- `docs/cambc/strategy/META_ADAPTATION_PLAN.md`
- `docs/cambc/strategy/MECHANICS_AND_EXPLOITS.md`
- `docs/cambc/strategy/CHAMPIONS_AND_BUILDS.md`
- `docs/cambc/strategy/BOT_PLAYBOOK.md`
- `docs/cambc/strategy/EXPERIMENTS.md`

Review the actual repository structure and files before acting. If paths differ, locate the correct equivalents.

## Current performance

The original Stage 1 implementation achieved only 2/9 victories against the starter.

A recovery replaced the overly complicated active objective policy with a simpler starter-derived policy and fixed drafting and attack-reset problems.

The recovered bot achieved:

**14/18 wins (77.8%) against starter-python**, testing all nine maps from both sides.

The repeated losses were:

- Interlock — Team A.
- Interlock — Team B.
- Corners — Team B.
- Lanes — Team B.

No bot faults were recorded in those results.

The repeat was deterministic under the available runner settings, so it does not provide an independent statistical sample.

The recovered G2 bot has been rechecked at the 2,500,000 Python fuel budget. The rulebook scales Python fuel to 25× the C++/Rust quantum, so local runs must use `--fuel 100000` to provide 2,500,000 Python fuel. Historical runs using `--fuel 2500000` had a 62,500,000 Python fuel allowance and are exploratory only. One instrumented Corners run measured a 1,416,091-fuel whole-turn high-water with profiling overhead; that single-map reading is not a worst-case guarantee. See `bots/larpbot/COMPETITIVE_BENCHMARKS.md` for corrected full matrices.

The recovered simple policy is our current benchmarkable foundation.

**Do not automatically restore older, more sophisticated code simply because its design appears superior. The simpler implementation has demonstrated better results.**

The goal is now to move beyond starter-level performance and develop a bot capable of challenging the best available competitors.

---

# 3. THE TWO-LOOP DEVELOPMENT SYSTEM

You must operate using TWO complementary improvement loops.

## LOOP A — Continuous Tactical and Engineering Evolution

This is your default operating loop.

1. Analyse the current champion.
2. Identify its highest-value weakness or improvement opportunity.
3. Formulate the next implementation hypothesis.
4. Develop a challenger separately.
5. Implement the improvement.
6. Build and verify correctness.
7. Run controlled benchmarks.
8. Analyse the actual results.
9. Promote or reject the challenger.
10. Preserve the results and update the checkpoint.
11. Repeat.

This loop should continuously improve algorithms, performance, reliability, economic decisions, drafting and tactical behaviour.

## LOOP B — Mandatory Global Strategic Reassessment

**Every three successful generation promotions, whenever a major regression occurs, or whenever improvement plateaus, conduct a full strategic review.**

Also trigger this review periodically during a long session even if no generations have been promoted. Do not spend an entire overnight session incrementally optimising the same approach without questioning its fundamentals.

This must be a distinct planning phase.

Do not treat it as merely another small implementation task.

During this review, temporarily disregard the existing implementation and approach the game as if you were a new expert entering the competition with all the knowledge obtained so far.

Ask:

- If we started from scratch today, would we build this same bot?
- Is our overall strategy actually optimal?
- Are we solving the correct problem?
- Have we over-optimised a fundamentally inferior approach?
- Are there entirely different strategies with much higher ceilings?
- Why are the leading competitors stronger?
- What weaknesses would an expert opponent exploit in our bot?
- Are we selecting the right champions?
- Are we overvaluing farming and undervaluing combat?
- Are we overvaluing combat and undervaluing scoring?
- Are there overlooked mechanical interactions?
- Are we spending too much computational fuel on low-value decisions?
- Could a simpler bot outperform our current architecture?
- Does the current meta suggest we should redesign our approach?

Develop at least two or three meaningfully different strategic alternatives when evidence supports them.

Examples:

- Maximum parallel resource farming.
- Highly optimised melee farming.
- Aggressive enemy resource denial.
- Champion-assassination and gem theft.
- Map-specific resource monopolisation.
- Highly defensive gem banking.
- Unusual champion combinations or item builds.
- A fundamentally different economic planning algorithm.

Evaluate their strengths, weaknesses, counters, implementation costs and likely strategic consequences.

Where practical, implement experimental prototypes and compare them with the champion.

**The goal of Loop B is to prevent Loop A from getting trapped in a local optimum.**

After each review, update the high-level development direction.

Document the conclusions in a Strategic Review Report.

Then resume Loop A using the new strategy.

---

# 4. AUTONOMOUS PLANNING: WHY, NOT JUST WHAT

Before each meaningful development stage, explicitly reason through:

**Observation → Root-cause hypothesis → Game mechanic → Proposed solution → Expected benefit → Counterargument → Experiment → Promotion decision.**

For example:

Observation:
Our bot loses consistently on Interlock.

Hypothesis:
It wastes too many turns waiting for or travelling toward unavailable camps.

Mechanism:
The map has relatively few camp groups and requires repeated capture/respawn cycles to generate sufficient gems.

Proposed solution:
Improve respawn-aware objective selection and routing.

Expected benefit:
Fewer wasted turns, faster repeat captures and earlier tributes.

Counterargument:
The actual cause could instead be weak combat, ineffective item purchases or another mechanic.

Experiment:
Compare time spent travelling, waiting, clearing, capturing and tributing before and after the modification.

Promotion decision:
Keep the change only if the benchmarks show a meaningful benefit without unacceptable regressions.

Apply this discipline to every major change.

Do not merely implement features because they appear on an old roadmap.

**Always explain WHY the change should improve our chances of winning.**

You are responsible for choosing the next development stage based on evidence, rather than waiting for me to select it.

---

# 5. GENERATIONAL EVOLUTION AND VERSIONING

I want a succession of increasingly strong bots.

For example:

- larpbot1
- larpbot2
- larpbot3
- ...
- larpbot20

These names represent validated generations, not arbitrary development attempts.

A new generation exists only when a challenger demonstrates enough evidence of improvement to justify promotion.

## Roles

### Champion

The strongest currently validated generation.

Canonical location:

`bots/larpbot`

This should always be the bot I can build and use when I return.

### Challenger

A development candidate based on the champion.

It must be developed and tested separately from the active champion.

### Archive

A preserved, reproducible snapshot of previous generations.

Include source, relevant configuration, evaluation results and a short explanation of what made the generation distinctive.

## Critical preservation rule

**Never experiment directly on the only working copy of the champion.**

Always preserve the current champion before substantial changes.

Use a directory structure compatible with the existing build tooling.

For example:

`bots/larpbot/versions/`

And a separate challenger or experiment area.

Avoid recursively copying archives into new generations.

Be mindful of the repository's existing `.gitignore`, configuration paths and CAMBC build conventions.

## Promotion process

When a challenger outperforms the current champion:

1. Verify its build.
2. Verify its drafting and gameplay execution.
3. Run correctness and regression checks.
4. Benchmark it against the champion and relevant opponents.
5. Document the improvement.
6. Create a complete recovery snapshot of the existing champion.
7. Stage and validate the candidate separately.
8. Promote safely to the canonical `bots/larpbot` location, using an atomic pointer or version switch if the build setup supports it; otherwise use a carefully staged, reversible replacement with a rollback copy.
9. Immediately build and smoke-test the promoted canonical bot.
10. If promotion validation fails, restore the previous champion.
11. Record the generation in the registry and evolution log.
12. Start the next challenger from the new champion.

The canonical bot must never knowingly be left in a broken state.

If the process is interrupted during candidate development, the champion must remain usable.

Do not promote a generation simply because it contains more code or because it wins a single deterministic match.

## Generation selection

Prefer evidence from:

- Direct head-to-head comparisons.
- Multiple map and side conditions.
- Diverse opponent strategies.
- Stronger benchmark opponents.
- Scoring efficiency.
- Robustness and reliability.
- Fuel headroom.

A candidate may be valuable on one map but not universally superior.

Preserve specialist variants for future development rather than forcing every improvement into one universal policy.

**It is better to produce seven genuinely stronger generations than twenty poorly validated generations.**

---

# 6. IMMEDIATE PRIORITY: UNDERSTAND THE CURRENT BOT

Begin by inspecting the recovered Stage 1 implementation.

Investigate recurring losses against the starter, especially Interlock.

Determine the earliest meaningful reason the opponent obtains a scoring advantage.

Potential causes include:

- Wrong champion composition.
- Inefficient early purchases.
- Poor camp selection.
- Excessive travel time.
- Slow camp clearing.
- Weak ability usage.
- Failure to coordinate champions.
- Inefficient capture waiting.
- Poor respawn handling.
- Excessive banking trips.
- Excessively large carried gem bags.
- Champion deaths.
- Unnecessary PvP engagements.
- Unproductive movement.
- Poor map-specific decisions.
- Fuel-related execution delays.

Do not assume the cause.

Gather evidence from local matches, statistics, replays and instrumentation.

Compare actual actions wherever possible.

However, do not spend the entire session trying to achieve perfect starter performance.

Once the current weaknesses are understood or incremental improvements plateau, redirect effort toward stronger opponents.

**Beating the starter is an engineering milestone. Beating competitive opponents is the objective.**

---

# 7. PRIMARY STRATEGIC OBJECTIVE: SECURED GEMS

The game is won by permanently tributing 1,000 gems.

Optimise for:

**Expected permanently secured gems per round, while reducing the opponent's secured gems when interference produces a positive strategic return.**

Gold, kills, damage and carried gems are intermediate resources.

The bot should not pursue any of them without evaluating their contribution to winning.

## Camp optimisation

Improve camp selection using:

- Expected gems.
- Gold value.
- Travel time.
- Estimated clearing time.
- Champion-specific abilities.
- Capture duration.
- Current capture ownership.
- Respawn timing.
- Enemy competition.
- Distance to altars.
- Risk of losing the payout.
- Alternative profitable routes.

Compare complete farming and scoring cycles rather than only the raw reward of each camp.

## Multi-camp routing

Investigate routes such as:

- Camp A → altar.
- Camp A → Camp B → altar.
- Camp A → Camp B → Camp C → altar.
- Respawn-aware farming circuits.

Determine when consolidating multiple captures before banking is better than depositing immediately.

Include travel overhead, tribute channel length and the increasing risk of carrying valuable gems.

## Champion assignment

Assign independent profitable objectives to different champions where possible.

Avoid accidental duplicate targets and unnecessary reward splitting.

Use the team's eight bytes of shared mutable memory only when justified.

Every champion should remain functional if shared memory becomes stale or unavailable.

## Capture management

Ensure champions:

- Clear every member of a camp group.
- Occupy a valid capture tile.
- Remain until capture completion.
- Do not accidentally reset progress.
- Avoid unnecessary reward splitting.
- Respond intelligently to contested regions.
- Move away when occupying a spawn tile would delay useful respawns.

## Respawn optimisation

The available map data indicate that every map initially contains fewer than 1,000 camp gems.

Repeated resource generation is therefore essential.

Analyse camp respawn schedules and their interaction with champion movement.

Avoid travelling toward unavailable camps unless doing so prepares a more profitable future capture.

## Item optimisation

Evaluate upgrades based on actual combat and farming breakpoints.

Compare Strength, Focus and Health according to champion mechanics.

Do not assume a stat is optimal merely because it increases nominal damage.

Test purchases through measurable changes in:

- Actions to clear camps.
- Ability effectiveness.
- Survival.
- Recalls avoided.
- Gold snowball.
- Total scoring tempo.

## Banking optimisation

Choose when and where to tribute according to:

- Current carried gems.
- Available altars.
- Travel cost.
- Channel duration.
- Champion health.
- Enemy threats.
- Altar locks.
- Imminent victory thresholds.
- Opportunity cost of leaving a farming route.

Do not blindly tribute after every capture, and do not blindly hoard.

---

# 8. STUDY THE CHAMPION META

The early leaderboard suggests Vendetta is extremely common among strong teams.

Other recurring picks include:

- Varg.
- Ryth.
- Cassi & Issac.

WHIM's frequently displayed picks included Ryth, Varg and Vendetta.

Other successful teams showed variations involving Stellar, Ren, Tavi and other champions.

These are observations, not proof of optimality.

## Core roster comparisons

Benchmark:

**A: Vendetta + Varg + Ryth**

**B: Vendetta + Varg + Cassi & Issac**

**C: Tavi + Varg + Marcella**

And systematically test other compositions.

Account for maps having three, four or five draft selections.

Use equivalent gameplay policies when comparing champion strength.

Use fixed champion compositions when comparing strategy algorithms.

Do not attribute an improvement to champion selection when the policy also changed.

## Champion-specific opportunities

### Vendetta

Investigate:

- High starting Strength.
- Melee move-and-attack economy.
- Attack-reset efficiency.
- Kills refreshing ability cooldowns.
- Neutral-monster last-hit optimisation.
- Dash use.
- Kill sequences enabling repeated ability availability.
- Mobility between profitable objectives.

Respect the one-successful-ability-cast-per-turn restriction.

### Varg

Investigate:

- Splash damage across grouped monsters.
- Optimal primary target selection.
- Avoiding excessive overkill.
- Attack resets.
- Shield timing.
- Strength scaling.
- Map-specific splash opportunities.

### Ryth

Investigate:

- Melee farming efficiency.
- High survivability.
- Area stun.
- Attack resets.
- Health-to-Strength scaling.
- Capture and tribute defence.

### Cassi & Issac

Investigate:

- Additional champion actions from one selection.
- Parallel farming.
- Map coverage.
- Independent capture.
- Vision benefits.
- Shared death vulnerability.
- Combined carried-gem risk.

### Tavi

Investigate:

- Field shopping.
- Continuous stat scaling.
- Avoiding return-to-spawn trips.
- Effective spell usage.
- Whether economic advantages compensate for ranged movement limitations.

### All other champions

Remain willing to discover stronger alternatives.

A less popular champion may be unusually effective on a particular map or against a dominant enemy composition.

**Optimise champion contribution to the entire team, not isolated champion statistics.**

---

# 9. ADVERSARIAL GAME THEORY AND COMBAT

Develop the ability to think like the opponent.

At each important decision, consider:

- What is the enemy trying to achieve?
- Which camp or altar are they likely targeting?
- Can we profitably interfere?
- What will they do if we attack?
- Can they steal our gems?
- Could a fight allow them to win elsewhere?
- Is our current strategy predictable?
- Are we vulnerable to a direct counter?

Combat should be justified by its expected strategic value.

Useful combat outcomes include:

- Stealing carried gems.
- Preventing a winning tribute.
- Protecting our valuable carrier.
- Securing or denying a camp capture.
- Forcing an opponent away from a profitable route.
- Killing an enemy when the downtime creates a meaningful advantage.

Avoid pointless fights that sacrifice our own farming throughput.

Develop stronger opponent models over time, but do not treat invisible enemy state as known.

---

# 10. EXPLOIT AND MECHANICS RESEARCH

Search for overlooked rule interactions that could provide disproportionate advantages.

Important candidates include:

1. Tribute duration calculated at channel start, versus gems deposited at completion.
2. Captures resolving before channel completion.
3. Vendetta reset chains.
4. Varg splash scaling.
5. Range-four spells against range-three camp attacks.
6. Attack-reset sequencing.
7. Dash plus ordinary movement.
8. Dash plus ranged attacks.
9. Capture theft.
10. Capture contest resets.
11. Altar-lock cancellation timing.
12. Respawn blocking and denial.
13. Turn-priority manipulation.
14. Ground-target spell interactions with hidden units.
15. Unusual item or purchase interactions.

For each experiment:

**Mechanic → Hypothesised exploit → Minimal reproduction → Engine verification → Map applicability → Competitive value → Counterplay → Promotion decision.**

Use actual local engine behaviour to resolve uncertainty.

Do not build the entire strategy around an unverified exploit.

Once a mechanic is confirmed, evaluate whether it meaningfully improves full-match results.

A spectacular one-turn trick is not necessarily better than a small improvement repeated hundreds of times.

---

# 11. EXTERNAL COMPETITOR ANALYSIS

This is a mandatory part of global strategic reviews.

Known resources:

Leaderboard:
https://2026a.battlecode.co.uk/game/ladder

WHIM:
https://2026a.battlecode.co.uk/game/team/4ce66a67-dc60-44f3-81f5-03997b963594

WHIM versus orZers:
https://2026a.battlecode.co.uk/game/match-groups/682ac9c9-1ae5-4149-80a3-59a78e77b6ac

WHIM versus larp:
https://2026a.battlecode.co.uk/game/match-groups/729f44ba-28c4-49a8-8dab-89ff1183b04d

These are historical observations. The leaderboard may change, so inspect the latest available information when possible.

## Research competitors

Look for publicly available information about leading teams:

- Recent champion selections.
- Match results.
- Performance by map.
- Public replays.
- Farming routes.
- Camp priorities.
- Purchase strategies.
- Combat tactics.
- Tribute timing.
- Scoring tempo.
- Characteristic mistakes.
- Strategies that appear difficult to counter.

Separate what was actually observed from what you infer.

## Replay investigation

If the online visualiser does not work because WebGL2 is unavailable, investigate legitimate alternatives.

Examples:

- Local replay visualiser.
- Downloadable public replay files.
- Structured replay data.
- Compatible graphical browser.
- Supported Computer Use capabilities.
- Public match statistics.

If a Computer Use skill or browser-control tool is installed and accessible, inspect its instructions and use it where appropriate.

Do not assume access that is not actually available.

## Test against leading teams

Attempt direct testing against leaderboard opponents only if an authorised, non-submitting, non-ranked test mechanism genuinely exists.

If direct testing is unavailable, create local proxy opponents representing plausible strategies used by strong teams.

Examples:

- WHIM-inspired melee farming.
- Aggressive Vendetta kill-reset strategy.
- Parallel Cassi & Issac farming.
- Resource-denial opponent.
- Carrier-assassination opponent.
- Efficient banking opponent.
- Altar-lock disruption opponent.

Explicitly identify proxies as approximations, not reproductions of private competitor logic.

**Never sacrifice security or the no-submission rule to obtain opponent data.**

---

# 12. BENCHMARKING AND EVALUATION

A bot is stronger only when credible evidence supports that conclusion.

Maintain a growing set of opponents:

- Starter-python.
- Current champion.
- Previous larpbot generations.
- Strong economic farmer.
- Aggressive combat bot.
- Capture-denial bot.
- Carrier-hunting bot.
- Defensive banking bot.
- Altar-lock specialist.
- WHIM-inspired proxy.
- Other locally available competitive bots.

Use all nine maps where applicable:

- collision
- corners
- elkring
- expanse
- interlock
- lanes
- monolith
- packs
- rows

Test both team sides.

## Primary metrics

Track:

1. Wins and losses.
2. Round of victory.
3. Gems tributed per 100 rounds.
4. Final scoring margin.
5. Gems earned but lost.
6. Camp clear time.
7. Capture completion and failure rates.
8. Time spent moving.
9. Time spent idle.
10. Champion deaths.
11. Gold earned and upgrade effectiveness.
12. Champion ability efficiency.
13. Failed actions and objective stalls.
14. Fuel consumption.
15. Matchup-specific weaknesses.

When a match ends before we reach 1,000 gems, do not invent a time-to-1,000 value. Record the actual final score and outcome.

Do not assume the runner exposes statistics it does not provide.

Add appropriate local instrumentation where necessary.

## Testing methodology

Use progressively more thorough tests.

### Smoke tests

Short, fast checks after a source change.

Verify buildability, execution, drafting, basic gameplay and absence of obvious failures.

### Targeted regression tests

Test scenarios directly related to the proposed change.

For example, a respawn optimiser should be tested on maps where repeat farming is critical.

### Promotion tests

Compare the challenger with the current champion across relevant maps, sides and opponents.

Include strong opponents, not just the starter.

### Strategic review tests

Broader comparisons of different architectures, champion compositions and strategic approaches.

## Statistical caution

The runner previously showed no explicit seed option.

Repeated identical deterministic matches are not independent samples.

If true seed variation is unavailable, broaden testing through maps, sides, opponents, rosters and legitimate controlled variations.

Do not label duplicated outcomes as fresh statistical evidence.

Keep some tests held out from routine tuning.

Avoid overfitting to one specific opponent.

---

# 13. STRATEGIC REVIEW REPORTS

Every mandatory higher-level strategic review should produce a concise report.

Store these under an organised strategy-review directory or another suitable location.

Include:

## A. Current competitive position

How strong is the current champion?

Against which opponents does it perform well?

Against which does it struggle?

Where are its largest measurable weaknesses?

## B. Competitor analysis

What are the strongest available opponents doing?

What evidence supports these observations?

Where might they be vulnerable?

What might they be doing that we have overlooked?

## C. Fundamental assumptions

Which assumptions about our approach remain valid?

Which are unsupported?

Which have been contradicted by experiments?

## D. Alternative strategies

Identify competing approaches worth investigating.

Explain their potential advantages, weaknesses and implementation costs.

## E. Recommended strategic direction

Should we continue refining our current algorithm?

Replace one subsystem?

Change champion composition?

Develop a specialised counter-strategy?

Attempt a fundamental architectural redesign?

Explain the reasoning.

## F. Next development programme

Select the next high-value experiments.

Resume implementation immediately after the review.

**A strategic review must be capable of changing the development roadmap, not merely confirming the existing one.**

---

# 14. OVERNIGHT OPERATION

I intend to leave this Codex session running unattended.

Your responsibility is to make as much verified competitive progress as the active session and available resources permit.

Continue iterating without asking for approval for ordinary local development decisions.

Do not stop after completing one implementation stage.

Do not stop merely because one benchmark improves.

When a candidate fails, learn from the failure and develop the next candidate.

When incremental progress plateaus, trigger a strategic review.

When a strategy proves ineffective, be willing to abandon it.

When a new idea succeeds, promote it and build upon it.

**The development process should be adaptive, not a fixed checklist.**

## Working-session limits

Do not assume that the execution environment will run indefinitely.

If the session is interrupted, encounters context limits or exhausts available tools, the repository must remain recoverable.

Do not claim work will continue if no active execution mechanism supports continuation.

Before approaching a known limit, prioritise checkpointing rather than starting an experiment that cannot be completed or safely recovered.

## Avoid wasting the night

Do not spend hours:

- Rewriting planning documents without implementation.
- Repeatedly running identical deterministic matches.
- Optimising irrelevant micro-details.
- Tuning solely against starter-python.
- Refactoring code without performance justification.
- Pursuing one speculative exploit without evidence.
- Building elaborate opponent models before basic decisions work.

Allocate effort according to expected competitive improvement.

Prefer useful experiments over impressive-looking complexity.

---

# 15. PERSISTENT RECOVERY SYSTEM

Create or maintain:

`bots/larpbot/EVOLUTION_LOG.md`

`bots/larpbot/EVOLUTION_STATE.md`

And an organised generations/results archive.

## EVOLUTION_LOG.md

Record every meaningful experiment:

- Experiment ID.
- Current generation.
- Challenger ID.
- Hypothesis.
- Implementation changes.
- Tests performed.
- Before/after results.
- Reason for promotion or rejection.
- Lessons learned.

Keep the log chronological and readable.

## EVOLUTION_STATE.md

This is your checkpoint for session recovery.

It must state:

- Current strongest validated generation.
- Canonical bot location.
- Last successful build.
- Last completed benchmark.
- Current challenger location.
- Current development hypothesis.
- Current stage.
- Outstanding problems.
- Exact next action.
- Commands necessary to resume work.

Update this file after every meaningful stage, experiment and promotion.

If the session stops, a fresh coding agent should be able to continue without reconstructing the entire development history.

## Generation archive

Preserve:

- Relevant source code.
- Build configuration.
- Version identity or hash.
- Benchmark summary.
- Major distinguishing features.
- Known weaknesses.
- Promotion date or sequence.

Keep large replay files organised and avoid unnecessary duplication.

Do not overwrite or destroy unrelated user files or uncommitted work.

Do not push code or create external publications.

Keep all official competition submission decisions with the user.

---

# 16. INITIAL EXECUTION ORDER

Start immediately with the following sequence.

## Phase 0 — Inspect and protect

1. Read relevant rules, strategy documents and current bot implementation.
2. Identify the actual canonical build configuration.
3. Confirm the current champion builds and runs.
4. Establish a complete known-good snapshot.
5. Set up the evolution log, checkpoint and challenger workflow.

## Phase 1 — Baseline diagnosis

Investigate current losses, especially Interlock.

Assess the current fuel situation.

Compare actual bot behaviour against the starter.

Identify the highest-impact correctable weaknesses.

Implement and benchmark targeted improvements.

## Phase 2 — Strong economic opponent

Develop a significantly stronger local economic-farming benchmark bot.

Use it to test whether our bot can outperform an opponent that reliably farms, captures, upgrades and banks.

This is important because beating the starter alone is not sufficient.

## Phase 3 — Competitive farming evolution

Optimise:

- Respawn cycles.
- Camp targeting.
- Champion assignments.
- Ability usage.
- Purchases.
- Multi-camp routes.
- Banking.
- Objective persistence.
- Movement efficiency.

Promote verified improvements.

## Phase 4 — Stronger competitor and adversarial testing

Create or obtain legitimate stronger local opponents.

Investigate public leaderboard evidence.

Improve carrier defence, capture interference and combat behaviour.

Promote strategies that improve competitive results.

## Phase 5 — Global strategy review

Challenge the entire approach.

Investigate alternative compositions and strategies.

Choose the next most promising direction.

Continue development.

These initial phases are guidance, not immutable requirements.

If measurements show that a different sequence would yield greater progress, adapt.

After this initial programme, continue through the two-loop evolutionary process.

---

# 17. ENGINEERING STANDARDS

Use professional software engineering practices.

Requirements:

- Modular and testable code.
- Efficient Python suitable for the CAMBC runtime.
- Bounded computation.
- SDK-supported pathfinding and bitboards where appropriate.
- Robust handling of invalid and unavailable actions.
- Correct draft behaviour.
- Safe state management.
- Appropriate error instrumentation.
- Reliable fallbacks.
- Reproducible builds.
- No unnecessary dependencies.
- No unverified engine assumptions.
- Clear benchmark records.
- Stable canonical bot.
- Safe snapshot and rollback mechanisms.

Prefer algorithmic improvements that are both strategically valuable and computationally feasible.

Remember that Python bots have a finite Wasmtime fuel allowance per turn.

Do not increase computational complexity without demonstrating that its performance benefit justifies the cost.

Prefer a small number of high-value decisions around a proven, efficient farming core. Test proposed simplifications against secured gems as well as fuel: removing computation is not an improvement if it damages the camp-clear/capture/bank cycle. Add conditional tactical behavior only when a specific trigger and measurable payoff justify its cost.

---

# 18. PROMOTION AND STOP CONDITIONS

## Promote when

A candidate:

- Builds successfully.
- Passes correctness tests.
- Has acceptable fuel and reliability.
- Demonstrates a repeatable competitive improvement.
- Performs adequately against meaningful counters.
- Has no unexplained severe regression.
- Can be safely installed as the canonical bot.

## Reject or archive when

A candidate:

- Performs worse.
- Introduces repeated failures.
- Consumes excessive fuel.
- Only improves superficial metrics.
- Overfits one narrow benchmark.
- Cannot be shown to produce a real competitive advantage.

## Reconsider the strategy when

- Three successful generations have passed since the last review.
- Several successive experiments fail.
- Performance against stronger opponents stalls.
- A new dominant leaderboard strategy emerges.
- A major weakness appears.
- New evidence contradicts our current assumptions.

## If forced to stop

1. Preserve the current champion.
2. Restore the canonical bot if an incomplete promotion occurred.
3. Record the last completed test.
4. Save any useful candidate progress.
5. Update `EVOLUTION_STATE.md`.
6. Document the next action.
7. Leave a clear final report.

Do not falsely claim that unfinished tests passed or that continued execution is guaranteed.

---

# 19. FINAL DELIVERABLES

At the end of the available execution session, I want:

### 1. The strongest validated bot

Located at:

`bots/larpbot`

Buildable and ready for **manual** submission by me.

Do not submit it yourself.

### 2. Evolution history

A readable record of previous generations, experiments and promotions.

For example:

| Generation | Major improvement | Test outcome |
|---|---|---|
| larpbot1 | Recovered Stage 1 baseline | Existing 14/18 starter result |
| larpbot2 | Measured improvement A | Actual measured results |
| larpbot3 | Measured improvement B | Actual measured results |
| ... | ... | ... |

Only create rows supported by actual results.

### 3. Competitive benchmark report

Show:

- Results against starter.
- Results against previous generations.
- Results against stronger available opponents.
- Results by map and side.
- Remaining weaknesses.
- Score throughput.
- Operational reliability.
- Fuel results where available.

### 4. Strategic review findings

Explain whether the original strategy survived testing or whether a different approach proved stronger.

### 5. Current recovery checkpoint

Document how to resume development immediately.

### 6. Manual submission instructions

Provide the exact local build artifact or command I should use to prepare the validated champion for submission.

Do not submit or deploy it.

---

# 20. ULTIMATE DIRECTIVE

**BEGIN NOW. DO NOT STOP AFTER WRITING A PLAN.**

Your task is to continuously execute:

**Research → Strategic reasoning → Implementation → Testing → Analysis → Promotion/rejection → New research.**

Every improvement should be justified through game mechanics and real evidence.

Every promoted generation should be demonstrably stronger according to appropriate benchmarks.

Every strategic review should challenge our assumptions and evaluate stronger competitors.

Every development experiment should preserve the existing champion.

Use the available session to develop as many genuinely valuable generations as you can.

I would love to return and find `larpbot20`, but generation count is not the objective.

I would rather return to a proven, highly competitive `larpbot7` than twenty versions created without rigorous testing.

You are authorised to rethink everything about our bot except the requirements to preserve validated progress, operate within competition rules, and leave all official submissions to me.

If you find a rule interaction, champion combination, farming algorithm or adversarial tactic that offers a major advantage, investigate it seriously.

If an entirely different strategy proves stronger than our current approach, pursue it.

If the apparent best strategy is surprisingly simple, use it.

**Be ambitious in strategy, rigorous in experimentation, ruthless about eliminating weak approaches, and disciplined in engineering.**

**Your mission is to make LARPBOT the strongest bot you can possibly build.**

**Start with the current champion. Protect it. Develop a challenger. Test it. Promote improvements. Study competitors. Reassess globally. Repeat.**

**And remember: NEVER submit to the official competition. I will handle that personally.**
