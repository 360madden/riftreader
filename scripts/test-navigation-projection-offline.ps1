[CmdletBinding()]
param(
    [switch]$SkipArtifactSmoke,
    [switch]$SkipDiffCheck,
    [ValidateRange(0, 500)]
    [int]$OutputTailLines = 80,
    [switch]$IncludeFullOutput,
    [switch]$Json
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$repoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$workflowValidator = Join-Path $PSScriptRoot 'test-projection-screenshot-gate-workflow.ps1'
$readerTests = Join-Path $repoRoot 'reader\RiftReader.Reader.Tests\RiftReader.Reader.Tests.csproj'

$steps = [System.Collections.Generic.List[object]]::new()

function Invoke-OfflineStep {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Name,
        [Parameter(Mandatory = $true)]
        [string]$FilePath,
        [string[]]$Arguments = @(),
        [scriptblock]$Summarize
    )

    $startedUtc = (Get-Date).ToUniversalTime()
    $output = & $FilePath @Arguments 2>&1
    $exitCode = $LASTEXITCODE
    $text = $output -join [Environment]::NewLine
    $outputTail = if ($OutputTailLines -le 0) {
        ''
    }
    else {
        (@($output) | Select-Object -Last $OutputTailLines) -join [Environment]::NewLine
    }
    $summary = $null
    if ($null -ne $Summarize) {
        $summary = & $Summarize $text
    }

    $steps.Add([pscustomobject][ordered]@{
        name = $Name
        status = if ($exitCode -eq 0) { 'passed' } else { 'failed' }
        exitCode = $exitCode
        durationSeconds = [Math]::Round(((Get-Date).ToUniversalTime() - $startedUtc).TotalSeconds, 3)
        command = @($FilePath) + @($Arguments)
        summary = $summary
        outputTail = $outputTail
        output = if ($IncludeFullOutput) { $text } else { $null }
    }) | Out-Null
}

if (-not (Test-Path -LiteralPath $workflowValidator -PathType Leaf)) {
    throw "Missing projection workflow validator: $workflowValidator"
}

if (-not (Test-Path -LiteralPath $readerTests -PathType Leaf)) {
    throw "Missing Reader test project: $readerTests"
}

$workflowArgs = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $workflowValidator, '-Json')
if ($SkipArtifactSmoke) {
    $workflowArgs += '-SkipArtifactSmoke'
}

Invoke-OfflineStep -Name 'projection-workflow-validator' -FilePath 'pwsh' -Arguments $workflowArgs -Summarize {
    param([string]$Text)
    try {
        $result = $Text | ConvertFrom-Json -Depth 40
        $checks = @($result.checks)
        return [pscustomobject][ordered]@{
            ok = [bool]$result.ok
            checkCount = $checks.Count
            passed = @($checks | Where-Object { $_.status -eq 'passed' }).Count
            skipped = @($checks | Where-Object { $_.status -eq 'skipped' }).Count
            failed = @($checks | Where-Object { $_.status -eq 'failed' }).Count
        }
    }
    catch {
        return [pscustomobject][ordered]@{
            parseError = $_.Exception.Message
        }
    }
}

Invoke-OfflineStep -Name 'reader-tests' -FilePath 'dotnet' -Arguments @('test', $readerTests, '-v:minimal') -Summarize {
    param([string]$Text)
    $match = [regex]::Match($Text, 'Failed:\s+(?<failed>\d+),\s+Passed:\s+(?<passed>\d+),\s+Skipped:\s+(?<skipped>\d+),\s+Total:\s+(?<total>\d+)')
    if (-not $match.Success) {
        return $null
    }

    return [pscustomobject][ordered]@{
        failed = [int]$match.Groups['failed'].Value
        passed = [int]$match.Groups['passed'].Value
        skipped = [int]$match.Groups['skipped'].Value
        total = [int]$match.Groups['total'].Value
    }
}

if (-not $SkipDiffCheck) {
    Invoke-OfflineStep -Name 'git-diff-check' -FilePath 'git' -Arguments @('-C', $repoRoot, 'diff', '--check') -Summarize {
        param([string]$Text)
        return [pscustomobject][ordered]@{
            outputIsEmpty = [string]::IsNullOrWhiteSpace($Text)
        }
    }
}
else {
    $steps.Add([pscustomobject][ordered]@{
        name = 'git-diff-check'
        status = 'skipped'
        exitCode = 0
        durationSeconds = 0
        command = @('git', '-C', $repoRoot, 'diff', '--check')
        summary = [pscustomobject][ordered]@{ reason = 'SkipDiffCheck was set.' }
        outputTail = ''
        output = $null
    }) | Out-Null
}

$failedSteps = @($steps | Where-Object { $_.status -eq 'failed' })
$result = [pscustomobject][ordered]@{
    ok = ($failedSteps.Count -eq 0)
    repoRoot = $repoRoot
    steps = @($steps)
}

if ($Json) {
    $result | ConvertTo-Json -Depth 40
}
else {
    $result | Select-Object -ExpandProperty steps | Format-Table name,status,exitCode,durationSeconds -AutoSize
}

if ($failedSteps.Count -gt 0) {
    exit 1
}
