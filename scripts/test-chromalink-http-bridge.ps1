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

function Get-JsonPropertyValue {
    param(
        [object]$InputObject,

        [Parameter(Mandatory = $true)]
        [string]$Name
    )

    if ($null -eq $InputObject) {
        return $null
    }

    if ($InputObject -is [System.Collections.IDictionary]) {
        if ($InputObject.Contains($Name)) {
            return $InputObject[$Name]
        }

        return $null
    }

    $property = $InputObject.PSObject.Properties[$Name]
    if ($null -eq $property) {
        return $null
    }

    return $property.Value
}

function Add-ReadinessEndpointFailures {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Name,

        [object]$Response,

        [System.Collections.Generic.List[string]]$Failures
    )

    if ($null -eq $Response) {
        $Failures.Add("$Name endpoint did not return a response.") | Out-Null
        return
    }

    if ([int]$Response.StatusCode -lt 200 -or [int]$Response.StatusCode -gt 299) {
        $Failures.Add("$Name endpoint returned non-success status=$($Response.StatusCode).") | Out-Null
    }

    if ($null -eq $Response.Json) {
        $Failures.Add("$Name endpoint response could not be parsed as JSON.") | Out-Null
        return
    }

    foreach ($field in @('ok', 'ready', 'healthy', 'fresh')) {
        $value = Get-JsonPropertyValue -InputObject $Response.Json -Name $field
        if ($value -ne $true) {
            $Failures.Add("$Name endpoint $field is not true; value=$value.") | Out-Null
        }
    }

    $stale = Get-JsonPropertyValue -InputObject $Response.Json -Name 'stale'
    if ($stale -eq $true) {
        $Failures.Add("$Name endpoint stale is true.") | Out-Null
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

function Resolve-BridgeLaunchTarget {
    param([Parameter(Mandatory = $true)][string]$ProjectPath)

    $projectDocument = [xml](Get-Content -LiteralPath $ProjectPath -Raw)
    $targetFramework = @(
        $projectDocument.Project.PropertyGroup |
            ForEach-Object { $_.TargetFramework } |
            Where-Object { -not [string]::IsNullOrWhiteSpace([string]$_) } |
            Select-Object -First 1
    )
    if (-not $targetFramework) {
        throw "Unable to resolve TargetFramework from ChromaLink HTTP bridge project: $ProjectPath"
    }

    $projectDirectory = Split-Path -Path $ProjectPath -Parent
    $assemblyName = [System.IO.Path]::GetFileNameWithoutExtension($ProjectPath)
    $targetDirectory = Join-Path $projectDirectory (Join-Path 'bin\Debug' ([string]$targetFramework))
    $exePath = Join-Path $targetDirectory ('{0}.exe' -f $assemblyName)
    if (Test-Path -LiteralPath $exePath) {
        return [pscustomobject]@{
            FilePath = $exePath
            ArgumentList = @()
        }
    }

    $dllPath = Join-Path $targetDirectory ('{0}.dll' -f $assemblyName)
    if (Test-Path -LiteralPath $dllPath) {
        return [pscustomobject]@{
            FilePath = 'dotnet'
            ArgumentList = @($dllPath)
        }
    }

    throw "ChromaLink HTTP bridge build output not found after build: $exePath"
}

function Write-Utf8LogFile {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path,

        [string]$Content = ''
    )

    [System.IO.File]::WriteAllText($Path, $Content, [System.Text.UTF8Encoding]::new($false))
}

$base = $BaseUrl.TrimEnd('/')
$startedProcess = $null
$startedByScript = $false
$bridgeStopped = $false
$stdoutLog = $null
$stderrLog = $null
$buildLog = $null
$buildExitCode = $null
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

        $buildLog = Join-Path $env:TEMP ('riftreader-chromalink-httpbridge-build-{0}.log' -f ([Guid]::NewGuid().ToString('N')))
        $buildRun = Invoke-NativeCommand -Arguments @(
            'dotnet',
            'build',
            $resolvedProject,
            '--nologo',
            '-v',
            'quiet'
        )
        $buildExitCode = $buildRun.ExitCode
        Write-Utf8LogFile -Path $buildLog -Content $buildRun.Output
        if ($buildRun.ExitCode -ne 0) {
            throw "ChromaLink HTTP bridge build failed; exitCode=$($buildRun.ExitCode); buildLog=$buildLog"
        }

        $launchTarget = Resolve-BridgeLaunchTarget -ProjectPath $resolvedProject
        $startProcessParameters = @{
            FilePath = $launchTarget.FilePath
            WorkingDirectory = $resolvedRoot
            PassThru = $true
            WindowStyle = 'Hidden'
        }
        if (@($launchTarget.ArgumentList).Count -gt 0) {
            $startProcessParameters.ArgumentList = @($launchTarget.ArgumentList)
        }

        if (-not $KeepRunning) {
            $stdoutLog = Join-Path $env:TEMP ('riftreader-chromalink-httpbridge-out-{0}.log' -f ([Guid]::NewGuid().ToString('N')))
            $stderrLog = Join-Path $env:TEMP ('riftreader-chromalink-httpbridge-err-{0}.log' -f ([Guid]::NewGuid().ToString('N')))
            $startProcessParameters.RedirectStandardOutput = $stdoutLog
            $startProcessParameters.RedirectStandardError = $stderrLog
        }

        $startedProcess = Start-Process @startProcessParameters
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
            Add-ReadinessEndpointFailures -Name 'Health' -Response $health -Failures $failures
        }
        catch {
            $failures.Add("Health endpoint query failed: $($_.Exception.Message)") | Out-Null
        }

        try {
            $ready = Invoke-HttpJson -Url ('{0}/ready' -f $base)
            Add-ReadinessEndpointFailures -Name 'Ready' -Response $ready -Failures $failures
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
    buildExitCode = $buildExitCode
    buildLog = $buildLog
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
