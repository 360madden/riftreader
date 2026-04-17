[CmdletBinding()]
param(
    [Parameter(Mandatory = $true, Position = 0)]
    [string]$Left,

    [Parameter(Mandatory = $true, Position = 1)]
    [string]$Right,

    [switch]$Json,
    [string]$OutputFile = (Join-Path $PSScriptRoot 'captures\readerbridge-orientation-probe.diff.json')
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$resolvedOutputFile = [System.IO.Path]::GetFullPath($OutputFile)

function Resolve-ProbeArtifactPath {
    param(
        [Parameter(Mandatory = $true)]
        [string]$InputPath
    )

    $resolved = [System.IO.Path]::GetFullPath($InputPath)
    if (-not (Test-Path -LiteralPath $resolved)) {
        throw "Path not found: $InputPath"
    }

    $item = Get-Item -LiteralPath $resolved
    if ($item.PSIsContainer) {
        $artifactPath = Join-Path $resolved 'readerbridge-orientation-probe.json'
        if (-not (Test-Path -LiteralPath $artifactPath)) {
            throw "Directory does not contain readerbridge-orientation-probe.json: $resolved"
        }

        return $artifactPath
    }

    return $resolved
}

function Read-ProbeDocument {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path
    )

    return Get-Content -LiteralPath $Path -Raw | ConvertFrom-Json -Depth 80
}

function Get-NormalizedText {
    param($Value)

    if ($null -eq $Value) {
        return $null
    }

    $text = [string]$Value
    if ([string]::IsNullOrWhiteSpace($text)) {
        return $null
    }

    return $text.Trim()
}

function Get-ObjectValue {
    param(
        $Object,
        [Parameter(Mandatory = $true)]
        [string]$Name
    )

    if ($null -eq $Object) {
        return $null
    }

    $property = $Object.PSObject.Properties[$Name]
    if ($null -eq $property) {
        return $null
    }

    return $property.Value
}

function Convert-CandidateList {
    param($Candidates)

    $items = New-Object System.Collections.Generic.List[object]
    foreach ($candidate in @($Candidates)) {
        if ($null -eq $candidate) {
            continue
        }

        $items.Add([pscustomobject]@{
            Key = Get-NormalizedText (Get-ObjectValue -Object $candidate -Name 'Key')
            Value = Get-NormalizedText (Get-ObjectValue -Object $candidate -Name 'Value')
            Kind = Get-NormalizedText (Get-ObjectValue -Object $candidate -Name 'Kind')
        }) | Out-Null
    }

    return @($items.ToArray())
}

function Get-CandidateIdentity {
    param($Candidate)

    return '{0}|{1}|{2}' -f
        (Get-NormalizedText (Get-ObjectValue -Object $Candidate -Name 'Key')),
        (Get-NormalizedText (Get-ObjectValue -Object $Candidate -Name 'Kind')),
        (Get-NormalizedText (Get-ObjectValue -Object $Candidate -Name 'Value'))
}

function Compare-CandidateLists {
    param(
        $LeftCandidates,
        $RightCandidates
    )

    $leftItems = @(Convert-CandidateList -Candidates $LeftCandidates)
    $rightItems = @(Convert-CandidateList -Candidates $RightCandidates)

    $leftMap = @{}
    foreach ($item in $leftItems) {
        $identity = Get-CandidateIdentity -Candidate $item
        if (-not [string]::IsNullOrWhiteSpace($identity)) {
            $leftMap[$identity] = $item
        }
    }

    $rightMap = @{}
    foreach ($item in $rightItems) {
        $identity = Get-CandidateIdentity -Candidate $item
        if (-not [string]::IsNullOrWhiteSpace($identity)) {
            $rightMap[$identity] = $item
        }
    }

    $added = New-Object System.Collections.Generic.List[object]
    foreach ($identity in @($rightMap.Keys | Sort-Object)) {
        if (-not $leftMap.ContainsKey($identity)) {
            $added.Add($rightMap[$identity]) | Out-Null
        }
    }

    $removed = New-Object System.Collections.Generic.List[object]
    foreach ($identity in @($leftMap.Keys | Sort-Object)) {
        if (-not $rightMap.ContainsKey($identity)) {
            $removed.Add($leftMap[$identity]) | Out-Null
        }
    }

    return [pscustomobject]@{
        Added = @($added.ToArray())
        Removed = @($removed.ToArray())
        AddedCount = $added.Count
        RemovedCount = $removed.Count
        UnchangedCount = @($leftMap.Keys | Where-Object { $rightMap.ContainsKey($_) }).Count
        Changed = ($added.Count -gt 0 -or $removed.Count -gt 0)
    }
}

function Compare-Scalar {
    param(
        [string]$Name,
        $LeftValue,
        $RightValue
    )

    $leftText = Get-NormalizedText $LeftValue
    $rightText = Get-NormalizedText $RightValue
    $leftNumber = $null
    $rightNumber = $null
    $hasLeftNumber = [double]::TryParse([string]$leftText, [System.Globalization.NumberStyles]::Float, [System.Globalization.CultureInfo]::InvariantCulture, [ref]$leftNumber)
    $hasRightNumber = [double]::TryParse([string]$rightText, [System.Globalization.NumberStyles]::Float, [System.Globalization.CultureInfo]::InvariantCulture, [ref]$rightNumber)

    return [pscustomobject]@{
        Name = $Name
        Left = $LeftValue
        Right = $RightValue
        Changed = ($leftText -ne $rightText)
        Delta = if ($hasLeftNumber -and $hasRightNumber) { $rightNumber - $leftNumber } else { $null }
    }
}

function Get-UnitDiff {
    param(
        [string]$Label,
        $LeftUnit,
        $RightUnit
    )

    $detailDiff = Compare-CandidateLists `
        -LeftCandidates (Get-ObjectValue -Object $LeftUnit -Name 'DetailCandidates') `
        -RightCandidates (Get-ObjectValue -Object $RightUnit -Name 'DetailCandidates')
    $stateDiff = Compare-CandidateLists `
        -LeftCandidates (Get-ObjectValue -Object $LeftUnit -Name 'StateCandidates') `
        -RightCandidates (Get-ObjectValue -Object $RightUnit -Name 'StateCandidates')

    $directHeading = Compare-Scalar -Name 'DirectHeading' `
        -LeftValue (Get-ObjectValue -Object $LeftUnit -Name 'DirectHeading') `
        -RightValue (Get-ObjectValue -Object $RightUnit -Name 'DirectHeading')
    $directPitch = Compare-Scalar -Name 'DirectPitch' `
        -LeftValue (Get-ObjectValue -Object $LeftUnit -Name 'DirectPitch') `
        -RightValue (Get-ObjectValue -Object $RightUnit -Name 'DirectPitch')
    $yaw = Compare-Scalar -Name 'Yaw' `
        -LeftValue (Get-ObjectValue -Object $LeftUnit -Name 'Yaw') `
        -RightValue (Get-ObjectValue -Object $RightUnit -Name 'Yaw')
    $facing = Compare-Scalar -Name 'Facing' `
        -LeftValue (Get-ObjectValue -Object $LeftUnit -Name 'Facing') `
        -RightValue (Get-ObjectValue -Object $RightUnit -Name 'Facing')

    return [pscustomobject]@{
        Label = $Label
        HasAnyChange = (
            $directHeading.Changed -or
            $directPitch.Changed -or
            $yaw.Changed -or
            $facing.Changed -or
            $detailDiff.Changed -or
            $stateDiff.Changed)
        DirectHeading = $directHeading
        DirectPitch = $directPitch
        Yaw = $yaw
        Facing = $facing
        DetailCandidates = $detailDiff
        StateCandidates = $stateDiff
    }
}

function Format-Nullable {
    param(
        $Value,
        [string]$Format = '0.0000'
    )

    if ($null -eq $Value) {
        return 'n/a'
    }

    return ([double]$Value).ToString($Format, [System.Globalization.CultureInfo]::InvariantCulture)
}

function Format-Candidate {
    param($Candidate)

    $key = Get-NormalizedText (Get-ObjectValue -Object $Candidate -Name 'Key')
    $kind = Get-NormalizedText (Get-ObjectValue -Object $Candidate -Name 'Kind')
    $value = Get-NormalizedText (Get-ObjectValue -Object $Candidate -Name 'Value')

    $kindSuffix = if (-not [string]::IsNullOrWhiteSpace($kind)) { " [$kind]" } else { '' }
    return '{0}{1} = {2}' -f $(if ($key) { $key } else { '(unnamed)' }), $kindSuffix, $(if ($value) { $value } else { '(blank)' })
}

function Write-CandidateDelta {
    param(
        [string]$Title,
        $Diff
    )

    if (-not $Diff.Changed) {
        Write-Host ("{0}:                    unchanged ({1})" -f $Title, $Diff.UnchangedCount)
        return
    }

    Write-Host ("{0}:                    +{1} / -{2} / ={3}" -f $Title, $Diff.AddedCount, $Diff.RemovedCount, $Diff.UnchangedCount)
    foreach ($candidate in @($Diff.Added)) {
        Write-Host ('  + ' + (Format-Candidate -Candidate $candidate)) -ForegroundColor Green
    }

    foreach ($candidate in @($Diff.Removed)) {
        Write-Host ('  - ' + (Format-Candidate -Candidate $candidate)) -ForegroundColor Yellow
    }
}

$leftArtifact = Resolve-ProbeArtifactPath -InputPath $Left
$rightArtifact = Resolve-ProbeArtifactPath -InputPath $Right
$leftDoc = Read-ProbeDocument -Path $leftArtifact
$rightDoc = Read-ProbeDocument -Path $rightArtifact

$leftPlayer = Get-ObjectValue -Object $leftDoc -Name 'Player'
$rightPlayer = Get-ObjectValue -Object $rightDoc -Name 'Player'
$leftTarget = Get-ObjectValue -Object $leftDoc -Name 'Target'
$rightTarget = Get-ObjectValue -Object $rightDoc -Name 'Target'

$playerDiff = Get-UnitDiff -Label 'player' -LeftUnit $leftPlayer -RightUnit $rightPlayer
$targetDiff = Get-UnitDiff -Label 'target' -LeftUnit $leftTarget -RightUnit $rightTarget
$statDiff = Compare-CandidateLists `
    -LeftCandidates (Get-ObjectValue -Object $leftDoc -Name 'StatCandidates') `
    -RightCandidates (Get-ObjectValue -Object $rightDoc -Name 'StatCandidates')
$probePresence = Compare-Scalar -Name 'OrientationProbePresent' `
    -LeftValue (Get-ObjectValue -Object $leftDoc -Name 'OrientationProbePresent') `
    -RightValue (Get-ObjectValue -Object $rightDoc -Name 'OrientationProbePresent')

$notes = New-Object System.Collections.Generic.List[string]
if ($probePresence.Changed) {
    $notes.Add("orientationProbe presence changed: $($probePresence.Left) -> $($probePresence.Right)") | Out-Null
}

foreach ($field in @($playerDiff.DirectHeading, $playerDiff.DirectPitch, $playerDiff.Yaw, $playerDiff.Facing)) {
    if ($field.Changed) {
        $deltaSuffix = if ($null -ne $field.Delta) { " (delta $([double]$field.Delta))" } else { '' }
        $notes.Add("player $($field.Name) changed: $($field.Left) -> $($field.Right)$deltaSuffix") | Out-Null
    }
}

foreach ($field in @($targetDiff.DirectHeading, $targetDiff.DirectPitch, $targetDiff.Yaw, $targetDiff.Facing)) {
    if ($field.Changed) {
        $deltaSuffix = if ($null -ne $field.Delta) { " (delta $([double]$field.Delta))" } else { '' }
        $notes.Add("target $($field.Name) changed: $($field.Left) -> $($field.Right)$deltaSuffix") | Out-Null
    }
}

if ($playerDiff.DetailCandidates.Changed) {
    $notes.Add("player detail candidates changed (+$($playerDiff.DetailCandidates.AddedCount) / -$($playerDiff.DetailCandidates.RemovedCount))") | Out-Null
}
if ($playerDiff.StateCandidates.Changed) {
    $notes.Add("player state candidates changed (+$($playerDiff.StateCandidates.AddedCount) / -$($playerDiff.StateCandidates.RemovedCount))") | Out-Null
}
if ($targetDiff.DetailCandidates.Changed) {
    $notes.Add("target detail candidates changed (+$($targetDiff.DetailCandidates.AddedCount) / -$($targetDiff.DetailCandidates.RemovedCount))") | Out-Null
}
if ($targetDiff.StateCandidates.Changed) {
    $notes.Add("target state candidates changed (+$($targetDiff.StateCandidates.AddedCount) / -$($targetDiff.StateCandidates.RemovedCount))") | Out-Null
}
if ($statDiff.Changed) {
    $notes.Add("stat candidates changed (+$($statDiff.AddedCount) / -$($statDiff.RemovedCount))") | Out-Null
}
if ($notes.Count -le 0) {
    $notes.Add('No orientation-probe differences were detected.') | Out-Null
}

$report = [pscustomobject]@{
    Mode = 'readerbridge-orientation-probe-diff'
    GeneratedAtUtc = [DateTimeOffset]::UtcNow.ToString('O', [System.Globalization.CultureInfo]::InvariantCulture)
    OutputFile = $resolvedOutputFile
    LeftFile = $leftArtifact
    RightFile = $rightArtifact
    LeftGeneratedAtUtc = [string](Get-ObjectValue -Object $leftDoc -Name 'GeneratedAtUtc')
    RightGeneratedAtUtc = [string](Get-ObjectValue -Object $rightDoc -Name 'GeneratedAtUtc')
    LeftSnapshotFile = [string](Get-ObjectValue -Object $leftDoc -Name 'SnapshotFile')
    RightSnapshotFile = [string](Get-ObjectValue -Object $rightDoc -Name 'SnapshotFile')
    OrientationProbePresent = $probePresence
    Player = $playerDiff
    Target = $targetDiff
    StatCandidates = $statDiff
    HasAnyChange = (
        $probePresence.Changed -or
        $playerDiff.HasAnyChange -or
        $targetDiff.HasAnyChange -or
        $statDiff.Changed)
    Notes = @($notes.ToArray())
}

$outputDirectory = Split-Path -Path $resolvedOutputFile -Parent
if (-not [string]::IsNullOrWhiteSpace($outputDirectory)) {
    New-Item -ItemType Directory -Path $outputDirectory -Force | Out-Null
}

$jsonText = $report | ConvertTo-Json -Depth 80
[System.IO.File]::WriteAllText($resolvedOutputFile, $jsonText)

if ($Json) {
    Write-Output $jsonText
    exit 0
}

Write-Host 'ReaderBridge orientation probe diff'
Write-Host ("Left file:                    {0}" -f $leftArtifact)
Write-Host ("Right file:                   {0}" -f $rightArtifact)
Write-Host ("Left generated (UTC):         {0}" -f $(if ($report.LeftGeneratedAtUtc) { $report.LeftGeneratedAtUtc } else { 'n/a' }))
Write-Host ("Right generated (UTC):        {0}" -f $(if ($report.RightGeneratedAtUtc) { $report.RightGeneratedAtUtc } else { 'n/a' }))
Write-Host ("Probe present change:         {0} -> {1}" -f $probePresence.Left, $probePresence.Right)
Write-Host ("Has any change:               {0}" -f $report.HasAnyChange)
Write-Host ("Player heading delta:         {0}" -f $(if ($null -ne $playerDiff.DirectHeading.Delta) { Format-Nullable $playerDiff.DirectHeading.Delta } else { 'n/a' }))
Write-Host ("Player pitch delta:           {0}" -f $(if ($null -ne $playerDiff.DirectPitch.Delta) { Format-Nullable $playerDiff.DirectPitch.Delta } else { 'n/a' }))
Write-Host ("Player yaw delta:             {0}" -f $(if ($null -ne $playerDiff.Yaw.Delta) { Format-Nullable $playerDiff.Yaw.Delta } else { 'n/a' }))
Write-Host ("Target heading delta:         {0}" -f $(if ($null -ne $targetDiff.DirectHeading.Delta) { Format-Nullable $targetDiff.DirectHeading.Delta } else { 'n/a' }))
Write-Host ("Target pitch delta:           {0}" -f $(if ($null -ne $targetDiff.DirectPitch.Delta) { Format-Nullable $targetDiff.DirectPitch.Delta } else { 'n/a' }))
Write-Host ("Target yaw delta:             {0}" -f $(if ($null -ne $targetDiff.Yaw.Delta) { Format-Nullable $targetDiff.Yaw.Delta } else { 'n/a' }))
Write-CandidateDelta -Title 'Player detail candidates' -Diff $playerDiff.DetailCandidates
Write-CandidateDelta -Title 'Player state candidates' -Diff $playerDiff.StateCandidates
Write-CandidateDelta -Title 'Target detail candidates' -Diff $targetDiff.DetailCandidates
Write-CandidateDelta -Title 'Target state candidates' -Diff $targetDiff.StateCandidates
Write-CandidateDelta -Title 'Stat candidates' -Diff $statDiff
if ($report.Notes.Count -gt 0) {
    Write-Host ("Notes:                        {0}" -f ([string]::Join('; ', $report.Notes)))
}
Write-Host ("Output file:                  {0}" -f $resolvedOutputFile)
