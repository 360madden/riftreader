[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$BaselineRunRoot,

    [Parameter(Mandatory = $true)]
    [string]$ReproofRunRoot,

    [int]$StartOffset = 0,
    [int]$Length = 0,
    [int]$Top = 20,

    [switch]$Json
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Resolve-RunRoot {
    param([Parameter(Mandatory = $true)][string]$Path)
    return (Resolve-Path -LiteralPath $Path).Path
}

function Read-JsonFile {
    param([Parameter(Mandatory = $true)][string]$Path)
    return Get-Content -LiteralPath $Path -Raw | ConvertFrom-Json -Depth 80
}

function Convert-HexStringToBytes {
    param([Parameter(Mandatory = $true)][string]$Hex)

    $clean = $Hex -replace '[^0-9A-Fa-f]', ''
    if (($clean.Length % 2) -ne 0) {
        throw 'bytesHex has an odd number of hex digits after normalization.'
    }

    $bytes = [byte[]]::new($clean.Length / 2)
    for ($i = 0; $i -lt $bytes.Length; $i++) {
        $bytes[$i] = [Convert]::ToByte($clean.Substring($i * 2, 2), 16)
    }

    return $bytes
}

function Add-Check {
    param(
        [System.Collections.Generic.List[object]]$Checks,
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][bool]$Passed,
        [string]$Detail,
        [object]$Data
    )

    $Checks.Add([pscustomobject][ordered]@{
        name = $Name
        status = if ($Passed) { 'passed' } else { 'failed' }
        detail = $Detail
        data = $Data
    }) | Out-Null
}

function Test-SequenceEqual {
    param([string[]]$Actual, [string[]]$Expected)

    if ($Actual.Count -ne $Expected.Count) {
        return $false
    }

    for ($i = 0; $i -lt $Expected.Count; $i++) {
        if ($Actual[$i] -ne $Expected[$i]) {
            return $false
        }
    }

    return $true
}

function Read-Samples {
    param([Parameter(Mandatory = $true)][string]$Path)

    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        return @()
    }

    return @(Get-Content -LiteralPath $Path | Where-Object { -not [string]::IsNullOrWhiteSpace($_) } | ForEach-Object {
        $row = $_ | ConvertFrom-Json -Depth 80
        [pscustomobject][ordered]@{
            state = [string]$row.state
            stateRole = [string]$row.stateRole
            isActiveState = [bool]$row.isActiveState
            bytes = Convert-HexStringToBytes -Hex ([string]$row.bytesHex)
        }
    })
}

function Get-GatedRun {
    param([Parameter(Mandatory = $true)][string]$RunRoot)

    $screenshotGatePath = Join-Path $RunRoot 'diffs\screenshot-gate.json'
    $samplesPath = Join-Path $RunRoot 'samples.ndjson'
    $screenshotGateExists = Test-Path -LiteralPath $screenshotGatePath -PathType Leaf
    $samplesExist = Test-Path -LiteralPath $samplesPath -PathType Leaf
    $gate = if ($screenshotGateExists) { (Read-JsonFile -Path $screenshotGatePath).screenshotGate } else { $null }

    return [pscustomobject][ordered]@{
        runRoot = $RunRoot
        screenshotGatePath = $screenshotGatePath
        samplesPath = $samplesPath
        screenshotGateExists = $screenshotGateExists
        samplesExist = $samplesExist
        visualGateStatus = if ($null -ne $gate) { [string]$gate.visualGateStatus } else { $null }
        expectedStateSequencePassed = if ($null -ne $gate -and $null -ne $gate.expectedStateSequence) { [bool]$gate.expectedStateSequence.passed } else { $false }
        states = if ($null -ne $gate -and $null -ne $gate.expectedStateSequence) { @($gate.expectedStateSequence.actualStates | ForEach-Object { [string]$_ }) } else { @() }
        stateRoles = if ($null -ne $gate -and $null -ne $gate.expectedStateSequence) { @($gate.expectedStateSequence.actualStateRoles | ForEach-Object { [string]$_ }) } else { @() }
        samples = @(Read-Samples -Path $samplesPath)
    }
}

function Get-ByteSequence {
    param(
        [object[]]$Samples,
        [Parameter(Mandatory = $true)][int]$Offset
    )

    return @($Samples | ForEach-Object {
        if ($Offset -ge $_.bytes.Length) { $null } else { [int]$_.bytes[$Offset] }
    })
}

function Join-ByteSequence {
    param([object[]]$Values)
    return (@($Values | ForEach-Object { if ($null -eq $_) { '<null>' } else { [string]$_ } }) -join ',')
}

if ($StartOffset -lt 0) {
    throw 'StartOffset must be non-negative.'
}

if ($Length -lt 0) {
    throw 'Length must be non-negative. Use 0 to compare the common window length.'
}

if ($Top -le 0) {
    throw 'Top must be greater than zero.'
}

$baselineRoot = Resolve-RunRoot -Path $BaselineRunRoot
$reproofRoot = Resolve-RunRoot -Path $ReproofRunRoot
$baseline = Get-GatedRun -RunRoot $baselineRoot
$reproof = Get-GatedRun -RunRoot $reproofRoot
$checks = [System.Collections.Generic.List[object]]::new()

foreach ($run in @(
    [pscustomobject]@{ Name = 'baseline'; Summary = $baseline },
    [pscustomobject]@{ Name = 'reproof'; Summary = $reproof }
)) {
    Add-Check -Checks $checks -Name "$($run.Name)-screenshot-gate-file" -Passed ([bool]$run.Summary.screenshotGateExists) -Detail "Expected screenshot gate file: $($run.Summary.screenshotGatePath)"
    Add-Check -Checks $checks -Name "$($run.Name)-samples-file" -Passed ([bool]$run.Summary.samplesExist) -Detail "Expected samples file: $($run.Summary.samplesPath)"
    Add-Check -Checks $checks -Name "$($run.Name)-visual-gate-passed" -Passed ([string]$run.Summary.visualGateStatus -eq 'passed') -Detail "visualGateStatus=$($run.Summary.visualGateStatus)"
    Add-Check -Checks $checks -Name "$($run.Name)-sequence-passed" -Passed ([bool]$run.Summary.expectedStateSequencePassed) -Detail "expectedStateSequence.passed=$($run.Summary.expectedStateSequencePassed)"
}

$statesMatch = Test-SequenceEqual -Actual @($reproof.states) -Expected @($baseline.states)
$rolesMatch = Test-SequenceEqual -Actual @($reproof.stateRoles) -Expected @($baseline.stateRoles)
Add-Check -Checks $checks -Name 'state-sequence-match' -Passed $statesMatch -Detail "baseline=$($baseline.states -join ','), reproof=$($reproof.states -join ',')"
Add-Check -Checks $checks -Name 'state-role-sequence-match' -Passed $rolesMatch -Detail "baseline=$($baseline.stateRoles -join ','), reproof=$($reproof.stateRoles -join ',')"

$baselineMinLength = if (@($baseline.samples).Count -gt 0) { [int](@($baseline.samples | ForEach-Object { $_.bytes.Length }) | Measure-Object -Minimum).Minimum } else { 0 }
$reproofMinLength = if (@($reproof.samples).Count -gt 0) { [int](@($reproof.samples | ForEach-Object { $_.bytes.Length }) | Measure-Object -Minimum).Minimum } else { 0 }
$commonLength = [Math]::Min($baselineMinLength, $reproofMinLength)
$effectiveLength = if ($Length -gt 0) { $Length } else { [Math]::Max(0, $commonLength - $StartOffset) }
if (($StartOffset + $effectiveLength) -gt $commonLength) {
    throw "Requested byte window StartOffset=$StartOffset Length=$effectiveLength exceeds common sample length $commonLength."
}

$offsetRows = [System.Collections.Generic.List[object]]::new()
for ($offset = $StartOffset; $offset -lt ($StartOffset + $effectiveLength); $offset++) {
    $baselineValues = @(Get-ByteSequence -Samples @($baseline.samples) -Offset $offset)
    $reproofValues = @(Get-ByteSequence -Samples @($reproof.samples) -Offset $offset)
    $baselineSequence = Join-ByteSequence -Values $baselineValues
    $reproofSequence = Join-ByteSequence -Values $reproofValues
    $baselineDistinct = @($baselineValues | Select-Object -Unique).Count
    $reproofDistinct = @($reproofValues | Select-Object -Unique).Count
    $baselineChanged = $baselineDistinct -gt 1
    $reproofChanged = $reproofDistinct -gt 1
    $sequenceMatches = $baselineSequence -eq $reproofSequence

    $classification = if ($sequenceMatches -and $baselineChanged) {
        'repeated-changing'
    }
    elseif ($sequenceMatches) {
        'repeated-static'
    }
    elseif ($baselineChanged -and $reproofChanged) {
        'changed-in-both-different'
    }
    elseif ($baselineChanged) {
        'baseline-only-change'
    }
    elseif ($reproofChanged) {
        'reproof-only-change'
    }
    else {
        'different-static'
    }

    $offsetRows.Add([pscustomobject][ordered]@{
        offset = ('+0x{0:X}' -f $offset)
        offsetDecimal = $offset
        classification = $classification
        sequenceMatches = $sequenceMatches
        baselineChanged = $baselineChanged
        reproofChanged = $reproofChanged
        baselineDistinct = $baselineDistinct
        reproofDistinct = $reproofDistinct
        baselineBytes = @($baselineValues)
        reproofBytes = @($reproofValues)
    }) | Out-Null
}

$rows = @($offsetRows.ToArray())
$repeatedChanging = @($rows | Where-Object { $_.classification -eq 'repeated-changing' })
$baselineOnlyChange = @($rows | Where-Object { $_.classification -eq 'baseline-only-change' })
$reproofOnlyChange = @($rows | Where-Object { $_.classification -eq 'reproof-only-change' })
$changedInBothDifferent = @($rows | Where-Object { $_.classification -eq 'changed-in-both-different' })

$failedChecks = @($checks | Where-Object { $_.status -ne 'passed' })
$result = [pscustomobject][ordered]@{
    ok = ($failedChecks.Count -eq 0)
    baselineRunRoot = $baselineRoot
    reproofRunRoot = $reproofRoot
    comparedWindow = [ordered]@{
        startOffset = ('+0x{0:X}' -f $StartOffset)
        startOffsetDecimal = $StartOffset
        length = $effectiveLength
        commonSampleLength = $commonLength
    }
    counts = [ordered]@{
        comparedOffsets = $rows.Count
        repeatedChanging = $repeatedChanging.Count
        baselineOnlyChange = $baselineOnlyChange.Count
        reproofOnlyChange = $reproofOnlyChange.Count
        changedInBothDifferent = $changedInBothDifferent.Count
    }
    topRepeatedChanging = @($repeatedChanging | Select-Object -First $Top)
    topBaselineOnlyChange = @($baselineOnlyChange | Select-Object -First $Top)
    topReproofOnlyChange = @($reproofOnlyChange | Select-Object -First $Top)
    topChangedInBothDifferent = @($changedInBothDifferent | Select-Object -First $Top)
    checks = @($checks)
}

if ($Json) {
    $result | ConvertTo-Json -Depth 80
}
else {
    $result
}

if (-not [bool]$result.ok) {
    exit 1
}
