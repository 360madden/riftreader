[CmdletBinding()]
param(
    [switch]$Json,
    [string]$LedgerFile,
    [string]$ScreenHistoryFile,
    [string]$CurrentScreenFile,
    [string]$RecoveryFile,
    [string]$RecoveryDirectory,
    [string]$OutputFile
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

if ([string]::IsNullOrWhiteSpace($LedgerFile)) {
    $LedgerFile = Join-Path $PSScriptRoot 'captures\actor-orientation-candidate-ledger.ndjson'
}

if ([string]::IsNullOrWhiteSpace($ScreenHistoryFile)) {
    $ScreenHistoryFile = Join-Path $PSScriptRoot 'captures\actor-orientation-candidate-screen-history.ndjson'
}

if ([string]::IsNullOrWhiteSpace($CurrentScreenFile)) {
    $CurrentScreenFile = Join-Path $PSScriptRoot 'captures\actor-orientation-candidate-screen.json'
}

if ([string]::IsNullOrWhiteSpace($RecoveryFile)) {
    $RecoveryFile = Join-Path $PSScriptRoot 'captures\actor-orientation-recovery.json'
}

if ([string]::IsNullOrWhiteSpace($RecoveryDirectory)) {
    $RecoveryDirectory = Join-Path $PSScriptRoot 'captures\screening'
}

if ([string]::IsNullOrWhiteSpace($OutputFile)) {
    $OutputFile = Join-Path $PSScriptRoot 'captures\actor-orientation-offline-analysis.json'
}

$resolvedLedgerFile = [System.IO.Path]::GetFullPath($LedgerFile)
$resolvedScreenHistoryFile = [System.IO.Path]::GetFullPath($ScreenHistoryFile)
$resolvedCurrentScreenFile = [System.IO.Path]::GetFullPath($CurrentScreenFile)
$resolvedRecoveryFile = [System.IO.Path]::GetFullPath($RecoveryFile)
$resolvedRecoveryDirectory = [System.IO.Path]::GetFullPath($RecoveryDirectory)
$resolvedOutputFile = [System.IO.Path]::GetFullPath($OutputFile)

function ConvertFrom-JsonCompat {
    param(
        [Parameter(Mandatory = $true)]
        [string]$JsonText,
        [int]$Depth = 40
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

    if ($Value -is [string]) {
        if ([string]::IsNullOrWhiteSpace($Value)) {
            return $false
        }

        $parsed = $false
        if ([bool]::TryParse($Value, [ref]$parsed)) {
            return $parsed
        }

        return $true
    }

    $isPresent = Get-OptionalPropertyValue -Object $Value -Name 'IsPresent'
    if ($null -ne $isPresent) {
        return [bool]$isPresent
    }

    return [bool]$Value
}

function Normalize-HexString {
    param([string]$Value)

    if ([string]::IsNullOrWhiteSpace($Value)) {
        return $null
    }

    $trimmed = $Value.Trim()
    if ($trimmed.StartsWith('0x', [System.StringComparison]::OrdinalIgnoreCase)) {
        $trimmed = $trimmed.Substring(2)
    }

    $parsedValue = 0UL
    if ([UInt64]::TryParse($trimmed, [System.Globalization.NumberStyles]::HexNumber, [System.Globalization.CultureInfo]::InvariantCulture, [ref]$parsedValue)) {
        return ('0x{0:X}' -f $parsedValue)
    }

    if ([UInt64]::TryParse($trimmed, [System.Globalization.NumberStyles]::Integer, [System.Globalization.CultureInfo]::InvariantCulture, [ref]$parsedValue)) {
        return ('0x{0:X}' -f $parsedValue)
    }

    return $Value
}

function New-CandidateKey {
    param(
        [string]$SourceAddress,
        [string]$BasisForwardOffset
    )

    $normalizedSource = Normalize-HexString -Value $SourceAddress
    if ([string]::IsNullOrWhiteSpace($normalizedSource)) {
        return $null
    }

    $normalizedBasis = Normalize-HexString -Value $BasisForwardOffset
    if ([string]::IsNullOrWhiteSpace($normalizedBasis)) {
        $normalizedBasis = '0x0'
    }

    return '{0}|{1}' -f $normalizedSource, $normalizedBasis
}

function Parse-DateTimeOffsetOrNull {
    param([string]$Value)

    if ([string]::IsNullOrWhiteSpace($Value)) {
        return $null
    }

    $parsed = [DateTimeOffset]::MinValue
    if ([DateTimeOffset]::TryParse($Value, [System.Globalization.CultureInfo]::InvariantCulture, [System.Globalization.DateTimeStyles]::AssumeUniversal, [ref]$parsed)) {
        return $parsed
    }

    return $null
}

function Read-NdjsonFile {
    param([string]$Path)

    if (-not (Test-Path -LiteralPath $Path)) {
        return @()
    }

    $items = New-Object System.Collections.Generic.List[object]
    foreach ($line in (Get-Content -LiteralPath $Path)) {
        if ([string]::IsNullOrWhiteSpace($line)) {
            continue
        }

        $items.Add((ConvertFrom-JsonCompat -JsonText $line -Depth 80))
    }

    return $items.ToArray()
}

function Read-JsonDocumentOrNull {
    param([string]$Path)

    if (-not (Test-Path -LiteralPath $Path)) {
        return $null
    }

    return ConvertFrom-JsonCompat -JsonText (Get-Content -LiteralPath $Path -Raw) -Depth 100
}

function Get-RunHistory {
    $historyRuns = New-Object System.Collections.Generic.List[object]

    foreach ($historyEntry in @(Read-NdjsonFile -Path $resolvedScreenHistoryFile)) {
        $historyRuns.Add($historyEntry)
    }

    if (Test-Path -LiteralPath $resolvedCurrentScreenFile) {
        $currentRun = ConvertFrom-JsonCompat -JsonText (Get-Content -LiteralPath $resolvedCurrentScreenFile -Raw) -Depth 80
        $currentRunGeneratedAt = [string](Get-OptionalPropertyValue -Object $currentRun -Name 'GeneratedAtUtc')
        $alreadyPresent = @($historyRuns | Where-Object { [string](Get-OptionalPropertyValue -Object $_ -Name 'GeneratedAtUtc') -eq $currentRunGeneratedAt }).Count -gt 0
        if (-not $alreadyPresent) {
            $historyRuns.Add($currentRun)
        }
    }

    return @($historyRuns.ToArray() | Sort-Object { Parse-DateTimeOffsetOrNull -Value ([string](Get-OptionalPropertyValue -Object $_ -Name 'GeneratedAtUtc')) })
}

function Get-RecoveryArtifacts {
    $recoveryDocuments = New-Object System.Collections.Generic.List[object]

    if (Test-Path -LiteralPath $resolvedRecoveryFile) {
        $document = Read-JsonDocumentOrNull -Path $resolvedRecoveryFile
        if ($null -ne $document) {
            $recoveryDocuments.Add($document)
        }
    }

    if (Test-Path -LiteralPath $resolvedRecoveryDirectory) {
        foreach ($file in @(Get-ChildItem -LiteralPath $resolvedRecoveryDirectory -Filter 'recovery-*.json' -File | Sort-Object LastWriteTimeUtc)) {
            $document = Read-JsonDocumentOrNull -Path $file.FullName
            if ($null -ne $document) {
                $recoveryDocuments.Add($document)
            }
        }
    }

    return @($recoveryDocuments.ToArray() | Sort-Object { Parse-DateTimeOffsetOrNull -Value ([string](Get-OptionalPropertyValue -Object $_ -Name 'GeneratedAtUtc')) })
}

function Get-ResultStimulusValue {
    param(
        [Parameter(Mandatory = $true)]
        $Result,
        [Parameter(Mandatory = $true)]
        [string]$NestedName,
        [Parameter(Mandatory = $true)]
        [string]$FlatName
    )

    $nested = Get-OptionalPropertyValue -Object $Result -Name $NestedName
    if ($null -ne $nested) {
        return $nested
    }

    return Get-OptionalPropertyValue -Object $Result -Name $FlatName
}

function Get-ResultPrimaryYawDeltaDegrees {
    param($Result)

    if ($null -eq $Result) {
        return $null
    }

    $stimulus = Get-OptionalPropertyValue -Object $Result -Name 'Stimulus'
    if ($null -ne $stimulus) {
        return Get-OptionalPropertyValue -Object $stimulus -Name 'YawDeltaDegrees'
    }

    return Get-OptionalPropertyValue -Object $Result -Name 'PrimaryYawDeltaDegrees'
}

function Get-ResultSecondaryYawDeltaDegrees {
    param($Result)

    if ($null -eq $Result) {
        return $null
    }

    $stimulus = Get-OptionalPropertyValue -Object $Result -Name 'SecondaryStimulus'
    if ($null -ne $stimulus) {
        return Get-OptionalPropertyValue -Object $stimulus -Name 'YawDeltaDegrees'
    }

    return Get-OptionalPropertyValue -Object $Result -Name 'SecondaryYawDeltaDegrees'
}

function Get-ResultRecoveryRejectedReason {
    param($Result)

    if ($null -eq $Result) {
        return $null
    }

    $recovery = Get-OptionalPropertyValue -Object $Result -Name 'Recovery'
    if ($null -ne $recovery) {
        $reason = [string](Get-OptionalPropertyValue -Object $recovery -Name 'RecoveryCandidateRejectedReason')
        if ([string]::IsNullOrWhiteSpace($reason)) {
            $reason = [string](Get-OptionalPropertyValue -Object $recovery -Name 'CandidateRejectedReason')
        }

        return $reason
    }

    return [string](Get-OptionalPropertyValue -Object $Result -Name 'RecoveryCandidateRejectedReason')
}

function Get-ResultRecoveryYawRecovered {
    param($Result)

    if ($null -eq $Result) {
        return $false
    }

    $recovery = Get-OptionalPropertyValue -Object $Result -Name 'Recovery'
    if ($null -ne $recovery) {
        return ConvertTo-BooleanLoose (Get-OptionalPropertyValue -Object $recovery -Name 'YawRecovered')
    }

    return ConvertTo-BooleanLoose (Get-OptionalPropertyValue -Object $Result -Name 'YawRecovered')
}

function Get-CandidateClassification {
    param(
        [string]$LatestRejectedReason,
        [bool]$LatestResponsive,
        [bool]$YawRecovered,
        [bool]$BasisRecovered
    )

    if ($YawRecovered) {
        return 'yaw-recovered'
    }

    if (-not $BasisRecovered) {
        return 'basis-unresolved'
    }

    switch ($LatestRejectedReason) {
        'idle_drift' { return 'drifting' }
        'inter_preflight_idle_drift' { return 'drifting' }
        'inter_preflight_source_drift' { return 'source-drifting' }
        'source_drift' { return 'source-drifting' }
        'preflight_direction_mismatch' { return 'direction-mismatch' }
        'stable_but_nonresponsive' { return 'dead-nonresponsive' }
        'secondary_stable_but_nonresponsive' { return 'dead-nonresponsive' }
        'secondary_preflight_failed' { return 'secondary-preflight-failed' }
    }

    if ($LatestResponsive) {
        return 'responsive-unconfirmed'
    }

    if (-not [string]::IsNullOrWhiteSpace($LatestRejectedReason)) {
        return 'other-rejected'
    }

    return 'unclassified'
}

function New-CountSummaryObjects {
    param(
        [Parameter(Mandatory = $true)]
        [hashtable]$Map
    )

    return @($Map.GetEnumerator() |
        Sort-Object Name |
        ForEach-Object {
            [pscustomobject]@{
                Name = [string]$_.Key
                Count = [int]$_.Value
            }
        })
}

$ledgerEntries = @(Read-NdjsonFile -Path $resolvedLedgerFile)
$screenRuns = @(Get-RunHistory)
$recoveryArtifacts = @(Get-RecoveryArtifacts)

$latestLedgerByCandidate = @{}
foreach ($entry in $ledgerEntries) {
    $candidateKey = New-CandidateKey -SourceAddress ([string](Get-OptionalPropertyValue -Object $entry -Name 'SourceAddress')) -BasisForwardOffset ([string](Get-OptionalPropertyValue -Object $entry -Name 'BasisForwardOffset'))
    if ([string]::IsNullOrWhiteSpace($candidateKey)) {
        continue
    }

    $entryTime = Parse-DateTimeOffsetOrNull -Value ([string](Get-OptionalPropertyValue -Object $entry -Name 'GeneratedAtUtc'))
    if (-not $latestLedgerByCandidate.ContainsKey($candidateKey)) {
        $latestLedgerByCandidate[$candidateKey] = $entry
        continue
    }

    $existingTime = Parse-DateTimeOffsetOrNull -Value ([string](Get-OptionalPropertyValue -Object $latestLedgerByCandidate[$candidateKey] -Name 'GeneratedAtUtc'))
    if ($null -eq $existingTime -or ($null -ne $entryTime -and $entryTime -ge $existingTime)) {
        $latestLedgerByCandidate[$candidateKey] = $entry
    }
}

$latestHistoryByCandidate = @{}
foreach ($run in $screenRuns) {
    foreach ($result in @((Get-OptionalPropertyValue -Object $run -Name 'Results'))) {
        if ($null -eq $result) {
            continue
        }

        $candidateKey = New-CandidateKey -SourceAddress ([string](Get-OptionalPropertyValue -Object $result -Name 'SourceAddress')) -BasisForwardOffset ([string](Get-OptionalPropertyValue -Object $result -Name 'BasisForwardOffset'))
        if ([string]::IsNullOrWhiteSpace($candidateKey)) {
            continue
        }

        $runTime = Parse-DateTimeOffsetOrNull -Value ([string](Get-OptionalPropertyValue -Object $run -Name 'GeneratedAtUtc'))
        $observation = [pscustomobject]@{
            RunGeneratedAtUtc = [string](Get-OptionalPropertyValue -Object $run -Name 'GeneratedAtUtc')
            RunTime = $runTime
            PreflightKey = [string](Get-OptionalPropertyValue -Object $run -Name 'PreflightKey')
            DualKeyPreflight = ConvertTo-BooleanLoose (Get-OptionalPropertyValue -Object $run -Name 'DualKeyPreflight')
            SecondaryPreflightKey = [string](Get-OptionalPropertyValue -Object $run -Name 'SecondaryPreflightKey')
            Result = $result
        }

        if (-not $latestHistoryByCandidate.ContainsKey($candidateKey)) {
            $latestHistoryByCandidate[$candidateKey] = $observation
            continue
        }

        $existing = $latestHistoryByCandidate[$candidateKey]
        if ($null -eq $existing.RunTime -or ($null -ne $runTime -and $runTime -ge $existing.RunTime)) {
            $latestHistoryByCandidate[$candidateKey] = $observation
        }
    }
}

$latestRecoveryByCandidate = @{}
foreach ($recoveryDocument in $recoveryArtifacts) {
    $baseline = Get-OptionalPropertyValue -Object $recoveryDocument -Name 'Baseline'
    $readerOrientation = if ($null -ne $baseline) { Get-OptionalPropertyValue -Object $baseline -Name 'ReaderOrientation' } else { $null }
    $liveSourceSample = if ($null -ne $readerOrientation) { Get-OptionalPropertyValue -Object $readerOrientation -Name 'LiveSourceSample' } else { $null }

    $sourceAddress = [string](Get-OptionalPropertyValue -Object $readerOrientation -Name 'PinnedSourceAddress')
    if ([string]::IsNullOrWhiteSpace($sourceAddress)) {
        $sourceAddress = [string](Get-OptionalPropertyValue -Object $readerOrientation -Name 'SelectedSourceAddress')
    }

    $basisForwardOffset = [string](Get-OptionalPropertyValue -Object $readerOrientation -Name 'PinnedBasisForwardOffset')
    if ([string]::IsNullOrWhiteSpace($basisForwardOffset)) {
        $basisForwardOffset = [string](Get-OptionalPropertyValue -Object $liveSourceSample -Name 'BasisPrimaryForwardOffset')
    }

    $candidateKey = New-CandidateKey -SourceAddress $sourceAddress -BasisForwardOffset $basisForwardOffset
    if ([string]::IsNullOrWhiteSpace($candidateKey)) {
        continue
    }

    $recoveryTime = Parse-DateTimeOffsetOrNull -Value ([string](Get-OptionalPropertyValue -Object $recoveryDocument -Name 'GeneratedAtUtc'))
    $observation = [pscustomobject]@{
        GeneratedAtUtc = [string](Get-OptionalPropertyValue -Object $recoveryDocument -Name 'GeneratedAtUtc')
        RecoveryTime = $recoveryTime
        SourceAddress = $sourceAddress
        BasisForwardOffset = $basisForwardOffset
        DiscoveryMode = [string](Get-OptionalPropertyValue -Object $liveSourceSample -Name 'DiscoveryMode')
        ParentAddress = [string](Get-OptionalPropertyValue -Object $liveSourceSample -Name 'ParentAddress')
        RootAddress = [string](Get-OptionalPropertyValue -Object $liveSourceSample -Name 'RootAddress')
        RootSource = [string](Get-OptionalPropertyValue -Object $liveSourceSample -Name 'RootSource')
        HopDepth = Get-OptionalPropertyValue -Object $liveSourceSample -Name 'HopDepth'
        Recovery = Get-OptionalPropertyValue -Object $recoveryDocument -Name 'Recovery'
        OutputFile = [string](Get-OptionalPropertyValue -Object $recoveryDocument -Name 'OutputFile')
    }

    if (-not $latestRecoveryByCandidate.ContainsKey($candidateKey)) {
        $latestRecoveryByCandidate[$candidateKey] = $observation
        continue
    }

    $existing = $latestRecoveryByCandidate[$candidateKey]
    if ($null -eq $existing.RecoveryTime -or ($null -ne $recoveryTime -and $recoveryTime -ge $existing.RecoveryTime)) {
        $latestRecoveryByCandidate[$candidateKey] = $observation
    }
}

$candidateKeys = New-Object System.Collections.Generic.HashSet[string]
foreach ($key in $latestLedgerByCandidate.Keys) { [void]$candidateKeys.Add($key) }
foreach ($key in $latestHistoryByCandidate.Keys) { [void]$candidateKeys.Add($key) }
foreach ($key in $latestRecoveryByCandidate.Keys) { [void]$candidateKeys.Add($key) }

$latestCandidateStates = New-Object System.Collections.Generic.List[object]
$classificationCounts = @{}
$rejectionCounts = @{}
$basisOffsetCounts = @{}
$discoveryModeCounts = @{}
$recoveryRejectionCounts = @{}

foreach ($candidateKey in $candidateKeys) {
    $latestLedger = if ($latestLedgerByCandidate.ContainsKey($candidateKey)) { $latestLedgerByCandidate[$candidateKey] } else { $null }
    $latestHistory = if ($latestHistoryByCandidate.ContainsKey($candidateKey)) { $latestHistoryByCandidate[$candidateKey] } else { $null }
    $latestRecovery = if ($latestRecoveryByCandidate.ContainsKey($candidateKey)) { $latestRecoveryByCandidate[$candidateKey] } else { $null }
    $historyResult = if ($null -ne $latestHistory) { $latestHistory.Result } else { $null }
    $historyRecoveryRejectedReason = Get-ResultRecoveryRejectedReason -Result $historyResult
    $historyPreflightRejectedReason = if ($null -ne $historyResult) { [string](Get-OptionalPropertyValue -Object $historyResult -Name 'PreflightRejectedReason') } else { $null }
    $historyRecoveryYawRecovered = Get-ResultRecoveryYawRecovered -Result $historyResult
    $historyPreflightPassed = if ($null -ne $historyResult) { ConvertTo-BooleanLoose (Get-OptionalPropertyValue -Object $historyResult -Name 'PreflightPassed') } else { $false }
    $recoveryRejectedReason = if ($null -ne $latestRecovery) { [string](Get-OptionalPropertyValue -Object $latestRecovery.Recovery -Name 'CandidateRejectedReason') } else { $null }
    $latestRejectedReason = if (-not [string]::IsNullOrWhiteSpace($historyRecoveryRejectedReason)) {
        $historyRecoveryRejectedReason
    } elseif (-not [string]::IsNullOrWhiteSpace($recoveryRejectedReason)) {
        $recoveryRejectedReason
    } elseif (-not [string]::IsNullOrWhiteSpace($historyPreflightRejectedReason)) {
        $historyPreflightRejectedReason
    } else {
        [string](Get-OptionalPropertyValue -Object $latestLedger -Name 'CandidateRejectedReason')
    }

    $latestResponsive = if ($historyRecoveryYawRecovered) {
        $true
    } elseif ($null -ne $historyResult) {
        $historyPreflightPassed
    } elseif ($null -ne $latestRecovery) {
        ConvertTo-BooleanLoose (Get-OptionalPropertyValue -Object $latestRecovery.Recovery -Name 'CandidateResponsive')
    } else {
        ConvertTo-BooleanLoose (Get-OptionalPropertyValue -Object $latestLedger -Name 'CandidateResponsive')
    }

    $yawRecovered = if ($historyRecoveryYawRecovered) {
        $true
    } elseif ($null -ne $latestRecovery) {
        ConvertTo-BooleanLoose (Get-OptionalPropertyValue -Object $latestRecovery.Recovery -Name 'YawRecovered')
    } else {
        $false
    }

    $basisRecovered = if ($null -ne $historyResult -and $null -ne (Get-OptionalPropertyValue -Object $historyResult -Name 'Recovery')) {
        ConvertTo-BooleanLoose (Get-OptionalPropertyValue -Object (Get-OptionalPropertyValue -Object $historyResult -Name 'Recovery') -Name 'BasisRecovered')
    } elseif ($null -ne $latestRecovery) {
        ConvertTo-BooleanLoose (Get-OptionalPropertyValue -Object $latestRecovery.Recovery -Name 'BasisRecovered')
    } else {
        $true
    }

    $classification = Get-CandidateClassification -LatestRejectedReason $latestRejectedReason -LatestResponsive $latestResponsive -YawRecovered $yawRecovered -BasisRecovered $basisRecovered
    $classificationCounts[$classification] = 1 + [int]($classificationCounts[$classification])
    if (-not [string]::IsNullOrWhiteSpace($latestRejectedReason)) {
        $rejectionCounts[$latestRejectedReason] = 1 + [int]($rejectionCounts[$latestRejectedReason])
    }
    if (-not [string]::IsNullOrWhiteSpace($recoveryRejectedReason)) {
        $recoveryRejectionCounts[$recoveryRejectedReason] = 1 + [int]($recoveryRejectionCounts[$recoveryRejectedReason])
    }

    $sourceAddress = if ($null -ne $historyResult) { [string](Get-OptionalPropertyValue -Object $historyResult -Name 'SourceAddress') } elseif ($null -ne $latestRecovery) { $latestRecovery.SourceAddress } else { [string](Get-OptionalPropertyValue -Object $latestLedger -Name 'SourceAddress') }
    $basisForwardOffset = if ($null -ne $historyResult) { [string](Get-OptionalPropertyValue -Object $historyResult -Name 'BasisForwardOffset') } elseif ($null -ne $latestRecovery) { $latestRecovery.BasisForwardOffset } else { [string](Get-OptionalPropertyValue -Object $latestLedger -Name 'BasisForwardOffset') }
    if (-not [string]::IsNullOrWhiteSpace($basisForwardOffset)) {
        $basisOffsetCounts[$basisForwardOffset] = 1 + [int]($basisOffsetCounts[$basisForwardOffset])
    }

    $discoveryMode = if ($null -ne $historyResult) { [string](Get-OptionalPropertyValue -Object $historyResult -Name 'DiscoveryMode') } elseif ($null -ne $latestRecovery) { $latestRecovery.DiscoveryMode } else { [string](Get-OptionalPropertyValue -Object $latestLedger -Name 'DiscoveryMode') }
    if (-not [string]::IsNullOrWhiteSpace($discoveryMode)) {
        $discoveryModeCounts[$discoveryMode] = 1 + [int]($discoveryModeCounts[$discoveryMode])
    }

    $latestCandidateStates.Add([pscustomobject]@{
        CandidateKey = $candidateKey
        SourceAddress = $sourceAddress
        BasisForwardOffset = $basisForwardOffset
        DiscoveryMode = $discoveryMode
        ParentAddress = if ($null -ne $historyResult) { [string](Get-OptionalPropertyValue -Object $historyResult -Name 'ParentAddress') } elseif ($null -ne $latestRecovery) { $latestRecovery.ParentAddress } else { [string](Get-OptionalPropertyValue -Object $latestLedger -Name 'ParentAddress') }
        RootAddress = if ($null -ne $historyResult) { [string](Get-OptionalPropertyValue -Object $historyResult -Name 'RootAddress') } elseif ($null -ne $latestRecovery) { $latestRecovery.RootAddress } else { [string](Get-OptionalPropertyValue -Object $latestLedger -Name 'RootAddress') }
        RootSource = if ($null -ne $historyResult) { [string](Get-OptionalPropertyValue -Object $historyResult -Name 'RootSource') } elseif ($null -ne $latestRecovery) { $latestRecovery.RootSource } else { [string](Get-OptionalPropertyValue -Object $latestLedger -Name 'RootSource') }
        HopDepth = if ($null -ne $historyResult) { Get-OptionalPropertyValue -Object $historyResult -Name 'HopDepth' } elseif ($null -ne $latestRecovery) { $latestRecovery.HopDepth } else { Get-OptionalPropertyValue -Object $latestLedger -Name 'HopDepth' }
        LatestObservedAtUtc = if ($null -ne $latestHistory) { $latestHistory.RunGeneratedAtUtc } elseif ($null -ne $latestRecovery) { $latestRecovery.GeneratedAtUtc } else { [string](Get-OptionalPropertyValue -Object $latestLedger -Name 'GeneratedAtUtc') }
        LatestClassification = $classification
        LatestRejectedReason = $latestRejectedReason
        LatestResponsive = $latestResponsive
        YawRecovered = $yawRecovered
        BasisRecovered = $basisRecovered
        PrimaryYawDeltaDegrees = if ($null -ne $historyResult) { Get-ResultPrimaryYawDeltaDegrees -Result $historyResult } elseif ($null -ne $latestRecovery) { Get-OptionalPropertyValue -Object $latestRecovery.Recovery -Name 'InterStimulusYawDeltaDegrees' } else { Get-OptionalPropertyValue -Object $latestLedger -Name 'YawDeltaDegrees' }
        SecondaryYawDeltaDegrees = if ($null -ne $historyResult) { Get-ResultSecondaryYawDeltaDegrees -Result $historyResult } else { $null }
        InterPreflightYawDriftDegrees = if ($null -ne $historyResult) { Get-OptionalPropertyValue -Object $historyResult -Name 'InterPreflightYawDriftDegrees' } elseif ($null -ne $latestRecovery) { Get-OptionalPropertyValue -Object $latestRecovery.Recovery -Name 'BaselineIdleYawDeltaDegrees' } else { $null }
        SearchScore = if ($null -ne $historyResult) { Get-OptionalPropertyValue -Object $historyResult -Name 'SearchScore' } else { $null }
        SearchLedgerPenalty = if ($null -ne $historyResult) { Get-OptionalPropertyValue -Object $historyResult -Name 'SearchLedgerPenalty' } else { $null }
        RecoveryCandidateRejectedReason = if (-not [string]::IsNullOrWhiteSpace($historyRecoveryRejectedReason)) { $historyRecoveryRejectedReason } else { $recoveryRejectedReason }
        RecoveryOutputFile = if ($null -ne (Get-OptionalPropertyValue -Object $historyResult -Name 'Recovery')) { [string](Get-OptionalPropertyValue -Object (Get-OptionalPropertyValue -Object $historyResult -Name 'Recovery') -Name 'OutputFile') } elseif ($null -ne $latestRecovery) { $latestRecovery.OutputFile } else { $null }
        RecoveryIdleConsistencyPass = if ($null -ne (Get-OptionalPropertyValue -Object $historyResult -Name 'Recovery')) { Get-OptionalPropertyValue -Object (Get-OptionalPropertyValue -Object $historyResult -Name 'Recovery') -Name 'IdleConsistencyPass' } elseif ($null -ne $latestRecovery) { Get-OptionalPropertyValue -Object $latestRecovery.Recovery -Name 'IdleConsistencyPass' } else { $null }
    })
}

$rootClusterMap = @{}
$parentClusterMap = @{}
foreach ($state in @($latestCandidateStates.ToArray())) {
    $rootKey = if (-not [string]::IsNullOrWhiteSpace([string]$state.RootAddress)) { '{0}|{1}' -f $state.RootAddress, $(if (-not [string]::IsNullOrWhiteSpace([string]$state.RootSource)) { [string]$state.RootSource } else { 'n/a' }) } else { $null }
    if (-not [string]::IsNullOrWhiteSpace($rootKey)) {
        if (-not $rootClusterMap.ContainsKey($rootKey)) {
            $rootClusterMap[$rootKey] = [ordered]@{
                RootAddress = $state.RootAddress
                RootSource = $state.RootSource
                CandidateCount = 0
                DeadNonresponsiveCount = 0
                DriftingCount = 0
                DirectionMismatchCount = 0
                ResponsiveUnconfirmedCount = 0
                UnclassifiedCount = 0
                FirstHopCount = 0
                SecondHopCount = 0
                SampleCandidates = New-Object System.Collections.Generic.List[string]
            }
        }

        $bucket = $rootClusterMap[$rootKey]
        $bucket.CandidateCount++
        switch ([string]$state.LatestClassification) {
            'dead-nonresponsive' { $bucket.DeadNonresponsiveCount++ }
            'drifting' { $bucket.DriftingCount++ }
            'direction-mismatch' { $bucket.DirectionMismatchCount++ }
            'responsive-unconfirmed' { $bucket.ResponsiveUnconfirmedCount++ }
            default { $bucket.UnclassifiedCount++ }
        }

        if ($null -ne $state.HopDepth -and [int]$state.HopDepth -ge 2) {
            $bucket.SecondHopCount++
        } else {
            $bucket.FirstHopCount++
        }

        if ($bucket.SampleCandidates.Count -lt 5) {
            $bucket.SampleCandidates.Add(('{0}@{1}' -f $state.SourceAddress, $state.BasisForwardOffset))
        }
    }

    $parentKey = Normalize-HexString -Value ([string]$state.ParentAddress)
    if (-not [string]::IsNullOrWhiteSpace($parentKey)) {
        if (-not $parentClusterMap.ContainsKey($parentKey)) {
            $parentClusterMap[$parentKey] = [ordered]@{
                ParentAddress = $parentKey
                CandidateCount = 0
                DeadNonresponsiveCount = 0
                DriftingCount = 0
                SampleCandidates = New-Object System.Collections.Generic.List[string]
            }
        }

        $parentBucket = $parentClusterMap[$parentKey]
        $parentBucket.CandidateCount++
        switch ([string]$state.LatestClassification) {
            'dead-nonresponsive' { $parentBucket.DeadNonresponsiveCount++ }
            'drifting' { $parentBucket.DriftingCount++ }
        }

        if ($parentBucket.SampleCandidates.Count -lt 5) {
            $parentBucket.SampleCandidates.Add(('{0}@{1}' -f $state.SourceAddress, $state.BasisForwardOffset))
        }
    }
}

$rootClusters = @($rootClusterMap.Values |
    Sort-Object @{ Expression = { [int]$_.CandidateCount }; Descending = $true }, @{ Expression = { [int]$_.DeadNonresponsiveCount }; Descending = $true } |
    ForEach-Object {
        [pscustomobject]@{
            RootAddress = $_.RootAddress
            RootSource = $_.RootSource
            CandidateCount = $_.CandidateCount
            DeadNonresponsiveCount = $_.DeadNonresponsiveCount
            DriftingCount = $_.DriftingCount
            DirectionMismatchCount = $_.DirectionMismatchCount
            ResponsiveUnconfirmedCount = $_.ResponsiveUnconfirmedCount
            UnclassifiedCount = $_.UnclassifiedCount
            FirstHopCount = $_.FirstHopCount
            SecondHopCount = $_.SecondHopCount
            SampleCandidates = @($_.SampleCandidates.ToArray())
        }
    })

$parentClusters = @($parentClusterMap.Values |
    Sort-Object @{ Expression = { [int]$_.CandidateCount }; Descending = $true }, @{ Expression = { [int]$_.DeadNonresponsiveCount }; Descending = $true } |
    ForEach-Object {
        [pscustomobject]@{
            ParentAddress = $_.ParentAddress
            CandidateCount = $_.CandidateCount
            DeadNonresponsiveCount = $_.DeadNonresponsiveCount
            DriftingCount = $_.DriftingCount
            SampleCandidates = @($_.SampleCandidates.ToArray())
        }
    })

$interestingCandidates = @($latestCandidateStates.ToArray() |
    Where-Object {
        @('responsive-unconfirmed', 'direction-mismatch', 'unclassified') -contains [string]$_.LatestClassification
    } |
    Sort-Object @{ Expression = { if ($null -ne $_.SearchScore) { [int]$_.SearchScore } else { -1 } }; Descending = $true }, @{ Expression = { Parse-DateTimeOffsetOrNull -Value ([string]$_.LatestObservedAtUtc) }; Descending = $true })

$deprioritizedRoots = @($rootClusters | Where-Object {
        [int]$_.CandidateCount -ge 3 -and
        ([int]$_.DeadNonresponsiveCount + [int]$_.DriftingCount) -eq [int]$_.CandidateCount
    })

$topNotes = New-Object System.Collections.Generic.List[string]
if ($deprioritizedRoots.Count -gt 0) {
    $worstRoot = $deprioritizedRoots | Select-Object -First 1
    $topNotes.Add("Most exhausted root cluster so far: $($worstRoot.RootAddress) ($($worstRoot.RootSource)) with $($worstRoot.CandidateCount) candidates, $($worstRoot.DeadNonresponsiveCount) dead-nonresponsive, $($worstRoot.DriftingCount) drifting.")
}

$driftingCandidates = @($latestCandidateStates.ToArray() | Where-Object { [string]$_.LatestClassification -eq 'drifting' })
if ($driftingCandidates.Count -gt 0) {
    $driftCandidate = $driftingCandidates | Select-Object -First 1
    $topNotes.Add("At least one candidate is now classified as drifting rather than simply dead: $($driftCandidate.SourceAddress) @ $($driftCandidate.BasisForwardOffset) ($($driftCandidate.LatestRejectedReason)).")
}

$recoveryCoverageCount = @($latestCandidateStates.ToArray() | Where-Object { -not [string]::IsNullOrWhiteSpace([string]$_.RecoveryOutputFile) }).Count
if ($recoveryCoverageCount -gt 0) {
    $topNotes.Add("Offline analysis merged $recoveryCoverageCount recovery-backed candidates even when screen-history provenance was incomplete.")
}

if ($interestingCandidates.Count -eq 0) {
    $topNotes.Add('No candidate currently has surviving positive evidence after the latest offline evidence merge.')
}
else {
    $bestInteresting = $interestingCandidates | Select-Object -First 1
    $topNotes.Add("Most relevant remaining candidate class to inspect offline is '$($bestInteresting.LatestClassification)' from $($bestInteresting.SourceAddress) @ $($bestInteresting.BasisForwardOffset).")
}

$basisOffsetSummary = New-CountSummaryObjects -Map $basisOffsetCounts
$classificationSummary = New-CountSummaryObjects -Map $classificationCounts
$rejectionSummary = New-CountSummaryObjects -Map $rejectionCounts
$discoveryModeSummary = New-CountSummaryObjects -Map $discoveryModeCounts
$recoveryRejectionSummary = New-CountSummaryObjects -Map $recoveryRejectionCounts
$provenanceCoverage = [pscustomobject]@{
    CandidatesWithDiscoveryMode = @($latestCandidateStates.ToArray() | Where-Object { -not [string]::IsNullOrWhiteSpace([string]$_.DiscoveryMode) }).Count
    CandidatesWithParentAddress = @($latestCandidateStates.ToArray() | Where-Object { -not [string]::IsNullOrWhiteSpace([string]$_.ParentAddress) }).Count
    CandidatesWithRootAddress = @($latestCandidateStates.ToArray() | Where-Object { -not [string]::IsNullOrWhiteSpace([string]$_.RootAddress) }).Count
    CandidatesWithRecoveryArtifacts = $recoveryCoverageCount
}

$document = [pscustomobject]@{
    Mode = 'actor-orientation-offline-analysis'
    GeneratedAtUtc = [DateTimeOffset]::UtcNow.ToString('O')
    OutputFile = $resolvedOutputFile
    SourceFiles = [pscustomobject]@{
        LedgerFile = $resolvedLedgerFile
        ScreenHistoryFile = $resolvedScreenHistoryFile
        CurrentScreenFile = $resolvedCurrentScreenFile
        RecoveryFile = $resolvedRecoveryFile
        RecoveryDirectory = $resolvedRecoveryDirectory
    }
    InputSummary = [pscustomobject]@{
        LedgerEntryCount = @($ledgerEntries).Count
        ScreenRunCount = @($screenRuns).Count
        RecoveryArtifactCount = @($recoveryArtifacts).Count
        UniqueCandidateCount = $latestCandidateStates.Count
    }
    LatestClassificationSummary = $classificationSummary
    LatestRejectionSummary = $rejectionSummary
    RecoveryRejectionSummary = $recoveryRejectionSummary
    BasisOffsetSummary = $basisOffsetSummary
    DiscoveryModeSummary = $discoveryModeSummary
    ProvenanceCoverage = $provenanceCoverage
    RootClusters = $rootClusters
    ParentClusters = $parentClusters
    DeprioritizedRoots = $deprioritizedRoots
    InterestingCandidates = @($interestingCandidates | Select-Object -First 12)
    LatestCandidateStates = @($latestCandidateStates.ToArray() | Sort-Object @{ Expression = { Parse-DateTimeOffsetOrNull -Value ([string]$_.LatestObservedAtUtc) }; Descending = $true }, @{ Expression = { if ($null -ne $_.SearchScore) { [int]$_.SearchScore } else { -1 } }; Descending = $true })
    Notes = @($topNotes.ToArray())
}

$outputDirectory = Split-Path -Path $resolvedOutputFile -Parent
if (-not [string]::IsNullOrWhiteSpace($outputDirectory)) {
    New-Item -ItemType Directory -Path $outputDirectory -Force | Out-Null
}

$jsonText = $document | ConvertTo-Json -Depth 80
[System.IO.File]::WriteAllText($resolvedOutputFile, $jsonText)

if ($Json) {
    Write-Output $jsonText
    return
}

Write-Host 'Actor orientation offline analysis'
Write-Host ("Ledger entries:              {0}" -f $document.InputSummary.LedgerEntryCount)
Write-Host ("Screen runs:                 {0}" -f $document.InputSummary.ScreenRunCount)
Write-Host ("Recovery artifacts:          {0}" -f $document.InputSummary.RecoveryArtifactCount)
Write-Host ("Unique candidates:           {0}" -f $document.InputSummary.UniqueCandidateCount)
Write-Host ''
Write-Host 'Latest classification summary'
foreach ($item in @($document.LatestClassificationSummary)) {
    Write-Host ("  {0,-26} {1}" -f $item.Name, $item.Count)
}

Write-Host ''
Write-Host 'Latest rejection summary'
foreach ($item in @($document.LatestRejectionSummary)) {
    Write-Host ("  {0,-26} {1}" -f $item.Name, $item.Count)
}

if (@($document.RecoveryRejectionSummary).Count -gt 0) {
    Write-Host ''
    Write-Host 'Recovery rejection summary'
    foreach ($item in @($document.RecoveryRejectionSummary)) {
        Write-Host ("  {0,-26} {1}" -f $item.Name, $item.Count)
    }
}

Write-Host ''
Write-Host 'Basis offset summary'
foreach ($item in @($document.BasisOffsetSummary)) {
    Write-Host ("  {0,-26} {1}" -f $item.Name, $item.Count)
}

if (@($document.DiscoveryModeSummary).Count -gt 0) {
    Write-Host ''
    Write-Host 'Discovery mode summary'
    foreach ($item in @($document.DiscoveryModeSummary)) {
        Write-Host ("  {0,-26} {1}" -f $item.Name, $item.Count)
    }
}

Write-Host ''
Write-Host 'Provenance coverage'
Write-Host ("  discovery mode:            {0}" -f $document.ProvenanceCoverage.CandidatesWithDiscoveryMode)
Write-Host ("  parent address:            {0}" -f $document.ProvenanceCoverage.CandidatesWithParentAddress)
Write-Host ("  root address:              {0}" -f $document.ProvenanceCoverage.CandidatesWithRootAddress)
Write-Host ("  recovery artifacts:        {0}" -f $document.ProvenanceCoverage.CandidatesWithRecoveryArtifacts)

if (@($document.RootClusters).Count -gt 0) {
    Write-Host ''
    Write-Host 'Top root clusters'
    foreach ($cluster in @($document.RootClusters | Select-Object -First 8)) {
        Write-Host ("  {0} ({1}) -> candidates={2}, dead={3}, drifting={4}, firstHop={5}, secondHop={6}" -f `
            $cluster.RootAddress, `
            $(if ([string]::IsNullOrWhiteSpace([string]$cluster.RootSource)) { 'n/a' } else { [string]$cluster.RootSource }), `
            $cluster.CandidateCount, `
            $cluster.DeadNonresponsiveCount, `
            $cluster.DriftingCount, `
            $cluster.FirstHopCount, `
            $cluster.SecondHopCount)
    }
}

if (@($document.InterestingCandidates).Count -gt 0) {
    Write-Host ''
    Write-Host 'Interesting remaining candidates'
    foreach ($candidate in @($document.InterestingCandidates | Select-Object -First 8)) {
        Write-Host ("  {0} @ {1} -> {2} (root {3}, parent {4})" -f `
            $candidate.SourceAddress, `
            $candidate.BasisForwardOffset, `
            $candidate.LatestClassification, `
            $(if ([string]::IsNullOrWhiteSpace([string]$candidate.RootAddress)) { 'n/a' } else { [string]$candidate.RootAddress }), `
            $(if ([string]::IsNullOrWhiteSpace([string]$candidate.ParentAddress)) { 'n/a' } else { [string]$candidate.ParentAddress }))
    }
}

if (@($document.Notes).Count -gt 0) {
    Write-Host ''
    Write-Host 'Notes'
    foreach ($note in @($document.Notes)) {
        Write-Host ("  - {0}" -f $note)
    }
}

Write-Host ''
Write-Host ("Output file:                 {0}" -f $resolvedOutputFile)
