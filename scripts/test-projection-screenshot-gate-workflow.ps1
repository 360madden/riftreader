[CmdletBinding()]
param(
    [string]$CandidateAddress = '0x12CFC40B7D0',
    [string]$NameplateText = 'Atank of Sanctum',
    [switch]$SkipBuild,
    [switch]$SkipCmdWrapperSmoke,
    [switch]$SkipArtifactSmoke,
    [switch]$Json
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$repoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$captureProject = Join-Path $repoRoot 'tools\rift-window-capture\RiftWindowCapture.csproj'
$wrapperScript = Join-Path $PSScriptRoot 'run-nameplate-projection-proof.ps1'
$wrapperCmd = Join-Path $PSScriptRoot 'run-nameplate-projection-proof.cmd'
$analyzerScript = Join-Path $PSScriptRoot 'analyze-tooltip-hover-diff.ps1'
$psScripts = @(
    'capture-rift-window-wgc.ps1',
    'capture-rift-window-printwindow.ps1',
    'test-rift-window-capture-methods.ps1',
    'capture-tooltip-hover-diff.ps1',
    'analyze-tooltip-hover-diff.ps1',
    'run-nameplate-projection-proof.ps1'
) | ForEach-Object { Join-Path $PSScriptRoot $_ }
$cmdWrappers = @(
    'capture-rift-window-wgc.cmd',
    'capture-rift-window-printwindow.cmd',
    'test-rift-window-capture-methods.cmd',
    'capture-tooltip-hover-diff.cmd',
    'analyze-tooltip-hover-diff.cmd',
    'run-nameplate-projection-proof.cmd',
    'test-projection-screenshot-gate-workflow.cmd'
) | ForEach-Object { Join-Path $PSScriptRoot $_ }

$checks = [System.Collections.Generic.List[object]]::new()
function Add-Check {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][string]$Status,
        [string]$Detail,
        [object]$Data
    )

    $checks.Add([pscustomobject][ordered]@{
        name = $Name
        status = $Status
        detail = $Detail
        data = $Data
    }) | Out-Null
}

try {
    foreach ($path in $psScripts) {
        if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
            throw "Missing script: $path"
        }

        $tokens = $null
        $errors = $null
        [System.Management.Automation.Language.Parser]::ParseFile($path, [ref]$tokens, [ref]$errors) | Out-Null
        if ($errors.Count -gt 0) {
            throw "PowerShell parse failed for $path`: $($errors[0].Message)"
        }
    }
    Add-Check -Name 'powershell-parse' -Status 'passed' -Detail ('Parsed {0} scripts.' -f $psScripts.Count)

    foreach ($path in $cmdWrappers) {
        if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
            throw "Missing CMD wrapper: $path"
        }

        $content = Get-Content -LiteralPath $path -Raw
        if ($content -notmatch '_run-pwsh\.cmd') {
            throw "CMD wrapper does not call _run-pwsh.cmd: $path"
        }
    }
    Add-Check -Name 'cmd-wrapper-inspection' -Status 'passed' -Detail ('Inspected {0} CMD wrappers.' -f $cmdWrappers.Count)

    if (-not (Test-Path -LiteralPath $captureProject -PathType Leaf)) {
        throw "Missing capture project: $captureProject"
    }

    if (-not $SkipBuild) {
        $buildOutput = & dotnet build $captureProject -v:minimal 2>&1
        $buildCode = $LASTEXITCODE
        if ($buildCode -ne 0) {
            throw "dotnet build failed with exit code $buildCode`n$($buildOutput -join [Environment]::NewLine)"
        }
        Add-Check -Name 'capture-project-build' -Status 'passed' -Detail 'RiftWindowCapture.csproj built successfully.'
    }
    else {
        Add-Check -Name 'capture-project-build' -Status 'skipped' -Detail 'SkipBuild was set.'
    }

    $planOutput = & pwsh -NoProfile -ExecutionPolicy Bypass -File $wrapperScript -CandidateAddress $CandidateAddress -NameplateText $NameplateText -PlanOnly -Json 2>&1
    $planCode = $LASTEXITCODE
    if ($planCode -ne 0) {
        throw "Wrapper plan-only failed with exit code $planCode`n$($planOutput -join [Environment]::NewLine)"
    }
    $plan = ($planOutput -join [Environment]::NewLine) | ConvertFrom-Json -Depth 40
    if (-not [bool]$plan.captureScreenshot -or -not [bool]$plan.requireUsableScreenshot -or -not [bool]$plan.analyzeAfterCapture -or -not [bool]$plan.analyzerRequireVisualGate) {
        throw 'Wrapper plan did not preserve required screenshot/analyzer gates.'
    }
    Add-Check -Name 'nameplate-wrapper-plan' -Status 'passed' -Detail 'Wrapper preserved screenshot-gated capture and fail-closed analysis defaults.' -Data $plan

    if (-not $SkipCmdWrapperSmoke) {
        $escapedNameplateText = $NameplateText.Replace('"', '\"')
        $cmdLine = '"{0}" -CandidateAddress {1} -NameplateText "{2}" -PlanOnly -Json' -f $wrapperCmd, $CandidateAddress, $escapedNameplateText
        $cmdOutput = & cmd.exe /d /c $cmdLine 2>&1
        $cmdCode = $LASTEXITCODE
        if ($cmdCode -ne 0) {
            throw "CMD wrapper plan-only failed with exit code $cmdCode`n$($cmdOutput -join [Environment]::NewLine)"
        }

        $cmdPlan = ($cmdOutput -join [Environment]::NewLine) | ConvertFrom-Json -Depth 40
        if (-not [bool]$cmdPlan.captureScreenshot -or -not [bool]$cmdPlan.requireUsableScreenshot -or -not [bool]$cmdPlan.analyzeAfterCapture -or -not [bool]$cmdPlan.analyzerRequireVisualGate) {
            throw 'CMD wrapper plan did not preserve required screenshot/analyzer gates.'
        }
        Add-Check -Name 'nameplate-cmd-wrapper-plan' -Status 'passed' -Detail 'CMD wrapper preserved screenshot-gated capture and fail-closed analysis defaults.' -Data $cmdPlan
    }
    else {
        Add-Check -Name 'nameplate-cmd-wrapper-plan' -Status 'skipped' -Detail 'SkipCmdWrapperSmoke was set.'
    }

    $smokeRun = Join-Path $repoRoot 'artifacts\tooltip-projection\20260424-095742-screenshot-gate-analyzer-smoke'
    if (-not $SkipArtifactSmoke -and (Test-Path -LiteralPath $smokeRun -PathType Container)) {
        $analysisOutput = & pwsh -NoProfile -ExecutionPolicy Bypass -File $analyzerScript -InputDirectory $smokeRun -BaselineStateRegex '^baseline' -ActiveStateRegex '^active' -BaselineLabel baseline -ActiveLabel active -RequireVisualGate -Json 2>&1
        $analysisCode = $LASTEXITCODE
        if ($analysisCode -ne 0) {
            throw "Analyzer artifact smoke failed with exit code $analysisCode`n$($analysisOutput -join [Environment]::NewLine)"
        }
        $analysis = ($analysisOutput -join [Environment]::NewLine) | ConvertFrom-Json -Depth 40
        if ([string]$analysis.screenshotGate.visualGateStatus -ne 'passed') {
            throw "Expected screenshotGate.visualGateStatus=passed, got $($analysis.screenshotGate.visualGateStatus)."
        }
        Add-Check -Name 'analyzer-visual-gate-smoke' -Status 'passed' -Detail 'Existing screenshot-gated smoke artifact passed RequireVisualGate.' -Data ([ordered]@{ inputDirectory = $smokeRun; visualGateStatus = $analysis.screenshotGate.visualGateStatus })
    }
    else {
        Add-Check -Name 'analyzer-visual-gate-smoke' -Status 'skipped' -Detail 'Smoke artifact missing or SkipArtifactSmoke was set.'
    }
}
catch {
    Add-Check -Name 'workflow-validation' -Status 'failed' -Detail $_.Exception.Message
    $result = [pscustomobject][ordered]@{
        ok = $false
        repoRoot = $repoRoot
        checks = @($checks)
    }
    if ($Json) { $result | ConvertTo-Json -Depth 40 } else { $result }
    exit 1
}

$result = [pscustomobject][ordered]@{
    ok = $true
    repoRoot = $repoRoot
    checks = @($checks)
}

if ($Json) {
    $result | ConvertTo-Json -Depth 40
}
else {
    $result
}
