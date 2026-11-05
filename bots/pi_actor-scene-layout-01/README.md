# actor-scene-layout-01

Repairs the recovery adapter's public bitboard-to-scalar conversion on
`pi_actor-turn-core-01` at `21f464db747069b7dc360710e5ddfc1bf2a49bc7`.
Planner, ordinary navigation and economic behavior remain inherited.

Run local checks from the repository root:

```sh
python3 bots/pi_actor-scene-layout-01/tests/run_focused.py
```

See [IMPLEMENTATION.md](IMPLEMENTATION.md) for the SDK contract, changes,
validation and frozen PC follow-through. No strength claim is made.
