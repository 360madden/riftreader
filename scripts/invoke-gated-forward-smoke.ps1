[CmdletBinding()]
param(
    [string]$ProcessName = 'rift_x64',
    [Parameter(Mandatory = $true)]
    [int]$ProcessId,
    [Parameter(Mandatory = $true)]
    [string]$TargetWindowHandle,
    [string]$Key = 'w',
    [int]$HoldMilliseconds = 250,
    [int]$PulseCount = 1,
    [int]$InterPulseDelayMilliseconds = 150,
    [int]$ProofAnchorMaxAgeSeconds = 60,
    [int]$MinimumPostReadbackAgeBudgetSeconds = 15,
    [int]$ReadbackSampleCount = 3,
    [int]$ReadbackIntervalMilliseconds = 100,
    [string]$ProofCoordAnchorFile,
    [string]$OutputRoot = (Join-Path $PSScriptRoot 'captures'),
    [string]$PreflightScript = (Join-Path $PSScriptRoot 'assert-current-proof-coord-anchor-readback.ps1'),
    [string]$KeyScript = (Join-Path $PSScriptRoot 'post-rift-key.ps1'),
    [switch]$UseCacheOnly,
    [switch]$AllowBackgroundPostMessage,
    [switch]$DryRun,
    [switch]$Json
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$maxHoldMilliseconds = 1000
$maxPulseCount = 3

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

function Get-JsonPropertyValue {
    param(
        $InputObject,

        [Parameter(Mandatory = $true)]
        [string[]]$Names
    )

    if ($null -eq $InputObject) {
        return $null
    }

    if ($InputObject -is [System.Collections.IDictionary]) {
        foreach ($name in $Names) {
            foreach ($key in $InputObject.Keys) {
                if ([string]::Equals([string]$key, $name, [System.StringComparison]::OrdinalIgnoreCase)) {
                    return $InputObject[$key]
                }
            }
        }

        return $null
    }

    foreach ($name in $Names) {
        foreach ($property in @($InputObject.PSObject.Properties)) {
            if ([string]::Equals($property.Name, $name, [System.StringComparison]::OrdinalIgnoreCase)) {
                return $property.Value
            }
        }
    }

    return $null
}

function ConvertTo-BoolCompat {
    param($Value)

    if ($null -eq $Value) {
        return $false
    }

    if ($Value -is [bool]) {
        return [bool]$Value
    }

    return [System.Convert]::ToBoolean($Value, [System.Globalization.CultureInfo]::InvariantCulture)
}

function ConvertTo-JsonSafeValue {
    param($Value)

    if ($null -eq $Value) {
        return $null
    }

    if ($Value -is [DateTimeOffset]) {
        return ([DateTimeOffset]$Value).ToUniversalTime().ToString('O', [System.Globalization.CultureInfo]::InvariantCulture)
    }

    if ($Value -is [DateTime]) {
        return ([DateTime]$Value).ToUniversalTime().ToString('O', [System.Globalization.CultureInfo]::InvariantCulture)
    }

    if ($Value -is [string] -or $Value.GetType().IsPrimitive -or $Value -is [decimal]) {
        return $Value
    }

    if ($Value -is [System.Collections.IDictionary]) {
        $copy = [ordered]@{}
        foreach ($key in $Value.Keys) {
            $copy[[string]$key] = ConvertTo-JsonSafeValue -Value $Value[$key]
        }

        return [pscustomobject]$copy
    }

    if ($Value -is [System.Collections.IEnumerable]) {
        return @($Value | ForEach-Object { ConvertTo-JsonSafeValue -Value $_ })
    }

    $properties = @($Value.PSObject.Properties)
    if ($properties.Count -gt 0) {
        $copy = [ordered]@{}
        foreach ($property in $properties) {
            $copy[$property.Name] = ConvertTo-JsonSafeValue -Value $property.Value
        }

        return [pscustomobject]$copy
    }

    return $Value
}

function Write-Utf8Json {
    param(
        [Parameter(Mandatory = $true)]
        $Document,

        [Parameter(Mandatory = $true)]
        [string]$Path,

        [int]$Depth = 80
    )

    $jsonText = $Document | ConvertTo-Json -Depth $Depth
    $utf8NoBom = [System.Text.UTF8Encoding]::new($false)
    [System.IO.File]::WriteAllText($Path, $jsonText, $utf8NoBom)
}

function Get-PowerShellExecutable {
    if (Get-Command -Name pwsh -CommandType Application -ErrorAction SilentlyContinue) {
        return 'pwsh'
    }

    return 'powershell'
}

function Invoke-ExternalCommand {
    param(
        [Parameter(Mandatory = $true)]
        [string]$FilePath,

        [Parameter(Mandatory = $true)]
        [string[]]$Arguments,

        [string]$WorkingDirectory,

        [switch]$AllowFailure
    )

    $previousLocation = Get-Location
    try {
        if (-not [string]::IsNullOrWhiteSpace($WorkingDirectory)) {
            Set-Location -LiteralPath $WorkingDirectory
        }

        $output = & $FilePath @Arguments 2>&1
        $exitCode = $LASTEXITCODE
        $text = $output -join [Environment]::NewLine
        if ($exitCode -ne 0 -and -not $AllowFailure) {
            throw "Command failed (`$LASTEXITCODE=$exitCode): $FilePath $($Arguments -join ' ')`n$text"
        }

        return [pscustomobject]@{
            FilePath = $FilePath
            Arguments = @($Arguments)
            ExitCode = $exitCode
            Output = $text
        }
    }
    finally {
        Set-Location -LiteralPath $previousLocation
    }
}

function Invoke-PowerShellScript {
    param(
        [Parameter(Mandatory = $true)]
        [string]$ScriptPath,

        [Parameter(Mandatory = $true)]
        [string[]]$Arguments,

        [switch]$AllowFailure
    )

    Invoke-ExternalCommand -FilePath (Get-PowerShellExecutable) -Arguments (@(
            '-NoLogo',
            '-NoProfile',
            '-ExecutionPolicy',
            'Bypass',
            '-File',
            $ScriptPath
        ) + $Arguments) -WorkingDirectory $repoRoot -AllowFailure:$AllowFailure
}

function Get-CommandSummary {
    param($CommandResult)

    if ($null -eq $CommandResult) {
        return $null
    }

    $outputText = [string]$CommandResult.Output
    $preview = if ([string]::IsNullOrWhiteSpace($outputText)) {
        ''
    }
    elseif ($outputText.Length -gt 3000) {
        $outputText.Substring(0, 3000)
    }
    else {
        $outputText
    }

    return [pscustomobject][ordered]@{
        FilePath = [string]$CommandResult.FilePath
        Arguments = @($CommandResult.Arguments)
        ExitCode = [int]$CommandResult.ExitCode
        OutputPreview = $preview
    }
}

function Convert-CommandOutputToJson {
    param(
        [Parameter(Mandatory = $true)]
        $CommandResult,

        [Parameter(Mandatory = $true)]
        [string]$CommandName
    )

    $text = ([string]$CommandResult.Output).Trim()
    if ([string]::IsNullOrWhiteSpace($text)) {
        throw "$CommandName produced no JSON output. ExitCode=$($CommandResult.ExitCode)"
    }

    return ConvertFrom-JsonCompat -Text $text -Depth 80
}

function Get-Coordinate {
    param($Summary)

    $coordinate = Get-JsonPropertyValue -InputObject $Summary -Names @('CurrentCoordinate', 'coordinate')
    if ($null -eq $coordinate) {
        return $null
    }

    $x = Get-JsonPropertyValue -InputObject $coordinate -Names @('X', 'x')
    $y = Get-JsonPropertyValue -InputObject $coordinate -Names @('Y', 'y')
    $z = Get-JsonPropertyValue -InputObject $coordinate -Names @('Z', 'z')
    if ($null -eq $x -or $null -eq $y -or $null -eq $z) {
        return $null
    }

    return [pscustomobject][ordered]@{
        X = [double]$x
        Y = [double]$y
        Z = [double]$z
        RecordedAtUtc = ConvertTo-JsonSafeValue -Value (Get-JsonPropertyValue -InputObject $coordinate -Names @('RecordedAtUtc', 'recordedAtUtc', 'captured_at_utc'))
    }
}

function New-CoordinateDelta {
    param(
        $Before,
        $After
    )

    if ($null -eq $Before -or $null -eq $After) {
        return $null
    }

    $deltaX = [double]$After.X - [double]$Before.X
    $deltaY = [double]$After.Y - [double]$Before.Y
    $deltaZ = [double]$After.Z - [double]$Before.Z
    $planar = [Math]::Sqrt(($deltaX * $deltaX) + ($deltaZ * $deltaZ))
    $spatial = [Math]::Sqrt(($deltaX * $deltaX) + ($deltaY * $deltaY) + ($deltaZ * $deltaZ))

    return [pscustomobject][ordered]@{
        DeltaX = $deltaX
        DeltaY = $deltaY
        DeltaZ = $deltaZ
        PlanarDistance = $planar
        SpatialDistance = $spatial
    }
}

function Test-ReadbackGateValid {
    param(
        $CommandResult,
        $Summary
    )

    $status = [string](Get-JsonPropertyValue -InputObject $Summary -Names @('Status'))
    $movementAllowed = ConvertTo-BoolCompat -Value (Get-JsonPropertyValue -InputObject $Summary -Names @('MovementAllowed'))
    return ($CommandResult.ExitCode -eq 0 -and
        [string]::Equals($status, 'valid', [System.StringComparison]::OrdinalIgnoreCase) -and
        $movementAllowed)
}

function Get-ProofAnchorAgeBudget {
    param($Summary)

    if ($ProofAnchorMaxAgeSeconds -le 0 -or $MinimumPostReadbackAgeBudgetSeconds -le 0) {
        return [pscustomobject][ordered]@{
            Enforced = $false
            Computed = $false
            ProofCoordAnchorCacheFile = $null
            GeneratedAtUtc = $null
            AgeSeconds = $null
            RemainingSeconds = $null
            RequiredRemainingSeconds = $MinimumPostReadbackAgeBudgetSeconds
            IsSufficient = $true
            Issues = @()
        }
    }

    $issues = [System.Collections.Generic.List[string]]::new()
    $anchorFile = [string](Get-JsonPropertyValue -InputObject $Summary -Names @('ProofCoordAnchorCacheFile'))
    if ([string]::IsNullOrWhiteSpace($anchorFile)) {
        $issues.Add('proof_anchor_cache_file_missing_from_preflight_summary') | Out-Null
    }
    elseif (-not (Test-Path -LiteralPath $anchorFile -PathType Leaf)) {
        $issues.Add("proof_anchor_cache_file_not_found:$anchorFile") | Out-Null
    }

    $generatedAtText = $null
    $ageSeconds = $null
    $remainingSeconds = $null
    if ($issues.Count -eq 0) {
        try {
            $anchor = ConvertFrom-JsonCompat -Text (Get-Content -LiteralPath $anchorFile -Raw) -Depth 80
            $generatedAtText = [string](Get-JsonPropertyValue -InputObject $anchor -Names @('GeneratedAtUtc'))
            if ([string]::IsNullOrWhiteSpace($generatedAtText)) {
                $issues.Add('proof_anchor_generated_at_missing') | Out-Null
            }
            else {
                $generatedAt = [DateTimeOffset]::Parse($generatedAtText, [System.Globalization.CultureInfo]::InvariantCulture).ToUniversalTime()
                $ageSeconds = ([DateTimeOffset]::UtcNow - $generatedAt).TotalSeconds
                $remainingSeconds = [double]$ProofAnchorMaxAgeSeconds - [double]$ageSeconds
            }
        }
        catch {
            $issues.Add("proof_anchor_age_budget_unreadable:$($_.Exception.Message)") | Out-Null
        }
    }

    $computed = ($issues.Count -eq 0 -and $null -ne $remainingSeconds)
    $sufficient = ($computed -and [double]$remainingSeconds -ge [double]$MinimumPostReadbackAgeBudgetSeconds)
    return [pscustomobject][ordered]@{
        Enforced = $true
        Computed = $computed
        ProofCoordAnchorCacheFile = if ([string]::IsNullOrWhiteSpace($anchorFile)) { $null } else { $anchorFile }
        GeneratedAtUtc = $generatedAtText
        AgeSeconds = $ageSeconds
        RemainingSeconds = $remainingSeconds
        RequiredRemainingSeconds = $MinimumPostReadbackAgeBudgetSeconds
        IsSufficient = $sufficient
        Issues = @($issues.ToArray())
    }
}

function Get-ProofAnchorAgeBudgetIssues {
    param(
        [Parameter(Mandatory = $true)]
        $Budget
    )

    $issues = [System.Collections.Generic.List[string]]::new()
    foreach ($issue in @($Budget.Issues)) {
        if (-not [string]::IsNullOrWhiteSpace([string]$issue)) {
            $issues.Add([string]$issue) | Out-Null
        }
    }

    if (-not [bool]$Budget.Computed) {
        $issues.Add('proof_anchor_age_budget_not_computed') | Out-Null
    }
    elseif (-not [bool]$Budget.IsSufficient) {
        $issues.Add(("proof_anchor_remaining_age_budget_too_low:remainingSeconds={0:0.000};requiredSeconds={1}" -f [double]$Budget.RemainingSeconds, [int]$Budget.RequiredRemainingSeconds)) | Out-Null
    }

    return @($issues.ToArray())
}

function Get-ReadbackGateIssues {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Label,

        $CommandResult,
        $Summary
    )

    $issues = [System.Collections.Generic.List[string]]::new()
    $status = [string](Get-JsonPropertyValue -InputObject $Summary -Names @('Status'))
    $movementAllowed = ConvertTo-BoolCompat -Value (Get-JsonPropertyValue -InputObject $Summary -Names @('MovementAllowed'))
    $issues.Add(("{0}_not_valid:status={1};movementAllowed={2};exitCode={3}" -f $Label, $status, $movementAllowed, $CommandResult.ExitCode)) | Out-Null

    foreach ($issue in @(Get-JsonPropertyValue -InputObject $Summary -Names @('Issues'))) {
        if (-not [string]::IsNullOrWhiteSpace([string]$issue)) {
            $issues.Add([string]$issue) | Out-Null
        }
    }

    return @($issues.ToArray())
}

function New-ReadbackArguments {
    $arguments = @(
        '-ProcessName',
        $ProcessName,
        '-ProcessId',
        $ProcessId.ToString([System.Globalization.CultureInfo]::InvariantCulture),
        '-TargetWindowHandle',
        $TargetWindowHandle,
        '-ProofAnchorMaxAgeSeconds',
        $ProofAnchorMaxAgeSeconds.ToString([System.Globalization.CultureInfo]::InvariantCulture),
        '-ReadbackSampleCount',
        $ReadbackSampleCount.ToString([System.Globalization.CultureInfo]::InvariantCulture),
        '-ReadbackIntervalMilliseconds',
        $ReadbackIntervalMilliseconds.ToString([System.Globalization.CultureInfo]::InvariantCulture),
        '-Json'
    )

    if (-not [string]::IsNullOrWhiteSpace($ProofCoordAnchorFile)) {
        $arguments += @('-ProofCoordAnchorFile', [System.IO.Path]::GetFullPath($ProofCoordAnchorFile))
    }

    if ($UseCacheOnly) {
        $arguments += '-UseCacheOnly'
    }

    return @($arguments)
}

function New-KeyArguments {
    $arguments = @(
        '-Key',
        $Key,
        '-HoldMilliseconds',
        $HoldMilliseconds.ToString([System.Globalization.CultureInfo]::InvariantCulture),
        '-TargetProcessName',
        $ProcessName,
        '-TargetProcessId',
        $ProcessId.ToString([System.Globalization.CultureInfo]::InvariantCulture),
        '-TargetWindowHandle',
        $TargetWindowHandle
    )

    if (-not $AllowBackgroundPostMessage) {
        $arguments += '-RequireTargetForeground'
    }

    return @($arguments)
}

function New-BaseSummary {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Status,

        [bool]$MovementSent,
        [bool]$MovementAttempted,
        [string[]]$Issues = @(),
        $FirstPreflight = $null,
        $LastPostReadback = $null,
        $CoordinateDelta = $null,
        [object[]]$Pulses = @()
    )

    return [pscustomobject][ordered]@{
        SchemaVersion = 1
        Mode = 'gated-forward-smoke'
        GeneratedAtUtc = [DateTimeOffset]::UtcNow.ToString('O')
        Status = $Status
        ProcessName = $ProcessName
        ProcessId = $ProcessId
        TargetWindowHandle = $TargetWindowHandle
        Key = $Key
        HoldMilliseconds = $HoldMilliseconds
        PulseCount = $PulseCount
        InterPulseDelayMilliseconds = $InterPulseDelayMilliseconds
        ProofAnchorMaxAgeSeconds = $ProofAnchorMaxAgeSeconds
        MinimumPostReadbackAgeBudgetSeconds = $MinimumPostReadbackAgeBudgetSeconds
        ReadbackSampleCount = $ReadbackSampleCount
        ReadbackIntervalMilliseconds = $ReadbackIntervalMilliseconds
        MaxHoldMilliseconds = $maxHoldMilliseconds
        MaxPulseCount = $maxPulseCount
        RequireTargetForeground = (-not [bool]$AllowBackgroundPostMessage)
        AllowBackgroundPostMessage = [bool]$AllowBackgroundPostMessage
        DryRun = [bool]$DryRun
        NoCheatEngine = $true
        SavedVariablesUsedAsLiveTruth = $false
        MovementSent = $MovementSent
        MovementAttempted = $MovementAttempted
        MovementAllowedAfterWrapper = (
            [string]::Equals($Status, 'passed', [System.StringComparison]::OrdinalIgnoreCase) -or
            [string]::Equals($Status, 'dry-run-valid', [System.StringComparison]::OrdinalIgnoreCase)
        )
        Preflight = ConvertTo-JsonSafeValue -Value $FirstPreflight
        PostReadback = ConvertTo-JsonSafeValue -Value $LastPostReadback
        CoordinateDelta = ConvertTo-JsonSafeValue -Value $CoordinateDelta
        Pulses = @($Pulses)
        OutputRoot = $resolvedOutputRoot
        SummaryFile = $summaryPath
        MovementGate = if ([string]::Equals($Status, 'passed', [System.StringComparison]::OrdinalIgnoreCase)) {
            'satisfied_before_input_and_after_each_pulse'
        }
        elseif ([string]::Equals($Status, 'dry-run-valid', [System.StringComparison]::OrdinalIgnoreCase)) {
            'satisfied_no_input_sent'
        }
        else {
            'blocked_until_current_process_proof_anchor_current_readback_is_valid'
        }
        Issues = @($Issues)
        Warnings = @(
            'No Cheat Engine path is used by this wrapper.',
            'SavedVariables are not used as live truth.',
            'The wrapper fails closed before input unless the current proof-anchor readback returns Status=valid and MovementAllowed=true.',
            'The wrapper rechecks current proof-anchor readback after each pulse and fails closed if the post-readback gate is not green.'
        )
    }
}

function Write-HumanSummary {
    param($Summary)

    $status = [string](Get-JsonPropertyValue -InputObject $Summary -Names @('Status'))
    $color = if ([string]::Equals($status, 'passed', [System.StringComparison]::OrdinalIgnoreCase) -or
        [string]::Equals($status, 'dry-run-valid', [System.StringComparison]::OrdinalIgnoreCase)) {
        'Green'
    }
    else {
        'Yellow'
    }

    Write-Host 'Gated forward smoke complete.' -ForegroundColor $color
    Write-Host ("Status:       {0}" -f $status)
    Write-Host ("PID/HWND:     {0} / {1}" -f $Summary.ProcessId, $Summary.TargetWindowHandle)
    Write-Host ("Input:        {0} x{1} for {2} ms" -f $Summary.Key, $Summary.PulseCount, $Summary.HoldMilliseconds)
    Write-Host ("Movement:     attempted={0}; sent={1}" -f $Summary.MovementAttempted, $Summary.MovementSent)
    Write-Host ("Gate:         {0}" -f $Summary.MovementGate)
    if ($null -ne $Summary.CoordinateDelta) {
        Write-Host ("Delta:        dX={0:0.######} dY={1:0.######} dZ={2:0.######}; planar={3:0.######}" -f [double]$Summary.CoordinateDelta.DeltaX, [double]$Summary.CoordinateDelta.DeltaY, [double]$Summary.CoordinateDelta.DeltaZ, [double]$Summary.CoordinateDelta.PlanarDistance)
    }
    Write-Host ("Summary:      {0}" -f $Summary.SummaryFile)
    Write-Host 'CE usage:     none'
    Write-Host 'SavedVars:    not live truth'

    $issues = @(Get-JsonPropertyValue -InputObject $Summary -Names @('Issues'))
    if ($issues.Count -gt 0) {
        Write-Host ("Issues:       {0}" -f ($issues -join '; ')) -ForegroundColor Yellow
    }
}

function Complete-Summary {
    param(
        [Parameter(Mandatory = $true)]
        $Summary,

        [Parameter(Mandatory = $true)]
        [int]$ExitCode
    )

    Write-Utf8Json -Document $Summary -Path $summaryPath -Depth 80
    if ($Json) {
        $Summary | ConvertTo-Json -Depth 80
    }
    else {
        Write-HumanSummary -Summary $Summary
    }

    exit $ExitCode
}

$resolvedOutputRoot = [System.IO.Path]::GetFullPath($OutputRoot)
New-Item -ItemType Directory -Path $resolvedOutputRoot -Force | Out-Null
$stamp = (Get-Date).ToUniversalTime().ToString('yyyyMMdd-HHmmss', [System.Globalization.CultureInfo]::InvariantCulture)
$summaryPath = Join-Path $resolvedOutputRoot ("gated-forward-smoke-currentpid-{0}-summary-{1}.json" -f $ProcessId, $stamp)

$firstPreflight = $null
$lastPostReadback = $null
$pulseResults = [System.Collections.Generic.List[object]]::new()
$movementSent = $false
$movementAttempted = $false

try {
    if ($ProcessId -le 0) {
        throw 'ProcessId must be greater than zero. Exact PID targeting is required for gated live input.'
    }

    if ([string]::IsNullOrWhiteSpace($TargetWindowHandle)) {
        throw 'TargetWindowHandle is required. Exact HWND targeting is required for gated live input.'
    }

    if (-not [string]::Equals($Key.Trim(), 'w', [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Only the forward key 'W' is allowed by this smoke wrapper. Requested key: '$Key'."
    }

    $Key = 'w'

    if ($HoldMilliseconds -le 0 -or $HoldMilliseconds -gt $maxHoldMilliseconds) {
        throw "HoldMilliseconds must be between 1 and $maxHoldMilliseconds."
    }

    if ($PulseCount -le 0 -or $PulseCount -gt $maxPulseCount) {
        throw "PulseCount must be between 1 and $maxPulseCount."
    }

    if ($InterPulseDelayMilliseconds -lt 0 -or $ProofAnchorMaxAgeSeconds -lt 0 -or $MinimumPostReadbackAgeBudgetSeconds -lt 0 -or
        $ReadbackSampleCount -le 0 -or $ReadbackIntervalMilliseconds -lt 0) {
        throw 'InterPulseDelayMilliseconds, ProofAnchorMaxAgeSeconds, and MinimumPostReadbackAgeBudgetSeconds must be zero or greater; ReadbackSampleCount must be greater than zero; ReadbackIntervalMilliseconds must be zero or greater.'
    }

    if (-not (Test-Path -LiteralPath $PreflightScript -PathType Leaf)) {
        throw "Preflight script was not found: $PreflightScript"
    }

    if (-not $DryRun -and -not (Test-Path -LiteralPath $KeyScript -PathType Leaf)) {
        throw "Key script was not found: $KeyScript"
    }

    $resolvedPreflightScript = [System.IO.Path]::GetFullPath($PreflightScript)
    $resolvedKeyScript = if ($DryRun) { $null } else { [System.IO.Path]::GetFullPath($KeyScript) }

    if ($DryRun) {
        $preCommand = Invoke-PowerShellScript -ScriptPath $resolvedPreflightScript -Arguments (New-ReadbackArguments) -AllowFailure
        $preSummary = Convert-CommandOutputToJson -CommandResult $preCommand -CommandName 'Dry-run preflight'
        $firstPreflight = $preSummary
        $preValid = Test-ReadbackGateValid -CommandResult $preCommand -Summary $preSummary
        $preAgeBudget = if ($preValid) { Get-ProofAnchorAgeBudget -Summary $preSummary } else { $null }
        if (-not $preValid) {
            $issues = Get-ReadbackGateIssues -Label 'preflight' -CommandResult $preCommand -Summary $preSummary
            $blockedDryRun = New-BaseSummary `
                -Status 'blocked-preflight' `
                -MovementSent:$false `
                -MovementAttempted:$false `
                -Issues $issues `
                -FirstPreflight $firstPreflight `
                -Pulses @(
                    [pscustomobject][ordered]@{
                        PulseIndex = 0
                        DryRun = $true
                        Preflight = ConvertTo-JsonSafeValue -Value $preSummary
                        PreflightProofAnchorAgeBudget = ConvertTo-JsonSafeValue -Value $preAgeBudget
                        PreflightCommand = Get-CommandSummary -CommandResult $preCommand
                    }
                )
            Complete-Summary -Summary $blockedDryRun -ExitCode 1
        }

        if ($null -ne $preAgeBudget -and -not [bool]$preAgeBudget.IsSufficient) {
            $issues = Get-ProofAnchorAgeBudgetIssues -Budget $preAgeBudget
            $blockedDryRunAgeBudget = New-BaseSummary `
                -Status 'blocked-preflight-age-budget' `
                -MovementSent:$false `
                -MovementAttempted:$false `
                -Issues $issues `
                -FirstPreflight $firstPreflight `
                -Pulses @(
                    [pscustomobject][ordered]@{
                        PulseIndex = 0
                        DryRun = $true
                        Preflight = ConvertTo-JsonSafeValue -Value $preSummary
                        PreflightProofAnchorAgeBudget = ConvertTo-JsonSafeValue -Value $preAgeBudget
                        PreflightCommand = Get-CommandSummary -CommandResult $preCommand
                    }
                )
            Complete-Summary -Summary $blockedDryRunAgeBudget -ExitCode 1
        }

        $dryRunSummary = New-BaseSummary `
            -Status 'dry-run-valid' `
            -MovementSent:$false `
            -MovementAttempted:$false `
            -FirstPreflight $firstPreflight `
            -Pulses @(
                [pscustomobject][ordered]@{
                    PulseIndex = 0
                    DryRun = $true
                    Preflight = ConvertTo-JsonSafeValue -Value $preSummary
                    PreflightProofAnchorAgeBudget = ConvertTo-JsonSafeValue -Value $preAgeBudget
                    PreflightCommand = Get-CommandSummary -CommandResult $preCommand
                }
            )
        Complete-Summary -Summary $dryRunSummary -ExitCode 0
    }

    for ($pulseIndex = 1; $pulseIndex -le $PulseCount; $pulseIndex++) {
        $preCommand = Invoke-PowerShellScript -ScriptPath $resolvedPreflightScript -Arguments (New-ReadbackArguments) -AllowFailure
        $preSummary = Convert-CommandOutputToJson -CommandResult $preCommand -CommandName "Pulse $pulseIndex preflight"
        if ($null -eq $firstPreflight) {
            $firstPreflight = $preSummary
        }

        $preCoordinate = Get-Coordinate -Summary $preSummary
        $preValid = Test-ReadbackGateValid -CommandResult $preCommand -Summary $preSummary
        $preAgeBudget = if ($preValid) { Get-ProofAnchorAgeBudget -Summary $preSummary } else { $null }
        if (-not $preValid) {
            $issues = Get-ReadbackGateIssues -Label 'preflight' -CommandResult $preCommand -Summary $preSummary
            $pulseResults.Add([pscustomobject][ordered]@{
                    PulseIndex = $pulseIndex
                    MovementAttempted = $false
                    MovementSent = $false
                    Preflight = ConvertTo-JsonSafeValue -Value $preSummary
                    PreflightProofAnchorAgeBudget = ConvertTo-JsonSafeValue -Value $preAgeBudget
                    PreflightCommand = Get-CommandSummary -CommandResult $preCommand
                    PostReadback = $null
                    PostReadbackCommand = $null
                    KeyCommand = $null
                    CoordinateDelta = $null
                }) | Out-Null
            $blocked = New-BaseSummary `
                -Status 'blocked-preflight' `
                -MovementSent:$movementSent `
                -MovementAttempted:$movementAttempted `
                -Issues $issues `
                -FirstPreflight $firstPreflight `
                -LastPostReadback $lastPostReadback `
                -CoordinateDelta (New-CoordinateDelta -Before (Get-Coordinate -Summary $firstPreflight) -After (Get-Coordinate -Summary $lastPostReadback)) `
                -Pulses @($pulseResults.ToArray())
            Complete-Summary -Summary $blocked -ExitCode 1
        }

        if ($null -ne $preAgeBudget -and -not [bool]$preAgeBudget.IsSufficient) {
            $issues = Get-ProofAnchorAgeBudgetIssues -Budget $preAgeBudget
            $pulseResults.Add([pscustomobject][ordered]@{
                    PulseIndex = $pulseIndex
                    MovementAttempted = $false
                    MovementSent = $false
                    Preflight = ConvertTo-JsonSafeValue -Value $preSummary
                    PreflightProofAnchorAgeBudget = ConvertTo-JsonSafeValue -Value $preAgeBudget
                    PreflightCommand = Get-CommandSummary -CommandResult $preCommand
                    PostReadback = $null
                    PostReadbackCommand = $null
                    KeyCommand = $null
                    CoordinateDelta = $null
                }) | Out-Null
            $blockedAgeBudget = New-BaseSummary `
                -Status 'blocked-preflight-age-budget' `
                -MovementSent:$movementSent `
                -MovementAttempted:$movementAttempted `
                -Issues $issues `
                -FirstPreflight $firstPreflight `
                -LastPostReadback $lastPostReadback `
                -CoordinateDelta (New-CoordinateDelta -Before (Get-Coordinate -Summary $firstPreflight) -After (Get-Coordinate -Summary $lastPostReadback)) `
                -Pulses @($pulseResults.ToArray())
            Complete-Summary -Summary $blockedAgeBudget -ExitCode 1
        }

        $movementAttempted = $true
        $keyCommand = Invoke-PowerShellScript -ScriptPath $resolvedKeyScript -Arguments (New-KeyArguments) -AllowFailure
        $keySucceeded = $keyCommand.ExitCode -eq 0
        if ($keySucceeded) {
            $movementSent = $true
        }

        if (-not $keySucceeded) {
            $pulseResults.Add([pscustomobject][ordered]@{
                    PulseIndex = $pulseIndex
                    MovementAttempted = $true
                    MovementSent = $false
                    Preflight = ConvertTo-JsonSafeValue -Value $preSummary
                    PreflightProofAnchorAgeBudget = ConvertTo-JsonSafeValue -Value $preAgeBudget
                    PreflightCommand = Get-CommandSummary -CommandResult $preCommand
                    PostReadback = $null
                    PostReadbackCommand = $null
                    KeyCommand = Get-CommandSummary -CommandResult $keyCommand
                    CoordinateDelta = $null
                }) | Out-Null
            $failedKey = New-BaseSummary `
                -Status 'failed-key-command' `
                -MovementSent:$movementSent `
                -MovementAttempted:$movementAttempted `
                -Issues @("key_command_failed:exitCode=$($keyCommand.ExitCode)") `
                -FirstPreflight $firstPreflight `
                -LastPostReadback $lastPostReadback `
                -CoordinateDelta (New-CoordinateDelta -Before (Get-Coordinate -Summary $firstPreflight) -After (Get-Coordinate -Summary $lastPostReadback)) `
                -Pulses @($pulseResults.ToArray())
            Complete-Summary -Summary $failedKey -ExitCode 1
        }

        $postCommand = Invoke-PowerShellScript -ScriptPath $resolvedPreflightScript -Arguments (New-ReadbackArguments) -AllowFailure
        $postSummary = Convert-CommandOutputToJson -CommandResult $postCommand -CommandName "Pulse $pulseIndex post-readback"
        $lastPostReadback = $postSummary
        $postCoordinate = Get-Coordinate -Summary $postSummary
        $pulseDelta = New-CoordinateDelta -Before $preCoordinate -After $postCoordinate

        $pulseResults.Add([pscustomobject][ordered]@{
                PulseIndex = $pulseIndex
                MovementAttempted = $true
                MovementSent = $true
                Preflight = ConvertTo-JsonSafeValue -Value $preSummary
                PreflightProofAnchorAgeBudget = ConvertTo-JsonSafeValue -Value $preAgeBudget
                PreflightCommand = Get-CommandSummary -CommandResult $preCommand
                KeyCommand = Get-CommandSummary -CommandResult $keyCommand
                PostReadback = ConvertTo-JsonSafeValue -Value $postSummary
                PostReadbackCommand = Get-CommandSummary -CommandResult $postCommand
                CoordinateDelta = ConvertTo-JsonSafeValue -Value $pulseDelta
            }) | Out-Null

        $postValid = Test-ReadbackGateValid -CommandResult $postCommand -Summary $postSummary
        if (-not $postValid) {
            $issues = Get-ReadbackGateIssues -Label 'post_readback' -CommandResult $postCommand -Summary $postSummary
            $blockedPost = New-BaseSummary `
                -Status 'blocked-post-readback' `
                -MovementSent:$movementSent `
                -MovementAttempted:$movementAttempted `
                -Issues $issues `
                -FirstPreflight $firstPreflight `
                -LastPostReadback $lastPostReadback `
                -CoordinateDelta (New-CoordinateDelta -Before (Get-Coordinate -Summary $firstPreflight) -After (Get-Coordinate -Summary $lastPostReadback)) `
                -Pulses @($pulseResults.ToArray())
            Complete-Summary -Summary $blockedPost -ExitCode 1
        }

        if ($pulseIndex -lt $PulseCount -and $InterPulseDelayMilliseconds -gt 0) {
            Start-Sleep -Milliseconds $InterPulseDelayMilliseconds
        }
    }

    $totalDelta = New-CoordinateDelta -Before (Get-Coordinate -Summary $firstPreflight) -After (Get-Coordinate -Summary $lastPostReadback)
    $passed = New-BaseSummary `
        -Status 'passed' `
        -MovementSent:$movementSent `
        -MovementAttempted:$movementAttempted `
        -FirstPreflight $firstPreflight `
        -LastPostReadback $lastPostReadback `
        -CoordinateDelta $totalDelta `
        -Pulses @($pulseResults.ToArray())
    Complete-Summary -Summary $passed -ExitCode 0
}
catch {
    $issues = @($_.Exception.Message)
    $failed = New-BaseSummary `
        -Status 'failed' `
        -MovementSent:$movementSent `
        -MovementAttempted:$movementAttempted `
        -Issues $issues `
        -FirstPreflight $firstPreflight `
        -LastPostReadback $lastPostReadback `
        -CoordinateDelta (New-CoordinateDelta -Before (Get-Coordinate -Summary $firstPreflight) -After (Get-Coordinate -Summary $lastPostReadback)) `
        -Pulses @($pulseResults.ToArray())
    Complete-Summary -Summary $failed -ExitCode 1
}
