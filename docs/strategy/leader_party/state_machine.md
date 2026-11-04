# Implemented state machine

Source: `state_machine.cpp` in `bots/leader_party`, `bots/leader_party_subhan` and the preferred `bots/leader_party_tuned`, with execution and task bookkeeping in `bot.cpp`. Their transition order is shared; both Subhan-based variants additionally advance planned camp routes when tasks finish or are abandoned. Thresholds below describe the tuned profile; see [configuration](config.md) for baseline differences. Earlier proposals are preserved under `history/`.

The pure decision function applies the first matching condition:

| Order | Condition | State/action |
| --- | --- | --- |
| 1 | Dead | DEATH; clear lost-bag/task intent on first observed death, shop legally |
| 2 | Engine reports tribute or teleport | BANK_GEMS; preserve channel |
| 3 | At spawn within estimated incoming basic-damage threat | DEFEND_SPAWN |
| 4 | Champion disadvantage, <=35% HP under threat, or estimated lethal basic damage | RUN_AWAY |
| 5 | Recall active | RECALL, or RUN_AWAY if enemies/camp attacks prevent safe recall |
| 6 | At spawn below maximum HP | HEALING |
| 7 | Recovery flag, or safe off-spawn equipment return with no bag and >=300 gold | RECALL; escape first if threatened |
| 8 | Positive bag needs banking | PREPARE_GEM_BANKING |
| 9 | Exact visible bank-carrier protection remains live | PROTECT_POINT |
| 10 | Valid local camp task | CAPTURE_POINT, or PROTECT_POINT if another ally occupies cleared reward tiles |
| 11 | Rally fact | RALLY; unused in release |
| 12 | Experimental leader/follower guidance | LEAD_TEAM/FOLLOW_LEADER, both retain local planning |
| 13 | Otherwise | EXPLORE with autonomous camp selection |

Recovery uses 35%/55% HP hysteresis in both the tuned profile and untuned bots. Danger uses visible champion counts within six tiles, nearby usable allies, awake camp attacks and raw incoming basic damage. These estimates omit hidden spells and mitigations.

Every uncommitted body selects its own camp; leadership is not required. A task ends after 90 total rounds or eight rounds without reduced route distance, observed objective damage or capture-countdown progress. Abandoned objectives receive a ten-round cooldown. The initial 30-round limit rejected the available gem camps on ambush; the measured change is documented in the results. Camp guarding ends after 12 rounds. A vacant reward region is approached through free tiles; current occupancy is rechecked after movement. The implementation does not add a special Capture Emblem co-occupant policy.

Banking starts at bag 20, age 40, a winning bag, near match end, or a stalled positive-bag task. Pending bags survive escape. Death clears them. Engine channel truth takes priority over discretionary actions; this implementation preserves tribute rather than trying to cancel it on a predicted lethal hit.

Visible carrier protection ends on observed channel abandonment, death, two failed visibility reacquisitions or the recorded remaining channel duration plus three rounds. An unrelated team-score increase is not authoritative completion evidence; benchmark cycle counts come from engine gemSubmission events. Quiet protection does not chase unrelated enemies.

RALLY is retained in the model but remote inspection/ATTACK initiation are disabled. There is one dispatch per turn; target selection can establish a task and execute it in that dispatch. Some execution bookkeeping updates state labels directly; there is no separate generic effects interpreter.
