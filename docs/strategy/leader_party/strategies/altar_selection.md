# Banking and local carrier protection

Source: `economy.cpp`, `objectives.cpp` and `bot.cpp`. Banking is driven by positive bag, age, endgame and task-stall deadlines. Altar candidates use native path distance, visible enemy/lock penalties, an unknown-vision penalty and three-point switch hysteresis. Opposing locks are attacked rather than treated as permanent terrain. Three failed routes cool down that altar for three rounds and release the choice.

A carrier rechecks its actual position after moving and enters BANK_GEMS only when the SDK confirms submission. Channels remain stationary. An available altar lock is placed before submitting. Existing visible channeling carriers receive courtesy; visible waiters prefer larger bag then stable ID. After three stalled rounds a waiter switches altar if another exists. This is a local policy, not an assertion of global engine exclusivity or a tested simultaneous-channel guarantee.

An idle empty-bag body can guard one personally visible channeling carrier within three tiles, outside the altar approach. Protection remembers exact carrier/altar, lasts through remaining channel time plus three rounds, and ends on death, observed abandonment or two failed reacquisition rounds. Remote BANK requests do not recruit responders in the release.

Telemetry is observational. Engine gemSubmission events in benchmark summaries establish completed scoring cycles; unrelated team score changes and a vanished camp do not prove a particular body banked or captured.
