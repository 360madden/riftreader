[CmdletBinding()]
param(
    [switch]$Json,
    [string]$CurrentScreenFile,
    [string]$HistoryFile,
    [switch]$Force
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

if ([string]::IsNullOrWhiteSpace($CurrentScreenFile)) {
    $CurrentScreenFile = Join-Path $PSScriptRoot 'captures\actor-orientation-candidate-screen.json'
}

if ([string]::IsNullOrWhiteSpace($HistoryFile)) {
    $HistoryFile = Join-Path $PSScriptRoot 'captures\actor-orientation-candidate-screen-history.ndjson'
}

$resolvedCurrentScreenFile = [System.IO.Path]::GetFullPath($CurrentScreenFile)
$resolvedHistoryFile = [System.IO.Path]::GetFullPath($HistoryFile)

function ConvertFrom-JsonCompat {
    param(
        [Parameter(Mandatory = $true)]
        [string]$JsonText,
        [int]$Depth = 80
    )

    if ($PSVersionTable.PSVersion.Major -ge 6) {
        return $JsonText | ConvertFrom-Json -Depth $Depth
    }

    return $JsonText | ConvertFrom-Json
}

function Get-OptionalPropertyValue {
    param(
        [Parameter(Mandatory = $true)]
        [AllowNull()]
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

function ConvertTo-BooleanLoose {
    param($Value)

    if ($null -eq $Value) {
        return $false
    }

    if ($Value -is [bool]) {
        return [bool]$Value
    }

    $isPresent = Get-OptionalPropertyValue -Object $Value -Name 'IsPresent'
    if ($null -ne $isPresent) {
        return [bool]$isPresent
    }

    if ($Value -is [string]) {
        $parsed = $false
        if ([bool]::TryParse($Value, [ref]$parsed)) {
            return $parsed
        }
    }

    return [bool]$Value
}

if (-not (Test-Path -LiteralPath $resolvedCurrentScreenFile)) {
    throw "Current screen file not found: $resolvedCurrentScreenFile"
}

$screenDocument = ConvertFrom-JsonCompat -JsonText (Get-Content -LiteralPath $resolvedCurrentScreenFile -Raw) -Depth 100
$generatedAtUtc = [string](Get-OptionalPropertyValue -Object $screenDocument -Name 'GeneratedAtUtc')
if ([string]::IsNullOrWhiteSpace($generatedAtUtc)) {
    throw "Current screen file is missing GeneratedAtUtc: $resolvedCurrentScreenFile"
}

$alreadyPresent = $false
if (Test-Path -LiteralPath $resolvedHistoryFile) {
    foreach ($line in (Get-Content -LiteralPath $resolvedHistoryFile)) {
        if ([string]::IsNullOrWhiteSpace($line)) {
            continue
        }

        $existing = ConvertFrom-JsonCompat -JsonText $line -Depth 40
        if ([string](Get-OptionalPropertyValue -Object $existing -Name 'GeneratedAtUtc') -eq $generatedAtUtc) {
            $alreadyPresent = $true
            break
        }
    }
}

$historyDocument = [pscustomobject]@{
    HistoryEntrySchema = 'screen-document-v1'
    BackfilledAtUtc = [DateTimeOffset]::UtcNow.ToString('O')
    BackfilledFromFile = $resolvedCurrentScreenFile
    Mode = [string](Get-OptionalPropertyValue -Object $screenDocument -Name 'Mode')
    GeneratedAtUtc = $generatedAtUtc
    OutputFile = [string](Get-OptionalPropertyValue -Object $screenDocument -Name 'OutputFile')
    LedgerFile = [string](Get-OptionalPropertyValue -Object $screenDocument -Name 'LedgerFile')
    HistoryFile = $resolvedHistoryFile
    ProcessName = [string](Get-OptionalPropertyValue -Object $screenDocument -Name 'ProcessName')
    PreflightKey = [string](Get-OptionalPropertyValue -Object $screenDocument -Name 'PreflightKey')
    DualKeyPreflight = ConvertTo-BooleanLoose (Get-OptionalPropertyValue -Object $screenDocument -Name 'DualKeyPreflight')
    SecondaryPreflightKey = [string](Get-OptionalPropertyValue -Object $screenDocument -Name 'SecondaryPreflightKey')
    MinimumYawResponseDegrees = Get-OptionalPropertyValue -Object $screenDocument -Name 'MinimumYawResponseDegrees'
    MaxCoordDrift = Get-OptionalPropertyValue -Object $screenDocument -Name 'MaxCoordDrift'
    MaxInterPreflightIdleDriftDegrees = Get-OptionalPropertyValue -Object $screenDocument -Name 'MaxInterPreflightIdleDriftDegrees'
    FullRecoveryLimit = Get-OptionalPropertyValue -Object $screenDocument -Name 'FullRecoveryLimit'
    CandidateSearch = Get-OptionalPropertyValue -Object $screenDocument -Name 'CandidateSearch'
    ScreenedCandidateCount = Get-OptionalPropertyValue -Object $screenDocument -Name 'ScreenedCandidateCount'
    SkippedCandidateCount = Get-OptionalPropertyValue -Object $screenDocument -Name 'SkippedCandidateCount'
    ResponsiveCandidateCount = Get-OptionalPropertyValue -Object $screenDocument -Name 'ResponsiveCandidateCount'
    DeadCandidateCount = Get-OptionalPropertyValue -Object $screenDocument -Name 'DeadCandidateCount'
    RecoveryRunCount = Get-OptionalPropertyValue -Object $screenDocument -Name 'RecoveryRunCount'
    Results = @((Get-OptionalPropertyValue -Object $screenDocument -Name 'Results'))
    Notes = @((Get-OptionalPropertyValue -Object $screenDocument -Name 'Notes'))
}

$historyDirectory = Split-Path -Path $resolvedHistoryFile -Parent
if (-not [string]::IsNullOrWhiteSpace($historyDirectory)) {
    New-Item -ItemType Directory -Path $historyDirectory -Force | Out-Null
}

$appended = $false
if (-not $alreadyPresent -or $Force) {
    Add-Content -LiteralPath $resolvedHistoryFile -Value ($historyDocument | ConvertTo-Json -Compress -Depth 100)
    $appended = $true
}

$result = [pscustomobject]@{
    Mode = 'actor-orientation-screen-history-backfill'
    GeneratedAtUtc = [DateTimeOffset]::UtcNow.ToString('O')
    CurrentScreenFile = $resolvedCurrentScreenFile
    HistoryFile = $resolvedHistoryFile
    SourceGeneratedAtUtc = $generatedAtUtc
    AlreadyPresent = $alreadyPresent
    Force = [bool]$Force
    Appended = $appended
}

$jsonText = $result | ConvertTo-Json -Depth 20
if ($Json) {
    Write-Output $jsonText
    return
}

Write-Host 'Actor orientation screen history backfill'
Write-Host ("Current screen file:         {0}" -f $resolvedCurrentScreenFile)
Write-Host ("History file:                {0}" -f $resolvedHistoryFile)
Write-Host ("Source GeneratedAtUtc:       {0}" -f $generatedAtUtc)
Write-Host ("Already present:             {0}" -f $alreadyPresent)
Write-Host ("Appended:                    {0}" -f $appended)
