[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Assert-Equal {
    param(
        [Parameter(Mandatory = $true)]
        $Actual,

        [Parameter(Mandatory = $true)]
        $Expected,

        [Parameter(Mandatory = $true)]
        [string]$Message
    )

    if ($Actual -ne $Expected) {
        throw "$Message Expected '$Expected', got '$Actual'."
    }
}

function Assert-True {
    param(
        [Parameter(Mandatory = $true)]
        [bool]$Condition,

        [Parameter(Mandatory = $true)]
        [string]$Message
    )

    if (-not $Condition) {
        throw $Message
    }
}

function Get-PowerShellExecutable {
    if (Get-Command -Name pwsh -CommandType Application -ErrorAction SilentlyContinue) {
        return 'pwsh'
    }

    return 'powershell'
}

function Invoke-ChildScript {
    param(
        [Parameter(Mandatory = $true)]
        [string]$ScriptPath,

        [Parameter(Mandatory = $true)]
        [string[]]$Arguments
    )

    $output = & (Get-PowerShellExecutable) @(
        '-NoLogo',
        '-NoProfile',
        '-ExecutionPolicy',
        'Bypass',
        '-File',
        $ScriptPath
    ) @Arguments 2>&1

    return [pscustomobject]@{
        ExitCode = $LASTEXITCODE
        Output = ($output -join [Environment]::NewLine)
    }
}

function ConvertFrom-JsonCompat {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Text,
        [int]$Depth = 80
    )

    $command = Get-Command -Name ConvertFrom-Json -CommandType Cmdlet
    if ($command.Parameters.ContainsKey('Depth')) {
        return $Text | ConvertFrom-Json -Depth $Depth
    }

    return $Text | ConvertFrom-Json
}

function Convert-OutputToJson {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Output
    )

    $trimmed = $Output.Trim()
    if ([string]::IsNullOrWhiteSpace($trimmed)) {
        throw 'Child script produced no output.'
    }

    return ConvertFrom-JsonCompat -Text $trimmed -Depth 80
}

function Escape-SingleQuotedPowerShellString {
    param([string]$Value)

    return $Value -replace "'", "''"
}

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$script = Join-Path $repoRoot 'scripts\invoke-gated-forward-smoke.ps1'
$tempRoot = Join-Path ([System.IO.Path]::GetTempPath()) ('RiftReader-gated-forward-smoke-' + [System.Guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $tempRoot -Force | Out-Null

try {
    $stateFile = Join-Path $tempRoot 'preflight-call-count.txt'
    $freshAnchorFile = Join-Path $tempRoot 'fresh-anchor.json'
    $staleAnchorFile = Join-Path $tempRoot 'stale-anchor.json'
    $keyMarkerFile = Join-Path $tempRoot 'key-marker.txt'
    $successPreflightScript = Join-Path $tempRoot 'fake-preflight-success.ps1'
    $staleBudgetPreflightScript = Join-Path $tempRoot 'fake-preflight-stale-budget.ps1'
    $blockedPreflightScript = Join-Path $tempRoot 'fake-preflight-blocked.ps1'
    $keyScript = Join-Path $tempRoot 'fake-key.ps1'

    $escapedStateFile = Escape-SingleQuotedPowerShellString -Value $stateFile
    $escapedFreshAnchorFile = Escape-SingleQuotedPowerShellString -Value $freshAnchorFile
    $escapedStaleAnchorFile = Escape-SingleQuotedPowerShellString -Value $staleAnchorFile
    $escapedKeyMarkerFile = Escape-SingleQuotedPowerShellString -Value $keyMarkerFile

    @"
[CmdletBinding()]
param(
    [Parameter(ValueFromRemainingArguments = `$true)]
    [string[]]`$Remaining
)

`$stateFile = '$escapedStateFile'
`$count = if (Test-Path -LiteralPath `$stateFile -PathType Leaf) {
    [int](Get-Content -LiteralPath `$stateFile -Raw)
}
else {
    0
}
`$count++
Set-Content -LiteralPath `$stateFile -Value ([string]`$count) -Encoding UTF8

`$x = if (`$count -eq 1) { 10.0 } else { 10.25 }
`$y = 20.0
`$z = if (`$count -eq 1) { 30.0 } else { 29.5 }
`$summaryFile = Join-Path ([System.IO.Path]::GetDirectoryName(`$stateFile)) ("fake-readback-`$count.json")
`$anchor = [ordered]@{
    SchemaVersion = 1
    Mode = 'proof-coord-anchor'
    GeneratedAtUtc = [DateTimeOffset]::UtcNow.ToString('O')
}
`$anchor | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath '$escapedFreshAnchorFile' -Encoding UTF8
`$summary = [ordered]@{
    SchemaVersion = 1
    Mode = 'proof-coord-anchor-current-readback'
    Status = 'valid'
    MovementAllowed = `$true
    NoCheatEngine = `$true
    MovementSent = `$false
    ProcessName = 'rift_x64'
    ProcessId = 4242
    TargetWindowHandle = '0x1234'
    ProofCoordAnchorCacheFile = '$escapedFreshAnchorFile'
    SummaryFile = `$summaryFile
    MovementGate = 'satisfied_by_fixture'
    CurrentCoordinate = [ordered]@{
        X = `$x
        Y = `$y
        Z = `$z
        RecordedAtUtc = ('2026-05-07T00:00:0{0}.0000000Z' -f `$count)
    }
    Issues = @()
}
`$summary | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath `$summaryFile -Encoding UTF8
`$summary | ConvertTo-Json -Depth 20
exit 0
"@ | Set-Content -LiteralPath $successPreflightScript -Encoding UTF8

    @"
[CmdletBinding()]
param(
    [Parameter(ValueFromRemainingArguments = `$true)]
    [string[]]`$Remaining
)

`$anchor = [ordered]@{
    SchemaVersion = 1
    Mode = 'proof-coord-anchor'
    GeneratedAtUtc = ([DateTimeOffset]::UtcNow.AddSeconds(-55)).ToString('O')
}
`$anchor | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath '$escapedStaleAnchorFile' -Encoding UTF8
`$summaryFile = Join-Path '$tempRoot' 'fake-stale-budget-readback.json'
`$summary = [ordered]@{
    SchemaVersion = 1
    Mode = 'proof-coord-anchor-current-readback'
    Status = 'valid'
    MovementAllowed = `$true
    NoCheatEngine = `$true
    MovementSent = `$false
    ProcessName = 'rift_x64'
    ProcessId = 4242
    TargetWindowHandle = '0x1234'
    ProofCoordAnchorCacheFile = '$escapedStaleAnchorFile'
    SummaryFile = `$summaryFile
    MovementGate = 'satisfied_by_fixture'
    CurrentCoordinate = [ordered]@{
        X = 10.0
        Y = 20.0
        Z = 30.0
        RecordedAtUtc = '2026-05-07T00:00:00.0000000Z'
    }
    Issues = @()
}
`$summary | ConvertTo-Json -Depth 20
exit 0
"@ | Set-Content -LiteralPath $staleBudgetPreflightScript -Encoding UTF8

    @"
[CmdletBinding()]
param(
    [Parameter(ValueFromRemainingArguments = `$true)]
    [string[]]`$Remaining
)

`$summary = [ordered]@{
    SchemaVersion = 1
    Mode = 'proof-coord-anchor-current-readback'
    Status = 'failed'
    MovementAllowed = `$false
    NoCheatEngine = `$true
    MovementSent = `$false
    ProcessName = 'rift_x64'
    ProcessId = 4242
    TargetWindowHandle = '0x1234'
    SummaryFile = (Join-Path '$tempRoot' 'fake-blocked-readback.json')
    MovementGate = 'blocked_until_fixture'
    CurrentCoordinate = [ordered]@{
        X = 10.0
        Y = 20.0
        Z = 30.0
        RecordedAtUtc = '2026-05-07T00:00:00.0000000Z'
    }
    Issues = @('fixture-preflight-blocked')
}
`$summary | ConvertTo-Json -Depth 20
exit 1
"@ | Set-Content -LiteralPath $blockedPreflightScript -Encoding UTF8

    @"
[CmdletBinding()]
param(
    [Parameter(ValueFromRemainingArguments = `$true)]
    [string[]]`$Remaining
)

Add-Content -LiteralPath '$escapedKeyMarkerFile' -Value (`$Remaining -join ' ')
Write-Host '[RiftKey] SUCCESS'
exit 0
"@ | Set-Content -LiteralPath $keyScript -Encoding UTF8

    $commonArgs = @(
        '-ProcessId',
        '4242',
        '-TargetWindowHandle',
        '0x1234',
        '-OutputRoot',
        $tempRoot,
        '-KeyScript',
        $keyScript,
        '-Json'
    )

    $legacyBackend = Invoke-ChildScript -ScriptPath $script -Arguments ($commonArgs + @(
            '-InputBackend',
            'window-message',
            '-AllowWindowMessageBackend',
            '-PreflightScript',
            $successPreflightScript
        ))
    Assert-Equal -Actual $legacyBackend.ExitCode -Expected 1 -Message 'WindowMessage backend should remain retired even if the old override is passed.'
    $legacyBackendSummary = Convert-OutputToJson -Output $legacyBackend.Output
    Assert-Equal -Actual $legacyBackendSummary.Status -Expected 'blocked-input-backend' -Message 'Legacy backend should fail closed before preflight/input.'
    Assert-True -Condition (-not [bool]$legacyBackendSummary.MovementAttempted) -Message 'Legacy backend block must not attempt input.'
    Assert-True -Condition (-not [bool]$legacyBackendSummary.MovementSent) -Message 'Legacy backend block must not send movement.'
    Assert-True -Condition ((@($legacyBackendSummary.Issues) -join ';') -like '*window-message-input-backend-retired-after-spin-incident*') -Message 'Backend blocker should identify the retired WindowMessage guard.'
    Assert-True -Condition (-not (Test-Path -LiteralPath $keyMarkerFile)) -Message 'Legacy backend block must not invoke the key script.'
    Assert-True -Condition (-not (Test-Path -LiteralPath $stateFile)) -Message 'Legacy backend block must not invoke preflight.'

    $success = Invoke-ChildScript -ScriptPath $script -Arguments ($commonArgs + @(
            '-PreflightScript',
            $successPreflightScript
        ))
    Assert-Equal -Actual $success.ExitCode -Expected 0 -Message 'Success fixture should exit 0.'
    $successSummary = Convert-OutputToJson -Output $success.Output
    Assert-Equal -Actual $successSummary.Mode -Expected 'gated-forward-smoke' -Message 'Unexpected summary mode.'
    Assert-Equal -Actual $successSummary.Status -Expected 'passed' -Message 'Success fixture should pass.'
    Assert-True -Condition ([bool]$successSummary.NoCheatEngine) -Message 'Wrapper must preserve no-CE boundary.'
    Assert-True -Condition (-not [bool]$successSummary.SavedVariablesUsedAsLiveTruth) -Message 'Wrapper must not use SavedVariables as live truth.'
    Assert-True -Condition ([bool]$successSummary.MovementAttempted) -Message 'Success fixture should attempt input.'
    Assert-True -Condition ([bool]$successSummary.MovementSent) -Message 'Success fixture should mark successful key command as sent.'
    Assert-Equal -Actual @($successSummary.Pulses).Count -Expected 1 -Message 'Default wrapper should send one pulse.'
    Assert-True -Condition ([double]$successSummary.CoordinateDelta.PlanarDistance -gt 0.0) -Message 'Wrapper should compute total coordinate delta.'
    Assert-True -Condition (Test-Path -LiteralPath ([string]$successSummary.SummaryFile) -PathType Leaf) -Message 'Wrapper summary file should be written.'
    Assert-True -Condition (Test-Path -LiteralPath $keyMarkerFile -PathType Leaf) -Message 'Key script should be invoked on green preflight.'
    Assert-True -Condition ((Get-Content -LiteralPath $keyMarkerFile -Raw) -like '*--input-mode ScanCode*') -Message 'Wrapper should use C# ScanCode by default.'
    Assert-True -Condition ((Get-Content -LiteralPath $keyMarkerFile -Raw) -like '*--pid 4242*') -Message 'Wrapper should pass exact PID to the C# backend.'
    Assert-Equal -Actual $successSummary.InputBackend -Expected 'csharp-scancode' -Message 'Summary should record the selected C# backend.'
    Assert-True -Condition (-not [bool]$successSummary.AllowWindowMessageBackend) -Message 'Summary should not require the retired WindowMessage override.'
    Assert-Equal -Actual ([int](Get-Content -LiteralPath $stateFile -Raw)) -Expected 2 -Message 'Success wrapper should run preflight before and after input.'

    Remove-Item -LiteralPath $keyMarkerFile -Force
    if (Test-Path -LiteralPath $stateFile) {
        Remove-Item -LiteralPath $stateFile -Force
    }

    $blocked = Invoke-ChildScript -ScriptPath $script -Arguments ($commonArgs + @(
            '-PreflightScript',
            $blockedPreflightScript
        ))
    Assert-Equal -Actual $blocked.ExitCode -Expected 1 -Message 'Blocked preflight fixture should exit 1.'
    $blockedSummary = Convert-OutputToJson -Output $blocked.Output
    Assert-Equal -Actual $blockedSummary.Status -Expected 'blocked-preflight' -Message 'Blocked preflight should be structured as blocked-preflight.'
    Assert-True -Condition (-not [bool]$blockedSummary.MovementAttempted) -Message 'Blocked preflight must not attempt input.'
    Assert-True -Condition (-not [bool]$blockedSummary.MovementSent) -Message 'Blocked preflight must not send movement.'
    Assert-True -Condition (@($blockedSummary.Issues) -contains 'fixture-preflight-blocked') -Message 'Preflight issues should be preserved.'
    Assert-True -Condition (-not (Test-Path -LiteralPath $keyMarkerFile)) -Message 'Blocked preflight must not invoke the key script.'

    $staleBudget = Invoke-ChildScript -ScriptPath $script -Arguments ($commonArgs + @(
            '-PreflightScript',
            $staleBudgetPreflightScript
        ))
    Assert-Equal -Actual $staleBudget.ExitCode -Expected 1 -Message 'Stale age-budget fixture should exit 1.'
    $staleBudgetSummary = Convert-OutputToJson -Output $staleBudget.Output
    Assert-Equal -Actual $staleBudgetSummary.Status -Expected 'blocked-preflight-age-budget' -Message 'Low age budget should be structured as blocked-preflight-age-budget.'
    Assert-True -Condition (-not [bool]$staleBudgetSummary.MovementAttempted) -Message 'Low age budget must not attempt input.'
    Assert-True -Condition (-not [bool]$staleBudgetSummary.MovementSent) -Message 'Low age budget must not send movement.'
    Assert-True -Condition ((@($staleBudgetSummary.Issues) -join ';') -like '*proof_anchor_remaining_age_budget_too_low*') -Message 'Low age budget issue should be explicit.'
    Assert-True -Condition (-not (Test-Path -LiteralPath $keyMarkerFile)) -Message 'Low age budget must not invoke the key script.'

    $limit = Invoke-ChildScript -ScriptPath $script -Arguments ($commonArgs + @(
            '-PreflightScript',
            $successPreflightScript,
            '-HoldMilliseconds',
            '1001'
        ))
    Assert-Equal -Actual $limit.ExitCode -Expected 1 -Message 'Hold cap violation should exit 1.'
    $limitSummary = Convert-OutputToJson -Output $limit.Output
    Assert-Equal -Actual $limitSummary.Status -Expected 'failed' -Message 'Hold cap violation should be structured as failed.'
    Assert-True -Condition ((@($limitSummary.Issues) -join ';') -like '*HoldMilliseconds must be between 1 and 1000*') -Message 'Hold cap issue should be explicit.'
    Assert-True -Condition (-not [bool]$limitSummary.MovementAttempted) -Message 'Hold cap violation must not attempt input.'

    Write-Host 'Gated forward smoke regression passed.' -ForegroundColor Green
}
finally {
    if (Test-Path -LiteralPath $tempRoot) {
        Remove-Item -LiteralPath $tempRoot -Recurse -Force
    }
}
