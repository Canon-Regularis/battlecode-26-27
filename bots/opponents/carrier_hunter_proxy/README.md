# Carrier Hunter Proxy

Local stress-test archetype, not a reproduction of a private team bot. It uses
the same Tavi / Varg / Ren draft and starter-derived economy policy as G2, but
chases a nearby visible enemy gem carrier when the hunter is healthy and has no
gems to bank. This isolates the pressure hypothesis from composition changes.

The proxy only reacts to visible enemy state. It does not infer hidden bags or
coordinate a designated team pack. It is an intentionally strong pressure
case, not a complete competitive strategy.

Build from the repository root with `cambc build bots/opponents/carrier_hunter_proxy`.
Keep its match statistics under this directory's `results/` and replays under
`replays/carrier_hunter_proxy/`.
