[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path -Parent $PSScriptRoot
$evidence = Join-Path $taskRoot 'docs/ai-work/uiux-20260923'
Push-Location $taskRoot
try {
    # Tests run from a separate source tree. conftest creates a fresh temporary
    # PostgreSQL database and never uses application records as test fixtures.
    docker exec ar100-ai-knowledge-1 mkdir -p /tmp/scada-uiux-qa/backend
    if ($LASTEXITCODE -ne 0) { throw 'Could not prepare test source directory.' }
    docker cp ai-layer/knowledge/backend/. ar100-ai-knowledge-1:/tmp/scada-uiux-qa/backend/
    if ($LASTEXITCODE -ne 0) { throw 'Could not copy isolated test source.' }
    # Native stderr contains ordinary progress messages in Windows PowerShell.
    $ErrorActionPreference = 'Continue'
    docker exec ar100-ai-knowledge-1 uv pip install --target /tmp/scada-uiux-qa/test-deps pytest pytest-asyncio
    if ($LASTEXITCODE -ne 0) { throw 'Could not prepare temporary test dependencies.' }
    docker exec -e PYTHONPATH=/tmp/scada-uiux-qa:/tmp/scada-uiux-qa/test-deps ar100-ai-knowledge-1 /app/.venv/bin/python -m pytest /tmp/scada-uiux-qa/backend/tests -q --junitxml=/tmp/scada-uiux-tests.xml 2>&1 | Tee-Object (Join-Path $evidence 'backend-tests.txt')
    $testExit = $LASTEXITCODE
    docker cp ar100-ai-knowledge-1:/tmp/scada-uiux-tests.xml (Join-Path $evidence 'backend-tests.xml')
    if ($testExit -ne 0) { throw "Backend tests failed: $testExit" }
    Push-Location ai-web
    try {
        node --test tests/*.test.js 2>&1 | Tee-Object (Join-Path $evidence 'frontend-tests.txt')
        if ($LASTEXITCODE -ne 0) { throw 'Frontend tests failed.' }
        npm.cmd run build 2>&1 | Tee-Object (Join-Path $evidence 'frontend-build.txt')
        if ($LASTEXITCODE -ne 0) { throw 'Frontend build failed.' }
    } finally { Pop-Location }
    docker system df | Set-Content -Encoding UTF8 (Join-Path $evidence 'docker-storage.txt')
    docker stats --no-stream --format '{{.Name}}|{{.MemUsage}}|{{.CPUPerc}}' | Set-Content -Encoding UTF8 (Join-Path $evidence 'docker-runtime.txt')
    docker exec ar100-ai-knowledge-1 du -sh /app/.venv /usr/lib/libreoffice 2>&1 | Set-Content -Encoding UTF8 (Join-Path $evidence 'backend-image-components-after.txt')
    docker exec ar100-ai-knowledge-1 /app/.venv/bin/python -c "from pathlib import Path; print('uv_cache_exists=' + str(Path('/root/.cache/uv').exists()))" | Add-Content -Encoding UTF8 (Join-Path $evidence 'backend-image-components-after.txt')
} finally { Pop-Location }
