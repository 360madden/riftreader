[CmdletBinding()]
param(
    [string]$CandidateAddress = '0x12CFC40B7D0',
    [string]$NameplateText = 'Atank of Sanctum',
    [switch]$SkipBuild,
    [switch]$SkipCmdWrapperSmoke,
    [switch]$SkipSelfCmdWrapperSmoke,
    [switch]$SkipArtifactSmoke,
    [switch]$Json
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$repoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$captureProject = Join-Path $repoRoot 'tools\rift-window-capture\RiftWindowCapture.csproj'
$wrapperScript = Join-Path $PSScriptRoot 'run-nameplate-projection-proof.ps1'
$wrapperCmd = Join-Path $PSScriptRoot 'run-nameplate-projection-proof.cmd'
$validatorCmd = Join-Path $PSScriptRoot 'test-projection-screenshot-gate-workflow.cmd'
$cmdLauncher = Join-Path $PSScriptRoot '_run-pwsh.cmd'
$analyzerScript = Join-Path $PSScriptRoot 'analyze-tooltip-hover-diff.ps1'
$psScripts = @(
    'capture-rift-window-wgc.ps1',
    'capture-rift-window-printwindow.ps1',
    'test-rift-window-capture-methods.ps1',
    'capture-tooltip-hover-diff.ps1',
    'analyze-tooltip-hover-diff.ps1',
    'run-nameplate-projection-proof.ps1',
    'test-projection-screenshot-gate-workflow.ps1'
) | ForEach-Object { Join-Path $PSScriptRoot $_ }
$cmdWrappers = @(
    [pscustomobject]@{ Wrapper = 'capture-rift-window-wgc.cmd'; Target = 'capture-rift-window-wgc.ps1' },
    [pscustomobject]@{ Wrapper = 'capture-rift-window-printwindow.cmd'; Target = 'capture-rift-window-printwindow.ps1' },
    [pscustomobject]@{ Wrapper = 'test-rift-window-capture-methods.cmd'; Target = 'test-rift-window-capture-methods.ps1' },
    [pscustomobject]@{ Wrapper = 'capture-tooltip-hover-diff.cmd'; Target = 'capture-tooltip-hover-diff.ps1' },
    [pscustomobject]@{ Wrapper = 'analyze-tooltip-hover-diff.cmd'; Target = 'analyze-tooltip-hover-diff.ps1' },
    [pscustomobject]@{ Wrapper = 'run-nameplate-projection-proof.cmd'; Target = 'run-nameplate-projection-proof.ps1' },
    [pscustomobject]@{ Wrapper = 'test-projection-screenshot-gate-workflow.cmd'; Target = 'test-projection-screenshot-gate-workflow.ps1' }
)

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

    if (-not (Test-Path -LiteralPath $cmdLauncher -PathType Leaf)) {
        throw "Missing shared CMD launcher: $cmdLauncher"
    }

    $inspectedCmdWrappers = [System.Collections.Generic.List[object]]::new()
    foreach ($wrapper in $cmdWrappers) {
        $path = Join-Path $PSScriptRoot ([string]$wrapper.Wrapper)
        if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
            throw "Missing CMD wrapper: $path"
        }

        $content = Get-Content -LiteralPath $path -Raw
        if ($content -notmatch '(?m)^@echo off\s*$') {
            throw "CMD wrapper is missing '@echo off': $path"
        }
        if ($content -notmatch '(?m)^setlocal EnableExtensions\s*$') {
            throw "CMD wrapper is missing 'setlocal EnableExtensions': $path"
        }
        if ($content -notmatch '_run-pwsh\.cmd') {
            throw "CMD wrapper does not call _run-pwsh.cmd: $path"
        }
        if ($content -notmatch '(?m)^call\s+"%~dp0_run-pwsh\.cmd"\s+%\*\s*$') {
            throw "CMD wrapper does not pass through arguments via the shared launcher: $path"
        }
        if ($content -notmatch '(?m)^exit /b %errorlevel%\s*$') {
            throw "CMD wrapper does not propagate shared launcher exit code: $path"
        }
        $escapedTarget = [regex]::Escape([string]$wrapper.Target)
        if ($content -notmatch ('set\s+"RIFTREADER_PS1=%~dp0{0}"' -f $escapedTarget)) {
            throw "CMD wrapper does not target expected PowerShell script. Wrapper=$path, ExpectedTarget=$($wrapper.Target)"
        }

        $inspectedCmdWrappers.Add([pscustomobject][ordered]@{
            wrapper = [string]$wrapper.Wrapper
            target = [string]$wrapper.Target
        }) | Out-Null
    }
    Add-Check -Name 'cmd-wrapper-inspection' -Status 'passed' -Detail ('Inspected {0} CMD wrappers and shared launcher.' -f $cmdWrappers.Count) -Data ([ordered]@{ launcher = $cmdLauncher; wrappers = @($inspectedCmdWrappers) })

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

    $planOnlyOutputRoot = Join-Path ([System.IO.Path]::GetTempPath()) ('riftreader-projection-planonly-{0}' -f ([guid]::NewGuid().ToString('N')))
    $planOutput = & pwsh -NoProfile -ExecutionPolicy Bypass -File $wrapperScript -CandidateAddress $CandidateAddress -NameplateText $NameplateText -OutputRoot $planOnlyOutputRoot -PlanOnly -Json 2>&1
    $planCode = $LASTEXITCODE
    if ($planCode -ne 0) {
        throw "Wrapper plan-only failed with exit code $planCode`n$($planOutput -join [Environment]::NewLine)"
    }
    $plan = ($planOutput -join [Environment]::NewLine) | ConvertFrom-Json -Depth 40
    if (-not [bool]$plan.captureScreenshot -or -not [bool]$plan.requireUsableScreenshot -or -not [bool]$plan.analyzeAfterCapture -or -not [bool]$plan.analyzerRequireVisualGate) {
        throw 'Wrapper plan did not preserve required screenshot/analyzer gates.'
    }
    if ([string]$plan.tooltipText -ne $NameplateText -or [string]$plan.candidateAddress -ne $CandidateAddress) {
        throw "Wrapper plan did not preserve key arguments. Expected CandidateAddress=$CandidateAddress, NameplateText='$NameplateText'; got CandidateAddress=$($plan.candidateAddress), NameplateText='$($plan.tooltipText)'."
    }
    if ([string]$plan.mode -ne 'plan-only' -or [bool]$plan.controlsInput) {
        throw "Wrapper plan did not preserve plan-only/no-input semantics. mode=$($plan.mode), controlsInput=$($plan.controlsInput)."
    }
    if ((Test-Path -LiteralPath $planOnlyOutputRoot) -or (Test-Path -LiteralPath ([string]$plan.runRoot))) {
        throw "Wrapper PlanOnly unexpectedly created artifacts. OutputRoot=$planOnlyOutputRoot, RunRoot=$($plan.runRoot)."
    }
    Add-Check -Name 'nameplate-wrapper-plan' -Status 'passed' -Detail 'Wrapper preserved screenshot-gated capture, fail-closed analysis defaults, key arguments, and plan-only no-artifact behavior.' -Data $plan

    if (-not $SkipCmdWrapperSmoke) {
        $cmdPlanOnlyOutputRoot = Join-Path ([System.IO.Path]::GetTempPath()) ('riftreader-projection-cmd-planonly-{0}' -f ([guid]::NewGuid().ToString('N')))
        $cmdOutput = & $wrapperCmd -CandidateAddress $CandidateAddress -NameplateText $NameplateText -OutputRoot $cmdPlanOnlyOutputRoot -PlanOnly -Json 2>&1
        $cmdCode = $LASTEXITCODE
        if ($cmdCode -ne 0) {
            throw "CMD wrapper plan-only failed with exit code $cmdCode`n$($cmdOutput -join [Environment]::NewLine)"
        }

        $cmdPlan = ($cmdOutput -join [Environment]::NewLine) | ConvertFrom-Json -Depth 40
        if (-not [bool]$cmdPlan.captureScreenshot -or -not [bool]$cmdPlan.requireUsableScreenshot -or -not [bool]$cmdPlan.analyzeAfterCapture -or -not [bool]$cmdPlan.analyzerRequireVisualGate) {
            throw 'CMD wrapper plan did not preserve required screenshot/analyzer gates.'
        }
        if ([string]$cmdPlan.tooltipText -ne $NameplateText -or [string]$cmdPlan.candidateAddress -ne $CandidateAddress) {
            throw "CMD wrapper plan did not preserve key arguments. Expected CandidateAddress=$CandidateAddress, NameplateText='$NameplateText'; got CandidateAddress=$($cmdPlan.candidateAddress), NameplateText='$($cmdPlan.tooltipText)'."
        }
        if ([string]$cmdPlan.mode -ne 'plan-only' -or [bool]$cmdPlan.controlsInput) {
            throw "CMD wrapper plan did not preserve plan-only/no-input semantics. mode=$($cmdPlan.mode), controlsInput=$($cmdPlan.controlsInput)."
        }
        if ((Test-Path -LiteralPath $cmdPlanOnlyOutputRoot) -or (Test-Path -LiteralPath ([string]$cmdPlan.runRoot))) {
            throw "CMD wrapper PlanOnly unexpectedly created artifacts. OutputRoot=$cmdPlanOnlyOutputRoot, RunRoot=$($cmdPlan.runRoot)."
        }
        Add-Check -Name 'nameplate-cmd-wrapper-plan' -Status 'passed' -Detail 'CMD wrapper preserved screenshot-gated capture, fail-closed analysis defaults, key arguments, and plan-only no-artifact behavior.' -Data $cmdPlan
    }
    else {
        Add-Check -Name 'nameplate-cmd-wrapper-plan' -Status 'skipped' -Detail 'SkipCmdWrapperSmoke was set.'
    }

    if (-not $SkipCmdWrapperSmoke -and -not $SkipSelfCmdWrapperSmoke) {
        $selfCmdOutput = & $validatorCmd -SkipBuild -SkipCmdWrapperSmoke -SkipSelfCmdWrapperSmoke -SkipArtifactSmoke -Json 2>&1
        $selfCmdCode = $LASTEXITCODE
        if ($selfCmdCode -ne 0) {
            throw "Validator CMD wrapper smoke failed with exit code $selfCmdCode`n$($selfCmdOutput -join [Environment]::NewLine)"
        }

        $selfCmdResult = ($selfCmdOutput -join [Environment]::NewLine) | ConvertFrom-Json -Depth 40
        if (-not [bool]$selfCmdResult.ok) {
            throw "Validator CMD wrapper smoke returned ok=false.`n$($selfCmdOutput -join [Environment]::NewLine)"
        }
        $selfCmdChecks = @($selfCmdResult.checks)
        if (-not @($selfCmdChecks | Where-Object { $_.name -eq 'cmd-wrapper-inspection' -and $_.status -eq 'passed' })) {
            throw "Validator CMD wrapper smoke did not pass cmd-wrapper-inspection.`n$($selfCmdOutput -join [Environment]::NewLine)"
        }
        Add-Check -Name 'validator-cmd-wrapper-smoke' -Status 'passed' -Detail 'Validator CMD wrapper launched successfully in non-recursive smoke mode.' -Data ([ordered]@{ skippedBuild = $true; skippedArtifactSmoke = $true })
    }
    else {
        Add-Check -Name 'validator-cmd-wrapper-smoke' -Status 'skipped' -Detail 'SkipCmdWrapperSmoke or SkipSelfCmdWrapperSmoke was set.'
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

    $negativeSmokeRoot = Join-Path ([System.IO.Path]::GetTempPath()) ('riftreader-projection-no-screenshot-{0}' -f ([guid]::NewGuid().ToString('N')))
    New-Item -ItemType Directory -Path $negativeSmokeRoot -Force | Out-Null
    try {
        $negativeRows = @(
            [pscustomobject][ordered]@{
                state = 'baseline'
                candidateAddress = $CandidateAddress
                windowStart = $CandidateAddress
                bytesHex = '0000000000000000'
            },
            [pscustomobject][ordered]@{
                state = 'active'
                candidateAddress = $CandidateAddress
                windowStart = $CandidateAddress
                bytesHex = '0100000000000000'
            }
        )
        $negativeRows | ForEach-Object { $_ | ConvertTo-Json -Compress -Depth 8 } | Set-Content -LiteralPath (Join-Path $negativeSmokeRoot 'samples.ndjson') -Encoding UTF8

        $negativeOutput = & pwsh -NoProfile -ExecutionPolicy Bypass -File $analyzerScript -InputDirectory $negativeSmokeRoot -BaselineStateRegex '^baseline' -ActiveStateRegex '^active' -BaselineLabel baseline -ActiveLabel active -RequireVisualGate -Json 2>&1
        $negativeCode = $LASTEXITCODE
        if ($negativeCode -eq 0) {
            throw "Analyzer RequireVisualGate unexpectedly passed without screenshot captures.`n$($negativeOutput -join [Environment]::NewLine)"
        }

        $negativeScreenshotGatePath = Join-Path $negativeSmokeRoot 'diffs\screenshot-gate.json'
        if (-not (Test-Path -LiteralPath $negativeScreenshotGatePath -PathType Leaf)) {
            throw "Analyzer RequireVisualGate failed before writing screenshot-gate evidence.`n$($negativeOutput -join [Environment]::NewLine)"
        }

        $negativeScreenshotGate = Get-Content -LiteralPath $negativeScreenshotGatePath -Raw | ConvertFrom-Json -Depth 32
        $negativeStatus = [string]$negativeScreenshotGate.screenshotGate.visualGateStatus
        if ($negativeStatus -ne 'not-captured') {
            throw "Analyzer RequireVisualGate failed with unexpected visualGateStatus=$negativeStatus.`n$($negativeOutput -join [Environment]::NewLine)"
        }

        Add-Check -Name 'analyzer-visual-gate-negative-smoke' -Status 'passed' -Detail 'Analyzer RequireVisualGate fails closed when samples do not include screenshot captures.' -Data ([ordered]@{ visualGateStatus = $negativeStatus; screenshotGateEvidenceParsed = $true })
    }
    finally {
        if (Test-Path -LiteralPath $negativeSmokeRoot) {
            Remove-Item -LiteralPath $negativeSmokeRoot -Recurse -Force
        }
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
