[CmdletBinding()]
param(
    [string]$BaseUrl = 'http://127.0.0.1:7337',

    [string]$ChromaLinkRoot = 'C:\Users\mrkoo\OneDrive\Documents\RIFT\Interface\AddOns\ChromaLink',

    [string]$BridgeProject = '',

    [int]$WaitSeconds = 10,

    [int]$PollIntervalMilliseconds = 500,

    [int]$RequestTimeoutSeconds = 2,

    [switch]$StartBridge,

    [switch]$KeepRunning,

    [switch]$SkipContractCheck,

    [switch]$Json
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$schemaVersion = 1
$contractScript = Join-Path $PSScriptRoot 'test-chromalink-world-state-contract.ps1'

if ($WaitSeconds -lt 0) {
    throw 'WaitSeconds must be zero or greater.'
}

if ($PollIntervalMilliseconds -lt 50) {
    throw 'PollIntervalMilliseconds must be at least 50.'
}

if ($RequestTimeoutSeconds -lt 1) {
    throw 'RequestTimeoutSeconds must be at least 1.'
}

function ConvertFrom-JsonOrNull {
    param([string]$Text)

    if ([string]::IsNullOrWhiteSpace($Text)) {
        return $null
    }

    try {
        return $Text | ConvertFrom-Json -Depth 64
    }
    catch {
        return $null
    }
}

function Convert-ResponseContentToString {
    param([object]$Content)

    if ($Content -is [byte[]]) {
        return [System.Text.Encoding]::UTF8.GetString($Content)
    }

    return [string]$Content
}

function Invoke-HttpJson {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Url
    )

    $response = Invoke-WebRequest -Method Get -Uri $Url -UseBasicParsing -SkipHttpErrorCheck -TimeoutSec $RequestTimeoutSeconds
    $content = Convert-ResponseContentToString -Content $response.Content
    return [pscustomobject]@{
        Url = $Url
        StatusCode = [int]$response.StatusCode
        Content = $content
        Json = ConvertFrom-JsonOrNull -Text $content
    }
}

function Test-BridgeApi {
    param([Parameter(Mandatory = $true)][string]$Url)

    try {
        $response = Invoke-HttpJson -Url ('{0}/api/v1' -f $Url.TrimEnd('/'))
        return [pscustomobject]@{
            Reachable = $response.StatusCode -ge 200 -and $response.StatusCode -lt 300
            Response = $response
            Error = $null
        }
    }
    catch {
        return [pscustomobject]@{
            Reachable = $false
            Response = $null
            Error = $_.Exception.Message
        }
    }
}

function Invoke-NativeCommand {
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$Arguments
    )

    $previousErrorActionPreference = $ErrorActionPreference
    $nativePreferenceVariable = Get-Variable -Name PSNativeCommandUseErrorActionPreference -Scope 1 -ErrorAction SilentlyContinue
    $previousNativeCommandPreference = if ($null -ne $nativePreferenceVariable) { $nativePreferenceVariable.Value } else { $null }
    try {
        $ErrorActionPreference = 'Continue'
        if ($null -ne $nativePreferenceVariable) {
            Set-Variable -Name PSNativeCommandUseErrorActionPreference -Scope 1 -Value $false
        }

        $output = & $Arguments[0] @($Arguments | Select-Object -Skip 1) 2>&1
        return [pscustomobject]@{
            ExitCode = $LASTEXITCODE
            Output = ($output -join [Environment]::NewLine)
        }
    }
    finally {
        $ErrorActionPreference = $previousErrorActionPreference
        if ($null -ne $nativePreferenceVariable) {
            Set-Variable -Name PSNativeCommandUseErrorActionPreference -Scope 1 -Value $previousNativeCommandPreference
        }
    }
}

function Resolve-BridgeProject {
    if (-not [string]::IsNullOrWhiteSpace($BridgeProject)) {
        return [System.IO.Path]::GetFullPath($BridgeProject)
    }

    return [System.IO.Path]::GetFullPath((Join-Path $ChromaLinkRoot 'DesktopDotNet\ChromaLink.HttpBridge\ChromaLink.HttpBridge.csproj'))
}

$base = $BaseUrl.TrimEnd('/')
$startedProcess = $null
$startedByScript = $false
$bridgeStopped = $false
$stdoutLog = $null
$stderrLog = $null
$failures = [System.Collections.Generic.List[string]]::new()
$apiProbe = $null
$health = $null
$ready = $null
$contract = $null

try {
    $apiProbe = Test-BridgeApi -Url $base
    if (-not $apiProbe.Reachable -and $StartBridge) {
        $resolvedProject = Resolve-BridgeProject
        if (-not (Test-Path -LiteralPath $resolvedProject)) {
            throw "ChromaLink HTTP bridge project not found: $resolvedProject"
        }

        $resolvedRoot = [System.IO.Path]::GetFullPath($ChromaLinkRoot)
        if (-not (Test-Path -LiteralPath $resolvedRoot)) {
            throw "ChromaLink root not found: $resolvedRoot"
        }

        $stdoutLog = Join-Path $env:TEMP ('riftreader-chromalink-httpbridge-out-{0}.log' -f ([Guid]::NewGuid().ToString('N')))
        $stderrLog = Join-Path $env:TEMP ('riftreader-chromalink-httpbridge-err-{0}.log' -f ([Guid]::NewGuid().ToString('N')))
        $startedProcess = Start-Process -FilePath 'dotnet' `
            -ArgumentList @('run', '--project', $resolvedProject, '--no-launch-profile') `
            -WorkingDirectory $resolvedRoot `
            -RedirectStandardOutput $stdoutLog `
            -RedirectStandardError $stderrLog `
            -PassThru `
            -WindowStyle Hidden
        $startedByScript = $true
    }

    $deadlineUtc = [DateTimeOffset]::UtcNow.AddSeconds($WaitSeconds)
    do {
        $apiProbe = Test-BridgeApi -Url $base
        if ($apiProbe.Reachable) {
            break
        }

        if ([DateTimeOffset]::UtcNow -ge $deadlineUtc) {
            break
        }

        Start-Sleep -Milliseconds $PollIntervalMilliseconds
    } while ($true)

    if (-not $apiProbe.Reachable) {
        $failures.Add("ChromaLink HTTP bridge is not reachable at $base/api/v1. Last error: $($apiProbe.Error)") | Out-Null
    }

    if ($apiProbe.Reachable) {
        try {
            $health = Invoke-HttpJson -Url ('{0}/health' -f $base)
        }
        catch {
            $failures.Add("Health endpoint query failed: $($_.Exception.Message)") | Out-Null
        }

        try {
            $ready = Invoke-HttpJson -Url ('{0}/ready' -f $base)
        }
        catch {
            $failures.Add("Ready endpoint query failed: $($_.Exception.Message)") | Out-Null
        }

        if (-not $SkipContractCheck) {
            if (-not (Test-Path -LiteralPath $contractScript)) {
                $failures.Add("ChromaLink contract script not found: $contractScript") | Out-Null
            }
            else {
                $contractRun = Invoke-NativeCommand -Arguments @(
                    'pwsh',
                    '-NoLogo',
                    '-NoProfile',
                    '-ExecutionPolicy',
                    'Bypass',
                    '-File',
                    $contractScript,
                    '-BaseUrl',
                    $base,
                    '-SkipWorldState',
                    '-Json'
                )
                $contract = ConvertFrom-JsonOrNull -Text $contractRun.Output
                if ($contractRun.ExitCode -ne 0 -or $null -eq $contract -or [string]$contract.status -ne 'pass') {
                    $failures.Add("ChromaLink contract preflight failed; exitCode=$($contractRun.ExitCode).") | Out-Null
                    if ($null -eq $contract) {
                        $failures.Add('ChromaLink contract preflight output could not be parsed.') | Out-Null
                    }
                    else {
                        foreach ($failure in @($contract.failures)) {
                            if (-not [string]::IsNullOrWhiteSpace([string]$failure)) {
                                $failures.Add([string]$failure) | Out-Null
                            }
                        }
                    }
                }
            }
        }
    }
}
catch {
    $failures.Add($_.Exception.Message) | Out-Null
}
finally {
    if ($startedProcess -and -not $KeepRunning -and -not $startedProcess.HasExited) {
        Stop-Process -Id $startedProcess.Id -Force
        $bridgeStopped = $true
    }
}

$status = if ($failures.Count -eq 0) { 'pass' } elseif ($apiProbe -and -not $apiProbe.Reachable) { 'unavailable' } else { 'fail' }
$result = [ordered]@{
    schemaVersion = $schemaVersion
    mode = 'chromalink-http-bridge-readiness'
    status = $status
    generatedAtUtc = [DateTimeOffset]::UtcNow.ToString('O', [System.Globalization.CultureInfo]::InvariantCulture)
    baseUrl = $base
    startBridgeRequested = [bool]$StartBridge
    startedByScript = $startedByScript
    keepRunning = [bool]$KeepRunning
    bridgeProcessId = if ($startedProcess) { $startedProcess.Id } else { $null }
    bridgeStopped = $bridgeStopped
    stdoutLog = $stdoutLog
    stderrLog = $stderrLog
    apiReachable = [bool]($apiProbe -and $apiProbe.Reachable)
    apiStatusCode = if ($apiProbe -and $apiProbe.Response) { $apiProbe.Response.StatusCode } else { $null }
    apiError = if ($apiProbe) { $apiProbe.Error } else { $null }
    healthStatusCode = if ($health) { $health.StatusCode } else { $null }
    health = if ($health) { $health.Json } else { $null }
    readyStatusCode = if ($ready) { $ready.StatusCode } else { $null }
    ready = if ($ready) { $ready.Json } else { $null }
    contract = $contract
    failures = $failures.ToArray()
}

if ($Json) {
    $result | ConvertTo-Json -Depth 32
}
else {
    $color = if ($status -eq 'pass') { 'Green' } else { 'Red' }
    Write-Host ("ChromaLink HTTP bridge readiness: {0}" -f $status) -ForegroundColor $color
    Write-Host ("Base URL: {0}" -f $base)
    if ($startedProcess) {
        Write-Host ("Started process: {0}" -f $startedProcess.Id)
    }
    foreach ($failure in @($result.failures)) {
        Write-Host ("- {0}" -f $failure) -ForegroundColor Red
    }
}

if ($status -ne 'pass') {
    exit 1
}
