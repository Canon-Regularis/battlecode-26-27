#!/usr/bin/env bash
set -euo pipefail
candidate_dir=$(cd "$(dirname "$0")/.." && pwd)
repo_dir=$(cd "$candidate_dir/../.." && pwd)
test_dir=$(mktemp -d /tmp/pts01-tests.XXXXXX)
trap 'rm -rf "$test_dir"' EXIT
compiler=${CXX:-g++}
"$compiler" -std=c++20 -O2 -Wall -Wextra -I "$candidate_dir/tests/fake_sdk" -I "$candidate_dir/src" \
    "$candidate_dir/tests/passive_threats.cpp" "$candidate_dir/src/observations.cpp" \
    "$candidate_dir/src/navigation.cpp" -o "$test_dir/passive_threats"
"$test_dir/passive_threats"
"$compiler" -std=c++20 -O2 -Wall -Wextra -I "$candidate_dir/src" \
    "$candidate_dir/tests/decisions.cpp" "$candidate_dir/src/state_machine.cpp" -o "$test_dir/decisions"
"$test_dir/decisions"
# Native GCC compatibility only: existing SDK team() declarations require
# -fpermissive, and baseline objectives/route_plan rely on transitive <cmath>.
# This checks real SDK syntax; it does not replace a WASM release build.
if ! "$compiler" -std=c++20 -fpermissive -include cmath -fsyntax-only -I "$repo_dir/sdk/cpp" \
    "$candidate_dir"/src/*.cpp > "$test_dir/syntax.log" 2>&1; then
    cat "$test_dir/syntax.log"
    exit 1
fi
echo 'PASS: all production translation units pass real-SDK native syntax checks (GCC compatibility flags; SDK warnings suppressed)'
