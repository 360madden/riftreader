[CmdletBinding()]
param(
    [switch]$Json,
    [Parameter(Mandatory = $true)]
    [string]$CandidateTestFile,
    [string]$LedgerFile = (Join-Path $(if ($PSScriptRoot) { $PSScriptRoot } elseif ($PSCommandPath) { Split-Path -Parent $PSCommandPath } else { (Get-Location).Path }) 'captures\actor-orientation-candidate-ledger.ndjson'),
    [string]$ProcessName
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$resolvedCandidateTestFile = [System.IO.Path]::GetFullPath($CandidateTestFile)
$resolvedLedgerFile = if ([string]::IsNullOrWhiteSpace($LedgerFile)) {
    $null
}
else {
    [System.IO.Path]::GetFullPath($LedgerFile)
}

function Test-CommandSupportsParameter {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Name,

        [Parameter(Mandatory = $true)]
        [string]$ParameterName
    )

    $command = Get-Command $Name -ErrorAction Stop
    return $command.Parameters.ContainsKey($ParameterName)
}

function ConvertTo-CompactJson {
    param(
        [Parameter(Mandatory = $true)]
        [object]$InputObject
    )

    $parameters = @{}
    if (Test-CommandSupportsParameter -Name 'Microsoft.PowerShell.Utility\ConvertTo-Json' -ParameterName 'Depth') {
        $parameters['Depth'] = 50
    }

    if (Test-CommandSupportsParameter -Name 'Microsoft.PowerShell.Utility\ConvertTo-Json' -ParameterName 'Compress') {
        $parameters['Compress'] = $true
    }

    return ($InputObject | Microsoft.PowerShell.Utility\ConvertTo-Json @parameters)
}

function Get-PropertyValue {
    param(
        [Parameter(Mandatory = $true)]
        [object]$InputObject,

        [Parameter(Mandatory = $true)]
        [string]$PropertyName
    )

    if ($null -eq $InputObject) {
        return $null
    }

    $property = $InputObject.PSObject.Properties[$PropertyName]
    if ($null -eq $property) {
        return $null
    }

    return $property.Value
}

function Format-DateValue {
    param($Value)

    if ($null -eq $Value) {
        return $null
    }

    if ($Value -is [DateTimeOffset]) {
        return $Value.ToString('O', [System.Globalization.CultureInfo]::InvariantCulture)
    }

    if ($Value -is [DateTime]) {
        return ([DateTimeOffset]$Value).ToString('O', [System.Globalization.CultureInfo]::InvariantCulture)
    }

    return [string]$Value
}

function Get-CandidateLookupKey {
    param(
        [Parameter(Mandatory = $true)]
        [object]$InputObject,

        [string]$AddressPropertyName = 'SourceAddress',

        [string]$BasisOffsetPropertyName = 'BasisForwardOffset'
    )

    $address = [string](Get-PropertyValue -InputObject $InputObject -PropertyName $AddressPropertyName)
    $basisOffset = [string](Get-PropertyValue -InputObject $InputObject -PropertyName $BasisOffsetPropertyName)
    $discoveryMode = [string](Get-PropertyValue -InputObject $InputObject -PropertyName 'DiscoveryMode')
    $rootAddress = [string](Get-PropertyValue -InputObject $InputObject -PropertyName 'RootAddress')

    if ([string]::IsNullOrWhiteSpace($address) -or
        [string]::IsNullOrWhiteSpace($basisOffset) -or
        [string]::IsNullOrWhiteSpace($discoveryMode)) {
        return $null
    }

    return ('{0}|{1}|{2}|{3}' -f
        $address.ToUpperInvariant(),
        $basisOffset.ToUpperInvariant(),
        $discoveryMode.ToLowerInvariant(),
        $rootAddress.ToUpperInvariant())
}

if (-not (Test-Path -LiteralPath $resolvedCandidateTestFile)) {
    throw "Candidate test file not found: $resolvedCandidateTestFile"
}

$candidateTest = Get-Content -LiteralPath $resolvedCandidateTestFile -Raw | Microsoft.PowerShell.Utility\ConvertFrom-Json
$candidateSearchLookup = @{}
$candidateSearchFile = Join-Path (Split-Path -Parent $resolvedCandidateTestFile) 'player-orientation-candidate-search.json'
if (Test-Path -LiteralPath $candidateSearchFile) {
    try {
        $candidateSearch = Get-Content -LiteralPath $candidateSearchFile -Raw | Microsoft.PowerShell.Utility\ConvertFrom-Json
        if ([string](Get-PropertyValue -InputObject $candidateSearch -PropertyName 'Mode') -eq 'player-orientation-candidate-search') {
            foreach ($candidate in @(@(Get-PropertyValue -InputObject $candidateSearch -PropertyName 'PointerHopCandidates') + @(Get-PropertyValue -InputObject $candidateSearch -PropertyName 'Candidates'))) {
                if ($null -eq $candidate) {
                    continue
                }

                $lookupKey = Get-CandidateLookupKey -InputObject $candidate -AddressPropertyName 'Address' -BasisOffsetPropertyName 'BasisPrimaryForwardOffset'
                $parentFamilyId = [string](Get-PropertyValue -InputObject $candidate -PropertyName 'ParentFamilyId')
                if ([string]::IsNullOrWhiteSpace($lookupKey) -or [string]::IsNullOrWhiteSpace($parentFamilyId)) {
                    continue
                }

                $candidateSearchLookup[$lookupKey] = $parentFamilyId
            }
        }
    }
    catch {
        # Companion search lookup is best-effort only; preserve the ledger update even if it cannot be loaded.
    }
}
$effectiveProcessName = if ([string]::IsNullOrWhiteSpace($ProcessName)) {
    [string](Get-PropertyValue -InputObject $candidateTest -PropertyName 'ProcessName')
}
else {
    $ProcessName
}

$skipStimulus = [bool](Get-PropertyValue -InputObject $candidateTest -PropertyName 'SkipStimulus')
$stimulusMode = [string](Get-PropertyValue -InputObject $candidateTest -PropertyName 'StimulusMode')
$stimulusKey = [string](Get-PropertyValue -InputObject $candidateTest -PropertyName 'StimulusKey')
$evaluationMode = if ($skipStimulus) {
    if ($stimulusMode -eq 'Manual') { 'manual-turn-window' } else { 'read-only-proof' }
}
else {
    'workflow-turn-proof'
}

$generatedAtUtc = Format-DateValue -Value (Get-PropertyValue -InputObject $candidateTest -PropertyName 'GeneratedAtUtc')
$turnObserved = [bool](Get-PropertyValue -InputObject $candidateTest -PropertyName 'TurnObserved')
$turnVerification = Get-PropertyValue -InputObject $candidateTest -PropertyName 'TurnVerification'
$results = @(
    @(Get-PropertyValue -InputObject $candidateTest -PropertyName 'Results')
)

$appendedEntries = New-Object System.Collections.Generic.List[object]
$recoveredParentFamilyIdCount = 0
foreach ($result in $results) {
    if ($null -eq $result) {
        continue
    }

    $notes = New-Object System.Collections.Generic.List[string]
    $familyKey = [string](Get-PropertyValue -InputObject $result -PropertyName 'CandidateFamilyKey')
    if (-not [string]::IsNullOrWhiteSpace($familyKey)) {
        $notes.Add("Candidate family key: $familyKey") | Out-Null
    }

    if ($null -ne $turnVerification -and -not [string]::IsNullOrWhiteSpace([string](Get-PropertyValue -InputObject $turnVerification -PropertyName 'Reason'))) {
        $notes.Add([string](Get-PropertyValue -InputObject $turnVerification -PropertyName 'Reason')) | Out-Null
    }

    $candidateRejectedReason = [string](Get-PropertyValue -InputObject $result -PropertyName 'CandidateRejectedReason')
    $sourceAddress = [string](Get-PropertyValue -InputObject $result -PropertyName 'SourceAddress')
    $parentFamilyId = [string](Get-PropertyValue -InputObject $result -PropertyName 'ParentFamilyId')
    if ([string]::IsNullOrWhiteSpace($parentFamilyId)) {
        $lookupKey = Get-CandidateLookupKey -InputObject $result
        if (-not [string]::IsNullOrWhiteSpace($lookupKey) -and $candidateSearchLookup.ContainsKey($lookupKey)) {
            $parentFamilyId = [string]$candidateSearchLookup[$lookupKey]
            if (-not [string]::IsNullOrWhiteSpace($parentFamilyId)) {
                $recoveredParentFamilyIdCount++
            }
        }
    }

    if ([bool](Get-PropertyValue -InputObject $result -PropertyName 'CandidateResponsive')) {
        $yawDeltaDegrees = Get-PropertyValue -InputObject $result -PropertyName 'YawDeltaDegrees'
        $notes.Add(("Stimulus produced a responsive yaw delta of {0} deg." -f ([double]$yawDeltaDegrees).ToString('0.###', [System.Globalization.CultureInfo]::InvariantCulture))) | Out-Null
    }
    elseif (-not [string]::IsNullOrWhiteSpace($candidateRejectedReason)) {
        $notes.Add("Candidate rejected after workflow proof: $candidateRejectedReason") | Out-Null
    }

    $entry = [ordered]@{
        GeneratedAtUtc = $generatedAtUtc
        ProcessName = $effectiveProcessName
        SourceAddress = $sourceAddress
        BasisForwardOffset = [string](Get-PropertyValue -InputObject $result -PropertyName 'BasisForwardOffset')
        ResolutionMode = 'actor-yaw-debug-workflow'
        DiscoveryMode = [string](Get-PropertyValue -InputObject $result -PropertyName 'DiscoveryMode')
        ParentFamilyId = $parentFamilyId
        ParentAddress = [string](Get-PropertyValue -InputObject $result -PropertyName 'ParentAddress')
        RootAddress = [string](Get-PropertyValue -InputObject $result -PropertyName 'RootAddress')
        RootSource = [string](Get-PropertyValue -InputObject $result -PropertyName 'RootSource')
        HopDepth = Get-PropertyValue -InputObject $result -PropertyName 'HopDepth'
        EvaluationMode = $evaluationMode
        StimulusKey = $stimulusKey
        SourceStable = ((Get-PropertyValue -InputObject $result -PropertyName 'BeforeReadSucceeded') -eq $true -and (Get-PropertyValue -InputObject $result -PropertyName 'AfterReadSucceeded') -eq $true)
        CoordDriftMagnitude = Get-PropertyValue -InputObject $result -PropertyName 'PlayerCoordDeltaMagnitude'
        YawDeltaDegrees = Get-PropertyValue -InputObject $result -PropertyName 'YawDeltaDegrees'
        PitchDeltaDegrees = Get-PropertyValue -InputObject $result -PropertyName 'PitchDeltaDegrees'
        CandidateResponsive = Get-PropertyValue -InputObject $result -PropertyName 'CandidateResponsive'
        CandidateRejectedReason = $candidateRejectedReason
        Notes = @($notes.ToArray())
    }

    $appendedEntries.Add([pscustomobject]$entry) | Out-Null
}

$summary = [ordered]@{
    Mode = 'orientation-candidate-ledger-update'
    GeneratedAtUtc = [DateTimeOffset]::UtcNow.ToString('O', [System.Globalization.CultureInfo]::InvariantCulture)
    CandidateTestFile = $resolvedCandidateTestFile
    LedgerFile = $resolvedLedgerFile
    ProcessName = $effectiveProcessName
    TurnObserved = $turnObserved
    StimulusMode = $stimulusMode
    SkipStimulus = $skipStimulus
    CandidateCount = @($results).Count
    AppendedEntryCount = $appendedEntries.Count
    RecoveredParentFamilyIdCount = $recoveredParentFamilyIdCount
    TruthLikeCandidateCount = [int](Get-PropertyValue -InputObject $candidateTest -PropertyName 'TruthLikeCandidateCount')
    ResponsiveCandidateCount = if ($null -eq $turnVerification) { 0 } else { [int](Get-PropertyValue -InputObject $turnVerification -PropertyName 'ResponsiveCandidateCount') }
}

if (-not [string]::IsNullOrWhiteSpace($resolvedLedgerFile)) {
    $ledgerDirectory = Split-Path -Parent $resolvedLedgerFile
    if (-not [string]::IsNullOrWhiteSpace($ledgerDirectory)) {
        New-Item -ItemType Directory -Path $ledgerDirectory -Force | Out-Null
    }

    foreach ($entry in $appendedEntries) {
        Add-Content -LiteralPath $resolvedLedgerFile -Value (ConvertTo-CompactJson -InputObject $entry) -Encoding UTF8
    }
}

$jsonText = ConvertTo-CompactJson -InputObject $summary
if ($Json) {
    Write-Output $jsonText
    return
}

Write-Host 'Orientation candidate ledger updated'
Write-Host ("Candidate test file:        {0}" -f $resolvedCandidateTestFile)
Write-Host ("Ledger file:                {0}" -f $resolvedLedgerFile)
Write-Host ("Appended entries:           {0}" -f $appendedEntries.Count)
Write-Host ("Turn observed:              {0}" -f $turnObserved)
