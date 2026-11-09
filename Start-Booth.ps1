param(
    [switch]$SkipBuild,
    [switch]$VerifyOnly
)
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
$dockerCandidates = @(
    (Join-Path $env:LOCALAPPDATA 'Programs/DockerDesktop/resources/bin/docker.exe'),
    'C:/Program Files/Docker/Docker/resources/bin/docker.exe'
)
$dockerPath = $dockerCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
if (-not $dockerPath) { throw 'Docker CLI was not found.' }
$env:PATH = (Split-Path $dockerPath) + ';' + $env:PATH
$config = @{}
Get-Content -LiteralPath (Join-Path $PSScriptRoot '.env') -Encoding UTF8 | ForEach-Object {
    if ($_ -match '^([^#=]+)=(.*)$') { $config[$Matches[1]] = $Matches[2] }
}
$webPort = [int]$config['PORT_AI_WEB']
if (-not $webPort) { $webPort = 38180 }
$webUrl = 'http://localhost:' + $webPort

function Get-DataStatus {
    try {
        $response = Invoke-WebRequest -UseBasicParsing -Uri ($webUrl + '/api/operations/pipeline') -TimeoutSec 15
        $state = [System.Text.Encoding]::UTF8.GetString($response.RawContentStream.ToArray()) | ConvertFrom-Json
        return $state
    } catch { return $null }
}
function Wait-DataStatus([int]$Seconds) {
    $until = (Get-Date).AddSeconds($Seconds)
    do {
        $state = Get-DataStatus
        if ($state -and $state.items.Count -eq 3 -and @($state.items | Where-Object { $_.status -ne 'available' }).Count -eq 0) {
            return $state
        }
        Start-Sleep -Seconds 3
    } while ((Get-Date) -lt $until)
    return $null
}
function Test-DockerEngine {
    try {
        & $dockerPath info --format '{{.ServerVersion}}' 2>$null | Out-Null
        return ($LASTEXITCODE -eq 0)
    } catch { return $false }
}
function Wait-StackReady([int]$Seconds) {
    $expected = @(& $dockerPath compose config --services)
    if ($LASTEXITCODE -ne 0 -or $expected.Count -eq 0) { throw 'Cannot list CECO services.' }
    $helpers = @('kafka-init','flink-job-submitter','fuxa-provisioner','graph-seed','model-trainer')
    $until = (Get-Date).AddSeconds($Seconds)
    do {
        $rows = @(& $dockerPath compose ps -a --format json | ForEach-Object { $_ | ConvertFrom-Json })
        if ($LASTEXITCODE -ne 0) { throw 'Cannot read CECO container state.' }
        $pending = @($expected | Where-Object {
            $serviceName = $_
            $row = @($rows | Where-Object { $_.Service -eq $serviceName })
            if ($row.Count -ne 1) { $true }
            elseif ($helpers -contains $serviceName) { $row[0].State -ne 'exited' -or $row[0].ExitCode -ne 0 }
            else { $row[0].State -ne 'running' -or $row[0].Health -ne 'healthy' }
        })
        if ($pending.Count -eq 0) { return $true }
        Start-Sleep -Seconds 3
    } while ((Get-Date) -lt $until)
    Write-Host ('Services not ready: ' + ($pending -join ', '))
    return $false
}

if (-not $VerifyOnly) {
    if (-not (Test-DockerEngine)) {
        $desktop = Join-Path (Split-Path (Split-Path (Split-Path $dockerPath))) 'Docker Desktop.exe'
        if (-not (Test-Path -LiteralPath $desktop)) { throw 'Docker Desktop launcher was not found.' }
        Start-Process -FilePath $desktop -WindowStyle Hidden
        $engineUntil = (Get-Date).AddSeconds(120)
        do {
            Start-Sleep -Seconds 3
            if (Test-DockerEngine) { break }
        } while ((Get-Date) -lt $engineUntil)
        if (-not (Test-DockerEngine)) { throw 'Docker engine did not start.' }
    }
    # Compose --wait treats an already completed standalone helper as a failed
    # service. Check long-running health and successful helper exits explicitly.
    $upArgs = @('compose','up','-d')
    if (-not $SkipBuild) { $upArgs += '--build' }
    & $dockerPath @upArgs
    if ($LASTEXITCODE -ne 0) { throw 'CECO stack could not start.' }
}
if (-not (Wait-StackReady 300)) { throw 'CECO services or startup helpers did not become ready.' }

$status = Wait-DataStatus 60
if (-not $status -and -not $VerifyOnly) {
    # Observed on 2026-10-13: OT data did not reach DMZ/Kafka even though all
    # containers were healthy. An OT hub restart restored data; cause unconfirmed.
    # This is an explicit recovery step; container health alone is never success.
    Write-Host 'Live sensor data is missing. Restarting the OT bridge once and checking the full data path.'
    & $dockerPath compose restart ot-hub
    if ($LASTEXITCODE -ne 0) { throw 'OT bridge restart failed.' }
    $status = Wait-DataStatus 60
}
if (-not $status) { throw 'Live process, sensor history, or the four Flink jobs could not be verified.' }
$portalResponse = Invoke-WebRequest -UseBasicParsing -Uri ($webUrl + '/simulation/state') -Headers @{ 'X-CECO-Portal' = 'interactive' } -TimeoutSec 20
$portalState = [System.Text.Encoding]::UTF8.GetString($portalResponse.RawContentStream.ToArray()) | ConvertFrom-Json
if (-not $portalState.commands -or $null -eq $portalState.seq) { throw 'Portal equipment controls are not connected.' }
Write-Host ('Verified: live process, sensor history, four Flink jobs. Dashboard: ' + $webUrl)
Write-Host 'Portal equipment controls connected. Use Operations -> Start fault -> Automatic analysis -> Review and approve.'
Write-Host 'This readiness check does not replace a maintenance scenario run.'
$status.items | Select-Object key,status,detail | Format-Table -AutoSize
