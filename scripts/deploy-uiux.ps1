[CmdletBinding()]
param([switch]$WebOnly)
$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path -Parent $PSScriptRoot
Push-Location $taskRoot
try {
    $active = docker exec ar100-ai-knowledge-1 /app/.venv/bin/python -c "from backend.src.modules.operations.api import connection; c=connection(); a=c.execute('SELECT count(*) AS n FROM manufacturing_analysis_runs WHERE status IN (%s,%s)', ('running','resuming')).fetchone()['n']; k=c.execute('SELECT count(*) AS n FROM manufacturing_knowledge_builds WHERE status=%s', ('running',)).fetchone()['n']; print(a+k); c.close()"
    if ($LASTEXITCODE -ne 0 -or [int]$active -ne 0) { throw 'Active analysis/action/knowledge build or failed status check; deployment stopped.' }
    $ErrorActionPreference = 'Continue'
    foreach ($image in @('ar100-ai-knowledge','ar100-ai-web')) {
        docker image inspect "${image}:uiux-before-20260923" --format '{{.Id}}' *> $null
        if ($LASTEXITCODE -ne 0) {
            docker image tag "${image}:latest" "${image}:uiux-before-20260923"
            if ($LASTEXITCODE -ne 0) { throw 'Could not retain previous image.' }
        }
    }
    $services = @('knowledge','web')
    if ($WebOnly) { $services = @('web') }
    docker compose --progress quiet --env-file ai-layer/.env.local -f ai-layer/compose.yml -f ai-layer/compose.scada.yml --profile knowledge up -d --build --no-deps --wait --wait-timeout 240 @services
    if ($LASTEXITCODE -ne 0) { throw 'Deployment failed; volumes preserved.' }
    $env:PYTHONUTF8 = '1'
    python scripts/apply-fuxa-dashboard.py
    if ($LASTEXITCODE -ne 0) { throw 'FUXA HMI verification failed.' }
    (Invoke-WebRequest -UseBasicParsing http://127.0.0.1:28180/healthz).StatusCode
} finally { Pop-Location }
