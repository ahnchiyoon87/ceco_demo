[CmdletBinding()]
param([switch]$Build)
$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path -Parent $PSScriptRoot
$taskEnv = Join-Path $PSScriptRoot '.env.local'
if (-not (Test-Path -LiteralPath $taskEnv)) {
    throw 'Run ai-layer/bootstrap.ps1 and configure ai-layer/.env.local first.'
}
Push-Location $taskRoot
try {
    & docker network inspect iiot --format '{{.Name}}' *> $null
    if ($LASTEXITCODE -ne 0) { throw 'Start the existing SCADA stack first; the iiot network is missing.' }
    $taskArgs = @('compose', '--env-file', $taskEnv, '-f', (Join-Path $PSScriptRoot 'compose.yml'),
        '-f', (Join-Path $PSScriptRoot 'compose.scada.yml'), '--profile', 'knowledge', 'up', '-d', '--wait', '--wait-timeout', '240')
    if ($Build) { $taskArgs += '--build' }
    & docker @taskArgs
    if ($LASTEXITCODE -ne 0) { throw 'AI services did not become ready. Inspect compose logs; data volumes were preserved.' }
    Write-Host 'Service: http://127.0.0.1:28180/ (model execution readiness is shown separately in the app)'
} finally { Pop-Location }
