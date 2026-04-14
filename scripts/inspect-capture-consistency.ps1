[CmdletBinding()]
param(
    [switch]$Json,
    [string]$CapturesPath
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$captureConsistencySchemaVersion = 1

$scriptRoot = if (-not [string]::IsNullOrWhiteSpace($PSScriptRoot)) { $PSScriptRoot } else { Split-Path -Parent $MyInvocation.MyCommand.Path }
if ([string]::IsNullOrWhiteSpace($CapturesPath)) {
    $CapturesPath = Join-Path $scriptRoot 'captures'
}

$resolvedCapturesPath = [System.IO.Path]::GetFullPath($CapturesPath)

function Get-NestedValue {
    param(
        [object]$InputObject,
        [Parameter(Mandatory = $true)]
        [string]$Path
    )

    $current = $InputObject
    foreach ($segment in $Path.Split('.')) {
        if ($null -eq $current) {
            return $null
        }

        if ($current -is [System.Collections.IDictionary]) {
            if (-not $current.Contains($segment)) {
                return $null
            }

            $current = $current[$segment]
            continue
        }

        $match = $current.PSObject.Properties[$segment]
        if ($null -eq $match) {
            return $null
        }

        $current = $match.Value
    }

    return $current
}

function Get-FirstValue {
    param(
        [object]$InputObject,
        [Parameter(Mandatory = $true)]
        [string[]]$Paths
    )

    foreach ($path in $Paths) {
        $value = Get-NestedValue -InputObject $InputObject -Path $path
        if ($null -ne $value -and -not [string]::IsNullOrWhiteSpace([string]$value)) {
            return $value
        }
    }

    return $null
}

function Try-ParseDateTimeOffset {
    param([object]$Value)

    if ($null -eq $Value) {
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

function Normalize-Hex {
    param([object]$Value)

    if ($null -eq $Value) {
        return $null
    }

    $text = [string]$Value
    if ([string]::IsNullOrWhiteSpace($text)) {
        return $null
    }

    return $text.Trim().ToUpperInvariant()
}

function Format-Value {
    param([object]$Value)

    if ($null -eq $Value) {
        return 'n/a'
    }

    $text = [string]$Value
    if ([string]::IsNullOrWhiteSpace($text)) {
        return 'n/a'
    }

    return $text
}

function Add-ComparisonWarning {
    param(
        [Parameter(Mandatory = $true)]
        [hashtable]$RecordsByFile,

        [Parameter(Mandatory = $true)]
        [System.Collections.Generic.List[string]]$Warnings,

        [Parameter(Mandatory = $true)]
        [string]$LeftFile,

        [Parameter(Mandatory = $true)]
        [string]$LeftProperty,

        [Parameter(Mandatory = $true)]
        [string]$RightFile,

        [Parameter(Mandatory = $true)]
        [string]$RightProperty,

        [Parameter(Mandatory = $true)]
        [string]$Message
    )

    if (-not $RecordsByFile.ContainsKey($LeftFile) -or -not $RecordsByFile.ContainsKey($RightFile)) {
        return
    }

    $leftValue = [string]$RecordsByFile[$LeftFile].$LeftProperty
    $rightValue = [string]$RecordsByFile[$RightFile].$RightProperty

    if ([string]::IsNullOrWhiteSpace($leftValue) -or [string]::IsNullOrWhiteSpace($rightValue)) {
        return
    }

    if ($leftValue -ne $rightValue) {
        $Warnings.Add(('{0} | {1}' -f $Message, "$LeftFile.$LeftProperty=$leftValue vs $RightFile.$RightProperty=$rightValue"))
    }
}

$captureFiles = Get-ChildItem -LiteralPath $resolvedCapturesPath -File -Filter '*.json' |
    Where-Object {
        $_.Name -notlike 'tmp-*' -and
        $_.Name -notlike '*.previous.json'
    } |
    Sort-Object Name

$records = New-Object System.Collections.Generic.List[object]
$warnings = New-Object System.Collections.Generic.List[string]
$parsedCount = 0

foreach ($file in $captureFiles) {
    $document = $null
    $parseError = $null

    try {
        $document = Get-Content -LiteralPath $file.FullName -Raw | ConvertFrom-Json
    }
    catch {
        $parseError = $_.Exception.Message
    }

    $mode = if ($null -ne $document) { Format-Value (Get-FirstValue $document @('Mode', 'mode')) } else { 'n/a' }
    $generatedAtUtc = Try-ParseDateTimeOffset (Get-FirstValue $document @('GeneratedAtUtc', 'generatedAtUtc', 'SavedAtUtc', 'savedAtUtc'))
    $loadedAtUtc = Try-ParseDateTimeOffset (Get-FirstValue $document @('LoadedAtUtc', 'loadedAtUtc'))
    $sourceFile = Format-Value (Get-FirstValue $document @('SourceFile', 'sourceFile', 'ReaderBridgeSourceFile', 'Reader.SourceFile', 'ClusterFile', 'TraceFile', 'SelectorTraceFile'))
    $processName = Format-Value (Get-FirstValue $document @('ProcessName', 'processName', 'Reader.ProcessName', 'Trace.ProcessName', 'Owner.ProcessName'))
    $processId = Get-FirstValue $document @('ProcessId', 'processId', 'Reader.ProcessId', 'Trace.ProcessId', 'Owner.ProcessId')
    $ownerAddress = Normalize-Hex (Get-FirstValue $document @('Owner.Address', 'Owner.ObjectAddress', 'OwnerAddress', 'ownerAddress'))
    $containerAddress = Normalize-Hex (Get-FirstValue $document @('Owner.ContainerAddress', 'ContainerAddress', 'containerAddress'))
    $selectedSourceAddress = Normalize-Hex (Get-FirstValue $document @('SelectedSource.Address', 'Owner.SelectedSourceAddress', 'SelectedSourceAddress', 'PreferredSourceAddress', 'SourceObjectAddress', 'SourceObjectRegisterValue'))
    $stateRecordAddress = Normalize-Hex (Get-FirstValue $document @('Owner.StateRecordAddress', 'StateRecordAddress', 'StateSlot50', 'StateSlot58', 'StateSlot60'))
    $selectedEntryAddress = Normalize-Hex (Get-FirstValue $document @('SelectedEntry.Address', 'SelectedEntryAddress'))
    $sourceObjectAddress = Normalize-Hex (Get-FirstValue $document @('SourceObjectAddress', 'SelectedSourceAddress', 'SourceObjectRegisterValue'))
    $selectorTraceFile = Format-Value (Get-FirstValue $document @('SelectorTraceFile', 'selectorTraceFile', 'TraceFile', 'SourceChainFile', 'ClusterFile'))
    $familyId = Format-Value (Get-FirstValue $document @('FamilyId', 'familyId'))
    $signature = Format-Value (Get-FirstValue $document @('Signature', 'signature'))
    $selectionSource = Format-Value (Get-FirstValue $document @('SelectionSource', 'selectionSource', 'AnchorProvenance'))

    $recordWarnings = New-Object System.Collections.Generic.List[string]
    if ($null -eq $document) {
        $recordWarnings.Add("parse failed: $parseError")
    }
    else {
        $parsedCount++
        if ([string]::IsNullOrWhiteSpace([string]$mode)) {
            $recordWarnings.Add('missing Mode')
        }
    }
    if ($null -eq $generatedAtUtc) {
        $recordWarnings.Add('missing or invalid GeneratedAtUtc')
    }
    if ([string]::IsNullOrWhiteSpace($selectedSourceAddress) -and [string]::IsNullOrWhiteSpace($sourceObjectAddress)) {
        $recordWarnings.Add('no selected source or source object anchor found')
    }

    $records.Add([pscustomobject][ordered]@{
        FileName = $file.Name
        FullName = $file.FullName
        Mode = $mode
        GeneratedAtUtc = if ($null -ne $generatedAtUtc) { $generatedAtUtc.ToString('O') } else { $null }
        LoadedAtUtc = if ($null -ne $loadedAtUtc) { $loadedAtUtc.ToString('O') } else { $null }
        ProcessName = $processName
        ProcessId = if ($null -ne $processId) { [string]$processId } else { $null }
        SourceFile = $sourceFile
        SelectorTraceFile = $selectorTraceFile
        FamilyId = $familyId
        Signature = $signature
        SelectionSource = $selectionSource
        OwnerAddress = $ownerAddress
        ContainerAddress = $containerAddress
        SelectedSourceAddress = $selectedSourceAddress
        StateRecordAddress = $stateRecordAddress
        SelectedEntryAddress = $selectedEntryAddress
        SourceObjectAddress = $sourceObjectAddress
        Warnings = @($recordWarnings)
    })

    foreach ($warning in $recordWarnings) {
        $warnings.Add("$($file.Name): $warning")
    }
}

$recordsByFile = @{}
foreach ($record in $records) {
    $recordsByFile[$record.FileName] = $record
}

Add-ComparisonWarning -RecordsByFile $recordsByFile -Warnings $warnings -LeftFile 'player-selector-owner-trace.json' -LeftProperty 'SelectedSourceAddress' -RightFile 'player-owner-components.json' -RightProperty 'SelectedSourceAddress' -Message 'selected-source mismatch'
Add-ComparisonWarning -RecordsByFile $recordsByFile -Warnings $warnings -LeftFile 'player-owner-components.json' -LeftProperty 'SelectedSourceAddress' -RightFile 'player-source-accessor-family.json' -RightProperty 'SourceObjectAddress' -Message 'owner/source-object mismatch'
Add-ComparisonWarning -RecordsByFile $recordsByFile -Warnings $warnings -LeftFile 'player-owner-components.json' -LeftProperty 'SelectedSourceAddress' -RightFile 'player-stat-hub-graph.json' -RightProperty 'SelectedSourceAddress' -Message 'owner/stat-hub selected-source mismatch'
Add-ComparisonWarning -RecordsByFile $recordsByFile -Warnings $warnings -LeftFile 'player-selector-owner-trace.json' -LeftProperty 'OwnerAddress' -RightFile 'player-owner-components.json' -RightProperty 'OwnerAddress' -Message 'owner-address mismatch'

$selectedSourceGroups = @(
    $records |
        Where-Object { -not [string]::IsNullOrWhiteSpace($_.SelectedSourceAddress) } |
        Group-Object SelectedSourceAddress |
        Sort-Object Count -Descending |
        ForEach-Object {
            [pscustomobject][ordered]@{
                Address = $_.Name
                Count = $_.Count
                Files = @($_.Group.FileName)
            }
        }
)

$ownerGroups = @(
    $records |
        Where-Object { -not [string]::IsNullOrWhiteSpace($_.OwnerAddress) } |
        Group-Object OwnerAddress |
        Sort-Object Count -Descending |
        ForEach-Object {
            [pscustomobject][ordered]@{
                Address = $_.Name
                Count = $_.Count
                Files = @($_.Group.FileName)
            }
        }
)

if ($Json) {
    $jsonReport = [ordered]@{
        SchemaVersion = $captureConsistencySchemaVersion
        Mode = 'capture-consistency-report'
        Root = $resolvedCapturesPath
        GeneratedAtUtc = [DateTimeOffset]::UtcNow.ToString('O', [System.Globalization.CultureInfo]::InvariantCulture)
        FileCount = $records.Count
        ParsedCount = $parsedCount
        WarningCount = $warnings.Count
        Records = @($records | Sort-Object FileName | ForEach-Object {
                [ordered]@{
                    FileName = $_.FileName
                    Mode = $_.Mode
                    GeneratedAtUtc = $_.GeneratedAtUtc
                    LoadedAtUtc = $_.LoadedAtUtc
                    ProcessName = $_.ProcessName
                    ProcessId = $_.ProcessId
                    SourceFile = $_.SourceFile
                    SelectorTraceFile = $_.SelectorTraceFile
                    FamilyId = $_.FamilyId
                    Signature = $_.Signature
                    SelectionSource = $_.SelectionSource
                    OwnerAddress = $_.OwnerAddress
                    ContainerAddress = $_.ContainerAddress
                    SelectedSourceAddress = $_.SelectedSourceAddress
                    StateRecordAddress = $_.StateRecordAddress
                    SelectedEntryAddress = $_.SelectedEntryAddress
                    SourceObjectAddress = $_.SourceObjectAddress
                    Warnings = @($_.Warnings)
                }
            })
        SelectedSourceGroups = @($selectedSourceGroups | ForEach-Object {
                [ordered]@{
                    Address = $_.Address
                    Count = $_.Count
                    Files = @($_.Files)
                }
            })
        OwnerGroups = @($ownerGroups | ForEach-Object {
                [ordered]@{
                    Address = $_.Address
                    Count = $_.Count
                    Files = @($_.Files)
                }
            })
        Warnings = $warnings.ToArray()
    }

    $jsonReport | ConvertTo-Json -Depth 20
    return
}

Write-Host 'Capture consistency report' -ForegroundColor Cyan
Write-Host "Root:      $resolvedCapturesPath"
Write-Host "Files:     $($records.Count)"
Write-Host "Parsed:    $parsedCount"
Write-Host "Warnings:  $($warnings.Count)"
Write-Host ''

Write-Host 'Files scanned:' -ForegroundColor Cyan
foreach ($record in $records) {
    $sourceColumn = if ($record.SourceObjectAddress) { $record.SourceObjectAddress } elseif ($record.SourceFile -ne 'n/a') { $record.SourceFile } else { 'n/a' }
    $traceColumn = if ($record.SelectorTraceFile -ne 'n/a') { $record.SelectorTraceFile } else { 'n/a' }
    $processColumn = if ($record.ProcessName -ne 'n/a' -and $record.ProcessId) { '{0}#{1}' -f $record.ProcessName, $record.ProcessId } elseif ($record.ProcessName -ne 'n/a') { $record.ProcessName } else { 'n/a' }
    $line = '{0} | mode={1} | gen={2} | proc={3} | owner={4} | selected={5} | source={6}' -f `
        $record.FileName,
        $record.Mode,
        $record.GeneratedAtUtc,
        $processColumn,
        $record.OwnerAddress,
        $record.SelectedSourceAddress,
        $sourceColumn
    Write-Host $line
    if ($traceColumn -ne 'n/a') {
        Write-Host ('  trace : ' + $traceColumn) -ForegroundColor DarkGray
    }

    if ($record.Warnings.Count -gt 0) {
        Write-Host ('  warnings: ' + ($record.Warnings -join '; ')) -ForegroundColor Yellow
    }
}

if ($selectedSourceGroups.Count -gt 0) {
    Write-Host ''
    Write-Host 'Selected-source groups:' -ForegroundColor Cyan
    foreach ($group in $selectedSourceGroups) {
        Write-Host ('  {0} -> {1}' -f $group.Address, ($group.Files -join ', '))
    }
}

if ($ownerGroups.Count -gt 0) {
    Write-Host ''
    Write-Host 'Owner groups:' -ForegroundColor Cyan
    foreach ($group in $ownerGroups) {
        Write-Host ('  {0} -> {1}' -f $group.Address, ($group.Files -join ', '))
    }
}

if ($warnings.Count -gt 0) {
    Write-Host ''
    Write-Host 'Warnings:' -ForegroundColor Cyan
    foreach ($warning in $warnings) {
        Write-Host ('  - ' + $warning) -ForegroundColor Yellow
    }
}
