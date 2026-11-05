param([switch]$Once)
$ErrorActionPreference = 'Stop'
$bridgeRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$bridgePython = Join-Path $bridgeRoot '.venv\Scripts\python.exe'
$bridgeScript = Join-Path $PSScriptRoot 'agent_bridge.py'
$bridgeAdapter = Join-Path $PSScriptRoot 'agent_pc_test.py'
$bridgeState = Join-Path $bridgeRoot '.cambc\agent-bridge'
$bridgeRemote = & git -C $bridgeRoot remote get-url origin
if ($LASTEXITCODE -ne 0) { throw 'Cannot resolve Git remote.' }
New-Item -ItemType Directory -Force -Path $bridgeState | Out-Null
$bridgeCommand = @($bridgePython, $bridgeAdapter, '--checkout', '{checkout}', '--bot', '{bot}', '--output', '{output}')
$bridgeCommandPath = Join-Path $bridgeState 'test-command.json'
$bridgeCommand | ConvertTo-Json | Set-Content -LiteralPath $bridgeCommandPath -Encoding UTF8
$bridgeArgs = @($bridgeScript, '--remote', $bridgeRemote.Trim(), '--state', $bridgeState,
    'work', '--role', 'tester', '--name', 'windows-pc', '--test-command-file', $bridgeCommandPath)
if ($Once) { $bridgeArgs += '--once' }
& $bridgePython @bridgeArgs
exit $LASTEXITCODE
