[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$CandidateFile,

    [string]$OutputFile = (Join-Path $PSScriptRoot 'captures\riftscan-coordinate-candidate-watchset.json'),
    [string]$ProcessName = 'rift_x64',
    [int]$ProcessId,
    [string]$TargetWindowHandle,
    [int]$TopCount = 16,
    [int]$ContextBytes = 64,
    [double]$MinScore = [double]::NegativeInfinity,
    [switch]$IncludeBlocked,
    [switch]$Json
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$resolvedCandidateFile = [System.IO.Path]::GetFullPath($CandidateFile)
$resolvedOutputFile = [System.IO.Path]::GetFullPath($OutputFile)

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
        [string]$Name
    )

    if ($null -eq $InputObject) {
        return $null
    }

    if ($InputObject -is [System.Collections.IDictionary]) {
        if ($InputObject.Contains($Name)) {
            return $InputObject[$Name]
        }

        return $null
    }

    $property = $InputObject.PSObject.Properties[$Name]
    if ($null -ne $property) {
        return $property.Value
    }

    return $null
}

function Parse-HexUInt64 {
    param([Parameter(Mandatory = $true)][string]$Value)

    $normalized = $Value.Trim()
    if ($normalized.StartsWith('0x', [System.StringComparison]::OrdinalIgnoreCase)) {
        $normalized = $normalized.Substring(2)
    }

    return [UInt64]::Parse($normalized, [System.Globalization.NumberStyles]::HexNumber, [System.Globalization.CultureInfo]::InvariantCulture)
}

function Format-HexUInt64 {
    param([Parameter(Mandatory = $true)][UInt64]$Value)

    return ('0x{0:X}' -f $Value)
}

function Get-StringValue {
    param($InputObject, [Parameter(Mandatory = $true)][string]$Name)

    $value = Get-JsonPropertyValue -InputObject $InputObject -Name $Name
    if ($null -eq $value) {
        return ''
    }

    return [string]$value
}

function Get-ScoreValue {
    param($InputObject)

    foreach ($name in @('best_score_total', 'score_total', 'rank_score', 'behavior_score')) {
        $value = Get-JsonPropertyValue -InputObject $InputObject -Name $name
        if ($null -ne $value) {
            return [double]$value
        }
    }

    $supportCount = Get-JsonPropertyValue -InputObject $InputObject -Name 'support_count'
    if ($null -ne $supportCount) {
        return [double]$supportCount
    }

    return 0.0
}

function Get-CandidateOffsetHex {
    param($Candidate)

    foreach ($name in @('x_offset_hex', 'offset_hex', 'source_offset_hex')) {
        $value = Get-StringValue -InputObject $Candidate -Name $name
        if (-not [string]::IsNullOrWhiteSpace($value)) {
            return $value
        }
    }

    return ''
}

function Read-CandidateDocuments {
    if (-not (Test-Path -LiteralPath $resolvedCandidateFile -PathType Leaf)) {
        throw "Candidate file not found: $resolvedCandidateFile"
    }

    $raw = Get-Content -LiteralPath $resolvedCandidateFile -Raw
    if ([string]::IsNullOrWhiteSpace($raw)) {
        throw "Candidate file is empty: $resolvedCandidateFile"
    }

    $isJsonLines = [string]::Equals(
        [System.IO.Path]::GetExtension($resolvedCandidateFile),
        '.jsonl',
        [System.StringComparison]::OrdinalIgnoreCase)

    if ($isJsonLines) {
        $items = New-Object System.Collections.Generic.List[object]
        $lineNumber = 0
        foreach ($line in [System.IO.File]::ReadLines($resolvedCandidateFile)) {
            $lineNumber++
            if ([string]::IsNullOrWhiteSpace($line)) {
                continue
            }

            try {
                $items.Add((ConvertFrom-JsonCompat -Text $line -Depth 80)) | Out-Null
            }
            catch {
                throw "Unable to parse JSONL line $lineNumber in $resolvedCandidateFile`: $($_.Exception.Message)"
            }
        }

        return @($items.ToArray())
    }

    $trimmed = $raw.TrimStart()
    if ($trimmed.StartsWith('{') -or $trimmed.StartsWith('[')) {
        $document = ConvertFrom-JsonCompat -Text $raw -Depth 100
        if ($document -is [array]) {
            return @($document)
        }

        $promotedCandidates = Get-JsonPropertyValue -InputObject $document -Name 'promoted_candidates'
        if ($null -ne $promotedCandidates) {
            return @($promotedCandidates)
        }

        $candidates = Get-JsonPropertyValue -InputObject $document -Name 'candidates'
        if ($null -ne $candidates) {
            return @($candidates)
        }

        return @($document)
    }

    $items = New-Object System.Collections.Generic.List[object]
    $lineNumber = 0
    foreach ($line in [System.IO.File]::ReadLines($resolvedCandidateFile)) {
        $lineNumber++
        if ([string]::IsNullOrWhiteSpace($line)) {
            continue
        }

        try {
            $items.Add((ConvertFrom-JsonCompat -Text $line -Depth 80)) | Out-Null
        }
        catch {
            throw "Unable to parse JSONL line $lineNumber in $resolvedCandidateFile`: $($_.Exception.Message)"
        }
    }

    return @($items.ToArray())
}

function Normalize-Candidate {
    param(
        [Parameter(Mandatory = $true)]
        $Candidate,
        [Parameter(Mandatory = $true)]
        [int]$Index
    )

    $baseAddressHex = Get-StringValue -InputObject $Candidate -Name 'base_address_hex'
    if ([string]::IsNullOrWhiteSpace($baseAddressHex)) {
        $baseAddressHex = Get-StringValue -InputObject $Candidate -Name 'source_base_address_hex'
    }

    $offsetHex = Get-CandidateOffsetHex -Candidate $Candidate
    if ([string]::IsNullOrWhiteSpace($baseAddressHex) -or [string]::IsNullOrWhiteSpace($offsetHex)) {
        return $null
    }

    $schemaVersion = Get-StringValue -InputObject $Candidate -Name 'schema_version'
    $candidateId = Get-StringValue -InputObject $Candidate -Name 'candidate_id'
    if ([string]::IsNullOrWhiteSpace($candidateId)) {
        $candidateId = 'riftscan-candidate-{0:000000}' -f $Index
    }

    $classification = Get-StringValue -InputObject $Candidate -Name 'classification'
    if ([string]::IsNullOrWhiteSpace($classification) -and -not [string]::IsNullOrWhiteSpace((Get-StringValue -InputObject $Candidate -Name 'source_region_id'))) {
        $classification = 'addon_coordinate_match_candidate'
    }

    $promotionStatus = Get-StringValue -InputObject $Candidate -Name 'promotion_status'
    $truthReadiness = Get-StringValue -InputObject $Candidate -Name 'truth_readiness'
    $corroborationStatus = Get-StringValue -InputObject $Candidate -Name 'corroboration_status'
    $validationStatus = Get-StringValue -InputObject $Candidate -Name 'validation_status'
    $confidenceLevel = Get-StringValue -InputObject $Candidate -Name 'confidence_level'
    $stimulusLabel = Get-StringValue -InputObject $Candidate -Name 'stimulus_label'
    $warning = Get-StringValue -InputObject $Candidate -Name 'warning'
    $valuePreview = Get-JsonPropertyValue -InputObject $Candidate -Name 'value_preview'
    if ($null -eq $valuePreview) {
        $bestMemoryX = Get-JsonPropertyValue -InputObject $Candidate -Name 'best_memory_x'
        $bestMemoryY = Get-JsonPropertyValue -InputObject $Candidate -Name 'best_memory_y'
        $bestMemoryZ = Get-JsonPropertyValue -InputObject $Candidate -Name 'best_memory_z'
        if ($null -ne $bestMemoryX -and $null -ne $bestMemoryY -and $null -ne $bestMemoryZ) {
            $valuePreview = @([double]$bestMemoryX, [double]$bestMemoryY, [double]$bestMemoryZ)
        }
    }

    $score = Get-ScoreValue -InputObject $Candidate

    if ($score -lt $MinScore) {
        return $null
    }

    $isBlocked =
        $promotionStatus -like '*blocked*' -or
        $truthReadiness -like '*blocked*' -or
        $corroborationStatus -like '*conflict*'
    if ($isBlocked -and -not $IncludeBlocked) {
        return $null
    }

    $baseAddress = Parse-HexUInt64 -Value $baseAddressHex
    $offset = Parse-HexUInt64 -Value $offsetHex
    $yOffsetHex = Get-StringValue -InputObject $Candidate -Name 'y_offset_hex'
    $zOffsetHex = Get-StringValue -InputObject $Candidate -Name 'z_offset_hex'
    $yOffset = if ([string]::IsNullOrWhiteSpace($yOffsetHex)) { [UInt64]($offset + [UInt64]4) } else { Parse-HexUInt64 -Value $yOffsetHex }
    $zOffset = if ([string]::IsNullOrWhiteSpace($zOffsetHex)) { [UInt64]($offset + [UInt64]8) } else { Parse-HexUInt64 -Value $zOffsetHex }
    $address = [UInt64]($baseAddress + $offset)
    $context = [Math]::Max(0, $ContextBytes)
    $regionStart = if ($address -gt [UInt64]$context) { [UInt64]($address - [UInt64]$context) } else { [UInt64]0 }
    $actualBefore = [int]($address - $regionStart)
    $regionLength = $actualBefore + 12 + $context

    return [pscustomobject][ordered]@{
        Index = $Index
        CandidateId = $candidateId
        SchemaVersion = $schemaVersion
        SourceKind = if ($schemaVersion -like '*promoted*') { 'riftscan-vec3-promotion' } elseif ($schemaVersion -like '*truth_candidate*') { 'riftscan-vec3-truth-candidate' } else { 'riftscan-vec3-candidate' }
        BaseAddressHex = Format-HexUInt64 -Value $baseAddress
        OffsetHex = Format-HexUInt64 -Value $offset
        XOffsetHex = Format-HexUInt64 -Value $offset
        YOffsetHex = Format-HexUInt64 -Value $yOffset
        ZOffsetHex = Format-HexUInt64 -Value $zOffset
        AddressHex = Format-HexUInt64 -Value $address
        AbsoluteAddressHex = Format-HexUInt64 -Value $address
        XAddressHex = Format-HexUInt64 -Value $address
        YAddressHex = Format-HexUInt64 -Value ([UInt64]($baseAddress + $yOffset))
        ZAddressHex = Format-HexUInt64 -Value ([UInt64]($baseAddress + $zOffset))
        RegionAddressHex = Format-HexUInt64 -Value $regionStart
        RegionLength = $regionLength
        ContextBytes = $context
        Score = $score
        Classification = $classification
        PromotionStatus = $promotionStatus
        TruthReadiness = $truthReadiness
        CorroborationStatus = $corroborationStatus
        ValidationStatus = $validationStatus
        ConfidenceLevel = $confidenceLevel
        StimulusLabel = $stimulusLabel
        Warning = $warning
        EvidenceSummary = Get-StringValue -InputObject $Candidate -Name 'evidence_summary'
        ValuePreview = if ($null -eq $valuePreview) { @() } else { @($valuePreview) }
        ValueSequenceSummary = Get-StringValue -InputObject $Candidate -Name 'value_sequence_summary'
        NextValidationStep = Get-StringValue -InputObject $Candidate -Name 'next_validation_step'
    }
}

$documents = Read-CandidateDocuments
$normalized = New-Object System.Collections.Generic.List[object]
$index = 0
foreach ($candidate in $documents) {
    $index++
    $normalizedCandidate = Normalize-Candidate -Candidate $candidate -Index $index
    if ($null -ne $normalizedCandidate) {
        $normalized.Add($normalizedCandidate) | Out-Null
    }
}

$selected = @(
    $normalized.ToArray() |
        Sort-Object @{ Expression = { -1 * [double]$_.Score } }, CandidateId |
        Select-Object -First ([Math]::Max(1, $TopCount))
)

if ($selected.Count -eq 0) {
    throw "No usable RiftScan coordinate candidates were found in $resolvedCandidateFile."
}

$regions = New-Object System.Collections.Generic.List[object]
$priority = 100
foreach ($candidate in $selected) {
    $safeId = ([string]$candidate.CandidateId) -replace '[^A-Za-z0-9_.-]', '-'
    $regions.Add([pscustomobject][ordered]@{
            Name = "riftscan-vec3-$safeId"
            Category = 'riftscan-coordinate-candidate'
            Address = [string]$candidate.RegionAddressHex
            Length = [int]$candidate.RegionLength
            Required = $false
            Priority = $priority
            Notes = "Candidate-only RiftScan vec3 window. Vec3 starts at $($candidate.AddressHex); source=$($candidate.SourceKind); classification=$($candidate.Classification); readiness=$($candidate.TruthReadiness); score=$([Math]::Round([double]$candidate.Score, 4)). Not movement proof."
        }) | Out-Null
    $priority = [Math]::Max(1, $priority - 1)
}

$result = [pscustomobject][ordered]@{
    SchemaVersion = 1
    Mode = 'riftscan-coordinate-candidate-watchset'
    GeneratedAtUtc = [DateTimeOffset]::UtcNow.ToString('O')
    ProcessName = $ProcessName
    ProcessId = if ($ProcessId -gt 0) { $ProcessId } else { $null }
    TargetWindowHandle = if ([string]::IsNullOrWhiteSpace($TargetWindowHandle)) { $null } else { $TargetWindowHandle }
    SourceCandidateFile = $resolvedCandidateFile
    NoCheatEngine = $true
    MovementAllowed = $false
    CanonicalCoordSource = 'none-candidate-watchset-only'
    CandidateCount = $selected.Count
    Candidates = @($selected)
    Warnings = @(
        'RiftScan candidates are candidate evidence only; this watchset is not a coord-trace proof anchor.',
        'Do not use this watchset to satisfy RiftReader movement polling invariants.',
        'No Cheat Engine path is used by this importer.',
        'Active movement remains blocked until a current-process validated canonical movement source exists.'
    )
    Regions = @($regions.ToArray())
}

$directory = Split-Path -Parent $resolvedOutputFile
if (-not [string]::IsNullOrWhiteSpace($directory)) {
    New-Item -ItemType Directory -Path $directory -Force | Out-Null
}

$result | ConvertTo-Json -Depth 32 | Set-Content -LiteralPath $resolvedOutputFile -Encoding UTF8

if ($Json) {
    $result | ConvertTo-Json -Depth 32
    return
}

Write-Host 'RiftScan coordinate candidate watchset exported.' -ForegroundColor Green
Write-Host ("Candidates:  {0}" -f $selected.Count)
Write-Host ("Output:      {0}" -f $resolvedOutputFile)
Write-Host 'Movement:    blocked (candidate-only watchset)'
Write-Host 'CE usage:    none'
