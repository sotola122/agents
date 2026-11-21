# Install the agents CLI on Windows and distribute the enabled assets.
#
#   .\install.ps1                (inside a clone)
#   irm https://raw.githubusercontent.com/sotola122/agents/main/install.ps1 | iex
#
# Options:
#   -NoApply   install the command only; skip distribution
#
# Environment:
#   AGENTS_DIR   clone target when run outside a clone (default: ~\agents)
#   AGENTS_REPO  clone source (default: https://github.com/sotola122/agents.git)
#
# Messages are ASCII so Windows PowerShell 5.1 reads this file correctly without a BOM.
[CmdletBinding()]
param([switch]$NoApply)

$ErrorActionPreference = 'Stop'

if ($PSVersionTable.PSVersion.Major -ge 6 -and -not $IsWindows) {
    throw 'install.ps1 is for Windows. Use install.sh on macOS/Linux.'
}
if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    throw 'git was not found.'
}

$pythonOk = $false
foreach ($candidate in @(@('py', '-3'), @('python'))) {
    if (Get-Command $candidate[0] -ErrorAction SilentlyContinue) {
        $extra = @($candidate | Select-Object -Skip 1)
        & $candidate[0] @extra -c 'import sys; sys.exit(sys.version_info < (3, 11))' 2>$null
        if ($LASTEXITCODE -eq 0) { $pythonOk = $true; break }
    }
}
if (-not $pythonOk) {
    throw 'Python 3.11 or later was not found (tried: py -3, python).'
}

# Run from a clone: use it. Piped into iex ($PSScriptRoot is empty): clone first.
$root = $PSScriptRoot
if (-not $root -or -not (Test-Path (Join-Path $root 'sources.toml'))) {
    $root = if ($env:AGENTS_DIR) { $env:AGENTS_DIR } else { Join-Path $HOME 'agents' }
    if (Test-Path (Join-Path $root 'sources.toml')) {
        Write-Host "Using existing clone: $root"
    } elseif (Test-Path $root) {
        throw "$root is not an agents clone. Set AGENTS_DIR to another location."
    } else {
        $repo = if ($env:AGENTS_REPO) { $env:AGENTS_REPO } else { 'https://github.com/sotola122/agents.git' }
        git clone --quiet $repo $root
        if ($LASTEXITCODE -ne 0) { throw "git clone failed: $repo" }
        Write-Host "Cloned: $root"
    }
}
$root = (Resolve-Path $root).Path
$binDir = Join-Path $root 'bin'

$userPath = [Environment]::GetEnvironmentVariable('Path', 'User')
$parts = @(($userPath -split ';') | Where-Object { $_ })
if ($parts -notcontains $binDir) {
    [Environment]::SetEnvironmentVariable('Path', (($parts + $binDir) -join ';'), 'User')
    Write-Host "Added to user PATH: $binDir (new terminals can run 'agents')"
}
if ((($env:Path -split ';') -notcontains $binDir)) {
    $env:Path = "$env:Path;$binDir"
}

$agents = Join-Path $binDir 'agents.cmd'
if ($NoApply) {
    Write-Host "Run 'agents' to distribute assets."
} else {
    & $agents
    if ($LASTEXITCODE -ne 0) { throw "agents failed (exit $LASTEXITCODE)" }
    & $agents ls
}
