[CmdletBinding()]
param(
    [switch]$Json,
    [string]$LedgerFile = (Join-Path $PSScriptRoot 'captures\ce-debugger-attach-failures.csv'),
    [ValidateRange(1, 100)]
    [int]$RecentCount = 8
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$summarySchemaVersion = 1
$resolvedLedgerFile = [System.IO.Path]::GetFullPath($LedgerFile)

function Try-ParseDateTimeOffset {
    param([object]$Value)

    if ($null -eq $Value -or [string]::IsNullOrWhiteSpace([string]$Value)) {
        return $null
    }

    try {
        return [DateTimeOffset]::Parse(
            [string]$Value,
            [System.Globalization.CultureInfo]::InvariantCulture,
            [System.Globalization.DateTimeStyles]::RoundtripKind)
    }
    catch {
        return $null
    }
}

function Get-NormalizedText {
    param([object]$Value)

    if ($null -eq $Value) {
        return $null
    }

    $text = [string]$Value
    if ([string]::IsNullOrWhiteSpace($text)) {
        return $null
    }

    return $text.Trim()
}

function Convert-ToBoolean {
    param([object]$Value)

    return ([string]$Value).Trim().Equals('True', [System.StringComparison]::OrdinalIgnoreCase)
}

function Get-StageFromNotes {
    param([object]$Notes)

    $text = Get-NormalizedText $Notes
    if ([string]::IsNullOrWhiteSpace($text)) {
        return $null
    }

    $match = [System.Text.RegularExpressions.Regex]::Match($text, '(?:^|;\s*)stage=([^;]+)')
    if (-not $match.Success) {
        return $null
    }

    return $match.Groups[1].Value.Trim()
}

function Get-SortTicks {
    param([psobject]$Entry)

    if ($null -eq $Entry.TimestampSort) {
        return [long]::MinValue
    }

    return $Entry.TimestampSort.UtcTicks
}

$rawEntries = if (Test-Path -LiteralPath $resolvedLedgerFile) {
    @(Import-Csv -LiteralPath $resolvedLedgerFile)
}
else {
    @()
}

$entries = @(
    foreach ($row in $rawEntries) {
        $timestamp = Try-ParseDateTimeOffset $row.TimestampUtc
        $stage = Get-StageFromNotes $row.Notes
        [pscustomobject][ordered]@{
            TimestampUtc = if ($null -ne $timestamp) { $timestamp.ToString('O', [System.Globalization.CultureInfo]::InvariantCulture) } else { Get-NormalizedText $row.TimestampUtc }
            TimestampSort = $timestamp
            ScriptName = Get-NormalizedText $row.ScriptName
            Outcome = Get-NormalizedText $row.Outcome
            Stage = $stage
            ErrorText = Get-NormalizedText $row.ErrorText
            DebuggerMode = Get-NormalizedText $row.DebuggerMode
            StatusFile = Get-NormalizedText $row.StatusFile
            StatusFileProduced = Convert-ToBoolean $row.StatusFileProduced
            CeStayedOpen = Convert-ToBoolean $row.CeStayedOpen
            CeDetached = Convert-ToBoolean $row.CeDetached
            CeCrashed = Convert-ToBoolean $row.CeCrashed
            CeProcessCount = if ([string]::IsNullOrWhiteSpace([string]$row.CeProcessCount)) { $null } else { [int]$row.CeProcessCount }
            RiftProcessId = if ([string]::IsNullOrWhiteSpace([string]$row.RiftProcessId)) { $null } else { [int]$row.RiftProcessId }
            Notes = Get-NormalizedText $row.Notes
        }
    }
)

$sortedEntries = @($entries | Sort-Object @{ Expression = { Get-SortTicks $_ }; Descending = $true }, ScriptName, ErrorText)
$firstTimestamp = @($entries | Where-Object { $null -ne $_.TimestampSort } | Sort-Object TimestampSort | Select-Object -First 1)
$lastTimestamp = @($entries | Where-Object { $null -ne $_.TimestampSort } | Sort-Object TimestampSort -Descending | Select-Object -First 1)

$scriptGroups = @(
    $entries |
        Group-Object ScriptName |
        Sort-Object @{ Expression = { $_.Count }; Descending = $true }, @{ Expression = { $_.Name }; Descending = $false } |
        ForEach-Object {
            $groupEntries = @($_.Group | Sort-Object @{ Expression = { Get-SortTicks $_ }; Descending = $true })
            $latest = if ($groupEntries.Count -gt 0) { $groupEntries[0] } else { $null }
            [pscustomobject][ordered]@{
                ScriptName = if ([string]::IsNullOrWhiteSpace($_.Name)) { '(unknown)' } else { $_.Name }
                Count = $_.Count
                LastTimestampUtc = if ($null -ne $latest) { $latest.TimestampUtc } else { $null }
                LastStage = if ($null -ne $latest) { $latest.Stage } else { $null }
                LastErrorText = if ($null -ne $latest) { $latest.ErrorText } else { $null }
            }
        }
)

$stageGroups = @(
    $entries |
        Group-Object { if ([string]::IsNullOrWhiteSpace($_.Stage)) { '(unknown)' } else { $_.Stage } } |
        Sort-Object @{ Expression = { $_.Count }; Descending = $true }, @{ Expression = { $_.Name }; Descending = $false } |
        ForEach-Object {
            [pscustomobject][ordered]@{
                Stage = $_.Name
                Count = $_.Count
            }
        }
)

$errorGroups = @(
    $entries |
        Group-Object { if ([string]::IsNullOrWhiteSpace($_.ErrorText)) { '(blank)' } else { $_.ErrorText } } |
        Sort-Object @{ Expression = { $_.Count }; Descending = $true }, @{ Expression = { $_.Name }; Descending = $false } |
        ForEach-Object {
            [pscustomobject][ordered]@{
                ErrorText = $_.Name
                Count = $_.Count
                Scripts = @($_.Group | ForEach-Object { $_.ScriptName } | Where-Object { -not [string]::IsNullOrWhiteSpace($_) } | Sort-Object -Unique)
            }
        }
)

$recentEntries = @(
    $sortedEntries |
        Select-Object -First $RecentCount |
        ForEach-Object {
            [pscustomobject][ordered]@{
                TimestampUtc = $_.TimestampUtc
                ScriptName = $_.ScriptName
                Outcome = $_.Outcome
                Stage = $_.Stage
                ErrorText = $_.ErrorText
                StatusFileProduced = $_.StatusFileProduced
                CeStayedOpen = $_.CeStayedOpen
                CeDetached = $_.CeDetached
                CeCrashed = $_.CeCrashed
                Notes = $_.Notes
            }
        }
)

$report = [ordered]@{
    SchemaVersion = $summarySchemaVersion
    Mode = 'ce-debugger-attach-failure-summary'
    LedgerFile = $resolvedLedgerFile
    GeneratedAtUtc = [DateTimeOffset]::UtcNow.ToString('O', [System.Globalization.CultureInfo]::InvariantCulture)
    EntryCount = $entries.Count
    FirstTimestampUtc = if ($firstTimestamp.Count -gt 0) { $firstTimestamp[0].TimestampUtc } else { $null }
    LastTimestampUtc = if ($lastTimestamp.Count -gt 0) { $lastTimestamp[0].TimestampUtc } else { $null }
    StatusFileProducedCount = @($entries | Where-Object { $_.StatusFileProduced }).Count
    CeStayedOpenCount = @($entries | Where-Object { $_.CeStayedOpen }).Count
    CeDetachedCount = @($entries | Where-Object { $_.CeDetached }).Count
    CeCrashedCount = @($entries | Where-Object { $_.CeCrashed }).Count
    Scripts = @($scriptGroups)
    Stages = @($stageGroups)
    Errors = @($errorGroups | Select-Object -First 10)
    RecentEntries = @($recentEntries)
}

if ($Json) {
    $report | ConvertTo-Json -Depth 20
    return
}

Write-Host 'CE debugger attach failure summary' -ForegroundColor Cyan
Write-Host "Ledger:              $resolvedLedgerFile"
Write-Host "Entries:             $($report.EntryCount)"
Write-Host "First failure UTC:   $($report.FirstTimestampUtc)"
Write-Host "Last failure UTC:    $($report.LastTimestampUtc)"
Write-Host "Status file present: $($report.StatusFileProducedCount)"
Write-Host "CE stayed open:      $($report.CeStayedOpenCount)"
Write-Host "CE detached:         $($report.CeDetachedCount)"
Write-Host "CE crashed:          $($report.CeCrashedCount)"

if ($entries.Count -le 0) {
    Write-Host ''
    Write-Host 'No CE debugger attach failures are logged yet.' -ForegroundColor Yellow
    return
}

Write-Host ''
Write-Host 'By script:' -ForegroundColor Cyan
foreach ($group in $scriptGroups) {
    Write-Host ("  {0} | count={1} | last={2} | stage={3}" -f $group.ScriptName, $group.Count, $group.LastTimestampUtc, $group.LastStage)
    if (-not [string]::IsNullOrWhiteSpace([string]$group.LastErrorText)) {
        Write-Host ('    last error: ' + $group.LastErrorText) -ForegroundColor DarkGray
    }
}

Write-Host ''
Write-Host 'By stage:' -ForegroundColor Cyan
foreach ($group in $stageGroups) {
    Write-Host ("  {0} | count={1}" -f $group.Stage, $group.Count)
}

Write-Host ''
Write-Host 'Top errors:' -ForegroundColor Cyan
foreach ($group in ($errorGroups | Select-Object -First 5)) {
    Write-Host ("  {0} | count={1}" -f $group.ErrorText, $group.Count)
    if ($group.Scripts.Count -gt 0) {
        Write-Host ('    scripts: ' + ($group.Scripts -join ', ')) -ForegroundColor DarkGray
    }
}

Write-Host ''
Write-Host ("Recent entries (top {0}):" -f [Math]::Min($RecentCount, $recentEntries.Count)) -ForegroundColor Cyan
foreach ($entry in $recentEntries) {
    Write-Host ("  {0} | {1} | stage={2} | status-file={3}" -f $entry.TimestampUtc, $entry.ScriptName, $entry.Stage, $entry.StatusFileProduced)
    if (-not [string]::IsNullOrWhiteSpace([string]$entry.ErrorText)) {
        Write-Host ('    error: ' + $entry.ErrorText) -ForegroundColor DarkGray
    }
    if (-not [string]::IsNullOrWhiteSpace([string]$entry.Notes)) {
        Write-Host ('    notes: ' + $entry.Notes) -ForegroundColor DarkGray
    }
}
