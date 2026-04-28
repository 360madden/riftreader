[CmdletBinding()]
param(
    [switch]$Json,
    [string]$ProcessName = 'rift_x64',
    [int]$ProcessId,
    [string]$TargetWindowHandle,
    [double]$MaxYawDeltaDegrees = 0.05,
    [double]$MaxPitchDeltaDegrees = 0.05
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$readerProject = Join-Path $repoRoot 'reader\RiftReader.Reader\RiftReader.Reader.csproj'
$captureScript = Join-Path $repoRoot 'scripts\capture-actor-orientation.ps1'

function Invoke-ReaderJson {
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$Arguments
    )

    $output = & dotnet run --project $readerProject -- @Arguments 2>&1
    $exitCode = $LASTEXITCODE
    if ($exitCode -ne 0) {
        throw "Reader command failed (`$LASTEXITCODE=$exitCode): $($output -join [Environment]::NewLine)"
    }

    return ($output -join [Environment]::NewLine) | ConvertFrom-Json -Depth 20
}

function Invoke-ScriptJson {
    param(
        [Parameter(Mandatory = $true)]
        [string]$ScriptFile,
        [Parameter(Mandatory = $true)]
        [string[]]$Arguments
    )

    $output = & pwsh -NoProfile -ExecutionPolicy Bypass -File $ScriptFile @Arguments 2>&1
    $exitCode = $LASTEXITCODE
    if ($exitCode -ne 0) {
        throw "Script command failed (`$LASTEXITCODE=$exitCode): $($output -join [Environment]::NewLine)"
    }

    return ($output -join [Environment]::NewLine) | ConvertFrom-Json -Depth 20
}

function Get-ReaderTargetArguments {
    if ($ProcessId -gt 0) {
        return @('--pid', $ProcessId.ToString([System.Globalization.CultureInfo]::InvariantCulture))
    }

    return @('--process-name', $ProcessName)
}

function Get-ScriptTargetArguments {
    $arguments = @()
    if ($ProcessId -gt 0) {
        $arguments += @('-ProcessId', $ProcessId.ToString([System.Globalization.CultureInfo]::InvariantCulture))
    }
    else {
        $arguments += @('-ProcessName', $ProcessName)
    }
    if (-not [string]::IsNullOrWhiteSpace($TargetWindowHandle)) {
        $arguments += @('-TargetWindowHandle', $TargetWindowHandle)
    }

    return $arguments
}

function Get-OrientationSummary {
    param(
        [Parameter(Mandatory = $true)]
        [psobject]$Document
    )

    $basisPrimaryForwardOffset = $null
    if ($Document.PSObject.Properties['BasisPrimaryForwardOffset']) {
        $basisPrimaryForwardOffset = [string]$Document.BasisPrimaryForwardOffset
    }
    elseif ($Document.PSObject.Properties['BasisForwardOffset']) {
        $basisPrimaryForwardOffset = [string]$Document.BasisForwardOffset
    }
    elseif ($Document.PSObject.Properties['LiveSourceSample'] -and $null -ne $Document.LiveSourceSample) {
        if ($Document.LiveSourceSample.PSObject.Properties['BasisPrimaryForwardOffset']) {
            $basisPrimaryForwardOffset = [string]$Document.LiveSourceSample.BasisPrimaryForwardOffset
        }
        elseif ($Document.LiveSourceSample.PSObject.Properties['ResolvedForwardOffset']) {
            $basisPrimaryForwardOffset = [string]$Document.LiveSourceSample.ResolvedForwardOffset
        }
    }

    $basisDuplicateForwardOffset = $null
    if ($Document.PSObject.Properties['BasisDuplicateForwardOffset']) {
        $basisDuplicateForwardOffset = [string]$Document.BasisDuplicateForwardOffset
    }
    elseif ($Document.PSObject.Properties['LiveSourceSample'] -and $null -ne $Document.LiveSourceSample) {
        if ($Document.LiveSourceSample.PSObject.Properties['BasisDuplicateForwardOffset']) {
            $basisDuplicateForwardOffset = [string]$Document.LiveSourceSample.BasisDuplicateForwardOffset
        }
        elseif ($Document.LiveSourceSample.PSObject.Properties['ResolvedDuplicateForwardOffset']) {
            $basisDuplicateForwardOffset = [string]$Document.LiveSourceSample.ResolvedDuplicateForwardOffset
        }
    }

    return [pscustomobject]@{
        SelectedSourceAddress = [string]$Document.SelectedSourceAddress
        ResolutionMode = [string]$Document.ResolutionMode
        BasisPrimaryForwardOffset = $basisPrimaryForwardOffset
        BasisDuplicateForwardOffset = $basisDuplicateForwardOffset
        PreferredYawDegrees = if ($null -ne $Document.PreferredEstimate -and $null -ne $Document.PreferredEstimate.YawDegrees) { [double]$Document.PreferredEstimate.YawDegrees } else { $null }
        PreferredPitchDegrees = if ($null -ne $Document.PreferredEstimate -and $null -ne $Document.PreferredEstimate.PitchDegrees) { [double]$Document.PreferredEstimate.PitchDegrees } else { $null }
    }
}

$captureDocument = Invoke-ScriptJson -ScriptFile $captureScript -Arguments (@('-Json') + (Get-ScriptTargetArguments))
$nativeDocument = Invoke-ReaderJson -Arguments (@(Get-ReaderTargetArguments) + @('--read-player-orientation', '--json'))

$captureOrientation = Get-OrientationSummary -Document $captureDocument.ReaderOrientation
$nativeOrientation = Get-OrientationSummary -Document $nativeDocument

$yawDeltaDegrees = if ($null -ne $captureOrientation.PreferredYawDegrees -and $null -ne $nativeOrientation.PreferredYawDegrees) {
    [Math]::Abs([double]$captureOrientation.PreferredYawDegrees - [double]$nativeOrientation.PreferredYawDegrees)
}
else {
    $null
}

$pitchDeltaDegrees = if ($null -ne $captureOrientation.PreferredPitchDegrees -and $null -ne $nativeOrientation.PreferredPitchDegrees) {
    [Math]::Abs([double]$captureOrientation.PreferredPitchDegrees - [double]$nativeOrientation.PreferredPitchDegrees)
}
else {
    $null
}

$issues = New-Object System.Collections.Generic.List[string]

if (-not [string]::Equals($captureOrientation.SelectedSourceAddress, $nativeOrientation.SelectedSourceAddress, [System.StringComparison]::OrdinalIgnoreCase)) {
    $issues.Add("Selected source mismatch: capture=$($captureOrientation.SelectedSourceAddress); native=$($nativeOrientation.SelectedSourceAddress)")
}

if (-not [string]::Equals($captureOrientation.BasisPrimaryForwardOffset, $nativeOrientation.BasisPrimaryForwardOffset, [System.StringComparison]::OrdinalIgnoreCase)) {
    $issues.Add("Primary basis offset mismatch: capture=$($captureOrientation.BasisPrimaryForwardOffset); native=$($nativeOrientation.BasisPrimaryForwardOffset)")
}

if (-not [string]::Equals($captureOrientation.BasisDuplicateForwardOffset, $nativeOrientation.BasisDuplicateForwardOffset, [System.StringComparison]::OrdinalIgnoreCase)) {
    $issues.Add("Duplicate basis offset mismatch: capture=$($captureOrientation.BasisDuplicateForwardOffset); native=$($nativeOrientation.BasisDuplicateForwardOffset)")
}

if ($null -ne $yawDeltaDegrees -and $yawDeltaDegrees -gt $MaxYawDeltaDegrees) {
    $issues.Add("Yaw delta $([Math]::Round($yawDeltaDegrees, 6)) deg exceeded tolerance $MaxYawDeltaDegrees deg.")
}

if ($null -ne $pitchDeltaDegrees -and $pitchDeltaDegrees -gt $MaxPitchDeltaDegrees) {
    $issues.Add("Pitch delta $([Math]::Round($pitchDeltaDegrees, 6)) deg exceeded tolerance $MaxPitchDeltaDegrees deg.")
}

$result = [ordered]@{
    Mode = 'orientation-reader-parity'
    GeneratedAtUtc = [DateTimeOffset]::UtcNow.ToString('O', [System.Globalization.CultureInfo]::InvariantCulture)
    ProcessName = $ProcessName
    ProcessId = if ($ProcessId -gt 0) { $ProcessId } else { $null }
    TargetWindowHandle = $TargetWindowHandle
    Status = if ($issues.Count -eq 0) { 'pass' } else { 'fail' }
    Capture = $captureOrientation
    Native = $nativeOrientation
    YawDeltaDegrees = $yawDeltaDegrees
    PitchDeltaDegrees = $pitchDeltaDegrees
    MaxYawDeltaDegrees = $MaxYawDeltaDegrees
    MaxPitchDeltaDegrees = $MaxPitchDeltaDegrees
    Issues = @($issues)
}

$jsonText = $result | ConvertTo-Json -Depth 10

if ($Json) {
    Write-Output $jsonText
}
else {
    Write-Host "Orientation parity: $($result.Status)"
    Write-Host "Capture source   : $($captureOrientation.SelectedSourceAddress)"
    Write-Host "Native source    : $($nativeOrientation.SelectedSourceAddress)"
    Write-Host "Yaw delta (deg)  : $yawDeltaDegrees"
    Write-Host "Pitch delta (deg): $pitchDeltaDegrees"
    if ($issues.Count -gt 0) {
        Write-Host "Issues:"
        foreach ($issue in $issues) {
            Write-Host "  - $issue"
        }
    }
}

if ($issues.Count -gt 0) {
    exit 1
}
