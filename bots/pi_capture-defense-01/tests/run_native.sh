#!/usr/bin/env bash
set -euo pipefail
here=$(cd -- "$(dirname -- "$0")" && pwd)
root=$(cd -- "$here/../../.." && pwd)
build=$(mktemp -d /tmp/cd01-tests.XXXXXX)
trap 'rm -rf "$build"' EXIT
cxx=${CXX:-g++}
"$cxx" -std=c++20 -O2 -Wall -Wextra -I "$here/../src" "$here/decisions.cpp" "$here/../src/state_machine.cpp" -o "$build/decisions"
"$build/decisions"
# GCC's SDK name-lookup warnings require -fpermissive; never edit the SDK.
flags=(-std=c++20 -O0 -fpermissive -fno-access-control -ffunction-sections -fdata-sections -I "$root/sdk/cpp" -I "$here/../src")
"$cxx" "${flags[@]}" "$here/capture_defense.cpp" "$here/../src/bot.cpp" "$here/../src/combat.cpp" "$here/../src/state_machine.cpp" -Wl,--gc-sections -Wl,--wrap=_ZN2lp5fightERNS_5WorldEib -Wl,--wrap=_ZN2lp13optional_wardERKNS_5WorldEi -o "$build/capture_defense"
"$build/capture_defense"
# Existing sources use std::ceil without their own <cmath> on this host.
"$cxx" -std=c++20 -fpermissive -include cmath -I "$root/sdk/cpp" -fsyntax-only "$here/../src/"*.cpp
