[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$PromotionGateFile,

    [string]$CandidateScoresFile,

    [string]$OutputJsonFile,

    [string]$OutputMarkdownFile,

    [switch]$Json
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$schemaVersion = 1

function Write-Utf8TextAtomic {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path,

        [Parameter(Mandatory = $true)]
        [string]$Content
    )

    $directory = Split-Path -Path $Path -Parent
    if (-not [string]::IsNullOrWhiteSpace($directory)) {
        New-Item -ItemType Directory -Path $directory -Force | Out-Null
    }

    $tempPath = '{0}.{1}.tmp' -f $Path, ([Guid]::NewGuid().ToString('N'))
    try {
        [System.IO.File]::WriteAllText($tempPath, $Content, [System.Text.UTF8Encoding]::new($false))
        Move-Item -LiteralPath $tempPath -Destination $Path -Force
    }
    finally {
        if (Test-Path -LiteralPath $tempPath) {
            Remove-Item -LiteralPath $tempPath -Force
        }
    }
}

function Get-PropertyValue {
    param(
        [object]$InputObject,

        [Parameter(Mandatory = $true)]
        [string[]]$Names
    )

    if ($null -eq $InputObject) {
        return $null
    }

    foreach ($name in $Names) {
        if ($InputObject -is [System.Collections.IDictionary]) {
            if ($InputObject.Contains($name)) {
                return $InputObject[$name]
            }
        }
        else {
            $property = $InputObject.PSObject.Properties[$name]
            if ($null -ne $property) {
                return $property.Value
            }
        }
    }

    return $null
}

function ConvertTo-DoubleOrNull {
    param([object]$Value)

    if ($null -eq $Value) {
        return $null
    }

    $text = [string]$Value
    if ([string]::IsNullOrWhiteSpace($text)) {
        return $null
    }

    try {
        $number = [double]::Parse($text, [System.Globalization.CultureInfo]::InvariantCulture)
        if ([double]::IsNaN($number) -or [double]::IsInfinity($number)) {
            return $null
        }

        return $number
    }
    catch {
        return $null
    }
}

function ConvertTo-IntOrNull {
    param([object]$Value)

    if ($null -eq $Value) {
        return $null
    }

    $text = [string]$Value
    if ([string]::IsNullOrWhiteSpace($text)) {
        return $null
    }

    try {
        return [int]::Parse($text, [System.Globalization.CultureInfo]::InvariantCulture)
    }
    catch {
        return $null
    }
}

function ConvertTo-DisplayValue {
    param([object]$Value)

    if ($null -eq $Value) {
        return ''
    }

    if ($Value -is [bool]) {
        return $Value.ToString().ToLowerInvariant()
    }

    if ($Value -is [double] -or $Value -is [float] -or $Value -is [decimal]) {
        return ([double]$Value).ToString('G8', [System.Globalization.CultureInfo]::InvariantCulture)
    }

    return [string]$Value
}

function New-MarkdownSummary {
    param(
        [Parameter(Mandatory = $true)]
        [object]$Summary
    )

    $lines = [System.Collections.Generic.List[string]]::new()
    $lines.Add('# Promotion gate summary') | Out-Null
    $lines.Add('') | Out-Null
    $lines.Add('| Field | Value |') | Out-Null
    $lines.Add('|---|---|') | Out-Null
    $lines.Add("| Promotion allowed | `$(ConvertTo-DisplayValue $Summary.promotionAllowed)` |") | Out-Null
    $lines.Add("| Gate status | `$(ConvertTo-DisplayValue $Summary.gateStatus)` |") | Out-Null
    $lines.Add("| Score status | `$(ConvertTo-DisplayValue $Summary.scoreStatus)` |") | Out-Null
    $lines.Add("| Promotion ready | `$(ConvertTo-DisplayValue $Summary.promotionReady)` |") | Out-Null
    $lines.Add("| Selected candidate | `$(ConvertTo-DisplayValue $Summary.selectedCandidateId)` |") | Out-Null
    $lines.Add("| Classification | `$(ConvertTo-DisplayValue $Summary.classification)` |") | Out-Null
    $lines.Add("| Score | `$(ConvertTo-DisplayValue $Summary.score)` |") | Out-Null
    $lines.Add("| Compared samples | `$(ConvertTo-DisplayValue $Summary.comparedSampleCount)` |") | Out-Null
    $lines.Add("| Missing samples | `$(ConvertTo-DisplayValue $Summary.missingSampleCount)` |") | Out-Null
    $lines.Add("| Absolute RMSE | `$(ConvertTo-DisplayValue $Summary.absoluteRmse)` |") | Out-Null
    $lines.Add("| Delta RMSE | `$(ConvertTo-DisplayValue $Summary.deltaRmse)` |") | Out-Null
    $lines.Add("| Stationary drift max | `$(ConvertTo-DisplayValue $Summary.stationaryDriftMax)` |") | Out-Null
    $lines.Add("| Truth samples | `$(ConvertTo-DisplayValue $Summary.truthSampleCount)` |") | Out-Null
    $lines.Add("| Memory records | `$(ConvertTo-DisplayValue $Summary.memoryRecordCount)` |") | Out-Null
    $lines.Add("| Candidate count | `$(ConvertTo-DisplayValue $Summary.candidateCount)` |") | Out-Null
    $lines.Add('') | Out-Null
    $lines.Add('## Gate failures') | Out-Null
    $lines.Add('') | Out-Null
    if (@($Summary.failures).Count -eq 0) {
        $lines.Add('- None') | Out-Null
    }
    else {
        foreach ($failure in @($Summary.failures)) {
            $lines.Add("- $failure") | Out-Null
        }
    }

    if (@($Summary.warnings).Count -gt 0) {
        $lines.Add('') | Out-Null
        $lines.Add('## Gate warnings') | Out-Null
        $lines.Add('') | Out-Null
        foreach ($warning in @($Summary.warnings)) {
            $lines.Add("- $warning") | Out-Null
        }
    }

    $lines.Add('') | Out-Null
    $lines.Add('## Source files') | Out-Null
    $lines.Add('') | Out-Null
    $lines.Add(('- Promotion gate: `{0}`' -f $Summary.promotionGateFile)) | Out-Null
    if (-not [string]::IsNullOrWhiteSpace([string]$Summary.candidateScoresFile)) {
        $lines.Add(('- Candidate scores: `{0}`' -f $Summary.candidateScoresFile)) | Out-Null
    }

    return ($lines -join [Environment]::NewLine)
}

$resolvedPromotionGateFile = [System.IO.Path]::GetFullPath($PromotionGateFile)
if (-not (Test-Path -LiteralPath $resolvedPromotionGateFile)) {
    throw "Promotion gate file not found: $resolvedPromotionGateFile"
}

$gateDocument = Get-Content -LiteralPath $resolvedPromotionGateFile -Raw | ConvertFrom-Json -Depth 80

if ([string]::IsNullOrWhiteSpace($CandidateScoresFile)) {
    $fromGate = [string](Get-PropertyValue -InputObject $gateDocument -Names @('candidateScoresFile'))
    if (-not [string]::IsNullOrWhiteSpace($fromGate)) {
        $CandidateScoresFile = $fromGate
    }
}

$resolvedCandidateScoresFile = $null
$scoresDocument = $null
if (-not [string]::IsNullOrWhiteSpace($CandidateScoresFile)) {
    $resolvedCandidateScoresFile = [System.IO.Path]::GetFullPath($CandidateScoresFile)
    if (Test-Path -LiteralPath $resolvedCandidateScoresFile) {
        $scoresDocument = Get-Content -LiteralPath $resolvedCandidateScoresFile -Raw | ConvertFrom-Json -Depth 80
    }
}

$selectedCandidate = Get-PropertyValue -InputObject $gateDocument -Names @('selectedCandidate')
if ($null -eq $selectedCandidate -and $null -ne $scoresDocument) {
    $selectedCandidate = Get-PropertyValue -InputObject $scoresDocument -Names @('bestCandidate')
}

$summary = [ordered]@{
    schemaVersion = $schemaVersion
    mode = 'promotion-gate-summary'
    generatedAtUtc = [DateTimeOffset]::UtcNow.ToString('O', [System.Globalization.CultureInfo]::InvariantCulture)
    promotionAllowed = [bool](Get-PropertyValue -InputObject $gateDocument -Names @('promotionAllowed'))
    gateStatus = [string](Get-PropertyValue -InputObject $gateDocument -Names @('status'))
    scoreStatus = if ($null -ne $scoresDocument) { [string](Get-PropertyValue -InputObject $scoresDocument -Names @('status')) } else { $null }
    promotionReady = if ($null -ne $scoresDocument) { [bool](Get-PropertyValue -InputObject $scoresDocument -Names @('promotionReady')) } else { $null }
    selectedCandidateId = [string](Get-PropertyValue -InputObject $gateDocument -Names @('selectedCandidateId'))
    classification = [string](Get-PropertyValue -InputObject $selectedCandidate -Names @('classification'))
    score = ConvertTo-DoubleOrNull (Get-PropertyValue -InputObject $selectedCandidate -Names @('score'))
    comparedSampleCount = ConvertTo-IntOrNull (Get-PropertyValue -InputObject $selectedCandidate -Names @('comparedSampleCount'))
    missingSampleCount = ConvertTo-IntOrNull (Get-PropertyValue -InputObject $selectedCandidate -Names @('missingSampleCount'))
    absoluteRmse = ConvertTo-DoubleOrNull (Get-PropertyValue -InputObject $selectedCandidate -Names @('absoluteRmse'))
    deltaRmse = ConvertTo-DoubleOrNull (Get-PropertyValue -InputObject $selectedCandidate -Names @('deltaRmse'))
    stationaryDriftMax = ConvertTo-DoubleOrNull (Get-PropertyValue -InputObject $selectedCandidate -Names @('stationaryDriftMax'))
    truthSampleCount = if ($null -ne $scoresDocument) { ConvertTo-IntOrNull (Get-PropertyValue -InputObject $scoresDocument -Names @('truthSampleCount')) } else { $null }
    memoryRecordCount = if ($null -ne $scoresDocument) { ConvertTo-IntOrNull (Get-PropertyValue -InputObject $scoresDocument -Names @('memoryRecordCount')) } else { $null }
    candidateCount = if ($null -ne $scoresDocument) { ConvertTo-IntOrNull (Get-PropertyValue -InputObject $scoresDocument -Names @('candidateCount')) } else { $null }
    promotionGateFile = $resolvedPromotionGateFile
    candidateScoresFile = $resolvedCandidateScoresFile
    failures = @((Get-PropertyValue -InputObject $gateDocument -Names @('failures')))
    warnings = @((Get-PropertyValue -InputObject $gateDocument -Names @('warnings')))
}

if ([string]::IsNullOrWhiteSpace($summary.selectedCandidateId) -and $null -ne $selectedCandidate) {
    $summary['selectedCandidateId'] = [string](Get-PropertyValue -InputObject $selectedCandidate -Names @('candidateId', 'addressHex'))
}

if (-not [string]::IsNullOrWhiteSpace($OutputJsonFile)) {
    Write-Utf8TextAtomic -Path $OutputJsonFile -Content ($summary | ConvertTo-Json -Depth 32)
}

if (-not [string]::IsNullOrWhiteSpace($OutputMarkdownFile)) {
    Write-Utf8TextAtomic -Path $OutputMarkdownFile -Content (New-MarkdownSummary -Summary ([pscustomobject]$summary))
}

if ($Json) {
    $summary | ConvertTo-Json -Depth 32
}
else {
    Write-Host ("Promotion allowed: {0}" -f $summary.promotionAllowed)
    Write-Host ("Gate status:       {0}" -f $summary.gateStatus)
    Write-Host ("Selected:          {0}" -f $summary.selectedCandidateId)
    Write-Host ("Class:             {0}" -f $summary.classification)
    Write-Host ("Score:             {0}" -f $summary.score)
    if (@($summary.failures).Count -gt 0) {
        Write-Host 'Failures:' -ForegroundColor Yellow
        foreach ($failure in @($summary.failures)) {
            Write-Host ("- {0}" -f $failure)
        }
    }
}
