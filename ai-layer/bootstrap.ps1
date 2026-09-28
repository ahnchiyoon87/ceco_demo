$ErrorActionPreference = 'Stop'
$envFile = Join-Path $PSScriptRoot '.env.local'
if (-not (Test-Path -LiteralPath $envFile)) {
    $bytes = New-Object byte[] 32
    $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try { $rng.GetBytes($bytes) } finally { $rng.Dispose() }
    $password = [Convert]::ToBase64String($bytes)
    [IO.File]::WriteAllText($envFile, "NEO4J_PASSWORD=$password`n", (New-Object Text.UTF8Encoding($false)))
}
if (-not (Select-String -LiteralPath $envFile -Pattern '^POSTGRES_PASSWORD=' -Quiet)) {
    $dbBytes = New-Object byte[] 32
    $dbRng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try { $dbRng.GetBytes($dbBytes) } finally { $dbRng.Dispose() }
    [IO.File]::AppendAllText($envFile, "POSTGRES_PASSWORD=$([Convert]::ToBase64String($dbBytes))`n", (New-Object Text.UTF8Encoding($false)))
}
& docker compose --env-file $envFile -f (Join-Path $PSScriptRoot 'compose.yml') up -d --wait --wait-timeout 240
if ($LASTEXITCODE -ne 0) { throw 'AI infrastructure did not become healthy. Inspect docker compose logs.' }
Write-Host 'Neo4j ready: http://localhost:27474, bolt://localhost:27687. Credentials stay in .env.local.'
