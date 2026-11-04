# Optional wards

Source: `combat.cpp::optional_ward`. Enabled in the release, after scoring/safety actions and status publication. Skip while channeling, below 55% HP, under visible champion threat, on cooldown or below 45,000 fuel. Placement must be currently visible, in the legal range, free and outside known ward occupancy.

The geometric score favors distant forward tiles toward the current camp or enemy spawn. An existing first ward within six tiles suppresses replacement. This is a bounded directional heuristic; the former terrain-aware route-cache and remote-report proposal is not implemented. Wards never admit an extra navigation field.
