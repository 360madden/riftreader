[CmdletBinding()]
param(
    [switch]$SkipTests,

    [switch]$SkipParserCheck,

    [switch]$SkipGitDiffCheck,

    [switch]$Json
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$schemaVersion = 1
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path

function Invoke-NativeValidation {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Name,

        [Parameter(Mandatory = $true)]
        [string[]]$Arguments
    )

    $startedAtUtc = [DateTimeOffset]::UtcNow
    $previousErrorActionPreference = $ErrorActionPreference
    $nativePreferenceVariable = Get-Variable -Name PSNativeCommandUseErrorActionPreference -Scope 1 -ErrorAction SilentlyContinue
    $previousNativeCommandPreference = if ($null -ne $nativePreferenceVariable) { $nativePreferenceVariable.Value } else { $null }
    try {
        $ErrorActionPreference = 'Continue'
        if ($null -ne $nativePreferenceVariable) {
            Set-Variable -Name PSNativeCommandUseErrorActionPreference -Scope 1 -Value $false
        }

        $output = & $Arguments[0] @($Arguments | Select-Object -Skip 1) 2>&1
        $exitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $previousErrorActionPreference
        if ($null -ne $nativePreferenceVariable) {
            Set-Variable -Name PSNativeCommandUseErrorActionPreference -Scope 1 -Value $previousNativeCommandPreference
        }
    }

    return [ordered]@{
        name = $Name
        kind = 'native-command'
        status = if ($exitCode -eq 0) { 'pass' } else { 'fail' }
        exitCode = $exitCode
        durationMilliseconds = [Math]::Round(([DateTimeOffset]::UtcNow - $startedAtUtc).TotalMilliseconds, 3)
        command = ($Arguments -join ' ')
        output = ($output -join [Environment]::NewLine)
    }
}

function Invoke-ParserValidation {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path
    )

    $resolvedPath = (Resolve-Path $Path).Path
    $tokens = $null
    $errors = $null
    [System.Management.Automation.Language.Parser]::ParseFile($resolvedPath, [ref]$tokens, [ref]$errors) | Out-Null
    $messages = @($errors | ForEach-Object { $_.Message })

    return [ordered]@{
        name = "parse $Path"
        kind = 'powershell-parser'
        status = if ($messages.Count -eq 0) { 'pass' } else { 'fail' }
        path = $resolvedPath
        errorCount = $messages.Count
        errors = $messages
    }
}

$tests = @(
    'scripts/test-write-capture-metadata.ps1',
    'scripts/test-export-chromalink-live-coords.ps1',
    'scripts/test-chromalink-live-telemetry-script.ps1',
    'scripts/test-capture-chromalink-live-coords.ps1',
    'scripts/test-score-candidate-trajectories.ps1',
    'scripts/test-write-promotion-gate.ps1',
    'scripts/test-run-candidate-trajectory-gate.ps1'
)

$parserFiles = @(
    'scripts/write-capture-metadata.ps1',
    'scripts/test-write-capture-metadata.ps1',
    'scripts/record-discovery-session.ps1',
    'scripts/export-chromalink-live-coords.ps1',
    'scripts/test-export-chromalink-live-coords.ps1',
    'scripts/test-chromalink-live-telemetry.ps1',
    'scripts/test-chromalink-live-telemetry-script.ps1',
    'scripts/capture-chromalink-live-coords.ps1',
    'scripts/test-capture-chromalink-live-coords.ps1',
    'scripts/score-candidate-trajectories.ps1',
    'scripts/test-score-candidate-trajectories.ps1',
    'scripts/write-promotion-gate.ps1',
    'scripts/test-write-promotion-gate.ps1',
    'scripts/run-candidate-trajectory-gate.ps1',
    'scripts/test-run-candidate-trajectory-gate.ps1',
    'scripts/run-offline-validation.ps1'
)

$results = [System.Collections.Generic.List[object]]::new()
Push-Location $repoRoot
try {
    if (-not $SkipTests) {
        foreach ($test in $tests) {
            $results.Add((Invoke-NativeValidation -Name $test -Arguments @('pwsh', '-NoLogo', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $test))) | Out-Null
        }
    }

    if (-not $SkipParserCheck) {
        foreach ($file in $parserFiles) {
            $results.Add((Invoke-ParserValidation -Path $file)) | Out-Null
        }
    }

    if (-not $SkipGitDiffCheck -and (Test-Path -LiteralPath (Join-Path $repoRoot '.git'))) {
        $results.Add((Invoke-NativeValidation -Name 'git diff --check' -Arguments @('git', 'diff', '--check'))) | Out-Null
    }
}
finally {
    Pop-Location
}

$failed = @($results.ToArray() | Where-Object { $_.status -ne 'pass' })
$status = if ($failed.Count -eq 0) { 'pass' } else { 'fail' }
$summary = [ordered]@{
    schemaVersion = $schemaVersion
    mode = 'offline-validation'
    generatedAtUtc = [DateTimeOffset]::UtcNow.ToString('O', [System.Globalization.CultureInfo]::InvariantCulture)
    status = $status
    repoRoot = $repoRoot
    totalChecks = $results.Count
    failedChecks = $failed.Count
    results = $results.ToArray()
}

if ($Json) {
    $summary | ConvertTo-Json -Depth 16
}
else {
    $color = if ($status -eq 'pass') { 'Green' } else { 'Red' }
    Write-Host ("Offline validation: {0}" -f $status) -ForegroundColor $color
    foreach ($result in $results) {
        $stepColor = if ($result.status -eq 'pass') { 'Green' } else { 'Red' }
        Write-Host ("[{0}] {1}" -f $result.status, $result.name) -ForegroundColor $stepColor
        if ($result.status -ne 'pass' -and -not [string]::IsNullOrWhiteSpace([string]$result.output)) {
            Write-Host $result.output
        }
    }
}

if ($status -ne 'pass') {
    exit 1
}
