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
$resultCheckerScript = Join-Path $PSScriptRoot 'check-nameplate-projection-proof-result.ps1'
$resultCheckerCmd = Join-Path $PSScriptRoot 'check-nameplate-projection-proof-result.cmd'
$proofCompareScript = Join-Path $PSScriptRoot 'compare-nameplate-projection-proof-runs.ps1'
$proofCompareCmd = Join-Path $PSScriptRoot 'compare-nameplate-projection-proof-runs.cmd'
$byteWindowCompareScript = Join-Path $PSScriptRoot 'compare-nameplate-proof-byte-windows.ps1'
$byteWindowCompareCmd = Join-Path $PSScriptRoot 'compare-nameplate-proof-byte-windows.cmd'
$leadExtractorScript = Join-Path $PSScriptRoot 'extract-nameplate-proof-leads.ps1'
$leadExtractorCmd = Join-Path $PSScriptRoot 'extract-nameplate-proof-leads.cmd'
$leadNeighborhoodScript = Join-Path $PSScriptRoot 'capture-nameplate-proof-lead-neighborhoods.ps1'
$leadNeighborhoodCmd = Join-Path $PSScriptRoot 'capture-nameplate-proof-lead-neighborhoods.cmd'
$leadNeighborhoodCompareScript = Join-Path $PSScriptRoot 'compare-nameplate-proof-lead-neighborhoods.ps1'
$leadNeighborhoodCompareCmd = Join-Path $PSScriptRoot 'compare-nameplate-proof-lead-neighborhoods.cmd'
$promotionPacketScript = Join-Path $PSScriptRoot 'write-nameplate-proof-promotion-packet.ps1'
$promotionPacketCmd = Join-Path $PSScriptRoot 'write-nameplate-proof-promotion-packet.cmd'
$promotionPipelineScript = Join-Path $PSScriptRoot 'run-nameplate-proof-promotion-pipeline.ps1'
$promotionPipelineCmd = Join-Path $PSScriptRoot 'run-nameplate-proof-promotion-pipeline.cmd'
$proofRunListScript = Join-Path $PSScriptRoot 'list-nameplate-proof-runs.ps1'
$proofRunListCmd = Join-Path $PSScriptRoot 'list-nameplate-proof-runs.cmd'
$promotionPlanScript = Join-Path $PSScriptRoot 'plan-nameplate-proof-promotion.ps1'
$promotionPlanCmd = Join-Path $PSScriptRoot 'plan-nameplate-proof-promotion.cmd'
$promotionNextActionScript = Join-Path $PSScriptRoot 'invoke-nameplate-promotion-next-action.ps1'
$promotionNextActionCmd = Join-Path $PSScriptRoot 'invoke-nameplate-promotion-next-action.cmd'
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
    'check-nameplate-projection-proof-result.ps1',
    'compare-nameplate-projection-proof-runs.ps1',
    'compare-nameplate-proof-byte-windows.ps1',
    'extract-nameplate-proof-leads.ps1',
    'capture-nameplate-proof-lead-neighborhoods.ps1',
    'compare-nameplate-proof-lead-neighborhoods.ps1',
    'write-nameplate-proof-promotion-packet.ps1',
    'run-nameplate-proof-promotion-pipeline.ps1',
    'list-nameplate-proof-runs.ps1',
    'plan-nameplate-proof-promotion.ps1',
    'invoke-nameplate-promotion-next-action.ps1',
    'test-projection-screenshot-gate-workflow.ps1'
) | ForEach-Object { Join-Path $PSScriptRoot $_ }
$expectedProjectionPsScriptCount = 18
$cmdWrappers = @(
    [pscustomobject]@{ Wrapper = 'capture-rift-window-wgc.cmd'; Target = 'capture-rift-window-wgc.ps1' },
    [pscustomobject]@{ Wrapper = 'capture-rift-window-printwindow.cmd'; Target = 'capture-rift-window-printwindow.ps1' },
    [pscustomobject]@{ Wrapper = 'test-rift-window-capture-methods.cmd'; Target = 'test-rift-window-capture-methods.ps1' },
    [pscustomobject]@{ Wrapper = 'capture-tooltip-hover-diff.cmd'; Target = 'capture-tooltip-hover-diff.ps1' },
    [pscustomobject]@{ Wrapper = 'analyze-tooltip-hover-diff.cmd'; Target = 'analyze-tooltip-hover-diff.ps1' },
    [pscustomobject]@{ Wrapper = 'run-nameplate-projection-proof.cmd'; Target = 'run-nameplate-projection-proof.ps1' },
    [pscustomobject]@{ Wrapper = 'check-nameplate-projection-proof-result.cmd'; Target = 'check-nameplate-projection-proof-result.ps1' },
    [pscustomobject]@{ Wrapper = 'compare-nameplate-projection-proof-runs.cmd'; Target = 'compare-nameplate-projection-proof-runs.ps1' },
    [pscustomobject]@{ Wrapper = 'compare-nameplate-proof-byte-windows.cmd'; Target = 'compare-nameplate-proof-byte-windows.ps1' },
    [pscustomobject]@{ Wrapper = 'extract-nameplate-proof-leads.cmd'; Target = 'extract-nameplate-proof-leads.ps1' },
    [pscustomobject]@{ Wrapper = 'capture-nameplate-proof-lead-neighborhoods.cmd'; Target = 'capture-nameplate-proof-lead-neighborhoods.ps1' },
    [pscustomobject]@{ Wrapper = 'compare-nameplate-proof-lead-neighborhoods.cmd'; Target = 'compare-nameplate-proof-lead-neighborhoods.ps1' },
    [pscustomobject]@{ Wrapper = 'write-nameplate-proof-promotion-packet.cmd'; Target = 'write-nameplate-proof-promotion-packet.ps1' },
    [pscustomobject]@{ Wrapper = 'run-nameplate-proof-promotion-pipeline.cmd'; Target = 'run-nameplate-proof-promotion-pipeline.ps1' },
    [pscustomobject]@{ Wrapper = 'list-nameplate-proof-runs.cmd'; Target = 'list-nameplate-proof-runs.ps1' },
    [pscustomobject]@{ Wrapper = 'plan-nameplate-proof-promotion.cmd'; Target = 'plan-nameplate-proof-promotion.ps1' },
    [pscustomobject]@{ Wrapper = 'invoke-nameplate-promotion-next-action.cmd'; Target = 'invoke-nameplate-promotion-next-action.ps1' },
    [pscustomobject]@{ Wrapper = 'test-projection-screenshot-gate-workflow.cmd'; Target = 'test-projection-screenshot-gate-workflow.ps1' }
)
$expectedProjectionCmdWrapperCount = 18

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
    $psScriptNames = @($psScripts | ForEach-Object { Split-Path -Leaf $_ })
    if ($psScriptNames.Count -ne $expectedProjectionPsScriptCount) {
        throw "Expected $expectedProjectionPsScriptCount projection PowerShell script entries, found $($psScriptNames.Count)."
    }

    $duplicatePsScriptNames = @($psScriptNames | Group-Object | Where-Object { $_.Count -gt 1 } | ForEach-Object { $_.Name })
    if ($duplicatePsScriptNames.Count -gt 0) {
        throw "Duplicate projection PowerShell script entries in validator manifest: $($duplicatePsScriptNames -join ', ')"
    }

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
    Add-Check -Name 'powershell-parse' -Status 'passed' -Detail ('Parsed {0} scripts.' -f $psScripts.Count) -Data ([ordered]@{ expectedScriptCount = $expectedProjectionPsScriptCount; scriptCount = $psScripts.Count; uniqueScriptCount = @($psScriptNames | Select-Object -Unique).Count; scripts = $psScriptNames })

    $captureScript = Join-Path $PSScriptRoot 'capture-tooltip-hover-diff.ps1'
    $captureScriptContent = Get-Content -LiteralPath $captureScript -Raw
    if ($captureScriptContent -match "\`$state\s+-match\s+'hover'") {
        throw 'Capture helper still classifies active states by literal hover instead of AnalyzerActiveStateRegex.'
    }
    if ($captureScriptContent -notmatch "\`$isActiveState\s*=\s*\`$state\s+-match\s+\`$AnalyzerActiveStateRegex") {
        throw 'Capture helper does not classify active states with AnalyzerActiveStateRegex.'
    }
    if ($captureScriptContent -notmatch 'stateRole\s*=') {
        throw 'Capture helper does not record stateRole in proof artifacts.'
    }
    if ($captureScriptContent -notmatch "Prepare proof state") {
        throw 'Capture helper operator prompt still uses legacy tooltip-state wording.'
    }
    Add-Check -Name 'nameplate-active-state-classification' -Status 'passed' -Detail 'Capture helper classifies active proof states with AnalyzerActiveStateRegex and records state roles in proof artifacts.'

    $directPlanOnlyOutputRoot = Join-Path ([System.IO.Path]::GetTempPath()) ('riftreader-projection-direct-planonly-{0}' -f ([guid]::NewGuid().ToString('N')))
    $directCapturePlanOutput = & pwsh -NoProfile -ExecutionPolicy Bypass -File $captureScript -CandidateAddress $CandidateAddress -TooltipText $NameplateText -States baseline1 -OutputRoot $directPlanOnlyOutputRoot -PlanOnly -Json 2>&1
    $directCapturePlanCode = $LASTEXITCODE
    if ($directCapturePlanCode -ne 0) {
        throw "Capture helper direct PlanOnly failed with exit code $directCapturePlanCode`n$($directCapturePlanOutput -join [Environment]::NewLine)"
    }
    $directCapturePlan = ($directCapturePlanOutput -join [Environment]::NewLine) | ConvertFrom-Json -Depth 40
    if ((@($directCapturePlan.states) -join ',') -ne 'baseline1') {
        throw "Capture helper direct PlanOnly did not preserve a single state as a one-item array. States=$(@($directCapturePlan.states) -join ',')"
    }
    if (@($directCapturePlan.extraPointerTargets).Count -ne 0 -or @($directCapturePlan.scanInt32Values).Count -ne 0 -or @($directCapturePlan.scanFloatValues).Count -ne 0 -or @($directCapturePlan.scanDoubleValues).Count -ne 0) {
        throw 'Capture helper direct PlanOnly serialized omitted optional scan lists as non-empty/null placeholders.'
    }
    if ((Test-Path -LiteralPath $directPlanOnlyOutputRoot) -or (Test-Path -LiteralPath ([string]$directCapturePlan.runRoot))) {
        throw "Capture helper direct PlanOnly unexpectedly created artifacts. OutputRoot=$directPlanOnlyOutputRoot, RunRoot=$($directCapturePlan.runRoot)."
    }
    Add-Check -Name 'capture-helper-planonly-empty-list-guards' -Status 'passed' -Detail 'Capture helper preserves single-state arrays and omitted optional scan lists under StrictMode without creating artifacts.' -Data ([ordered]@{ states = @($directCapturePlan.states); optionalScanListCount = 0 })

    if (-not (Test-Path -LiteralPath $cmdLauncher -PathType Leaf)) {
        throw "Missing shared CMD launcher: $cmdLauncher"
    }

    $launcherContent = Get-Content -LiteralPath $cmdLauncher -Raw
    if ($launcherContent -notmatch '(?m)^@echo off\s*$') {
        throw "Shared CMD launcher is missing '@echo off': $cmdLauncher"
    }
    if ($launcherContent -notmatch '(?m)^setlocal EnableExtensions\s*$') {
        throw "Shared CMD launcher is missing 'setlocal EnableExtensions': $cmdLauncher"
    }
    if ($launcherContent -notmatch '(?m)^set\s+"SCRIPT_PATH=%RIFTREADER_PS1%"\s*$') {
        throw "Shared CMD launcher does not read RIFTREADER_PS1 into SCRIPT_PATH: $cmdLauncher"
    }
    if ($launcherContent -notmatch '(?m)^where /q pwsh && set "PWSH_EXE=pwsh"\s*$') {
        throw "Shared CMD launcher does not prefer pwsh from PATH: $cmdLauncher"
    }
    if ($launcherContent -notmatch [regex]::Escape('"%PWSH_EXE%" -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_PATH%" %*')) {
        throw "Shared CMD launcher does not invoke PowerShell with the expected flags and argument pass-through: $cmdLauncher"
    }
    if ($launcherContent -notmatch '(?m)^exit /b %errorlevel%\s*$') {
        throw "Shared CMD launcher does not propagate PowerShell exit code: $cmdLauncher"
    }

    $launcherContract = [ordered]@{
        echoOff = $true
        setlocalEnableExtensions = $true
        readsRiftReaderPs1 = $true
        prefersPwshFromPath = $true
        usesNoLogoNoProfileExecutionPolicyBypass = $true
        passesArgumentsThrough = $true
        propagatesExitCode = $true
    }

    $wrapperNames = @($cmdWrappers | ForEach-Object { [string]$_.Wrapper })
    if ($wrapperNames.Count -ne $expectedProjectionCmdWrapperCount) {
        throw "Expected $expectedProjectionCmdWrapperCount projection CMD wrapper entries, found $($wrapperNames.Count)."
    }

    $duplicateWrapperNames = @($wrapperNames | Group-Object | Where-Object { $_.Count -gt 1 } | ForEach-Object { $_.Name })
    if ($duplicateWrapperNames.Count -gt 0) {
        throw "Duplicate CMD wrapper entries in validator manifest: $($duplicateWrapperNames -join ', ')"
    }

    $targetNames = @($cmdWrappers | ForEach-Object { [string]$_.Target })
    $duplicateTargetNames = @($targetNames | Group-Object | Where-Object { $_.Count -gt 1 } | ForEach-Object { $_.Name })
    if ($duplicateTargetNames.Count -gt 0) {
        throw "Duplicate CMD wrapper target entries in validator manifest: $($duplicateTargetNames -join ', ')"
    }
    $targetDrift = @(Compare-Object -ReferenceObject $psScriptNames -DifferenceObject $targetNames)
    if ($targetDrift.Count -gt 0) {
        $targetDriftText = @(($targetDrift | ForEach-Object { '{0}:{1}' -f $_.SideIndicator, $_.InputObject }) | Sort-Object) -join ', '
        throw "CMD wrapper targets do not match parsed PowerShell script manifest: $targetDriftText"
    }

    $inspectedCmdWrappers = [System.Collections.Generic.List[object]]::new()
    foreach ($wrapper in $cmdWrappers) {
        $path = Join-Path $PSScriptRoot ([string]$wrapper.Wrapper)
        $targetPath = Join-Path $PSScriptRoot ([string]$wrapper.Target)
        if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
            throw "Missing CMD wrapper: $path"
        }
        if (-not (Test-Path -LiteralPath $targetPath -PathType Leaf)) {
            throw "CMD wrapper target PowerShell script is missing. Wrapper=$path, Target=$targetPath"
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
            targetExists = $true
            echoOff = $true
            setlocalEnableExtensions = $true
            callsSharedLauncher = $true
            passesArgumentsThrough = $true
            propagatesExitCode = $true
        }) | Out-Null
    }
    Add-Check -Name 'cmd-wrapper-inspection' -Status 'passed' -Detail ('Inspected {0} CMD wrappers and shared launcher.' -f $cmdWrappers.Count) -Data ([ordered]@{ launcher = $cmdLauncher; launcherContract = $launcherContract; expectedWrapperCount = $expectedProjectionCmdWrapperCount; wrapperCount = $cmdWrappers.Count; uniqueWrapperCount = @($wrapperNames | Select-Object -Unique).Count; uniqueTargetCount = @($targetNames | Select-Object -Unique).Count; targetsMatchParsedScripts = $true; wrappers = @($inspectedCmdWrappers) })

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
    if ((@($plan.analyzerExpectedStates) -join ',') -ne 'baseline1,zoom1,baseline2,zoom2' -or (@($plan.analyzerExpectedStateRoles) -join ',') -ne 'baseline,active,baseline,active') {
        throw "Wrapper plan did not preserve expected nameplate proof state sequence. States=$(@($plan.analyzerExpectedStates) -join ','), Roles=$(@($plan.analyzerExpectedStateRoles) -join ',')."
    }
    if (@($plan.operatorChecklist).Count -ne 4 -or (@($plan.operatorChecklist | ForEach-Object { [string]$_.stateRole }) -join ',') -ne 'baseline,active,baseline,active') {
        throw "Wrapper plan did not expose the expected operator checklist. Count=$(@($plan.operatorChecklist).Count), Roles=$(@($plan.operatorChecklist | ForEach-Object { [string]$_.stateRole }) -join ',')."
    }
    if ([int]$plan.maxHits -ne 24 -or [string]$plan.textPointerScanMode -ne 'allHits' -or [bool]$plan.skipPointerScan) {
        throw "Wrapper default scan plan drifted. maxHits=$($plan.maxHits), textPointerScanMode=$($plan.textPointerScanMode), skipPointerScan=$($plan.skipPointerScan)."
    }
    if ((Test-Path -LiteralPath $planOnlyOutputRoot) -or (Test-Path -LiteralPath ([string]$plan.runRoot))) {
        throw "Wrapper PlanOnly unexpectedly created artifacts. OutputRoot=$planOnlyOutputRoot, RunRoot=$($plan.runRoot)."
    }
    Add-Check -Name 'nameplate-wrapper-plan' -Status 'passed' -Detail 'Wrapper preserved screenshot-gated capture, fail-closed analysis defaults, expected state sequence, operator checklist, key arguments, and plan-only no-artifact behavior.' -Data $plan

    $fastReproofPlanOnlyOutputRoot = Join-Path ([System.IO.Path]::GetTempPath()) ('riftreader-projection-fast-reproof-planonly-{0}' -f ([guid]::NewGuid().ToString('N')))
    $fastReproofOutput = & pwsh -NoProfile -ExecutionPolicy Bypass -File $wrapperScript -CandidateAddress $CandidateAddress -NameplateText $NameplateText -OutputRoot $fastReproofPlanOnlyOutputRoot -MaxHits 4 -TextPointerScanMode none -SkipPointerScan -PlanOnly -Json 2>&1
    $fastReproofCode = $LASTEXITCODE
    if ($fastReproofCode -ne 0) {
        throw "Wrapper fast-reproof PlanOnly failed with exit code $fastReproofCode`n$($fastReproofOutput -join [Environment]::NewLine)"
    }
    $fastReproofPlan = ($fastReproofOutput -join [Environment]::NewLine) | ConvertFrom-Json -Depth 40
    if ([int]$fastReproofPlan.maxHits -ne 4 -or [string]$fastReproofPlan.textPointerScanMode -ne 'none' -or -not [bool]$fastReproofPlan.skipPointerScan) {
        throw "Wrapper fast-reproof plan did not preserve bounded scan controls. maxHits=$($fastReproofPlan.maxHits), textPointerScanMode=$($fastReproofPlan.textPointerScanMode), skipPointerScan=$($fastReproofPlan.skipPointerScan)."
    }
    if (-not [bool]$fastReproofPlan.captureScreenshot -or -not [bool]$fastReproofPlan.requireUsableScreenshot -or -not [bool]$fastReproofPlan.analyzerRequireVisualGate) {
        throw 'Wrapper fast-reproof plan did not preserve screenshot-gated proof semantics.'
    }
    if ((Test-Path -LiteralPath $fastReproofPlanOnlyOutputRoot) -or (Test-Path -LiteralPath ([string]$fastReproofPlan.runRoot))) {
        throw "Wrapper fast-reproof PlanOnly unexpectedly created artifacts. OutputRoot=$fastReproofPlanOnlyOutputRoot, RunRoot=$($fastReproofPlan.runRoot)."
    }
    Add-Check -Name 'nameplate-wrapper-fast-reproof-plan' -Status 'passed' -Detail 'Wrapper exposes bounded scan controls for faster candidate reproof while preserving screenshot-gated PlanOnly semantics.' -Data ([ordered]@{ maxHits = $fastReproofPlan.maxHits; textPointerScanMode = $fastReproofPlan.textPointerScanMode; skipPointerScan = $fastReproofPlan.skipPointerScan })

    $nonInteractiveOutputRoot = Join-Path ([System.IO.Path]::GetTempPath()) ('riftreader-projection-noninteractive-{0}' -f ([guid]::NewGuid().ToString('N')))
    $nonInteractiveOutput = & pwsh -NoProfile -ExecutionPolicy Bypass -File $wrapperScript -CandidateAddress $CandidateAddress -NameplateText $NameplateText -OutputRoot $nonInteractiveOutputRoot -NonInteractive -Json 2>&1
    $nonInteractiveCode = $LASTEXITCODE
    if ($nonInteractiveCode -eq 0) {
        throw "Wrapper unexpectedly allowed non-interactive live proof capture.`n$($nonInteractiveOutput -join [Environment]::NewLine)"
    }
    if (($nonInteractiveOutput -join [Environment]::NewLine) -notmatch 'requires operator confirmation') {
        throw "Wrapper non-interactive guard failed with an unexpected error.`n$($nonInteractiveOutput -join [Environment]::NewLine)"
    }
    if (Test-Path -LiteralPath $nonInteractiveOutputRoot) {
        throw "Wrapper non-interactive guard unexpectedly created artifacts. OutputRoot=$nonInteractiveOutputRoot."
    }
    Add-Check -Name 'nameplate-wrapper-noninteractive-guard' -Status 'passed' -Detail 'Wrapper rejects non-interactive live proof capture before attaching or creating artifacts.'

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
        if ((@($cmdPlan.analyzerExpectedStates) -join ',') -ne 'baseline1,zoom1,baseline2,zoom2' -or (@($cmdPlan.analyzerExpectedStateRoles) -join ',') -ne 'baseline,active,baseline,active') {
            throw "CMD wrapper plan did not preserve expected nameplate proof state sequence. States=$(@($cmdPlan.analyzerExpectedStates) -join ','), Roles=$(@($cmdPlan.analyzerExpectedStateRoles) -join ',')."
        }
        if ([int]$cmdPlan.maxHits -ne 24 -or [string]$cmdPlan.textPointerScanMode -ne 'allHits' -or [bool]$cmdPlan.skipPointerScan) {
            throw "CMD wrapper default scan plan drifted. maxHits=$($cmdPlan.maxHits), textPointerScanMode=$($cmdPlan.textPointerScanMode), skipPointerScan=$($cmdPlan.skipPointerScan)."
        }
        if ((Test-Path -LiteralPath $cmdPlanOnlyOutputRoot) -or (Test-Path -LiteralPath ([string]$cmdPlan.runRoot))) {
            throw "CMD wrapper PlanOnly unexpectedly created artifacts. OutputRoot=$cmdPlanOnlyOutputRoot, RunRoot=$($cmdPlan.runRoot)."
        }
        Add-Check -Name 'nameplate-cmd-wrapper-plan' -Status 'passed' -Detail 'CMD wrapper preserved screenshot-gated capture, fail-closed analysis defaults, expected state sequence, key arguments, and plan-only no-artifact behavior.' -Data $cmdPlan
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
        if (-not @($selfCmdChecks | Where-Object { $_.name -eq 'capture-project-build' -and $_.status -eq 'skipped' })) {
            throw "Validator CMD wrapper smoke did not skip capture-project-build as expected.`n$($selfCmdOutput -join [Environment]::NewLine)"
        }
        if (-not @($selfCmdChecks | Where-Object { $_.name -eq 'nameplate-cmd-wrapper-plan' -and $_.status -eq 'skipped' })) {
            throw "Validator CMD wrapper smoke did not skip recursive nameplate CMD wrapper smoke as expected.`n$($selfCmdOutput -join [Environment]::NewLine)"
        }
        if (-not @($selfCmdChecks | Where-Object { $_.name -eq 'validator-cmd-wrapper-smoke' -and $_.status -eq 'skipped' })) {
            throw "Validator CMD wrapper smoke did not skip recursive validator CMD wrapper smoke as expected.`n$($selfCmdOutput -join [Environment]::NewLine)"
        }
        if (-not @($selfCmdChecks | Where-Object { $_.name -eq 'analyzer-visual-gate-smoke' -and $_.status -eq 'skipped' })) {
            throw "Validator CMD wrapper smoke did not skip local artifact smoke as expected.`n$($selfCmdOutput -join [Environment]::NewLine)"
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

    $nullValueSmokeRoot = Join-Path ([System.IO.Path]::GetTempPath()) ('riftreader-projection-null-view-values-{0}' -f ([guid]::NewGuid().ToString('N')))
    New-Item -ItemType Directory -Path $nullValueSmokeRoot -Force | Out-Null
    try {
        $nullValueRows = @(
            [pscustomobject][ordered]@{
                state = 'baseline'
                stateRole = 'baseline'
                isActiveState = $false
                candidateAddress = $CandidateAddress
                windowStart = $CandidateAddress
                bytesHex = '0000C07F'
            },
            [pscustomobject][ordered]@{
                state = 'active'
                stateRole = 'active'
                isActiveState = $true
                candidateAddress = $CandidateAddress
                windowStart = $CandidateAddress
                bytesHex = '0000C07F'
            }
        )
        $nullValueRows | ForEach-Object { $_ | ConvertTo-Json -Compress -Depth 8 } | Set-Content -LiteralPath (Join-Path $nullValueSmokeRoot 'samples.ndjson') -Encoding UTF8

        $nullValueOutput = & pwsh -NoProfile -ExecutionPolicy Bypass -File $analyzerScript -InputDirectory $nullValueSmokeRoot -BaselineStateRegex '^baseline' -ActiveStateRegex '^active' -BaselineLabel baseline -ActiveLabel active -Json 2>&1
        $nullValueCode = $LASTEXITCODE
        if ($nullValueCode -ne 0) {
            throw "Analyzer failed when a view returned null values for every sample. ExitCode=$nullValueCode`n$($nullValueOutput -join [Environment]::NewLine)"
        }

        $nullValueAnalysis = ($nullValueOutput -join [Environment]::NewLine) | ConvertFrom-Json -Depth 40
        if ([int]$nullValueAnalysis.sampleCount -ne 2) {
            throw "Analyzer null-value smoke returned unexpected sampleCount=$($nullValueAnalysis.sampleCount).`n$($nullValueOutput -join [Environment]::NewLine)"
        }

        Add-Check -Name 'analyzer-null-view-values-smoke' -Status 'passed' -Detail 'Analyzer tolerates offsets whose view value is null for every baseline/active sample.' -Data ([ordered]@{ sampleCount = $nullValueAnalysis.sampleCount; candidateCount = $nullValueAnalysis.candidateCount })
    }
    finally {
        if (Test-Path -LiteralPath $nullValueSmokeRoot) {
            Remove-Item -LiteralPath $nullValueSmokeRoot -Recurse -Force
        }
    }

    $negativeSmokeRoot = Join-Path ([System.IO.Path]::GetTempPath()) ('riftreader-projection-no-screenshot-{0}' -f ([guid]::NewGuid().ToString('N')))
    New-Item -ItemType Directory -Path $negativeSmokeRoot -Force | Out-Null
    try {
        $negativeRows = @(
            [pscustomobject][ordered]@{
                state = 'baseline'
                stateRole = 'baseline'
                isActiveState = $false
                candidateAddress = $CandidateAddress
                windowStart = $CandidateAddress
                bytesHex = '0000000000000000'
            },
            [pscustomobject][ordered]@{
                state = 'active'
                stateRole = 'active'
                isActiveState = $true
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

    $partialSmokeRoot = Join-Path ([System.IO.Path]::GetTempPath()) ('riftreader-projection-partial-screenshot-{0}' -f ([guid]::NewGuid().ToString('N')))
    New-Item -ItemType Directory -Path $partialSmokeRoot -Force | Out-Null
    try {
        $partialStateRoot = Join-Path $partialSmokeRoot 'states\baseline'
        $partialScreenshotRoot = Join-Path $partialStateRoot 'screenshots'
        New-Item -ItemType Directory -Path $partialScreenshotRoot -Force | Out-Null
        $partialCapturePath = Join-Path $partialScreenshotRoot 'baseline.capture.json'
        $partialImagePath = Join-Path $partialScreenshotRoot 'baseline.bmp'
        Set-Content -LiteralPath $partialImagePath -Value 'smoke' -Encoding ASCII
        [pscustomobject][ordered]@{
            ok = $true
            exitCode = 0
            outputPath = $partialImagePath
            requiredUsable = $true
            json = [pscustomobject][ordered]@{
                Ok = $true
                Usable = $true
                CaptureMethod = 'validator-smoke'
                ContentBlackPixelRatio = 0.01
                ContentLumaStdDev = 12.0
            }
        } | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $partialCapturePath -Encoding UTF8

        $partialRows = @(
            [pscustomobject][ordered]@{
                state = 'baseline'
                stateRole = 'baseline'
                isActiveState = $false
                candidateAddress = $CandidateAddress
                windowStart = $CandidateAddress
                bytesHex = '0000000000000000'
                files = [pscustomobject][ordered]@{
                    screenshotCapture = $partialCapturePath
                    screenshotOutput = $partialImagePath
                }
            },
            [pscustomobject][ordered]@{
                state = 'active'
                stateRole = 'active'
                isActiveState = $true
                candidateAddress = $CandidateAddress
                windowStart = $CandidateAddress
                bytesHex = '0100000000000000'
            }
        )
        $partialRows | ForEach-Object { $_ | ConvertTo-Json -Compress -Depth 8 } | Set-Content -LiteralPath (Join-Path $partialSmokeRoot 'samples.ndjson') -Encoding UTF8

        $partialOutput = & pwsh -NoProfile -ExecutionPolicy Bypass -File $analyzerScript -InputDirectory $partialSmokeRoot -BaselineStateRegex '^baseline' -ActiveStateRegex '^active' -BaselineLabel baseline -ActiveLabel active -RequireVisualGate -ExpectedStates baseline,active -ExpectedStateRoles baseline,active -Json 2>&1
        $partialCode = $LASTEXITCODE
        if ($partialCode -eq 0) {
            throw "Analyzer RequireVisualGate unexpectedly passed with partial screenshot coverage.`n$($partialOutput -join [Environment]::NewLine)"
        }

        $partialScreenshotGatePath = Join-Path $partialSmokeRoot 'diffs\screenshot-gate.json'
        if (-not (Test-Path -LiteralPath $partialScreenshotGatePath -PathType Leaf)) {
            throw "Analyzer partial screenshot smoke failed before writing screenshot-gate evidence.`n$($partialOutput -join [Environment]::NewLine)"
        }

        $partialScreenshotGate = Get-Content -LiteralPath $partialScreenshotGatePath -Raw | ConvertFrom-Json -Depth 32
        $partialStatus = [string]$partialScreenshotGate.screenshotGate.visualGateStatus
        if ($partialStatus -ne 'failed-or-partial') {
            throw "Analyzer partial screenshot smoke failed with unexpected visualGateStatus=$partialStatus.`n$($partialOutput -join [Environment]::NewLine)"
        }
        if ([bool]$partialScreenshotGate.screenshotGate.allSamplesHaveUsableCapture) {
            throw "Analyzer partial screenshot smoke unexpectedly reported allSamplesHaveUsableCapture=true.`n$($partialOutput -join [Environment]::NewLine)"
        }
        $partialRowsOut = @($partialScreenshotGate.screenshotGate.rows)
        if (-not @($partialRowsOut | Where-Object { $_.originalState -eq 'baseline' -and $_.stateRole -eq 'baseline' -and $_.isActiveState -eq $false })) {
            throw "Analyzer screenshot gate did not preserve baseline originalState/stateRole/isActiveState.`n$($partialOutput -join [Environment]::NewLine)"
        }
        if (-not @($partialRowsOut | Where-Object { $_.originalState -eq 'active' -and $_.stateRole -eq 'active' -and $_.isActiveState -eq $true })) {
            throw "Analyzer screenshot gate did not preserve active originalState/stateRole/isActiveState.`n$($partialOutput -join [Environment]::NewLine)"
        }
        $partialExpectedSequence = $partialScreenshotGate.screenshotGate.expectedStateSequence
        if ($null -eq $partialExpectedSequence -or -not [bool]$partialExpectedSequence.passed) {
            throw "Analyzer expected state sequence audit did not pass for matching synthetic states.`n$($partialOutput -join [Environment]::NewLine)"
        }

        Add-Check -Name 'analyzer-visual-gate-partial-smoke' -Status 'passed' -Detail 'Analyzer RequireVisualGate fails closed when only some samples include usable screenshot captures and preserves proof state labels/roles.' -Data ([ordered]@{ visualGateStatus = $partialStatus; allSamplesHaveUsableCapture = $partialScreenshotGate.screenshotGate.allSamplesHaveUsableCapture; proofStateRolesPreserved = $true; expectedStateSequencePassed = $partialExpectedSequence.passed })
    }
    finally {
        if (Test-Path -LiteralPath $partialSmokeRoot) {
            Remove-Item -LiteralPath $partialSmokeRoot -Recurse -Force
        }
    }

    $sequenceSmokeRoot = Join-Path ([System.IO.Path]::GetTempPath()) ('riftreader-projection-sequence-mismatch-{0}' -f ([guid]::NewGuid().ToString('N')))
    New-Item -ItemType Directory -Path $sequenceSmokeRoot -Force | Out-Null
    try {
        $sequenceRows = @()
        foreach ($sequenceState in @(
            [pscustomobject][ordered]@{ Name = 'baseline'; Role = 'baseline'; Active = $false; Hex = '0000000000000000' },
            [pscustomobject][ordered]@{ Name = 'active'; Role = 'active'; Active = $true; Hex = '0100000000000000' }
        )) {
            $sequenceStateRoot = Join-Path $sequenceSmokeRoot ('states\{0}' -f $sequenceState.Name)
            $sequenceScreenshotRoot = Join-Path $sequenceStateRoot 'screenshots'
            New-Item -ItemType Directory -Path $sequenceScreenshotRoot -Force | Out-Null
            $sequenceCapturePath = Join-Path $sequenceScreenshotRoot ('{0}.capture.json' -f $sequenceState.Name)
            $sequenceImagePath = Join-Path $sequenceScreenshotRoot ('{0}.bmp' -f $sequenceState.Name)
            Set-Content -LiteralPath $sequenceImagePath -Value 'smoke' -Encoding ASCII
            [pscustomobject][ordered]@{
                ok = $true
                exitCode = 0
                outputPath = $sequenceImagePath
                requiredUsable = $true
                json = [pscustomobject][ordered]@{
                    Ok = $true
                    Usable = $true
                    CaptureMethod = 'validator-smoke'
                    ContentBlackPixelRatio = 0.01
                    ContentLumaStdDev = 12.0
                }
            } | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $sequenceCapturePath -Encoding UTF8

            $sequenceRows += [pscustomobject][ordered]@{
                state = $sequenceState.Name
                stateRole = $sequenceState.Role
                isActiveState = $sequenceState.Active
                candidateAddress = $CandidateAddress
                windowStart = $CandidateAddress
                bytesHex = $sequenceState.Hex
                files = [pscustomobject][ordered]@{
                    screenshotCapture = $sequenceCapturePath
                    screenshotOutput = $sequenceImagePath
                }
            }
        }
        $sequenceRows | ForEach-Object { $_ | ConvertTo-Json -Compress -Depth 8 } | Set-Content -LiteralPath (Join-Path $sequenceSmokeRoot 'samples.ndjson') -Encoding UTF8

        $sequenceOutput = & pwsh -NoProfile -ExecutionPolicy Bypass -File $analyzerScript -InputDirectory $sequenceSmokeRoot -BaselineStateRegex '^baseline' -ActiveStateRegex '^active' -BaselineLabel baseline -ActiveLabel active -RequireVisualGate -ExpectedStates baseline,zoom -ExpectedStateRoles baseline,active -Json 2>&1
        $sequenceCode = $LASTEXITCODE
        if ($sequenceCode -eq 0) {
            throw "Analyzer expected state sequence gate unexpectedly passed a mismatched sequence.`n$($sequenceOutput -join [Environment]::NewLine)"
        }

        $sequenceScreenshotGatePath = Join-Path $sequenceSmokeRoot 'diffs\screenshot-gate.json'
        if (-not (Test-Path -LiteralPath $sequenceScreenshotGatePath -PathType Leaf)) {
            throw "Analyzer sequence mismatch smoke failed before writing screenshot-gate evidence.`n$($sequenceOutput -join [Environment]::NewLine)"
        }

        $sequenceScreenshotGate = Get-Content -LiteralPath $sequenceScreenshotGatePath -Raw | ConvertFrom-Json -Depth 32
        if ([string]$sequenceScreenshotGate.screenshotGate.visualGateStatus -ne 'passed') {
            throw "Analyzer sequence mismatch smoke should have visualGateStatus=passed, got $($sequenceScreenshotGate.screenshotGate.visualGateStatus).`n$($sequenceOutput -join [Environment]::NewLine)"
        }
        if ($null -eq $sequenceScreenshotGate.screenshotGate.expectedStateSequence -or [bool]$sequenceScreenshotGate.screenshotGate.expectedStateSequence.passed) {
            throw "Analyzer sequence mismatch smoke did not fail the expectedStateSequence audit.`n$($sequenceOutput -join [Environment]::NewLine)"
        }

        Add-Check -Name 'analyzer-expected-state-sequence-negative-smoke' -Status 'passed' -Detail 'Analyzer fails closed when usable screenshots are present but the expected proof state sequence does not match.' -Data ([ordered]@{ visualGateStatus = $sequenceScreenshotGate.screenshotGate.visualGateStatus; expectedStateSequencePassed = $sequenceScreenshotGate.screenshotGate.expectedStateSequence.passed })

        $sequenceCheckOutput = & pwsh -NoProfile -ExecutionPolicy Bypass -File $resultCheckerScript -RunRoot $sequenceSmokeRoot -Json 2>&1
        $sequenceCheckCode = $LASTEXITCODE
        if ($sequenceCheckCode -eq 0) {
            throw "Nameplate proof result checker unexpectedly accepted a mismatched proof sequence.`n$($sequenceCheckOutput -join [Environment]::NewLine)"
        }
        $sequenceCheck = ($sequenceCheckOutput -join [Environment]::NewLine) | ConvertFrom-Json -Depth 40
        if ([bool]$sequenceCheck.ok) {
            throw "Nameplate proof result checker returned ok=true for a mismatched proof sequence.`n$($sequenceCheckOutput -join [Environment]::NewLine)"
        }
        if (-not @($sequenceCheck.checks | Where-Object { $_.name -eq 'expected-state-sequence-passed' -and $_.status -eq 'failed' })) {
            throw "Nameplate proof result checker did not fail expected-state-sequence-passed for a mismatched proof sequence.`n$($sequenceCheckOutput -join [Environment]::NewLine)"
        }

        Add-Check -Name 'nameplate-result-checker-sequence-negative-smoke' -Status 'passed' -Detail 'Post-capture result checker rejects usable screenshot artifacts when the expected proof sequence is wrong.'
    }
    finally {
        if (Test-Path -LiteralPath $sequenceSmokeRoot) {
            Remove-Item -LiteralPath $sequenceSmokeRoot -Recurse -Force
        }
    }

    $resultCheckRoot = Join-Path ([System.IO.Path]::GetTempPath()) ('riftreader-projection-result-check-{0}-nameplate-baseline-zoom' -f ([guid]::NewGuid().ToString('N')))
    $latestPairOutputRoot = $null
    $unsafeLatestPairOutputRoot = $null
    $quotedSeedOutputRoot = $null
    New-Item -ItemType Directory -Path $resultCheckRoot -Force | Out-Null
    try {
        $resultRows = @()
        foreach ($proofState in @(
            [pscustomobject][ordered]@{ Name = 'baseline1'; Role = 'baseline'; Active = $false; Hex = '0000000000000000' },
            [pscustomobject][ordered]@{ Name = 'zoom1'; Role = 'active'; Active = $true; Hex = '0100000000000000' },
            [pscustomobject][ordered]@{ Name = 'baseline2'; Role = 'baseline'; Active = $false; Hex = '0000000000000000' },
            [pscustomobject][ordered]@{ Name = 'zoom2'; Role = 'active'; Active = $true; Hex = '0100000000000000' }
        )) {
            $proofStateRoot = Join-Path $resultCheckRoot ('states\{0}' -f $proofState.Name)
            $proofScreenshotRoot = Join-Path $proofStateRoot 'screenshots'
            New-Item -ItemType Directory -Path $proofScreenshotRoot -Force | Out-Null
            $proofCapturePath = Join-Path $proofScreenshotRoot ('{0}.capture.json' -f $proofState.Name)
            $proofImagePath = Join-Path $proofScreenshotRoot ('{0}.bmp' -f $proofState.Name)
            Set-Content -LiteralPath $proofImagePath -Value 'smoke' -Encoding ASCII
            [pscustomobject][ordered]@{
                ok = $true
                exitCode = 0
                outputPath = $proofImagePath
                requiredUsable = $true
                json = [pscustomobject][ordered]@{
                    Ok = $true
                    Usable = $true
                    CaptureMethod = 'validator-smoke'
                    ContentBlackPixelRatio = 0.01
                    ContentLumaStdDev = 12.0
                }
            } | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $proofCapturePath -Encoding UTF8

            $resultRows += [pscustomobject][ordered]@{
                state = $proofState.Name
                stateRole = $proofState.Role
                isActiveState = $proofState.Active
                candidateAddress = $CandidateAddress
                windowStart = $CandidateAddress
                bytesHex = $proofState.Hex
                tooltipTextHitAddresses = @(
                    '0X1000',
                    ('0X{0:X}' -f (0x2000 + $resultRows.Count))
                )
                knownTextPointers = @(
                    [pscustomobject][ordered]@{
                        tooltipTextAddress = '0X1000'
                        pointerScanFile = Join-Path $proofStateRoot 'scan-pointer-0x1000.json'
                        pointerHitAddresses = @('0X9000')
                    }
                )
                files = [pscustomobject][ordered]@{
                    screenshotCapture = $proofCapturePath
                    screenshotOutput = $proofImagePath
                }
            }
        }
        $resultRows | ForEach-Object { $_ | ConvertTo-Json -Compress -Depth 8 } | Set-Content -LiteralPath (Join-Path $resultCheckRoot 'samples.ndjson') -Encoding UTF8

        $resultAnalysisOutput = & pwsh -NoProfile -ExecutionPolicy Bypass -File $analyzerScript -InputDirectory $resultCheckRoot -BaselineStateRegex '^baseline' -ActiveStateRegex '^zoom' -BaselineLabel baseline -ActiveLabel zoom -RequireVisualGate -ExpectedStates baseline1,zoom1,baseline2,zoom2 -ExpectedStateRoles baseline,active,baseline,active -Json 2>&1
        $resultAnalysisCode = $LASTEXITCODE
        if ($resultAnalysisCode -ne 0) {
            throw "Analyzer result-check fixture failed with exit code $resultAnalysisCode.`n$($resultAnalysisOutput -join [Environment]::NewLine)"
        }

        $resultCheckOutput = & pwsh -NoProfile -ExecutionPolicy Bypass -File $resultCheckerScript -RunRoot $resultCheckRoot -Json 2>&1
        $resultCheckCode = $LASTEXITCODE
        if ($resultCheckCode -ne 0) {
            throw "Nameplate proof result checker failed with exit code $resultCheckCode.`n$($resultCheckOutput -join [Environment]::NewLine)"
        }
        $resultCheck = ($resultCheckOutput -join [Environment]::NewLine) | ConvertFrom-Json -Depth 40
        if (-not [bool]$resultCheck.ok) {
            throw "Nameplate proof result checker returned ok=false.`n$($resultCheckOutput -join [Environment]::NewLine)"
        }
        if (-not @($resultCheck.checks | Where-Object { $_.name -eq 'expected-state-sequence-passed' -and $_.status -eq 'passed' })) {
            throw "Nameplate proof result checker did not pass expected-state-sequence-passed.`n$($resultCheckOutput -join [Environment]::NewLine)"
        }

        $resultFieldCandidatesPath = Join-Path $resultCheckRoot 'diffs\field-candidates.json'
        $resultFieldCandidates = Get-Content -LiteralPath $resultFieldCandidatesPath -Raw | ConvertFrom-Json -Depth 40
        $firstCandidateOffset = [string](@($resultFieldCandidates.candidates)[0].offset)
        if ([string]::IsNullOrWhiteSpace($firstCandidateOffset)) {
            throw "Nameplate proof result checker fixture did not produce a candidate offset for comparator smoke."
        }

        $compareOutput = & pwsh -NoProfile -ExecutionPolicy Bypass -File $proofCompareScript -BaselineRunRoot $resultCheckRoot -ReproofRunRoot $resultCheckRoot -CandidateOffsets $firstCandidateOffset -MinRepeatCount 1 -Json 2>&1
        $compareCode = $LASTEXITCODE
        if ($compareCode -ne 0) {
            throw "Nameplate proof comparator failed with exit code $compareCode.`n$($compareOutput -join [Environment]::NewLine)"
        }
        $compare = ($compareOutput -join [Environment]::NewLine) | ConvertFrom-Json -Depth 60
        if (-not [bool]$compare.ok -or [int]$compare.repeatedCount -lt 1) {
            throw "Nameplate proof comparator did not report a repeated candidate for identical fixture roots.`n$($compareOutput -join [Environment]::NewLine)"
        }
        if (-not @($compare.checks | Where-Object { $_.name -eq 'minimum-repeat-count' -and $_.status -eq 'passed' })) {
            throw "Nameplate proof comparator did not pass minimum-repeat-count.`n$($compareOutput -join [Environment]::NewLine)"
        }

        Add-Check -Name 'nameplate-proof-comparator-smoke' -Status 'passed' -Detail 'Proof comparator accepts a fully gated fixture and reports a repeated candidate offset across baseline/reproof roots.' -Data ([ordered]@{ repeatedCount = $compare.repeatedCount; candidateOffsets = @($compare.candidateOffsets) })

        $byteWindowOutput = & pwsh -NoProfile -ExecutionPolicy Bypass -File $byteWindowCompareScript -BaselineRunRoot $resultCheckRoot -ReproofRunRoot $resultCheckRoot -Length 8 -Json 2>&1
        $byteWindowCode = $LASTEXITCODE
        if ($byteWindowCode -ne 0) {
            throw "Nameplate byte-window comparator failed with exit code $byteWindowCode.`n$($byteWindowOutput -join [Environment]::NewLine)"
        }
        $byteWindow = ($byteWindowOutput -join [Environment]::NewLine) | ConvertFrom-Json -Depth 80
        if (-not [bool]$byteWindow.ok -or [int]$byteWindow.counts.repeatedChanging -lt 1) {
            throw "Nameplate byte-window comparator did not report repeated changing offsets for identical fixture roots.`n$($byteWindowOutput -join [Environment]::NewLine)"
        }
        if (-not @($byteWindow.checks | Where-Object { $_.name -eq 'state-sequence-match' -and $_.status -eq 'passed' })) {
            throw "Nameplate byte-window comparator did not pass state-sequence-match.`n$($byteWindowOutput -join [Environment]::NewLine)"
        }

        Add-Check -Name 'nameplate-byte-window-comparator-smoke' -Status 'passed' -Detail 'Byte-window comparator accepts a fully gated fixture and reports repeated changing offsets for identical roots.' -Data ([ordered]@{ repeatedChanging = $byteWindow.counts.repeatedChanging; comparedOffsets = $byteWindow.counts.comparedOffsets })

        $leadOutput = & pwsh -NoProfile -ExecutionPolicy Bypass -File $leadExtractorScript -RunRoot $resultCheckRoot -Json 2>&1
        $leadCode = $LASTEXITCODE
        if ($leadCode -ne 0) {
            throw "Nameplate proof lead extractor failed with exit code $leadCode.`n$($leadOutput -join [Environment]::NewLine)"
        }
        $leadResult = ($leadOutput -join [Environment]::NewLine) | ConvertFrom-Json -Depth 80
        if (-not [bool]$leadResult.ok -or -not [bool]$leadResult.gated.passed) {
            throw "Nameplate proof lead extractor did not preserve gated proof status.`n$($leadOutput -join [Environment]::NewLine)"
        }
        if ([int]$leadResult.textLeadCount -lt 1 -or [int]$leadResult.pointerHitLeadCount -lt 1) {
            throw "Nameplate proof lead extractor did not report expected text and pointer-hit leads.`n$($leadOutput -join [Environment]::NewLine)"
        }
        if (-not @($leadResult.pointerHitLeads | Where-Object { $_.address -eq '0X9000' -and [int]$_.stateCount -eq 4 })) {
            throw "Nameplate proof lead extractor did not aggregate repeated pointer-hit lead 0X9000 across four states.`n$($leadOutput -join [Environment]::NewLine)"
        }

        Add-Check -Name 'nameplate-proof-lead-extractor-smoke' -Status 'passed' -Detail 'Lead extractor aggregates repeated text and pointer-hit leads from a fully gated fixture.' -Data ([ordered]@{ textLeadCount = $leadResult.textLeadCount; pointerHitLeadCount = $leadResult.pointerHitLeadCount })

        $leadNeighborhoodOutputFile = Join-Path $resultCheckRoot 'lead-neighborhoods\validator-smoke.json'
        $leadNeighborhoodOutput = & pwsh -NoProfile -ExecutionPolicy Bypass -File $leadNeighborhoodScript -RunRoot $resultCheckRoot -OutputFile $leadNeighborhoodOutputFile -PlanOnly -Json 2>&1
        $leadNeighborhoodCode = $LASTEXITCODE
        if ($leadNeighborhoodCode -ne 0) {
            throw "Nameplate proof lead-neighborhood PlanOnly failed with exit code $leadNeighborhoodCode.`n$($leadNeighborhoodOutput -join [Environment]::NewLine)"
        }
        $leadNeighborhoodPlan = ($leadNeighborhoodOutput -join [Environment]::NewLine) | ConvertFrom-Json -Depth 80
        if (-not [bool]$leadNeighborhoodPlan.ok -or [string]$leadNeighborhoodPlan.mode -ne 'plan-only' -or [bool]$leadNeighborhoodPlan.controlsInput -or [bool]$leadNeighborhoodPlan.attachesToProcess) {
            throw "Nameplate proof lead-neighborhood PlanOnly did not preserve no-input/no-attach semantics.`n$($leadNeighborhoodOutput -join [Environment]::NewLine)"
        }
        if ((Test-Path -LiteralPath $leadNeighborhoodOutputFile) -or (Test-Path -LiteralPath (Split-Path -Parent $leadNeighborhoodOutputFile))) {
            throw "Nameplate proof lead-neighborhood PlanOnly unexpectedly created artifacts. OutputFile=$leadNeighborhoodOutputFile."
        }
        $selectedNeighborhoodLeads = @($leadNeighborhoodPlan.leadSelection.selectedLeads)
        if ($selectedNeighborhoodLeads.Count -lt 1 -or -not @($selectedNeighborhoodLeads | Where-Object { $_.address -eq '0X9000' -and $_.kind -eq 'pointer-hit-address' })) {
            throw "Nameplate proof lead-neighborhood PlanOnly did not select repeated pointer-hit lead 0X9000.`n$($leadNeighborhoodOutput -join [Environment]::NewLine)"
        }
        if ([int]$leadNeighborhoodPlan.capturePlan.readLength -ne 256 -or [int]$leadNeighborhoodPlan.capturePlan.followPointerDepth -ne 1) {
            throw "Nameplate proof lead-neighborhood PlanOnly defaults drifted. ReadLength=$($leadNeighborhoodPlan.capturePlan.readLength), FollowPointerDepth=$($leadNeighborhoodPlan.capturePlan.followPointerDepth)."
        }

        Add-Check -Name 'nameplate-proof-lead-neighborhood-plan-smoke' -Status 'passed' -Detail 'Lead-neighborhood capture wrapper plans selected pointer-hit roots from a fully gated proof without attaching or creating artifacts.' -Data ([ordered]@{ selectedLeadCount = $leadNeighborhoodPlan.leadSelection.selectedLeadCount; readLength = $leadNeighborhoodPlan.capturePlan.readLength; followPointerDepth = $leadNeighborhoodPlan.capturePlan.followPointerDepth })

        $leadNeighborhoodCompareRoot = Join-Path $resultCheckRoot 'lead-neighborhood-compare-smoke'
        New-Item -ItemType Directory -Path $leadNeighborhoodCompareRoot -Force | Out-Null
        $baselineNeighborhoodFile = Join-Path $leadNeighborhoodCompareRoot 'baseline.json'
        $reproofNeighborhoodFile = Join-Path $leadNeighborhoodCompareRoot 'reproof.json'
        $syntheticNeighborhood = [pscustomobject][ordered]@{
            mode = 'capture'
            ok = $true
            controlsInput = $false
            leadSelection = [pscustomobject][ordered]@{
                selectedLeads = @(
                    [pscustomobject][ordered]@{
                        kind = 'pointer-hit-address'
                        address = '0X9000'
                        states = @('baseline1', 'zoom1')
                    }
                )
            }
            pointerSubgraph = [pscustomobject][ordered]@{
                nodeCount = 2
                edgeCount = 1
                nodes = @(
                    [pscustomobject][ordered]@{
                        address = '0X9000'
                        depth = 0
                        rootLabels = @('pointer-hit-address:0X9000')
                        asciiPreview = 'root'
                    },
                    [pscustomobject][ordered]@{
                        address = '0X9010'
                        depth = 1
                        rootLabels = @('pointer-hit-address:0X9000')
                        asciiPreview = 'child'
                    }
                )
                edges = @(
                    [pscustomobject][ordered]@{
                        fromAddress = '0X9000'
                        toAddress = '0X9010'
                        sourceOffsetHex = '0x8'
                    }
                )
            }
        }
        $syntheticNeighborhood | ConvertTo-Json -Depth 24 | Set-Content -LiteralPath $baselineNeighborhoodFile -Encoding UTF8
        $syntheticNeighborhood | ConvertTo-Json -Depth 24 | Set-Content -LiteralPath $reproofNeighborhoodFile -Encoding UTF8

        $leadNeighborhoodCompareOutput = & pwsh -NoProfile -ExecutionPolicy Bypass -File $leadNeighborhoodCompareScript -BaselineFile $baselineNeighborhoodFile -ReproofFile $reproofNeighborhoodFile -MinRepeatedRootCount 1 -MinRepeatedEdgeCount 1 -Json 2>&1
        $leadNeighborhoodCompareCode = $LASTEXITCODE
        if ($leadNeighborhoodCompareCode -ne 0) {
            throw "Nameplate proof lead-neighborhood comparator failed with exit code $leadNeighborhoodCompareCode.`n$($leadNeighborhoodCompareOutput -join [Environment]::NewLine)"
        }
        $leadNeighborhoodCompare = ($leadNeighborhoodCompareOutput -join [Environment]::NewLine) | ConvertFrom-Json -Depth 80
        if (-not [bool]$leadNeighborhoodCompare.ok -or [int]$leadNeighborhoodCompare.counts.repeatedSelectedRoots -lt 1 -or [int]$leadNeighborhoodCompare.counts.repeatedEdges -lt 1) {
            throw "Nameplate proof lead-neighborhood comparator did not report repeated roots/edges for identical fixture files.`n$($leadNeighborhoodCompareOutput -join [Environment]::NewLine)"
        }
        if ($null -eq $leadNeighborhoodCompare.candidateSummary -or -not [bool]$leadNeighborhoodCompare.candidateSummary.promotionReady) {
            throw "Nameplate proof lead-neighborhood comparator did not report promotion-ready candidate summary for identical fixture files.`n$($leadNeighborhoodCompareOutput -join [Environment]::NewLine)"
        }
        if (-not @($leadNeighborhoodCompare.candidateSummary.recommendedRoots | Where-Object { $_.address -eq '0X9000' })) {
            throw "Nameplate proof lead-neighborhood comparator candidate summary did not include repeated root 0X9000.`n$($leadNeighborhoodCompareOutput -join [Environment]::NewLine)"
        }
        if (-not @($leadNeighborhoodCompare.checks | Where-Object { $_.name -eq 'minimum-repeated-selected-roots' -and $_.status -eq 'passed' })) {
            throw "Nameplate proof lead-neighborhood comparator did not pass minimum-repeated-selected-roots.`n$($leadNeighborhoodCompareOutput -join [Environment]::NewLine)"
        }

        Add-Check -Name 'nameplate-proof-lead-neighborhood-comparator-smoke' -Status 'passed' -Detail 'Lead-neighborhood comparator reports repeated selected roots, pointer edges, and promotion candidate summaries across captured neighborhood artifacts.' -Data ([ordered]@{ repeatedSelectedRoots = $leadNeighborhoodCompare.counts.repeatedSelectedRoots; repeatedEdges = $leadNeighborhoodCompare.counts.repeatedEdges; promotionReady = $leadNeighborhoodCompare.candidateSummary.promotionReady })

        $promotionPacketOutputFile = Join-Path $leadNeighborhoodCompareRoot 'promotion-packet.json'
        $promotionPacketOutput = & pwsh -NoProfile -ExecutionPolicy Bypass -File $promotionPacketScript -BaselineFile $baselineNeighborhoodFile -ReproofFile $reproofNeighborhoodFile -OutputFile $promotionPacketOutputFile -MinRepeatedRootCount 1 -MinRepeatedEdgeCount 1 -Json 2>&1
        $promotionPacketCode = $LASTEXITCODE
        if ($promotionPacketCode -ne 0) {
            throw "Nameplate proof promotion packet writer failed with exit code $promotionPacketCode.`n$($promotionPacketOutput -join [Environment]::NewLine)"
        }
        if (-not (Test-Path -LiteralPath $promotionPacketOutputFile -PathType Leaf)) {
            throw "Nameplate proof promotion packet writer did not create expected packet: $promotionPacketOutputFile"
        }
        $promotionPacketResult = ($promotionPacketOutput -join [Environment]::NewLine) | ConvertFrom-Json -Depth 80
        $promotionPacket = Get-Content -LiteralPath $promotionPacketOutputFile -Raw | ConvertFrom-Json -Depth 100
        if (-not [bool]$promotionPacketResult.ok -or -not [bool]$promotionPacketResult.wrotePacket -or -not [bool]$promotionPacket.promotionReady) {
            throw "Nameplate proof promotion packet writer did not report/write a promotion-ready packet.`n$($promotionPacketOutput -join [Environment]::NewLine)"
        }
        if (-not @($promotionPacket.recommendedRoots | Where-Object { $_.address -eq '0X9000' })) {
            throw "Nameplate proof promotion packet did not include repeated root 0X9000."
        }

        Add-Check -Name 'nameplate-proof-promotion-packet-smoke' -Status 'passed' -Detail 'Promotion packet writer emits a durable packet only after comparator candidate-summary gates are promotion-ready.' -Data ([ordered]@{ recommendedRootCount = $promotionPacketResult.recommendedRootCount; recommendedEdgeCount = $promotionPacketResult.recommendedEdgeCount; outputFileExists = $true })

        $notReadyPromotionPacketOutputFile = Join-Path $leadNeighborhoodCompareRoot 'promotion-packet-not-ready.json'
        $notReadyPromotionPacketOutput = & pwsh -NoProfile -ExecutionPolicy Bypass -File $promotionPacketScript -BaselineFile $baselineNeighborhoodFile -ReproofFile $reproofNeighborhoodFile -OutputFile $notReadyPromotionPacketOutputFile -MinRepeatedRootCount 2 -MinRepeatedEdgeCount 1 -Json 2>&1
        $notReadyPromotionPacketCode = $LASTEXITCODE
        if ($notReadyPromotionPacketCode -eq 0) {
            throw "Nameplate proof promotion packet writer unexpectedly succeeded when MinRepeatedRootCount exceeded fixture evidence.`n$($notReadyPromotionPacketOutput -join [Environment]::NewLine)"
        }
        if (Test-Path -LiteralPath $notReadyPromotionPacketOutputFile -PathType Leaf) {
            throw "Nameplate proof promotion packet writer created a packet despite not-ready gates: $notReadyPromotionPacketOutputFile"
        }
        $notReadyPromotionPacketResult = ($notReadyPromotionPacketOutput -join [Environment]::NewLine) | ConvertFrom-Json -Depth 80
        if ([bool]$notReadyPromotionPacketResult.ok -or [bool]$notReadyPromotionPacketResult.promotionReady -or [bool]$notReadyPromotionPacketResult.wrotePacket) {
            throw "Nameplate proof promotion packet writer did not report fail-closed not-ready semantics.`n$($notReadyPromotionPacketOutput -join [Environment]::NewLine)"
        }
        if (-not @($notReadyPromotionPacketResult.blockers | Where-Object { $_ -eq 'insufficient-repeated-selected-roots' })) {
            throw "Nameplate proof promotion packet writer did not report the expected insufficient root blocker.`n$($notReadyPromotionPacketOutput -join [Environment]::NewLine)"
        }

        Add-Check -Name 'nameplate-proof-promotion-packet-negative-smoke' -Status 'passed' -Detail 'Promotion packet writer fails closed and does not write a packet when repeated-root thresholds are not met.' -Data ([ordered]@{ wrotePacket = $false; expectedBlocker = 'insufficient-repeated-selected-roots'; exitCode = $notReadyPromotionPacketCode })

        $promotionPipelinePlanOutputFile = Join-Path $leadNeighborhoodCompareRoot 'pipeline-plan-packet.json'
        $promotionPipelinePlanOutput = & pwsh -NoProfile -ExecutionPolicy Bypass -File $promotionPipelineScript -BaselineFile $baselineNeighborhoodFile -ReproofFile $reproofNeighborhoodFile -OutputFile $promotionPipelinePlanOutputFile -MinRepeatedRootCount 1 -MinRepeatedEdgeCount 1 -PlanOnly -Json 2>&1
        $promotionPipelinePlanCode = $LASTEXITCODE
        if ($promotionPipelinePlanCode -ne 0) {
            throw "Nameplate proof promotion pipeline PlanOnly failed with exit code $promotionPipelinePlanCode.`n$($promotionPipelinePlanOutput -join [Environment]::NewLine)"
        }
        $promotionPipelinePlan = ($promotionPipelinePlanOutput -join [Environment]::NewLine) | ConvertFrom-Json -Depth 80
        if ([string]$promotionPipelinePlan.mode -ne 'plan-only' -or -not [bool]$promotionPipelinePlan.ok -or [bool]$promotionPipelinePlan.controlsInput -or [bool]$promotionPipelinePlan.attachesToProcess) {
            throw "Nameplate proof promotion pipeline PlanOnly did not preserve no-input/no-attach semantics.`n$($promotionPipelinePlanOutput -join [Environment]::NewLine)"
        }
        if (Test-Path -LiteralPath $promotionPipelinePlanOutputFile -PathType Leaf) {
            throw "Nameplate proof promotion pipeline PlanOnly unexpectedly created output: $promotionPipelinePlanOutputFile"
        }

        $promotionPipelineOutputFile = Join-Path $leadNeighborhoodCompareRoot 'pipeline-promotion-packet.json'
        $promotionPipelineOutput = & pwsh -NoProfile -ExecutionPolicy Bypass -File $promotionPipelineScript -BaselineFile $baselineNeighborhoodFile -ReproofFile $reproofNeighborhoodFile -OutputFile $promotionPipelineOutputFile -MinRepeatedRootCount 1 -MinRepeatedEdgeCount 1 -Json 2>&1
        $promotionPipelineCode = $LASTEXITCODE
        if ($promotionPipelineCode -ne 0) {
            throw "Nameplate proof promotion pipeline failed with exit code $promotionPipelineCode.`n$($promotionPipelineOutput -join [Environment]::NewLine)"
        }
        $promotionPipeline = ($promotionPipelineOutput -join [Environment]::NewLine) | ConvertFrom-Json -Depth 100
        if (-not [bool]$promotionPipeline.ok -or -not [bool]$promotionPipeline.packet.promotionReady -or -not (Test-Path -LiteralPath $promotionPipelineOutputFile -PathType Leaf)) {
            throw "Nameplate proof promotion pipeline did not write a promotion-ready packet.`n$($promotionPipelineOutput -join [Environment]::NewLine)"
        }

        Add-Check -Name 'nameplate-proof-promotion-pipeline-smoke' -Status 'passed' -Detail 'Promotion pipeline plans without input/attach side effects and writes a promotion packet from existing lead-neighborhood artifacts.' -Data ([ordered]@{ planOnlyNoAttach = $true; wrotePacket = $promotionPipeline.packet.wrotePacket; outputFileExists = $true })

        $defaultLeadNeighborhoodDirectory = Join-Path $resultCheckRoot 'lead-neighborhoods'
        New-Item -ItemType Directory -Path $defaultLeadNeighborhoodDirectory -Force | Out-Null
        $defaultLeadNeighborhoodFile = Join-Path $defaultLeadNeighborhoodDirectory 'nameplate-proof-lead-neighborhoods.json'
        $defaultPromotionPacketFile = Join-Path $defaultLeadNeighborhoodDirectory 'nameplate-proof-promotion-packet.json'
        $syntheticNeighborhood | ConvertTo-Json -Depth 24 | Set-Content -LiteralPath $defaultLeadNeighborhoodFile -Encoding UTF8
        [pscustomobject][ordered]@{
            mode = 'nameplate-proof-promotion-packet'
            ok = $true
            promotionReady = $true
        } | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $defaultPromotionPacketFile -Encoding UTF8
        [pscustomobject][ordered]@{
            mode = 'capture'
            runLabel = 'nameplate-baseline-zoom'
            runRoot = $resultCheckRoot
            process = [pscustomobject][ordered]@{
                name = 'rift_x64'
            }
            candidateAddress = $CandidateAddress
            candidateLength = 1024
            tooltipText = $NameplateText
            createdUtc = '2026-04-24T00:00:00.0000000Z'
        } | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $resultCheckRoot 'manifest.json') -Encoding UTF8

        $latestPairOutputRoot = Join-Path ([System.IO.Path]::GetTempPath()) ('riftreader-latest-nameplate-pair-{0}' -f ([guid]::NewGuid().ToString('N')))
        $olderLatestPairRunRoot = Join-Path $latestPairOutputRoot '20260424-010000-nameplate-baseline-zoom'
        $newerLatestPairRunRoot = Join-Path $latestPairOutputRoot '20260424-020000-nameplate-baseline-zoom'
        foreach ($latestPairRunRoot in @($olderLatestPairRunRoot, $newerLatestPairRunRoot)) {
            New-Item -ItemType Directory -Path (Join-Path $latestPairRunRoot 'diffs') -Force | Out-Null
            New-Item -ItemType Directory -Path (Join-Path $latestPairRunRoot 'lead-neighborhoods') -Force | Out-Null
            Copy-Item -LiteralPath (Join-Path $resultCheckRoot 'samples.ndjson') -Destination (Join-Path $latestPairRunRoot 'samples.ndjson') -Force
            Copy-Item -LiteralPath (Join-Path $resultCheckRoot 'diffs\screenshot-gate.json') -Destination (Join-Path $latestPairRunRoot 'diffs\screenshot-gate.json') -Force
            Copy-Item -LiteralPath $defaultLeadNeighborhoodFile -Destination (Join-Path $latestPairRunRoot 'lead-neighborhoods\nameplate-proof-lead-neighborhoods.json') -Force
            [pscustomobject][ordered]@{
                mode = 'capture'
                runLabel = 'nameplate-baseline-zoom'
                runRoot = $latestPairRunRoot
                process = [pscustomobject][ordered]@{
                    name = 'rift_x64'
                }
                candidateAddress = $CandidateAddress
                candidateLength = 1024
                tooltipText = $NameplateText
                createdUtc = '2026-04-24T00:00:00.0000000Z'
            } | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $latestPairRunRoot 'manifest.json') -Encoding UTF8
        }
        (Get-Item -LiteralPath $olderLatestPairRunRoot).LastWriteTimeUtc = [datetime]'2026-04-24T01:00:00Z'
        (Get-Item -LiteralPath $newerLatestPairRunRoot).LastWriteTimeUtc = [datetime]'2026-04-24T02:00:00Z'

        $latestPairPlanOutput = & pwsh -NoProfile -ExecutionPolicy Bypass -File $promotionPipelineScript -OutputRoot $latestPairOutputRoot -LatestBaselineZoomPair -CaptureMissingNeighborhoods -PlanOnly -Json 2>&1
        $latestPairPlanCode = $LASTEXITCODE
        if ($latestPairPlanCode -ne 0) {
            throw "Nameplate proof promotion pipeline latest-pair PlanOnly failed with exit code $latestPairPlanCode.`n$($latestPairPlanOutput -join [Environment]::NewLine)"
        }
        $latestPairPlan = ($latestPairPlanOutput -join [Environment]::NewLine) | ConvertFrom-Json -Depth 100
        if (-not [bool]$latestPairPlan.ok -or [string]$latestPairPlan.mode -ne 'plan-only' -or [bool]$latestPairPlan.attachesToProcess -or $null -eq $latestPairPlan.selectedPair) {
            throw "Nameplate proof promotion pipeline latest-pair PlanOnly did not report the selected pair.`n$($latestPairPlanOutput -join [Environment]::NewLine)"
        }
        if ([string]$latestPairPlan.selectedPair.baselineRunRoot -ne $olderLatestPairRunRoot -or [string]$latestPairPlan.selectedPair.reproofRunRoot -ne $newerLatestPairRunRoot) {
            throw "Nameplate proof promotion pipeline latest-pair PlanOnly selected the wrong baseline/reproof order.`n$($latestPairPlanOutput -join [Environment]::NewLine)"
        }

        Add-Check -Name 'nameplate-proof-promotion-pipeline-latest-pair-smoke' -Status 'passed' -Detail 'Promotion pipeline can auto-select the latest two gated baseline/zoom proof roots in baseline-then-reproof order while preserving PlanOnly no-attach semantics.' -Data ([ordered]@{ baselineRunName = $latestPairPlan.selectedPair.baselineRunName; reproofRunName = $latestPairPlan.selectedPair.reproofRunName; selectedPairMode = $latestPairPlan.selectedPair.mode; planOnlyAttachesToProcess = $false })

        $latestPairPlannerOutput = & pwsh -NoProfile -ExecutionPolicy Bypass -File $promotionPlanScript -OutputRoot $latestPairOutputRoot -InventoryTop 5 -MinRepeatedRootCount 1 -MinRepeatedEdgeCount 1 -Json 2>&1
        $latestPairPlannerCode = $LASTEXITCODE
        if ($latestPairPlannerCode -ne 0) {
            throw "Nameplate proof promotion planner latest-pair fixture failed with exit code $latestPairPlannerCode.`n$($latestPairPlannerOutput -join [Environment]::NewLine)"
        }
        $latestPairPlanner = ($latestPairPlannerOutput -join [Environment]::NewLine) | ConvertFrom-Json -Depth 100
        if (-not [bool]$latestPairPlanner.readyForPipeline -or -not [bool]$latestPairPlanner.readyForPromotionCompare) {
            throw "Nameplate proof promotion planner did not mark the two-run latest-pair fixture ready for promotion compare.`n$($latestPairPlannerOutput -join [Environment]::NewLine)"
        }
        if ($null -eq $latestPairPlanner.nextAction -or [string]$latestPairPlanner.nextAction.name -ne 'promotion-pipeline-latest-pair-plan' -or [bool]$latestPairPlanner.nextAction.attachesToProcess -or -not [bool]$latestPairPlanner.nextAction.safeToRunNow) {
            throw "Nameplate proof promotion planner did not expose the expected safe latest-pair nextAction.`n$($latestPairPlannerOutput -join [Environment]::NewLine)"
        }
        if ([string]$latestPairPlanner.selectedBaselineRun.runRoot -ne $olderLatestPairRunRoot -or [string]$latestPairPlanner.selectedReproofRun.runRoot -ne $newerLatestPairRunRoot) {
            throw "Nameplate proof promotion planner selected the wrong baseline/reproof order for latest-pair fixture.`n$($latestPairPlannerOutput -join [Environment]::NewLine)"
        }
        if (-not @($latestPairPlanner.recommendedCommands | Where-Object { $_.name -eq 'promotion-pipeline-latest-pair-plan' })) {
            throw "Nameplate proof promotion planner did not recommend latest-pair pipeline plan for two-run fixture.`n$($latestPairPlannerOutput -join [Environment]::NewLine)"
        }
        $latestPairPipelinePlanCommand = @($latestPairPlanner.recommendedCommands | Where-Object { $_.name -eq 'promotion-pipeline-latest-pair-plan' }) | Select-Object -First 1
        $latestPairPipelineRunCommand = @($latestPairPlanner.recommendedCommands | Where-Object { $_.name -eq 'promotion-pipeline-latest-pair-run' }) | Select-Object -First 1
        if ($null -eq $latestPairPipelineRunCommand) {
            throw "Nameplate proof promotion planner did not recommend latest-pair pipeline run for two-run fixture.`n$($latestPairPlannerOutput -join [Environment]::NewLine)"
        }
        if (-not [bool]$latestPairPipelinePlanCommand.safeToRunNow -or @($latestPairPipelinePlanCommand.safetyBlockers).Count -ne 0) {
            throw "Nameplate proof promotion planner did not mark the latest-pair pipeline plan command safe.`n$($latestPairPlannerOutput -join [Environment]::NewLine)"
        }
        if ([bool]$latestPairPipelineRunCommand.safeToRunNow -or [bool]$latestPairPipelineRunCommand.attachesToProcess -or -not [bool]$latestPairPipelineRunCommand.createsArtifacts -or @($latestPairPipelineRunCommand.safetyBlockers | Where-Object { $_ -eq 'creates-artifacts' }).Count -eq 0) {
            throw "Nameplate proof promotion planner did not mark the latest-pair pipeline run command as artifact-writing but no-attach when neighborhoods already exist.`n$($latestPairPlannerOutput -join [Environment]::NewLine)"
        }
        if ([int]$latestPairPlanner.recommendedCommandSafety.total -ne @($latestPairPlanner.recommendedCommands).Count -or [int]$latestPairPlanner.recommendedCommandSafety.safeToRunNow -ne 3 -or [int]$latestPairPlanner.recommendedCommandSafety.unsafe -ne 2 -or [int]$latestPairPlanner.recommendedCommandSafety.attachesToProcess -ne 0 -or [int]$latestPairPlanner.recommendedCommandSafety.createsArtifacts -ne 2) {
            throw "Nameplate proof promotion planner did not summarize recommended command safety for the latest-pair fixture.`n$($latestPairPlannerOutput -join [Environment]::NewLine)"
        }
        foreach ($expectedUnsafeName in @('promotion-pipeline-latest-pair-run', 'promotion-pipeline-run')) {
            if (-not @($latestPairPlanner.recommendedCommandSafety.unsafeNames | Where-Object { $_ -eq $expectedUnsafeName })) {
                throw "Nameplate proof promotion planner latest-pair safety summary is missing unsafe command '$expectedUnsafeName'.`n$($latestPairPlannerOutput -join [Environment]::NewLine)"
            }
        }

        Add-Check -Name 'nameplate-proof-promotion-planner-latest-pair-smoke' -Status 'passed' -Detail 'Promotion planner selects previous gated baseline/zoom proof as baseline, newest as reproof, and recommends the latest-pair pipeline when two proofs exist.' -Data ([ordered]@{ readyForPromotionCompare = $latestPairPlanner.readyForPromotionCompare; selectedBaseline = $latestPairPlanner.selectedBaselineRun.name; selectedReproof = $latestPairPlanner.selectedReproofRun.name; nextAction = $latestPairPlanner.nextAction.name })

        Add-Check -Name 'nameplate-proof-promotion-latest-pair-command-safety-smoke' -Status 'passed' -Detail 'Promotion planner marks latest-pair pipeline plan safe and artifact-writing run unsafe without attach when lead-neighborhood evidence already exists.' -Data ([ordered]@{ planSafeToRunNow = $latestPairPipelinePlanCommand.safeToRunNow; runSafeToRunNow = $latestPairPipelineRunCommand.safeToRunNow; runAttachesToProcess = $latestPairPipelineRunCommand.attachesToProcess; runSafetyBlockers = @($latestPairPipelineRunCommand.safetyBlockers) })

        Add-Check -Name 'nameplate-proof-promotion-latest-pair-safety-summary-smoke' -Status 'passed' -Detail 'Promotion planner summarizes latest-pair recommended command safety with artifact-writing runs unsafe and no attach required when neighborhoods already exist.' -Data ([ordered]@{ total = $latestPairPlanner.recommendedCommandSafety.total; safeToRunNow = $latestPairPlanner.recommendedCommandSafety.safeToRunNow; unsafe = $latestPairPlanner.recommendedCommandSafety.unsafe; attachesToProcess = $latestPairPlanner.recommendedCommandSafety.attachesToProcess; unsafeNames = @($latestPairPlanner.recommendedCommandSafety.unsafeNames) })

        $unsafeLatestPairOutputRoot = Join-Path ([System.IO.Path]::GetTempPath()) ('riftreader-unsafe-latest-nameplate-pair-{0}' -f ([guid]::NewGuid().ToString('N')))
        New-Item -ItemType Directory -Path $unsafeLatestPairOutputRoot -Force | Out-Null
        Get-ChildItem -LiteralPath $latestPairOutputRoot | Copy-Item -Destination $unsafeLatestPairOutputRoot -Recurse -Force
        $unsafeReproofNeighborhoodFile = Join-Path $unsafeLatestPairOutputRoot '20260424-020000-nameplate-baseline-zoom\lead-neighborhoods\nameplate-proof-lead-neighborhoods.json'
        Remove-Item -LiteralPath $unsafeReproofNeighborhoodFile -Force

        $unsafePlannerOutput = & pwsh -NoProfile -ExecutionPolicy Bypass -File $promotionPlanScript -OutputRoot $unsafeLatestPairOutputRoot -InventoryTop 5 -MinRepeatedRootCount 1 -MinRepeatedEdgeCount 1 -Json 2>&1
        $unsafePlannerCode = $LASTEXITCODE
        if ($unsafePlannerCode -ne 0) {
            throw "Nameplate proof promotion planner missing-neighborhood fixture failed with exit code $unsafePlannerCode.`n$($unsafePlannerOutput -join [Environment]::NewLine)"
        }
        $unsafePlanner = ($unsafePlannerOutput -join [Environment]::NewLine) | ConvertFrom-Json -Depth 100
        $unsafePlannerRecommendedNextAction = @($unsafePlanner.recommendedCommands | Where-Object { $_.name -eq $unsafePlanner.nextAction.name }) | Select-Object -First 1
        if ($null -eq $unsafePlanner.nextAction -or [string]$unsafePlanner.nextAction.name -ne 'capture-reproof-lead-neighborhood' -or [bool]$unsafePlanner.nextAction.safeToRunNow -or -not [bool]$unsafePlanner.nextAction.attachesToProcess -or -not [bool]$unsafePlanner.nextAction.createsArtifacts) {
            throw "Nameplate proof promotion planner did not expose missing reproof lead-neighborhood capture as an unsafe nextAction.`n$($unsafePlannerOutput -join [Environment]::NewLine)"
        }
        if ($null -eq $unsafePlannerRecommendedNextAction -or [bool]$unsafePlannerRecommendedNextAction.safeToRunNow -or [bool]$unsafePlannerRecommendedNextAction.attachesToProcess -ne [bool]$unsafePlanner.nextAction.attachesToProcess -or [bool]$unsafePlannerRecommendedNextAction.createsArtifacts -ne [bool]$unsafePlanner.nextAction.createsArtifacts) {
            throw "Nameplate proof promotion planner nextAction safety did not match its recommended command safety metadata.`n$($unsafePlannerOutput -join [Environment]::NewLine)"
        }
        foreach ($expectedUnsafeNextActionBlocker in @('attaches-to-process', 'creates-artifacts')) {
            if (-not @($unsafePlanner.nextAction.safetyBlockers | Where-Object { $_ -eq $expectedUnsafeNextActionBlocker })) {
                throw "Nameplate proof promotion planner unsafe nextAction is missing expected safety blocker '$expectedUnsafeNextActionBlocker'.`n$($unsafePlannerOutput -join [Environment]::NewLine)"
            }
        }

        Add-Check -Name 'nameplate-proof-promotion-unsafe-next-action-safety-smoke' -Status 'passed' -Detail 'Promotion planner inherits unsafe recommended command safety onto missing-neighborhood nextAction metadata.' -Data ([ordered]@{ nextAction = $unsafePlanner.nextAction.name; safeToRunNow = $unsafePlanner.nextAction.safeToRunNow; safetyBlockers = @($unsafePlanner.nextAction.safetyBlockers) })

        $unsafeNextActionOutput = & pwsh -NoProfile -ExecutionPolicy Bypass -File $promotionNextActionScript -OutputRoot $unsafeLatestPairOutputRoot -InventoryTop 5 -MinRepeatedRootCount 1 -MinRepeatedEdgeCount 1 -Execute -Json 2>&1
        $unsafeNextActionCode = $LASTEXITCODE
        if ($unsafeNextActionCode -eq 0) {
            throw "Nameplate promotion next-action helper unexpectedly executed an unsafe nextAction.`n$($unsafeNextActionOutput -join [Environment]::NewLine)"
        }
        $unsafeNextAction = ($unsafeNextActionOutput -join [Environment]::NewLine) | ConvertFrom-Json -Depth 100
        if ([bool]$unsafeNextAction.ok -or [bool]$unsafeNextAction.executed -or [string]$unsafeNextAction.blocker -ne 'next-action-not-safe-to-run-now') {
            throw "Nameplate promotion next-action helper did not fail closed on an unsafe nextAction.`n$($unsafeNextActionOutput -join [Environment]::NewLine)"
        }
        if ([bool]$unsafeNextAction.controlsInput -or $null -ne $unsafeNextAction.executionSummary -or $null -ne $unsafeNextAction.execution -or $null -eq $unsafeNextAction.operatorChecklist -or @($unsafeNextAction.operatorChecklist).Count -ne 0) {
            throw "Nameplate promotion next-action helper unsafe response did not preserve the normalized no-execution result shape.`n$($unsafeNextActionOutput -join [Environment]::NewLine)"
        }
        if (-not @($unsafeNextAction.safetyBlockers | Where-Object { $_ -eq 'attaches-to-process' }) -or -not @($unsafeNextAction.safetyBlockers | Where-Object { $_ -eq 'creates-artifacts' })) {
            throw "Nameplate promotion next-action helper did not report expected unsafe blockers for missing lead-neighborhood capture.`n$($unsafeNextActionOutput -join [Environment]::NewLine)"
        }

        Add-Check -Name 'nameplate-proof-promotion-next-action-unsafe-smoke' -Status 'passed' -Detail 'Next-action helper refuses to execute an unsafe action that would attach and create artifacts while preserving the normalized result shape.' -Data ([ordered]@{ blocker = $unsafeNextAction.blocker; safetyBlockers = @($unsafeNextAction.safetyBlockers); executed = $unsafeNextAction.executed; operatorChecklistCount = @($unsafeNextAction.operatorChecklist).Count })

        $proofRunListOutputRoot = Split-Path -Parent $resultCheckRoot
        $proofRunListOutput = & pwsh -NoProfile -ExecutionPolicy Bypass -File $proofRunListScript -OutputRoot $proofRunListOutputRoot -RequireGated -Top 5 -Json 2>&1
        $proofRunListCode = $LASTEXITCODE
        if ($proofRunListCode -ne 0) {
            throw "Nameplate proof run inventory failed with exit code $proofRunListCode.`n$($proofRunListOutput -join [Environment]::NewLine)"
        }
        $proofRunList = ($proofRunListOutput -join [Environment]::NewLine) | ConvertFrom-Json -Depth 80
        $listedFixtureRun = @($proofRunList.runs | Where-Object { $_.runRoot -eq $resultCheckRoot }) | Select-Object -First 1
        if ($null -eq $listedFixtureRun -or -not [bool]$listedFixtureRun.gated.passed -or -not [bool]$listedFixtureRun.hasLeadNeighborhood -or -not [bool]$listedFixtureRun.hasPromotionPacket -or -not [bool]$listedFixtureRun.promotionReady) {
            throw "Nameplate proof run inventory did not report the gated fixture with lead-neighborhood and promotion packet status.`n$($proofRunListOutput -join [Environment]::NewLine)"
        }
        if ([string]$listedFixtureRun.candidateAddress -ne $CandidateAddress -or [string]$listedFixtureRun.nameplateText -ne $NameplateText) {
            throw "Nameplate proof run inventory did not expose manifest proof seed fields.`n$($proofRunListOutput -join [Environment]::NewLine)"
        }

        Add-Check -Name 'nameplate-proof-run-inventory-smoke' -Status 'passed' -Detail 'Proof-run inventory lists gated nameplate proof roots with lead-neighborhood, promotion-packet, and manifest seed status.' -Data ([ordered]@{ returnedRuns = $proofRunList.returnedRuns; fixtureGated = $listedFixtureRun.gated.passed; hasLeadNeighborhood = $listedFixtureRun.hasLeadNeighborhood; promotionReady = $listedFixtureRun.promotionReady; hasManifestSeed = $true })

        $promotionPlanOutput = & pwsh -NoProfile -ExecutionPolicy Bypass -File $promotionPlanScript -OutputRoot $proofRunListOutputRoot -InventoryTop 5 -MinRepeatedRootCount 1 -MinRepeatedEdgeCount 1 -Json 2>&1
        $promotionPlanCode = $LASTEXITCODE
        if ($promotionPlanCode -ne 0) {
            throw "Nameplate proof promotion planner failed with exit code $promotionPlanCode.`n$($promotionPlanOutput -join [Environment]::NewLine)"
        }
        $promotionPlan = ($promotionPlanOutput -join [Environment]::NewLine) | ConvertFrom-Json -Depth 100
        if (-not [bool]$promotionPlan.ok -or [int]$promotionPlan.inventory.gatedBaselineZoomRuns -lt 1 -or [int]$promotionPlan.inventory.baselineZoomRunsWithNeighborhood -lt 1) {
            throw "Nameplate proof promotion planner did not summarize the gated fixture inventory.`n$($promotionPlanOutput -join [Environment]::NewLine)"
        }
        if (-not @($promotionPlan.recommendedCommands | Where-Object { $_.name -eq 'run-second-baseline-zoom-proof' })) {
            throw "Nameplate proof promotion planner did not recommend the second proof when only one baseline/zoom proof was present.`n$($promotionPlanOutput -join [Environment]::NewLine)"
        }
        if (-not @($promotionPlan.recommendedCommands | Where-Object { $_.name -eq 'run-second-baseline-zoom-proof-plan' })) {
            throw "Nameplate proof promotion planner did not recommend a plan-only second proof check before the live second proof.`n$($promotionPlanOutput -join [Environment]::NewLine)"
        }
        if ($null -eq $promotionPlan.nextAction -or [string]$promotionPlan.nextAction.name -ne 'run-second-baseline-zoom-proof-plan' -or [bool]$promotionPlan.nextAction.attachesToProcess -or [bool]$promotionPlan.nextAction.createsArtifacts -or -not [bool]$promotionPlan.nextAction.safeToRunNow -or @($promotionPlan.nextAction.safetyBlockers).Count -ne 0) {
            throw "Nameplate proof promotion planner did not expose the plan-only second proof as the safe nextAction.`n$($promotionPlanOutput -join [Environment]::NewLine)"
        }
        $secondProofCommand = @($promotionPlan.recommendedCommands | Where-Object { $_.name -eq 'run-second-baseline-zoom-proof' }) | Select-Object -First 1
        $secondProofPlanCommand = @($promotionPlan.recommendedCommands | Where-Object { $_.name -eq 'run-second-baseline-zoom-proof-plan' }) | Select-Object -First 1
        if ($null -eq $secondProofCommand.seed -or [string]$secondProofCommand.seed.candidateAddress -ne $CandidateAddress -or [string]$secondProofCommand.seed.nameplateText -ne $NameplateText) {
            throw "Nameplate proof promotion planner did not seed the second proof command from manifest evidence.`n$($promotionPlanOutput -join [Environment]::NewLine)"
        }
        if ([string]$secondProofCommand.command -notmatch [regex]::Escape($CandidateAddress) -or [string]$secondProofCommand.command -notmatch [regex]::Escape($NameplateText)) {
            throw "Nameplate proof promotion planner did not include manifest seed arguments in the second proof command.`n$($promotionPlanOutput -join [Environment]::NewLine)"
        }
        if ([string]$secondProofPlanCommand.command -notmatch '(?i)(^|\s)-PlanOnly(\s|$)' -or [string]$secondProofCommand.command -match '(?i)(^|\s)-PlanOnly(\s|$)') {
            throw "Nameplate proof promotion planner did not keep plan-only and live second proof commands distinct.`n$($promotionPlanOutput -join [Environment]::NewLine)"
        }
        $secondProofPlanParts = @($secondProofPlanCommand.commandParts | ForEach-Object { [string]$_ })
        $secondProofParts = @($secondProofCommand.commandParts | ForEach-Object { [string]$_ })
        if ($secondProofPlanParts.Count -eq 0 -or $secondProofParts.Count -eq 0 -or -not ($secondProofPlanParts -contains $NameplateText) -or -not ($secondProofParts -contains $NameplateText)) {
            throw "Nameplate proof promotion planner did not expose structured commandParts with manifest seed arguments.`n$($promotionPlanOutput -join [Environment]::NewLine)"
        }
        if (-not ($secondProofPlanParts -contains '-PlanOnly') -or ($secondProofParts -contains '-PlanOnly')) {
            throw "Nameplate proof promotion planner did not keep structured plan-only and live commandParts distinct.`n$($promotionPlanOutput -join [Environment]::NewLine)"
        }
        if (-not [bool]$secondProofPlanCommand.safeToRunNow -or @($secondProofPlanCommand.safetyBlockers).Count -ne 0) {
            throw "Nameplate proof promotion planner did not mark the plan-only second proof command safe.`n$($promotionPlanOutput -join [Environment]::NewLine)"
        }
        if ([bool]$secondProofCommand.safeToRunNow -or -not [bool]$secondProofCommand.attachesToProcess -or -not [bool]$secondProofCommand.createsArtifacts -or -not [bool]$secondProofCommand.requiresOperatorConfirmation) {
            throw "Nameplate proof promotion planner did not mark the live second proof command as unsafe for automation.`n$($promotionPlanOutput -join [Environment]::NewLine)"
        }
        foreach ($expectedLiveBlocker in @('attaches-to-process', 'creates-artifacts', 'requires-operator-confirmation')) {
            if (-not @($secondProofCommand.safetyBlockers | Where-Object { $_ -eq $expectedLiveBlocker })) {
                throw "Nameplate proof promotion planner live second proof command is missing expected safety blocker '$expectedLiveBlocker'.`n$($promotionPlanOutput -join [Environment]::NewLine)"
            }
        }
        if ([int]$promotionPlan.recommendedCommandSafety.total -ne @($promotionPlan.recommendedCommands).Count -or [int]$promotionPlan.recommendedCommandSafety.safeToRunNow -ne 2 -or [int]$promotionPlan.recommendedCommandSafety.unsafe -ne 1 -or [int]$promotionPlan.recommendedCommandSafety.attachesToProcess -ne 1 -or [int]$promotionPlan.recommendedCommandSafety.createsArtifacts -ne 1 -or [int]$promotionPlan.recommendedCommandSafety.requiresOperatorConfirmation -ne 1) {
            throw "Nameplate proof promotion planner did not summarize recommended command safety for the one-proof fixture.`n$($promotionPlanOutput -join [Environment]::NewLine)"
        }
        if (-not @($promotionPlan.recommendedCommandSafety.unsafeNames | Where-Object { $_ -eq 'run-second-baseline-zoom-proof' })) {
            throw "Nameplate proof promotion planner safety summary did not identify the live second proof command as unsafe.`n$($promotionPlanOutput -join [Environment]::NewLine)"
        }

        Add-Check -Name 'nameplate-proof-promotion-planner-smoke' -Status 'passed' -Detail 'Promotion planner summarizes proof readiness and emits manifest-seeded plan-only plus live next-step commands when a second gated proof is still missing.' -Data ([ordered]@{ readyForPipeline = $promotionPlan.readyForPipeline; missingEvidence = @($promotionPlan.missingEvidence); recommendedCommandCount = @($promotionPlan.recommendedCommands).Count; seededSecondProofCommand = $true; hasSecondProofPlanCommand = $true; nextAction = $promotionPlan.nextAction.name })

        Add-Check -Name 'nameplate-proof-promotion-command-parts-smoke' -Status 'passed' -Detail 'Promotion planner emits structured commandParts alongside display command strings for safe execution.' -Data ([ordered]@{ planPartCount = $secondProofPlanParts.Count; livePartCount = $secondProofParts.Count; planOnlyPartPresent = ($secondProofPlanParts -contains '-PlanOnly') })

        Add-Check -Name 'nameplate-proof-promotion-recommended-command-safety-smoke' -Status 'passed' -Detail 'Promotion planner labels recommended commands with safety metadata so live proof commands are not automation-safe.' -Data ([ordered]@{ planSafeToRunNow = $secondProofPlanCommand.safeToRunNow; liveSafeToRunNow = $secondProofCommand.safeToRunNow; liveSafetyBlockers = @($secondProofCommand.safetyBlockers) })

        Add-Check -Name 'nameplate-proof-promotion-safety-summary-smoke' -Status 'passed' -Detail 'Promotion planner emits a top-level recommendedCommandSafety summary for quick automation gating.' -Data ([ordered]@{ total = $promotionPlan.recommendedCommandSafety.total; safeToRunNow = $promotionPlan.recommendedCommandSafety.safeToRunNow; unsafe = $promotionPlan.recommendedCommandSafety.unsafe; unsafeNames = @($promotionPlan.recommendedCommandSafety.unsafeNames) })

        $quotedSeedOutputRoot = Join-Path ([System.IO.Path]::GetTempPath()) ('riftreader-quoted-nameplate-seed-{0}' -f ([guid]::NewGuid().ToString('N')))
        New-Item -ItemType Directory -Path $quotedSeedOutputRoot -Force | Out-Null
        Copy-Item -LiteralPath $resultCheckRoot -Destination $quotedSeedOutputRoot -Recurse -Force
        $quotedRunRoot = Join-Path $quotedSeedOutputRoot (Split-Path -Leaf $resultCheckRoot)
        $quotedManifestPath = Join-Path $quotedRunRoot 'manifest.json'
        $quotedNameplateText = 'Atank''s "Sanctum";$(nope)&More'
        $quotedManifest = Get-Content -LiteralPath $quotedManifestPath -Raw | ConvertFrom-Json
        $quotedManifest.tooltipText = $quotedNameplateText
        $quotedManifest | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath $quotedManifestPath -Encoding UTF8
        $quotedNextActionOutput = & pwsh -NoProfile -ExecutionPolicy Bypass -File $promotionNextActionScript -OutputRoot $quotedSeedOutputRoot -InventoryTop 5 -MinRepeatedRootCount 1 -MinRepeatedEdgeCount 1 -Execute -Json 2>&1
        $quotedNextActionCode = $LASTEXITCODE
        if ($quotedNextActionCode -ne 0) {
            throw "Nameplate promotion next-action helper failed to execute a plan-only command seeded from quoted manifest text with exit code $quotedNextActionCode.`n$($quotedNextActionOutput -join [Environment]::NewLine)"
        }
        $quotedNextAction = ($quotedNextActionOutput -join [Environment]::NewLine) | ConvertFrom-Json -Depth 100
        $quotedExecutionParts = @($quotedNextAction.execution.commandParts | ForEach-Object { [string]$_ })
        if (-not [bool]$quotedNextAction.ok -or [string]$quotedNextAction.execution.commandSource -ne 'commandParts' -or [string]$quotedNextAction.execution.parsedJson.tooltipText -ne $quotedNameplateText -or [int]$quotedNextAction.executionSummary.operatorChecklistCount -ne 4 -or -not ($quotedExecutionParts -contains $quotedNameplateText)) {
            throw "Nameplate promotion next-action helper did not preserve quoted manifest text through the generated PowerShell command.`n$($quotedNextActionOutput -join [Environment]::NewLine)"
        }

        Add-Check -Name 'nameplate-proof-promotion-command-quoting-smoke' -Status 'passed' -Detail 'Promotion planner command strings and structured commandParts preserve manifest-seeded nameplate text containing PowerShell metacharacters.' -Data ([ordered]@{ nextAction = $quotedNextAction.nextAction.name; commandSource = $quotedNextAction.execution.commandSource; tooltipText = $quotedNextAction.execution.parsedJson.tooltipText; operatorChecklistCount = $quotedNextAction.executionSummary.operatorChecklistCount; commandPartCount = $quotedExecutionParts.Count })

        $nextActionPlanOutput = & pwsh -NoProfile -ExecutionPolicy Bypass -File $promotionNextActionScript -OutputRoot $proofRunListOutputRoot -InventoryTop 5 -MinRepeatedRootCount 1 -MinRepeatedEdgeCount 1 -Json 2>&1
        $nextActionPlanCode = $LASTEXITCODE
        if ($nextActionPlanCode -ne 0) {
            throw "Nameplate promotion next-action helper plan failed with exit code $nextActionPlanCode.`n$($nextActionPlanOutput -join [Environment]::NewLine)"
        }
        $nextActionPlan = ($nextActionPlanOutput -join [Environment]::NewLine) | ConvertFrom-Json -Depth 100
        if (-not [bool]$nextActionPlan.ok -or [string]$nextActionPlan.mode -ne 'plan-only' -or [bool]$nextActionPlan.executed -or [string]$nextActionPlan.nextAction.name -ne 'run-second-baseline-zoom-proof-plan') {
            throw "Nameplate promotion next-action helper did not expose the safe planner nextAction without executing it.`n$($nextActionPlanOutput -join [Environment]::NewLine)"
        }
        if ($null -eq $nextActionPlan.operatorChecklist -or @($nextActionPlan.operatorChecklist).Count -ne 0) {
            throw "Nameplate promotion next-action helper plan-only response should expose an empty operatorChecklist array before execution.`n$($nextActionPlanOutput -join [Environment]::NewLine)"
        }

        $nextActionExecuteOutput = & pwsh -NoProfile -ExecutionPolicy Bypass -File $promotionNextActionScript -OutputRoot $proofRunListOutputRoot -InventoryTop 5 -MinRepeatedRootCount 1 -MinRepeatedEdgeCount 1 -Execute -Json 2>&1
        $nextActionExecuteCode = $LASTEXITCODE
        if ($nextActionExecuteCode -ne 0) {
            throw "Nameplate promotion next-action helper safe execution failed with exit code $nextActionExecuteCode.`n$($nextActionExecuteOutput -join [Environment]::NewLine)"
        }
        $nextActionExecute = ($nextActionExecuteOutput -join [Environment]::NewLine) | ConvertFrom-Json -Depth 100
        if (-not [bool]$nextActionExecute.ok -or -not [bool]$nextActionExecute.executed -or [string]$nextActionExecute.execution.parsedJson.mode -ne 'plan-only') {
            throw "Nameplate promotion next-action helper did not execute the safe plan-only command as expected.`n$($nextActionExecuteOutput -join [Environment]::NewLine)"
        }
        if ([string]$nextActionExecute.execution.commandSource -ne 'commandParts') {
            throw "Nameplate promotion next-action helper did not execute the safe plan-only command from structured commandParts.`n$($nextActionExecuteOutput -join [Environment]::NewLine)"
        }
        if ($null -eq $nextActionExecute.executionSummary -or [string]$nextActionExecute.executionSummary.mode -ne 'plan-only' -or [int]$nextActionExecute.executionSummary.operatorChecklistCount -ne 4 -or @($nextActionExecute.operatorChecklist).Count -ne 4) {
            throw "Nameplate promotion next-action helper did not surface the plan-only operator checklist summary.`n$($nextActionExecuteOutput -join [Environment]::NewLine)"
        }
        if (Test-Path -LiteralPath ([string]$nextActionExecute.execution.parsedJson.runRoot)) {
            throw "Nameplate promotion next-action helper safe execution unexpectedly created the plan-only run root: $($nextActionExecute.execution.parsedJson.runRoot)"
        }

        Add-Check -Name 'nameplate-proof-promotion-next-action-smoke' -Status 'passed' -Detail 'Next-action helper reports the safe planner nextAction, executes only when safeToRunNow is true, and surfaces the plan-only operator checklist.' -Data ([ordered]@{ nextAction = $nextActionPlan.nextAction.name; executedMode = $nextActionExecute.execution.parsedJson.mode; safeToRunNow = $nextActionPlan.nextAction.safeToRunNow; operatorChecklistCount = $nextActionExecute.executionSummary.operatorChecklistCount })

        $latestOutputRoot = Split-Path -Parent $resultCheckRoot
        $latestCheckOutput = & pwsh -NoProfile -ExecutionPolicy Bypass -File $resultCheckerScript -Latest -OutputRoot $latestOutputRoot -Json 2>&1
        $latestCheckCode = $LASTEXITCODE
        if ($latestCheckCode -ne 0) {
            throw "Nameplate proof result checker -Latest failed with exit code $latestCheckCode.`n$($latestCheckOutput -join [Environment]::NewLine)"
        }
        $latestCheck = ($latestCheckOutput -join [Environment]::NewLine) | ConvertFrom-Json -Depth 40
        if (-not [bool]$latestCheck.ok -or [string]$latestCheck.runRoot -ne [string]$resultCheck.runRoot) {
            throw "Nameplate proof result checker -Latest did not resolve the expected fully gated run.`n$($latestCheckOutput -join [Environment]::NewLine)"
        }

        Add-Check -Name 'nameplate-result-checker-smoke' -Status 'passed' -Detail 'Post-capture nameplate proof result checker accepts a fully gated baseline/zoom fixture by explicit RunRoot and -Latest.' -Data ([ordered]@{ candidateCount = $resultCheck.candidateCount; checkCount = @($resultCheck.checks).Count; latestResolved = $true })
    }
    finally {
        if (Test-Path -LiteralPath $resultCheckRoot) {
            Remove-Item -LiteralPath $resultCheckRoot -Recurse -Force
        }
        if (-not [string]::IsNullOrWhiteSpace($latestPairOutputRoot) -and (Test-Path -LiteralPath $latestPairOutputRoot)) {
            Remove-Item -LiteralPath $latestPairOutputRoot -Recurse -Force
        }
        if (-not [string]::IsNullOrWhiteSpace($unsafeLatestPairOutputRoot) -and (Test-Path -LiteralPath $unsafeLatestPairOutputRoot)) {
            Remove-Item -LiteralPath $unsafeLatestPairOutputRoot -Recurse -Force
        }
        if (-not [string]::IsNullOrWhiteSpace($quotedSeedOutputRoot) -and (Test-Path -LiteralPath $quotedSeedOutputRoot)) {
            Remove-Item -LiteralPath $quotedSeedOutputRoot -Recurse -Force
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
