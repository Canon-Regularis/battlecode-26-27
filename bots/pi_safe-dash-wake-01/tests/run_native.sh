#!/bin/sh
# Run from the repository root. All artifacts go to /tmp, never other bots.
set -eu
candidate=bots/pi_safe-dash-wake-01
python3 "$candidate/tests/make_fixtures.py"
g++ -std=c++20 -O2 -Wall -Wextra -Werror -I"$candidate/tests/host" -I"$candidate/src" "$candidate/tests/sdw01_native.cpp" "$candidate/src/navigation.cpp" -o /tmp/sdw01-native
/tmp/sdw01-native < "$candidate/tests/sdw01-fixtures.txt"
g++ -std=c++20 -O2 -Wall -Wextra -I"$candidate/src" "$candidate/tests/decisions.cpp" "$candidate/src/state_machine.cpp" -o /tmp/sdw01-decisions
/tmp/sdw01-decisions
# GCC 13 needs -fpermissive for three existing SDK team() declarations.
# Force cmath for inherited ceil uses relying on libc++ transitive includes.
g++ -std=c++20 -fpermissive -include cmath -Wall -Wextra -Isdk/cpp -fsyntax-only "$candidate"/src/*.cpp > /tmp/sdw01-syntax.log 2>&1
# Build actual SDK-facing objects for each changed production translation unit.
for unit in navigation bot economy objectives; do
    g++ -std=c++20 -O2 -fpermissive -include cmath -Wall -Wextra -Isdk/cpp -c "$candidate/src/$unit.cpp" -o "/tmp/sdw01-$unit.o" >> /tmp/sdw01-syntax.log 2>&1
done
