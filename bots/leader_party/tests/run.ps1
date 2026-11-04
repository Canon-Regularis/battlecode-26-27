$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path "$PSScriptRoot/../../..").Path
$output = Join-Path $repoRoot '.cambc/leader-party-decisions.exe'
& g++ -std=c++20 -O2 -Wall -Wextra -I "$PSScriptRoot/../src" "$PSScriptRoot/decisions.cpp" "$PSScriptRoot/../src/state_machine.cpp" -o $output
if ($LASTEXITCODE -ne 0) { throw 'C++ scenario compilation failed' }
& $output
if ($LASTEXITCODE -ne 0) { throw 'C++ scenarios failed' }
