[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$RunRoot,

    [int]$MinStateCount = 1,
    [switch]$AllowUngated,
    [switch]$Json
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Normalize-Address {
    param([object]$Value)

    if ($null -eq $Value) {
        return $null
    }

    $text = ([string]$Value).Trim()
    if ([string]::IsNullOrWhiteSpace($text)) {
        return $null
    }

    if ($text -match '^0x[0-9A-Fa-f]+$') {
        return $text.ToUpperInvariant()
    }

    return $text
}

function Read-JsonFile {
    param([Parameter(Mandatory = $true)][string]$Path)
    return Get-Content -LiteralPath $Path -Raw | ConvertFrom-Json -Depth 80
}

function Read-Samples {
    param([Parameter(Mandatory = $true)][string]$Path)

    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "Samples file not found: $Path"
    }

    return @(Get-Content -LiteralPath $Path | Where-Object { -not [string]::IsNullOrWhiteSpace($_) } | ForEach-Object {
        $_ | ConvertFrom-Json -Depth 80
    })
}

function Get-OrCreateBucket {
    param(
        [hashtable]$Map,
        [Parameter(Mandatory = $true)][string]$Address,
        [Parameter(Mandatory = $true)][string]$Kind
    )

    if (-not $Map.ContainsKey($Address)) {
        $Map[$Address] = [pscustomobject][ordered]@{
            kind = $Kind
            address = $Address
            states = [System.Collections.Generic.List[string]]::new()
            stateRoles = [System.Collections.Generic.List[string]]::new()
            activeStates = [System.Collections.Generic.List[string]]::new()
            baselineStates = [System.Collections.Generic.List[string]]::new()
            sourceTextAddresses = [System.Collections.Generic.List[string]]::new()
            pointerHitAddresses = [System.Collections.Generic.List[string]]::new()
            pointerScanFiles = [System.Collections.Generic.List[string]]::new()
        }
    }

    return $Map[$Address]
}

function Add-Unique {
    param(
        [System.Collections.Generic.List[string]]$List,
        [string]$Value
    )

    if ([string]::IsNullOrWhiteSpace($Value)) {
        return
    }

    if (-not $List.Contains($Value)) {
        $List.Add($Value) | Out-Null
    }
}

if ($MinStateCount -le 0) {
    throw 'MinStateCount must be greater than zero.'
}

$resolvedRunRoot = (Resolve-Path -LiteralPath $RunRoot).Path
$samplesPath = Join-Path $resolvedRunRoot 'samples.ndjson'
$screenshotGatePath = Join-Path $resolvedRunRoot 'diffs\screenshot-gate.json'
$samples = @(Read-Samples -Path $samplesPath)

$gate = $null
$gatePassed = $false
if (Test-Path -LiteralPath $screenshotGatePath -PathType Leaf) {
    $gate = (Read-JsonFile -Path $screenshotGatePath).screenshotGate
    $gatePassed = (
        [string]$gate.visualGateStatus -eq 'passed' -and
        [bool]$gate.allSamplesHaveUsableCapture -and
        $null -ne $gate.expectedStateSequence -and
        [bool]$gate.expectedStateSequence.passed
    )
}

if (-not $AllowUngated -and -not $gatePassed) {
    throw "Run is not fully screenshot/sequence gated. Use -AllowUngated to extract leads anyway. RunRoot=$resolvedRunRoot"
}

$textAddressMap = @{}
$pointerHitMap = @{}
$stateSummaries = [System.Collections.Generic.List[object]]::new()

foreach ($sample in $samples) {
    $state = [string]$sample.state
    $role = [string]$sample.stateRole
    $textAddresses = @($sample.tooltipTextHitAddresses | ForEach-Object { Normalize-Address $_ } | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })
    $knownTextPointers = @($sample.knownTextPointers)
    $statePointerHitAddresses = [System.Collections.Generic.List[string]]::new()

    foreach ($textAddress in $textAddresses) {
        $bucket = Get-OrCreateBucket -Map $textAddressMap -Address $textAddress -Kind 'text-address'
        Add-Unique -List $bucket.states -Value $state
        Add-Unique -List $bucket.stateRoles -Value $role
        if ($role -eq 'active') { Add-Unique -List $bucket.activeStates -Value $state }
        if ($role -eq 'baseline') { Add-Unique -List $bucket.baselineStates -Value $state }
    }

    foreach ($pointerRecord in $knownTextPointers) {
        $sourceTextAddress = Normalize-Address $pointerRecord.tooltipTextAddress
        $pointerScanFile = [string]$pointerRecord.pointerScanFile
        foreach ($pointerHit in @($pointerRecord.pointerHitAddresses | ForEach-Object { Normalize-Address $_ } | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })) {
            Add-Unique -List $statePointerHitAddresses -Value $pointerHit
            $bucket = Get-OrCreateBucket -Map $pointerHitMap -Address $pointerHit -Kind 'pointer-hit-address'
            Add-Unique -List $bucket.states -Value $state
            Add-Unique -List $bucket.stateRoles -Value $role
            if ($role -eq 'active') { Add-Unique -List $bucket.activeStates -Value $state }
            if ($role -eq 'baseline') { Add-Unique -List $bucket.baselineStates -Value $state }
            Add-Unique -List $bucket.sourceTextAddresses -Value $sourceTextAddress
            Add-Unique -List $bucket.pointerScanFiles -Value $pointerScanFile
        }

        if (-not [string]::IsNullOrWhiteSpace($sourceTextAddress)) {
            $textBucket = Get-OrCreateBucket -Map $textAddressMap -Address $sourceTextAddress -Kind 'text-address'
            Add-Unique -List $textBucket.pointerScanFiles -Value $pointerScanFile
            foreach ($pointerHit in @($pointerRecord.pointerHitAddresses | ForEach-Object { Normalize-Address $_ } | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })) {
                Add-Unique -List $textBucket.pointerHitAddresses -Value $pointerHit
            }
        }
    }

    $stateSummaries.Add([pscustomobject][ordered]@{
        state = $state
        stateRole = $role
        isActiveState = [bool]$sample.isActiveState
        textHitCount = $textAddresses.Count
        textHitAddresses = @($textAddresses)
        pointerScanCount = @($knownTextPointers).Count
        pointerHitCount = @($statePointerHitAddresses).Count
        pointerHitAddresses = @($statePointerHitAddresses)
    }) | Out-Null
}

function Convert-BucketToLead {
    param([object]$Bucket)

    $stateCount = @($Bucket.states).Count
    $roleCount = @($Bucket.stateRoles).Count
    $sourceTextCount = @($Bucket.sourceTextAddresses).Count
    $pointerHitCount = @($Bucket.pointerHitAddresses).Count
    $score = ($stateCount * 10) + ($roleCount * 5) + ($sourceTextCount * 3) + $pointerHitCount

    return [pscustomobject][ordered]@{
        kind = $Bucket.kind
        address = $Bucket.address
        score = $score
        stateCount = $stateCount
        states = @($Bucket.states)
        stateRoles = @($Bucket.stateRoles)
        baselineStates = @($Bucket.baselineStates)
        activeStates = @($Bucket.activeStates)
        sourceTextAddresses = @($Bucket.sourceTextAddresses)
        pointerHitAddresses = @($Bucket.pointerHitAddresses)
        pointerScanFiles = @($Bucket.pointerScanFiles)
    }
}

$textLeads = @($textAddressMap.Values |
    ForEach-Object { Convert-BucketToLead -Bucket $_ } |
    Where-Object { $_.stateCount -ge $MinStateCount } |
    Sort-Object @{ Expression = { $_.score }; Descending = $true }, @{ Expression = { $_.stateCount }; Descending = $true }, address)

$pointerHitLeads = @($pointerHitMap.Values |
    ForEach-Object { Convert-BucketToLead -Bucket $_ } |
    Where-Object { $_.stateCount -ge $MinStateCount } |
    Sort-Object @{ Expression = { $_.score }; Descending = $true }, @{ Expression = { $_.stateCount }; Descending = $true }, address)

$result = [pscustomobject][ordered]@{
    ok = $true
    runRoot = $resolvedRunRoot
    gated = [ordered]@{
        screenshotGate = $screenshotGatePath
        passed = $gatePassed
        visualGateStatus = if ($null -ne $gate) { [string]$gate.visualGateStatus } else { $null }
        expectedStateSequencePassed = if ($null -ne $gate -and $null -ne $gate.expectedStateSequence) { [bool]$gate.expectedStateSequence.passed } else { $false }
    }
    sampleCount = $samples.Count
    stateSummaries = @($stateSummaries)
    textLeadCount = $textLeads.Count
    pointerHitLeadCount = $pointerHitLeads.Count
    textLeads = @($textLeads)
    pointerHitLeads = @($pointerHitLeads)
}

if ($Json) {
    $result | ConvertTo-Json -Depth 80
}
else {
    $result
}
