[CmdletBinding()]
param(
    [switch]$Json,
    [string]$ReaderBridgeSnapshotFile,
    [string]$OutputFile = (Join-Path $PSScriptRoot 'captures\readerbridge-orientation-probe.json')
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$readerProject = Join-Path $repoRoot 'reader\RiftReader.Reader\RiftReader.Reader.csproj'
$resolvedOutputFile = [System.IO.Path]::GetFullPath($OutputFile)

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

    return ($output -join [Environment]::NewLine) | ConvertFrom-Json -Depth 80
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

function Convert-CandidateList {
    param($Candidates)

    $result = New-Object System.Collections.Generic.List[object]
    foreach ($candidate in @($Candidates)) {
        if ($null -eq $candidate) {
            continue
        }

        $result.Add([pscustomobject]@{
            Key = [string]$candidate.Key
            Value = [string]$candidate.Value
            Kind = [string]$candidate.Kind
        }) | Out-Null
    }

    return $result.ToArray()
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

function Get-ProbeSummary {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Label,
        $Probe
    )

    $detailCandidates = @(Convert-CandidateList -Candidates (Get-ObjectValue -Object $Probe -Name 'DetailCandidates'))
    $stateCandidates = @(Convert-CandidateList -Candidates (Get-ObjectValue -Object $Probe -Name 'StateCandidates'))

    $hasAnySignal =
        ($null -ne $Probe -and (
            $null -ne (Get-ObjectValue -Object $Probe -Name 'DirectHeading') -or
            $null -ne (Get-ObjectValue -Object $Probe -Name 'DirectPitch') -or
            $null -ne (Get-ObjectValue -Object $Probe -Name 'Yaw') -or
            -not [string]::IsNullOrWhiteSpace([string](Get-ObjectValue -Object $Probe -Name 'Facing')) -or
            $detailCandidates.Count -gt 0 -or
            $stateCandidates.Count -gt 0))

    return [pscustomobject]@{
        Label = $Label
        DirectHeading = Get-ObjectValue -Object $Probe -Name 'DirectHeading'
        DirectPitch = Get-ObjectValue -Object $Probe -Name 'DirectPitch'
        Yaw = Get-ObjectValue -Object $Probe -Name 'Yaw'
        Facing = [string](Get-ObjectValue -Object $Probe -Name 'Facing')
        DetailCandidateCount = $detailCandidates.Count
        StateCandidateCount = $stateCandidates.Count
        DetailCandidates = $detailCandidates
        StateCandidates = $stateCandidates
        HasAnySignal = $hasAnySignal
    }
}

function Write-CandidateBlock {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Title,
        $Candidates
    )

    $items = @($Candidates)
    if ($items.Count -le 0) {
        Write-Host ("{0}:                 none" -f $Title)
        return
    }

    Write-Host ("{0}:                 {1}" -f $Title, $items.Count)
    foreach ($candidate in $items) {
        $kindSuffix = if (-not [string]::IsNullOrWhiteSpace([string]$candidate.Kind)) { " [$($candidate.Kind)]" } else { '' }
        Write-Host ("  - {0}{1} = {2}" -f $candidate.Key, $kindSuffix, $candidate.Value) -ForegroundColor DarkGray
    }
}

$readerArguments = @('--readerbridge-snapshot', '--json')
if (-not [string]::IsNullOrWhiteSpace($ReaderBridgeSnapshotFile)) {
    $readerArguments += @('--readerbridge-snapshot-file', [System.IO.Path]::GetFullPath($ReaderBridgeSnapshotFile))
}

$snapshotDocument = Invoke-ReaderJson -Arguments $readerArguments
$current = $snapshotDocument.Current
$orientationProbe = Get-ObjectValue -Object $current -Name 'OrientationProbe'
$playerProbe = Get-ProbeSummary -Label 'player' -Probe (Get-ObjectValue -Object $orientationProbe -Name 'Player')
$targetProbe = Get-ProbeSummary -Label 'target' -Probe (Get-ObjectValue -Object $orientationProbe -Name 'Target')
$statCandidates = @(Convert-CandidateList -Candidates (Get-ObjectValue -Object $orientationProbe -Name 'StatCandidates'))

$notes = New-Object System.Collections.Generic.List[string]
if ($null -eq $orientationProbe) {
    $notes.Add('ReaderBridge snapshot did not contain an orientationProbe block.') | Out-Null
    $notes.Add('If this repo build should export orientationProbe, validate/sync the addon and refresh ReaderBridgeExport.lua.') | Out-Null
}
else {
    if ($playerProbe.HasAnySignal) {
        $notes.Add('Player orientation probe contains at least one direct or candidate signal.') | Out-Null
    }
    else {
        $notes.Add('Player orientation probe did not expose any direct or candidate signal.') | Out-Null
    }

    if ($targetProbe.HasAnySignal) {
        $notes.Add('Target orientation probe contains at least one direct or candidate signal.') | Out-Null
    }

    if ($statCandidates.Count -gt 0) {
        $notes.Add("Inspect.Stat exposed $($statCandidates.Count) orientation-like candidate(s).") | Out-Null
    }
}

$report = [pscustomobject]@{
    Mode = 'readerbridge-orientation-probe'
    GeneratedAtUtc = [DateTimeOffset]::UtcNow.ToString('O', [System.Globalization.CultureInfo]::InvariantCulture)
    OutputFile = $resolvedOutputFile
    SnapshotFile = [string]$snapshotDocument.SourceFile
    SnapshotLoadedAtUtc = [string]$snapshotDocument.LoadedAtUtc
    SnapshotStatus = [string](Get-ObjectValue -Object $current -Name 'Status')
    ExportReason = [string](Get-ObjectValue -Object $current -Name 'ExportReason')
    ExportCount = Get-ObjectValue -Object $current -Name 'ExportCount'
    PlayerName = [string](Get-ObjectValue -Object (Get-ObjectValue -Object $current -Name 'Player') -Name 'Name')
    TargetName = [string](Get-ObjectValue -Object (Get-ObjectValue -Object $current -Name 'Target') -Name 'Name')
    OrientationProbePresent = $null -ne $orientationProbe
    Player = $playerProbe
    Target = $targetProbe
    StatCandidateCount = $statCandidates.Count
    StatCandidates = $statCandidates
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

Write-Host 'ReaderBridge orientation probe'
Write-Host ("Snapshot file:               {0}" -f $report.SnapshotFile)
Write-Host ("Snapshot loaded (UTC):       {0}" -f $report.SnapshotLoadedAtUtc)
Write-Host ("Snapshot status:             {0}" -f $(if ($report.SnapshotStatus) { $report.SnapshotStatus } else { 'n/a' }))
Write-Host ("Export reason:               {0}" -f $(if ($report.ExportReason) { $report.ExportReason } else { 'n/a' }))
Write-Host ("Export count:                {0}" -f $(if ($null -ne $report.ExportCount) { $report.ExportCount } else { 'n/a' }))
Write-Host ("Player:                      {0}" -f $(if ($report.PlayerName) { $report.PlayerName } else { 'n/a' }))
Write-Host ("Target:                      {0}" -f $(if ($report.TargetName) { $report.TargetName } else { 'n/a' }))
Write-Host ("Orientation probe present:   {0}" -f $report.OrientationProbePresent)
Write-Host ("Player heading/pitch/yaw:    {0} / {1} / {2}" -f (Format-Nullable $playerProbe.DirectHeading), (Format-Nullable $playerProbe.DirectPitch), (Format-Nullable $playerProbe.Yaw))
Write-Host ("Player facing:               {0}" -f $(if ($playerProbe.Facing) { $playerProbe.Facing } else { 'n/a' }))
Write-Host ("Target heading/pitch/yaw:    {0} / {1} / {2}" -f (Format-Nullable $targetProbe.DirectHeading), (Format-Nullable $targetProbe.DirectPitch), (Format-Nullable $targetProbe.Yaw))
Write-Host ("Target facing:               {0}" -f $(if ($targetProbe.Facing) { $targetProbe.Facing } else { 'n/a' }))
Write-CandidateBlock -Title 'Player detail candidates' -Candidates $playerProbe.DetailCandidates
Write-CandidateBlock -Title 'Player state candidates' -Candidates $playerProbe.StateCandidates
Write-CandidateBlock -Title 'Target detail candidates' -Candidates $targetProbe.DetailCandidates
Write-CandidateBlock -Title 'Target state candidates' -Candidates $targetProbe.StateCandidates
Write-CandidateBlock -Title 'Stat candidates' -Candidates $statCandidates
if ($report.Notes.Count -gt 0) {
    Write-Host ("Notes:                       {0}" -f ([string]::Join('; ', $report.Notes)))
}
Write-Host ("Output file:                 {0}" -f $resolvedOutputFile)
