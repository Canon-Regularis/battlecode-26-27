# actor-scene-epoch-01

Validates each coordinate conversion against its own entry epoch, allowing fresh
same-turn observations after actions. Parent: `914cf67173be7c5231ccaa2878e4292d236b71e4`,
`pi_actor-scene-layout-01`. All other production behavior is preserved.

Run from the repository root:

```sh
python3 bots/pi_actor-scene-epoch-01/tests/run_focused.py
```

See [IMPLEMENTATION.md](IMPLEMENTATION.md) for actual checks and PC follow-through.
