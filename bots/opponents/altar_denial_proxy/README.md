# Altar Denial Proxy

Local stress-test archetype, not a reproduction of a private team bot. It uses
the same Tavi / Varg / Ren draft and starter-derived economy policy as G2. At
spawn, it buys an altar lock before spending the remaining gold on strength;
when an enemy is visibly channeling a tribute and the champion is within lock
range, it places the lock to cancel that channel.

The proxy targets reactive interruption only. It does not pre-lock altars or
clear opposing locks, and its value must be established by local matches.

Build from the repository root with `cambc build bots/opponents/altar_denial_proxy`.
Keep its match statistics under this directory's `results/` and replays under
`replays/altar_denial_proxy/`.
