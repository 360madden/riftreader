[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateNotNullOrEmpty()]
    [string]$InputDirectory,

    [string]$CandidateAddress,

    [string]$BaselineStateRegex = 'hidden',
    [string]$ActiveStateRegex = 'hover',
    [string]$BaselineLabel = 'hidden',
    [string]$ActiveLabel = 'hover',

    [switch]$RequireVisualGate,

    [switch]$Json
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Get-JsonPropertyValue {
    param(
        [Parameter(Mandatory = $true)]$Object,
        [Parameter(Mandatory = $true)][string[]]$Names
    )

    if ($null -eq $Object) { return $null }
    $properties = $Object.PSObject.Properties
    foreach ($name in $Names) {
        $property = $properties | Where-Object { $_.Name -ieq $name } | Select-Object -First 1
        if ($null -ne $property) { return $property.Value }
    }

    return $null
}

function ConvertTo-UInt64OrNull {
    param($Value)

    if ($null -eq $Value) { return $null }
    if ($Value -is [System.ValueType] -and -not ($Value -is [string])) {
        try { return [uint64]$Value } catch { return $null }
    }

    $text = ([string]$Value).Trim()
    if ([string]::IsNullOrWhiteSpace($text)) { return $null }
    try {
        if ($text.StartsWith('0x', [StringComparison]::OrdinalIgnoreCase)) {
            return [Convert]::ToUInt64($text.Substring(2), 16)
        }

        return [Convert]::ToUInt64($text, 10)
    }
    catch {
        return $null
    }
}

function Format-HexAddress {
    param([uint64]$Value)
    return ('0x{0:X}' -f $Value)
}

function Convert-HexStringToBytes {
    param([Parameter(Mandatory = $true)][string]$Hex)

    $clean = ($Hex -replace '[^0-9A-Fa-f]', '')
    if (($clean.Length % 2) -ne 0) {
        throw "bytesHex contains an odd number of hex characters after normalization."
    }

    $bytes = [byte[]]::new($clean.Length / 2)
    for ($i = 0; $i -lt $bytes.Length; $i++) {
        $bytes[$i] = [Convert]::ToByte($clean.Substring($i * 2, 2), 16)
    }

    return $bytes
}

function ConvertTo-StringSet {
    param([object[]]$Values)

    $set = [System.Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
    foreach ($value in $Values) {
        if ($null -eq $value) { continue }
        [void]$set.Add(([string]$value))
    }

    Write-Output -NoEnumerate $set
}

function Get-DistinctCount {
    param([object[]]$Values)
    return (ConvertTo-StringSet -Values $Values).Count
}

function Test-PointerLike {
    param([uint64]$Value)

    if ($Value -lt 0x10000) { return $false }
    if ($Value -eq 0xffffffffffffffff) { return $false }
    if (($Value -band 0xffff000000000000) -eq 0xffff000000000000) { return $false }
    return $true
}

function Read-ViewValue {
    param(
        [Parameter(Mandatory = $true)][byte[]]$Bytes,
        [Parameter(Mandatory = $true)][int]$Offset,
        [Parameter(Mandatory = $true)][string]$View
    )

    switch ($View) {
        'byte' {
            if ($Offset -ge $Bytes.Length) { return $null }
            return [int]$Bytes[$Offset]
        }
        'uint16' {
            if (($Offset + 2) -gt $Bytes.Length) { return $null }
            return [int][BitConverter]::ToUInt16($Bytes, $Offset)
        }
        'int32' {
            if (($Offset + 4) -gt $Bytes.Length) { return $null }
            return [int][BitConverter]::ToInt32($Bytes, $Offset)
        }
        'float32' {
            if (($Offset + 4) -gt $Bytes.Length) { return $null }
            $value = [BitConverter]::ToSingle($Bytes, $Offset)
            if ([float]::IsNaN($value) -or [float]::IsInfinity($value)) { return $null }
            return [double]$value
        }
        'pointer' {
            if (($Offset + 8) -gt $Bytes.Length) { return $null }
            return [uint64][BitConverter]::ToUInt64($Bytes, $Offset)
        }
        default { throw "Unknown view '$View'." }
    }
}

function Get-ComparableValue {
    param($Value, [string]$View)

    if ($null -eq $Value) { return '<null>' }
    if ($View -eq 'float32') { return ('{0:R}' -f [double]$Value) }
    if ($View -eq 'pointer') { return Format-HexAddress -Value ([uint64]$Value) }
    return ([string]$Value)
}

function Get-ModeValue {
    param([object[]]$Values, [string]$View)

    $counts = @{}
    $raw = @{}
    foreach ($value in $Values) {
        $key = Get-ComparableValue -Value $value -View $View
        if (-not $counts.ContainsKey($key)) {
            $counts[$key] = 0
            $raw[$key] = $value
        }
        $counts[$key]++
    }

    if ($counts.Count -eq 0) { return $null }
    $best = $counts.GetEnumerator() | Sort-Object -Property Value -Descending | Select-Object -First 1
    return $raw[$best.Key]
}

function Test-ScreenishNumber {
    param($Value)

    if ($null -eq $Value) { return $false }
    $number = [double]$Value
    if ([math]::Abs($number) -gt 10000) { return $false }
    if ([math]::Abs($number) -lt 0.000001) { return $false }
    return $true
}

function Normalize-KnownPointerList {
    param($Value)

    $results = [System.Collections.Generic.List[uint64]]::new()
    if ($null -eq $Value) { Write-Output -NoEnumerate $results; return }

    $items = @($Value)
    foreach ($item in $items) {
        if ($null -eq $item) { continue }
        if ($item -is [string] -and $item.Contains(',')) {
            foreach ($part in $item.Split(',', [StringSplitOptions]::RemoveEmptyEntries)) {
                $parsed = ConvertTo-UInt64OrNull -Value $part
                if ($null -ne $parsed) { $results.Add([uint64]$parsed) }
            }
            continue
        }

        $parsedItem = ConvertTo-UInt64OrNull -Value $item
        if ($null -ne $parsedItem) { $results.Add([uint64]$parsedItem) }

        if ($item -is [psobject]) {
            foreach ($propertyName in @('tooltipTextAddress', 'TooltipTextAddress', 'textAddress', 'TextAddress', 'tooltipTextPointer', 'TooltipTextPointer', 'knownTextPointer', 'KnownTextPointer')) {
                if ($item.PSObject.Properties.Name -contains $propertyName) {
                    $parsedProperty = ConvertTo-UInt64OrNull -Value $item.$propertyName
                    if ($null -ne $parsedProperty) {
                        $results.Add([uint64]$parsedProperty)
                    }
                }
            }
        }
    }

    Write-Output -NoEnumerate @($results | Select-Object -Unique)
}

function Normalize-SampleRow {
    param(
        $Row,
        [string]$CandidateAddressOverride,
        [string]$BaselineStateRegex,
        [string]$ActiveStateRegex
    )

    $state = Get-JsonPropertyValue -Object $Row -Names @('state', 'tooltipState', 'phase', 'label')
    $bytesHex = Get-JsonPropertyValue -Object $Row -Names @('bytesHex', 'BytesHex')
    $windowStart = Get-JsonPropertyValue -Object $Row -Names @('windowStart', 'baseAddress', 'address', 'Address')
    $windowLength = Get-JsonPropertyValue -Object $Row -Names @('windowLength', 'length', 'Length', 'bytesRead', 'BytesRead')
    $candidateAddress = Get-JsonPropertyValue -Object $Row -Names @('candidateAddress', 'CandidateAddress')
    $knownTextPointers = Get-JsonPropertyValue -Object $Row -Names @('knownTextPointers', 'KnownTextPointers', 'knownTextPointer', 'tooltipTextPointer')
    $hasTarget = Get-JsonPropertyValue -Object $Row -Names @('hasTarget', 'HasTarget')
    $files = Get-JsonPropertyValue -Object $Row -Names @('files', 'Files')

    if ($null -eq $bytesHex) {
        $memory = Get-JsonPropertyValue -Object $Row -Names @('memoryRead', 'read', 'region')
        if ($null -ne $memory) {
            $bytesHex = Get-JsonPropertyValue -Object $memory -Names @('bytesHex', 'BytesHex')
            if ($null -eq $windowStart) { $windowStart = Get-JsonPropertyValue -Object $memory -Names @('windowStart', 'baseAddress', 'address', 'Address') }
            if ($null -eq $windowLength) { $windowLength = Get-JsonPropertyValue -Object $memory -Names @('windowLength', 'length', 'Length', 'bytesRead', 'BytesRead') }
        }
    }

    if ($null -eq $bytesHex) {
        $regions = Get-JsonPropertyValue -Object $Row -Names @('regions', 'Regions')
        if ($null -ne $regions) {
            $bestRegion = @($regions | Where-Object {
                $candidateBytes = Get-JsonPropertyValue -Object $_ -Names @('bytesHex', 'BytesHex')
                -not [string]::IsNullOrWhiteSpace([string]$candidateBytes)
            } | Select-Object -First 1)
            if ($bestRegion.Count -gt 0) {
                $region = $bestRegion[0]
                $bytesHex = Get-JsonPropertyValue -Object $region -Names @('bytesHex', 'BytesHex')
                if ($null -eq $windowStart) { $windowStart = Get-JsonPropertyValue -Object $region -Names @('windowStart', 'baseAddress', 'address', 'Address') }
                if ($null -eq $windowLength) { $windowLength = Get-JsonPropertyValue -Object $region -Names @('windowLength', 'length', 'Length', 'bytesRead', 'BytesRead') }
            }
        }
    }

    if ([string]::IsNullOrWhiteSpace([string]$state)) {
        $text = ($Row | ConvertTo-Json -Compress -Depth 8)
        if ($text -match $ActiveStateRegex) { $state = 'hover' }
        elseif ($text -match $BaselineStateRegex) { $state = 'hidden' }
    }

    if ($null -ne $CandidateAddressOverride -and -not [string]::IsNullOrWhiteSpace($CandidateAddressOverride)) {
        $candidateAddress = $CandidateAddressOverride
    }

    if ([string]::IsNullOrWhiteSpace([string]$bytesHex)) { return $null }
    if ([string]::IsNullOrWhiteSpace([string]$state)) { return $null }

    $stateText = [string]$state
    if ($stateText -notmatch $BaselineStateRegex -and $stateText -notmatch $ActiveStateRegex) { return $null }
    $normalizedState = if ($stateText -match $ActiveStateRegex) { 'hover' } else { 'hidden' }

    $bytes = Convert-HexStringToBytes -Hex ([string]$bytesHex)
    $parsedWindowStart = ConvertTo-UInt64OrNull -Value $windowStart
    $parsedCandidate = ConvertTo-UInt64OrNull -Value $candidateAddress
    $pointers = Normalize-KnownPointerList -Value $knownTextPointers

    return [pscustomobject]@{
        State = $normalizedState
        Bytes = $bytes
        WindowStart = $parsedWindowStart
        WindowLength = if ($null -ne $windowLength) { [int]$windowLength } else { $bytes.Length }
        CandidateAddress = $parsedCandidate
        KnownTextPointers = @($pointers)
        HasTarget = if ($null -eq $hasTarget) { $null } else { [bool]$hasTarget }
        ScreenshotCapture = if ($null -eq $files) { $null } else { Get-JsonPropertyValue -Object $files -Names @('screenshotCapture', 'ScreenshotCapture') }
        ScreenshotOutput = if ($null -eq $files) { $null } else { Get-JsonPropertyValue -Object $files -Names @('screenshotOutput', 'ScreenshotOutput') }
        Raw = $Row
    }
}

function Get-ScreenshotGateSummary {
    param([Parameter(Mandatory = $true)][object[]]$Samples)

    $rows = [System.Collections.Generic.List[object]]::new()
    foreach ($sample in $Samples) {
        $capturePath = $sample.ScreenshotCapture
        $outputPath = $sample.ScreenshotOutput
        $captureExists = -not [string]::IsNullOrWhiteSpace([string]$capturePath) -and (Test-Path -LiteralPath ([string]$capturePath) -PathType Leaf)
        $outputExists = -not [string]::IsNullOrWhiteSpace([string]$outputPath) -and (Test-Path -LiteralPath ([string]$outputPath) -PathType Leaf)
        $usable = $null
        $ok = $null
        $captureMethod = $null
        $contentBlackRatio = $null
        $contentLumaStdDev = $null
        $parseError = $null

        if ($captureExists) {
            try {
                $captureRecord = Get-Content -LiteralPath ([string]$capturePath) -Raw | ConvertFrom-Json -Depth 32
                $captureJson = Get-JsonPropertyValue -Object $captureRecord -Names @('json', 'Json')
                if ($null -ne $captureJson) {
                    $ok = Get-JsonPropertyValue -Object $captureJson -Names @('Ok', 'ok')
                    $usable = Get-JsonPropertyValue -Object $captureJson -Names @('Usable', 'usable')
                    $captureMethod = Get-JsonPropertyValue -Object $captureJson -Names @('CaptureMethod', 'captureMethod')
                    $contentBlackRatio = Get-JsonPropertyValue -Object $captureJson -Names @('ContentBlackPixelRatio', 'contentBlackPixelRatio')
                    $contentLumaStdDev = Get-JsonPropertyValue -Object $captureJson -Names @('ContentLumaStdDev', 'contentLumaStdDev')
                }
            }
            catch {
                $parseError = $_.Exception.Message
            }
        }

        $rows.Add([pscustomobject][ordered]@{
            state = $sample.State
            captureRecord = $capturePath
            captureRecordExists = $captureExists
            screenshotOutput = $outputPath
            screenshotOutputExists = $outputExists
            ok = if ($null -eq $ok) { $null } else { [bool]$ok }
            usable = if ($null -eq $usable) { $null } else { [bool]$usable }
            captureMethod = $captureMethod
            contentBlackRatio = $contentBlackRatio
            contentLumaStdDev = $contentLumaStdDev
            parseError = $parseError
        }) | Out-Null
    }

    $rowArray = @($rows.ToArray())
    $withCapture = @($rowArray | Where-Object { $_.captureRecordExists })
    $usableRows = @($rowArray | Where-Object { $_.usable -eq $true })
    $unusableRows = @($rowArray | Where-Object { $_.captureRecordExists -and $_.usable -ne $true })

    return [pscustomobject][ordered]@{
        sampleCount = $rowArray.Count
        captureRecordCount = $withCapture.Count
        usableCount = $usableRows.Count
        unusableCount = $unusableRows.Count
        allSamplesHaveCapture = ($rowArray.Count -gt 0 -and $withCapture.Count -eq $rowArray.Count)
        allCapturesUsable = ($withCapture.Count -gt 0 -and $usableRows.Count -eq $withCapture.Count)
        visualGateStatus = if ($withCapture.Count -eq 0) { 'not-captured' } elseif ($usableRows.Count -eq $withCapture.Count) { 'passed' } else { 'failed-or-partial' }
        rows = @($rowArray)
    }
}

function Normalize-AddressList {
    param($Value)

    $results = [System.Collections.Generic.List[uint64]]::new()
    if ($null -eq $Value) {
        return @()
    }

    foreach ($item in @($Value)) {
        if ($null -eq $item) {
            continue
        }

        if ($item -is [string] -and $item.Contains(',')) {
            foreach ($part in $item.Split(',', [StringSplitOptions]::RemoveEmptyEntries)) {
                $parsedPart = ConvertTo-UInt64OrNull -Value $part
                if ($null -ne $parsedPart) { $results.Add([uint64]$parsedPart) }
            }
            continue
        }

        $parsed = ConvertTo-UInt64OrNull -Value $item
        if ($null -ne $parsed) {
            $results.Add([uint64]$parsed)
            continue
        }

        if ($item -is [psobject]) {
            foreach ($propertyName in @('AddressHex', 'addressHex', 'Address', 'address', 'pointerHitAddress', 'hitAddress')) {
                if ($item.PSObject.Properties.Name -contains $propertyName) {
                    $parsedProperty = ConvertTo-UInt64OrNull -Value $item.$propertyName
                    if ($null -ne $parsedProperty) {
                        $results.Add([uint64]$parsedProperty)
                    }
                }
            }
        }
    }

    return @($results | Select-Object -Unique | Sort-Object)
}

function Convert-AddressListToText {
    param([uint64[]]$Addresses)

    return @($Addresses | Sort-Object | Select-Object -Unique | ForEach-Object { Format-HexAddress -Value $_ })
}

function Get-ScanEvidenceRows {
    param([Parameter(Mandatory = $true)]$Sample)

    $rows = [System.Collections.Generic.List[object]]::new()
    $raw = $Sample.Raw
    if ($null -eq $raw) {
        return @()
    }

    $extraPointerScans = Get-JsonPropertyValue -Object $raw -Names @('extraPointerScans', 'ExtraPointerScans')
    foreach ($scan in @($extraPointerScans)) {
        if ($null -eq $scan) { continue }
        $target = Get-JsonPropertyValue -Object $scan -Names @('pointerTarget', 'PointerTarget', 'target', 'Target')
        $targetAddress = ConvertTo-UInt64OrNull -Value $target
        $hitAddresses = @(Normalize-AddressList -Value (Get-JsonPropertyValue -Object $scan -Names @('pointerHitAddresses', 'PointerHitAddresses', 'hitAddresses', 'HitAddresses', 'hits', 'Hits')))
        $targetText = if ($null -ne $targetAddress) { Format-HexAddress -Value $targetAddress } else { [string]$target }
        if ([string]::IsNullOrWhiteSpace($targetText)) { $targetText = '<blank-pointer-target>' }

        $rows.Add([pscustomobject]@{
            state = $Sample.State
            kind = 'pointer'
            key = "pointer:$targetText"
            pointerTarget = $targetText
            scanType = $null
            scanValue = $null
            tolerance = $null
            hitCount = @($hitAddresses).Count
            hitAddresses = @(Convert-AddressListToText -Addresses $hitAddresses)
        }) | Out-Null
    }

    $numericScans = Get-JsonPropertyValue -Object $raw -Names @('numericScans', 'NumericScans')
    foreach ($scan in @($numericScans)) {
        if ($null -eq $scan) { continue }
        $type = [string](Get-JsonPropertyValue -Object $scan -Names @('type', 'Type', 'scanType', 'ScanType'))
        $value = [string](Get-JsonPropertyValue -Object $scan -Names @('value', 'Value', 'scanValue', 'ScanValue'))
        $tolerance = Get-JsonPropertyValue -Object $scan -Names @('tolerance', 'Tolerance')
        if ([string]::IsNullOrWhiteSpace($type)) { $type = 'numeric' }
        if ([string]::IsNullOrWhiteSpace($value)) { $value = '<blank-value>' }

        $hitAddresses = @(Normalize-AddressList -Value (Get-JsonPropertyValue -Object $scan -Names @('hitAddresses', 'HitAddresses', 'hits', 'Hits')))
        $rows.Add([pscustomobject]@{
            state = $Sample.State
            kind = 'numeric'
            key = "numeric:$($type.ToLowerInvariant()):$value"
            pointerTarget = $null
            scanType = $type.ToLowerInvariant()
            scanValue = $value
            tolerance = $tolerance
            hitCount = @($hitAddresses).Count
            hitAddresses = @(Convert-AddressListToText -Addresses $hitAddresses)
        }) | Out-Null
    }

    return @($rows)
}

function Get-AddressModeText {
    param([object[]]$Rows)

    $keys = @($Rows | ForEach-Object { (@($_.hitAddresses) | Sort-Object) -join ',' })
    if ($keys.Count -eq 0) {
        return ''
    }

    $mode = $keys | Group-Object | Sort-Object -Property Count -Descending | Select-Object -First 1
    return [string]$mode.Name
}

function Get-ScanEvidenceSummary {
    param(
        [Parameter(Mandatory = $true)][object[]]$Samples,
        [Parameter(Mandatory = $true)][int]$HiddenCount,
        [Parameter(Mandatory = $true)][int]$HoverCount
    )

    $rows = [System.Collections.Generic.List[object]]::new()
    foreach ($sample in $Samples) {
        foreach ($row in @(Get-ScanEvidenceRows -Sample $sample)) {
            $rows.Add($row) | Out-Null
        }
    }

    $summaries = [System.Collections.Generic.List[object]]::new()
    foreach ($group in ($rows | Group-Object -Property key)) {
        $groupRows = @($group.Group)
        $hiddenRows = @($groupRows | Where-Object { $_.state -eq 'hidden' })
        $hoverRows = @($groupRows | Where-Object { $_.state -eq 'hover' })
        $hiddenAddresses = @(Normalize-AddressList -Value @($hiddenRows | ForEach-Object { $_.hitAddresses }))
        $hoverAddresses = @(Normalize-AddressList -Value @($hoverRows | ForEach-Object { $_.hitAddresses }))
        $hiddenMode = Get-AddressModeText -Rows $hiddenRows
        $hoverMode = Get-AddressModeText -Rows $hoverRows
        $hiddenHitCounts = @($hiddenRows | ForEach-Object { [int]$_.hitCount })
        $hoverHitCounts = @($hoverRows | ForEach-Object { [int]$_.hitCount })
        $hiddenHasHits = $hiddenAddresses.Count -gt 0
        $hoverHasHits = $hoverAddresses.Count -gt 0
        $hiddenStable = $hiddenRows.Count -gt 0 -and (@($hiddenHitCounts | Select-Object -Unique).Count -le 1) -and (@($hiddenRows | ForEach-Object { (@($_.hitAddresses) | Sort-Object) -join ',' } | Select-Object -Unique).Count -le 1)
        $hoverStable = $hoverRows.Count -gt 0 -and (@($hoverHitCounts | Select-Object -Unique).Count -le 1) -and (@($hoverRows | ForEach-Object { (@($_.hitAddresses) | Sort-Object) -join ',' } | Select-Object -Unique).Count -le 1)
        $score = 0
        $classification = 'scan-no-hit-or-static'
        $evidence = [System.Collections.Generic.List[string]]::new()

        if ($hiddenRows.Count -eq $HiddenCount) { $score += 5; $evidence.Add('scan present for every hidden sample') }
        if ($hoverRows.Count -eq $HoverCount) { $score += 5; $evidence.Add('scan present for every hover sample') }
        if ($hiddenStable) { $score += 10; $evidence.Add('hidden scan hits are stable') }
        if ($hoverStable) { $score += 10; $evidence.Add('hover scan hits are stable') }

        if (-not $hiddenHasHits -and $hoverHasHits) {
            $classification = 'hover-only-scan-hit-candidate'
            $score += 70
            $evidence.Add('scan has hits only during hover samples')
        }
        elseif ($hiddenHasHits -and -not $hoverHasHits) {
            $classification = 'hidden-only-scan-hit-candidate'
            $score += 45
            $evidence.Add('scan has hits only during hidden samples')
        }
        elseif ($hiddenHasHits -and $hoverHasHits -and $hiddenMode -ne $hoverMode) {
            $classification = 'state-dependent-scan-hit-candidate'
            $score += 55
            $evidence.Add('hidden and hover scan hit address sets differ')
        }
        elseif ($hiddenHasHits -and $hoverHasHits) {
            $classification = 'state-invariant-scan-hit'
            $score += 20
            $evidence.Add('scan hits exist in both states with no state-dependent address-set change')
        }

        if ($groupRows[0].kind -eq 'pointer' -and $classification -match 'candidate') {
            $score += 10
            $evidence.Add('explicit pointer scan candidate')
        }

        $maxHiddenHitCount = if ($hiddenHitCounts.Count -gt 0) { ($hiddenHitCounts | Measure-Object -Maximum).Maximum } else { 0 }
        $maxHoverHitCount = if ($hoverHitCounts.Count -gt 0) { ($hoverHitCounts | Measure-Object -Maximum).Maximum } else { 0 }
        $broadNumericScan = $groupRows[0].kind -eq 'numeric' -and (
            $hiddenAddresses.Count -gt 12 -or
            $hoverAddresses.Count -gt 12 -or
            $maxHiddenHitCount -ge 12 -or
            $maxHoverHitCount -ge 12
        )

        if ($broadNumericScan) {
            $score -= 45
            $evidence.Add('downranked broad numeric scan with many hits')
            if ($classification -ne 'scan-no-hit-or-static' -and $score -lt 50) {
                $classification = 'broad-numeric-scan-noise'
            }
        }

        $summaries.Add([pscustomobject]@{
            key = $group.Name
            kind = $groupRows[0].kind
            pointerTarget = $groupRows[0].pointerTarget
            scanType = $groupRows[0].scanType
            scanValue = $groupRows[0].scanValue
            tolerance = $groupRows[0].tolerance
            classification = $classification
            score = [math]::Round([double]$score, 2)
            evidence = @($evidence)
            hiddenSampleRows = $hiddenRows.Count
            hoverSampleRows = $hoverRows.Count
            hiddenHitCounts = @($hiddenHitCounts)
            hoverHitCounts = @($hoverHitCounts)
            hiddenModeHitAddresses = if ([string]::IsNullOrWhiteSpace($hiddenMode)) { @() } else { @($hiddenMode -split ',' | Where-Object { -not [string]::IsNullOrWhiteSpace($_) }) }
            hoverModeHitAddresses = if ([string]::IsNullOrWhiteSpace($hoverMode)) { @() } else { @($hoverMode -split ',' | Where-Object { -not [string]::IsNullOrWhiteSpace($_) }) }
            hiddenAllHitAddresses = @(Convert-AddressListToText -Addresses $hiddenAddresses)
            hoverAllHitAddresses = @(Convert-AddressListToText -Addresses $hoverAddresses)
        }) | Out-Null
    }

    return @($summaries | Sort-Object -Property @{ Expression = 'score'; Descending = $true }, @{ Expression = 'key'; Descending = $false })
}

function Get-TransitionPairCount {
    param(
        [Parameter(Mandatory = $true)][object[]]$Samples,
        [Parameter(Mandatory = $true)][int]$Offset,
        [Parameter(Mandatory = $true)][string]$View
    )

    $pairs = 0
    $changed = 0
    for ($i = 1; $i -lt $Samples.Count; $i++) {
        $previous = $Samples[$i - 1]
        $current = $Samples[$i]
        if ($previous.State -eq $current.State) { continue }
        $pairs++
        $previousValue = Read-ViewValue -Bytes $previous.Bytes -Offset $Offset -View $View
        $currentValue = Read-ViewValue -Bytes $current.Bytes -Offset $Offset -View $View
        if ((Get-ComparableValue -Value $previousValue -View $View) -ne (Get-ComparableValue -Value $currentValue -View $View)) {
            $changed++
        }
    }

    return [pscustomobject]@{ Pairs = $pairs; Changed = $changed }
}

function Get-ClassificationForView {
    param(
        [Parameter(Mandatory = $true)][string]$View,
        [Parameter(Mandatory = $true)][int]$Offset,
        [Parameter(Mandatory = $true)][object[]]$HiddenValues,
        [Parameter(Mandatory = $true)][object[]]$HoverValues,
        [Parameter(Mandatory = $true)][object[]]$AllValues,
        [Parameter(Mandatory = $true)][AllowEmptyCollection()][uint64[]]$KnownTextPointers,
        [Parameter(Mandatory = $true)]$TransitionStats,
        [Parameter(Mandatory = $true)][int]$HiddenCount,
        [Parameter(Mandatory = $true)][int]$HoverCount
    )

    $hiddenDistinct = Get-DistinctCount -Values $HiddenValues
    $hoverDistinct = Get-DistinctCount -Values $HoverValues
    $allDistinct = Get-DistinctCount -Values $AllValues
    $hiddenStable = $HiddenCount -gt 0 -and $hiddenDistinct -le 1
    $hoverStable = $HoverCount -gt 0 -and $hoverDistinct -le 1
    $hiddenMode = Get-ModeValue -Values $HiddenValues -View $View
    $hoverMode = Get-ModeValue -Values $HoverValues -View $View
    $hiddenModeText = Get-ComparableValue -Value $hiddenMode -View $View
    $hoverModeText = Get-ComparableValue -Value $hoverMode -View $View
    $modeDiffers = $hiddenModeText -ne $hoverModeText
    $score = 0
    $classification = 'noise-or-static'
    $subtype = 'static-or-inconclusive'
    $evidence = [System.Collections.Generic.List[string]]::new()
    $rejectionReasons = [System.Collections.Generic.List[string]]::new()

    if ($hiddenStable) { $score += 10; $evidence.Add('hidden value is stable') }
    if ($hoverStable) { $score += 10; $evidence.Add('hover value is stable') }
    if ($modeDiffers) { $score += 20; $evidence.Add("hidden mode $hiddenModeText differs from hover mode $hoverModeText") }
    if ($TransitionStats.Pairs -gt 0) {
        $transitionRatio = $TransitionStats.Changed / [double]$TransitionStats.Pairs
        if ($transitionRatio -ge 0.75) { $score += 20; $evidence.Add("changed across $($TransitionStats.Changed)/$($TransitionStats.Pairs) hidden/hover transitions") }
        elseif ($TransitionStats.Changed -eq 1 -and $TransitionStats.Pairs -gt 1) { $score -= 20; $rejectionReasons.Add('one-cycle change only') }
    }

    if ($allDistinct -gt [math]::Max(3, [math]::Ceiling(($HiddenCount + $HoverCount) * 0.6))) {
        $score -= 25
        $rejectionReasons.Add('broad numeric noise')
    }

    if ($View -eq 'pointer') {
        $hoverPointer = if ($null -eq $hoverMode) { [uint64]0 } else { [uint64]$hoverMode }
        $hiddenPointer = if ($null -eq $hiddenMode) { [uint64]0 } else { [uint64]$hiddenMode }
        $knownSet = [System.Collections.Generic.HashSet[uint64]]::new()
        foreach ($pointer in $KnownTextPointers) { [void]$knownSet.Add($pointer) }

        if ($knownSet.Contains($hoverPointer)) {
            $classification = 'text-pointer-field'
            $subtype = 'known-hover-text-pointer'
            $score += 65
            $evidence.Add("hover pointer matches known tooltip text pointer $(Format-HexAddress -Value $hoverPointer)")
        }
        elseif ((Test-PointerLike -Value $hoverPointer) -and $modeDiffers -and ($hoverStable -or $TransitionStats.Changed -gt 1)) {
            $classification = 'owner-pointer-candidate'
            $subtype = if ($hiddenPointer -eq 0) { 'hover-appears-pointer' } else { 'pointer-swaps-with-hover-state' }
            $score += 35
            $evidence.Add("hover mode is pointer-like $(Format-HexAddress -Value $hoverPointer)")
        }
        elseif (-not (Test-PointerLike -Value $hoverPointer) -and $hoverPointer -ne 0) {
            $score -= 20
            $rejectionReasons.Add('pointer view is not pointer-like')
        }
    }
    elseif ($View -eq 'byte' -or $View -eq 'uint16' -or $View -eq 'int32') {
        $hiddenNumber = if ($null -eq $hiddenMode) { 0 } else { [int64]$hiddenMode }
        $hoverNumber = if ($null -eq $hoverMode) { 0 } else { [int64]$hoverMode }
        $isSmallFlag = $modeDiffers -and ([math]::Abs($hiddenNumber) -le 8) -and ([math]::Abs($hoverNumber) -le 8) -and (($hiddenNumber -eq 0) -or ($hoverNumber -eq 0))
        if ($isSmallFlag) {
            $classification = 'visibility-flag-candidate'
            $subtype = 'small-state-toggle'
            $score += 45
            $evidence.Add("small flag-like toggle $hiddenNumber -> $hoverNumber")
        }
        elseif ($modeDiffers -and (Test-ScreenishNumber -Value $hiddenNumber) -and (Test-ScreenishNumber -Value $hoverNumber) -and ($View -eq 'int32')) {
            $classification = 'ui-rect-candidate'
            $subtype = 'screen-ish-int32'
            $score += 25
            $evidence.Add('int32 modes are in a plausible UI screen-coordinate range')
        }
    }
    elseif ($View -eq 'float32') {
        if ($modeDiffers -and (Test-ScreenishNumber -Value $hiddenMode) -and (Test-ScreenishNumber -Value $hoverMode)) {
            $classification = 'projection-anchor-candidate'
            $subtype = 'screen-or-projection-float32'
            $score += 30
            $evidence.Add('float32 modes are finite and in a plausible screen/projection range')
        }
    }

    if ($classification -eq 'noise-or-static' -and $score -ge 50 -and $modeDiffers) {
        $classification = 'strong-tooltip-lifecycle-field'
        $subtype = 'stable-hidden-hover-difference'
    }
    elseif ($classification -ne 'noise-or-static' -and $score -ge 85 -and $classification -ne 'text-pointer-field') {
        $subtype = "strong-$subtype"
    }

    foreach ($knownPointer in $KnownTextPointers) {
        if ($View -eq 'uint16' -and $null -ne $hoverMode -and ([uint64][uint16]$hoverMode) -eq ($knownPointer -band 0xffff)) {
            $score -= 35
            $rejectionReasons.Add('pointer low-half false positive risk')
            break
        }
        if ($View -eq 'int32' -and $null -ne $hoverMode -and ([uint64][BitConverter]::ToUInt32([BitConverter]::GetBytes([int32]$hoverMode), 0)) -eq ($knownPointer -band 0xffffffff)) {
            $score -= 35
            $rejectionReasons.Add('pointer low-half false positive risk')
            break
        }
    }

    if ($TransitionStats.Pairs -gt 1 -and $TransitionStats.Changed -le 1 -and $modeDiffers) {
        $score -= 20
        if (-not $rejectionReasons.Contains('one-cycle change only')) { $rejectionReasons.Add('one-cycle change only') }
    }

    if ($score -lt 45) {
        $classification = 'noise-or-static'
    }

    $promotionStatus = if ($classification -eq 'noise-or-static') { 'rejected' } elseif ($score -ge 90) { 'strong-offline-candidate' } elseif ($score -ge 65) { 'candidate-needs-live-reproof' } else { 'weak-candidate' }

    return [pscustomobject]@{
        Classification = $classification
        Subtype = $subtype
        Score = [math]::Round([double]$score, 2)
        Evidence = @($evidence)
        RejectionReasons = @($rejectionReasons)
        HiddenMode = $hiddenModeText
        HoverMode = $hoverModeText
        HiddenDistinct = $hiddenDistinct
        HoverDistinct = $hoverDistinct
        AllDistinct = $allDistinct
        PromotionStatus = $promotionStatus
    }
}

$resolvedInputDirectory = [System.IO.Path]::GetFullPath($InputDirectory)
if (-not (Test-Path -LiteralPath $resolvedInputDirectory -PathType Container)) {
    throw "InputDirectory does not exist: $resolvedInputDirectory"
}

$samplesPath = Join-Path $resolvedInputDirectory 'samples.ndjson'
if (-not (Test-Path -LiteralPath $samplesPath -PathType Leaf)) {
    throw "Expected samples.ndjson in input directory: $samplesPath"
}

$rawRows = [System.Collections.Generic.List[object]]::new()
$lineNumber = 0
foreach ($line in [System.IO.File]::ReadLines($samplesPath)) {
    $lineNumber++
    if ([string]::IsNullOrWhiteSpace($line)) { continue }
    try {
        $rawRows.Add(($line | ConvertFrom-Json -Depth 32))
    }
    catch {
        throw "Failed to parse samples.ndjson line $lineNumber as JSON: $($_.Exception.Message)"
    }
}

$samples = [System.Collections.Generic.List[object]]::new()
$normalizationWarnings = [System.Collections.Generic.List[string]]::new()
foreach ($row in $rawRows) {
    try {
        $sample = Normalize-SampleRow -Row $row -CandidateAddressOverride $CandidateAddress -BaselineStateRegex $BaselineStateRegex -ActiveStateRegex $ActiveStateRegex
        if ($null -ne $sample) { $samples.Add($sample) }
    }
    catch {
        $normalizationWarnings.Add("Skipped sample row: $($_.Exception.Message)")
    }
}

if ($samples.Count -eq 0) {
    throw 'No usable hidden/hover samples with bytesHex were found in samples.ndjson.'
}

$hiddenSamples = @($samples | Where-Object { $_.State -eq 'hidden' })
$hoverSamples = @($samples | Where-Object { $_.State -eq 'hover' })
if ($hiddenSamples.Count -eq 0 -or $hoverSamples.Count -eq 0) {
    throw "Need at least one baseline sample and one active sample. Found baseline=$($hiddenSamples.Count), active=$($hoverSamples.Count). BaselineStateRegex='$BaselineStateRegex', ActiveStateRegex='$ActiveStateRegex'."
}

$windowStartCandidates = @($samples | ForEach-Object { $_.WindowStart } | Where-Object { $null -ne $_ } | Select-Object -Unique)
$windowStart = if ($windowStartCandidates.Count -gt 0) { [uint64]$windowStartCandidates[0] } else { [uint64]0 }
$baseCandidateCandidates = @($samples | ForEach-Object { $_.CandidateAddress } | Where-Object { $null -ne $_ } | Select-Object -Unique)
$baseCandidate = if ($baseCandidateCandidates.Count -gt 0) { [uint64]$baseCandidateCandidates[0] } else { $windowStart }
$windowLength = ($samples | ForEach-Object { $_.Bytes.Length } | Measure-Object -Minimum).Minimum
if ($windowLength -le 0) { throw 'Usable samples had zero-length byte windows.' }

$knownTextPointers = [System.Collections.Generic.HashSet[uint64]]::new()
foreach ($sample in $samples) {
    foreach ($pointer in @($sample.KnownTextPointers)) {
        [void]$knownTextPointers.Add([uint64]$pointer)
    }
}
$knownTextPointerArray = @($knownTextPointers)

$candidates = [System.Collections.Generic.List[object]]::new()
$rejections = [System.Collections.Generic.List[object]]::new()
$views = @('byte', 'uint16', 'int32', 'float32', 'pointer')

for ($offset = 0; $offset -lt $windowLength; $offset++) {
    foreach ($view in $views) {
        if (($view -eq 'uint16' -and ($offset + 2) -gt $windowLength) -or
            (($view -eq 'int32' -or $view -eq 'float32') -and ($offset + 4) -gt $windowLength) -or
            ($view -eq 'pointer' -and ($offset + 8) -gt $windowLength)) {
            continue
        }

        if ($view -eq 'pointer' -and ($offset % 8) -ne 0) { continue }
        if (($view -eq 'uint16') -and ($offset % 2) -ne 0) { continue }
        if (($view -eq 'int32' -or $view -eq 'float32') -and ($offset % 4) -ne 0) { continue }

        $hiddenValues = @($hiddenSamples | ForEach-Object { Read-ViewValue -Bytes $_.Bytes -Offset $offset -View $view })
        $hoverValues = @($hoverSamples | ForEach-Object { Read-ViewValue -Bytes $_.Bytes -Offset $offset -View $view })
        $allValues = @($samples | ForEach-Object { Read-ViewValue -Bytes $_.Bytes -Offset $offset -View $view })
        $transitionStats = Get-TransitionPairCount -Samples @($samples) -Offset $offset -View $view
        $classification = Get-ClassificationForView `
            -View $view `
            -Offset $offset `
            -HiddenValues $hiddenValues `
            -HoverValues $hoverValues `
            -AllValues $allValues `
            -KnownTextPointers $knownTextPointerArray `
            -TransitionStats $transitionStats `
            -HiddenCount $hiddenSamples.Count `
            -HoverCount $hoverSamples.Count

        $address = $windowStart + [uint64]$offset
        $record = [ordered]@{
            offset = ('+0x{0:X}' -f $offset)
            offsetDecimal = $offset
            address = if ($windowStart -ne 0) { Format-HexAddress -Value $address } else { $null }
            type = $view
            subtype = $classification.Subtype
            score = $classification.Score
            classification = $classification.Classification
            evidence = @($classification.Evidence)
            promotionStatus = $classification.PromotionStatus
            hiddenMode = $classification.HiddenMode
            hoverMode = $classification.HoverMode
            hiddenDistinct = $classification.HiddenDistinct
            hoverDistinct = $classification.HoverDistinct
            allDistinct = $classification.AllDistinct
            transitionPairs = $transitionStats.Pairs
            transitionChanges = $transitionStats.Changed
        }

        if ($classification.Classification -eq 'noise-or-static') {
            if (@($classification.RejectionReasons).Count -gt 0 -or $classification.Score -gt 20) {
                $record['reasons'] = @($classification.RejectionReasons)
                $rejections.Add([pscustomobject]$record)
            }
        }
        else {
            if (@($classification.RejectionReasons).Count -gt 0) { $record['downrankReasons'] = @($classification.RejectionReasons) }
            $candidates.Add([pscustomobject]$record)
        }
    }
}

$sortedCandidates = @($candidates | Sort-Object -Property @{ Expression = 'score'; Descending = $true }, @{ Expression = 'offsetDecimal'; Descending = $false }, @{ Expression = 'type'; Descending = $false })
$sortedRejections = @($rejections | Sort-Object -Property @{ Expression = 'score'; Descending = $true }, @{ Expression = 'offsetDecimal'; Descending = $false } | Select-Object -First 200)
$stableHoverFields = @($sortedCandidates | Where-Object { $_.hoverDistinct -le 1 -and $_.classification -ne 'noise-or-static' })
$scanEvidence = @(Get-ScanEvidenceSummary -Samples @($samples) -HiddenCount $hiddenSamples.Count -HoverCount $hoverSamples.Count)
$screenshotGate = Get-ScreenshotGateSummary -Samples @($samples)

$diffDirectory = Join-Path $resolvedInputDirectory 'diffs'
New-Item -ItemType Directory -Path $diffDirectory -Force | Out-Null

$common = [ordered]@{
    generatedAtUtc = [DateTimeOffset]::UtcNow.ToString('O')
    analyzer = 'scripts/analyze-tooltip-hover-diff.ps1'
    inputDirectory = $resolvedInputDirectory
    samplesPath = $samplesPath
    sampleCount = $samples.Count
    hiddenSampleCount = $hiddenSamples.Count
    hoverSampleCount = $hoverSamples.Count
    baselineLabel = $BaselineLabel
    activeLabel = $ActiveLabel
    baselineStateRegex = $BaselineStateRegex
    activeStateRegex = $ActiveStateRegex
    requireVisualGate = [bool]$RequireVisualGate
    baseCandidate = if ($baseCandidate -ne 0) { Format-HexAddress -Value $baseCandidate } else { $null }
    windowStart = if ($windowStart -ne 0) { Format-HexAddress -Value $windowStart } else { $null }
    windowLength = [int]$windowLength
    knownTextPointers = @($knownTextPointerArray | ForEach-Object { Format-HexAddress -Value $_ })
    hasTargetStates = @($samples | ForEach-Object { $_.HasTarget } | Where-Object { $null -ne $_ } | Select-Object -Unique)
    scanEvidenceCount = $scanEvidence.Count
    screenshotGateStatus = $screenshotGate.visualGateStatus
    warnings = @($normalizationWarnings)
}

$hiddenVsHover = [ordered]@{} + $common
$hiddenVsHover['candidates'] = @($sortedCandidates | Select-Object -First 100)
$hiddenVsHover['rejections'] = @($sortedRejections)

$stableHover = [ordered]@{} + $common
$stableHover['candidates'] = @($stableHoverFields | Select-Object -First 100)
$stableHover['rejections'] = @($sortedRejections | Where-Object { $_.reasons -contains 'one-cycle change only' -or $_.reasons -contains 'broad numeric noise' } | Select-Object -First 100)

$fieldCandidates = [ordered]@{} + $common
$fieldCandidates['candidates'] = @($sortedCandidates | Select-Object -First 50)
$fieldCandidates['rejections'] = @($sortedRejections | Select-Object -First 100)
$fieldCandidates['classificationCounts'] = @($sortedCandidates | Group-Object -Property classification | ForEach-Object { [pscustomobject]@{ classification = $_.Name; count = $_.Count } })

$scanEvidenceDocument = [ordered]@{} + $common
$scanEvidenceDocument['scanEvidence'] = @($scanEvidence)
$scanEvidenceDocument['classificationCounts'] = @($scanEvidence | Group-Object -Property classification | ForEach-Object { [pscustomobject]@{ classification = $_.Name; count = $_.Count } })

$screenshotGateDocument = [ordered]@{} + $common
$screenshotGateDocument['screenshotGate'] = $screenshotGate

$hiddenVsHoverPath = Join-Path $diffDirectory 'hidden_vs_hover.json'
$stableHoverPath = Join-Path $diffDirectory 'stable-hover-fields.json'
$fieldCandidatesPath = Join-Path $diffDirectory 'field-candidates.json'
$scanEvidencePath = Join-Path $diffDirectory 'scan-evidence.json'
$screenshotGatePath = Join-Path $diffDirectory 'screenshot-gate.json'
$summaryPath = Join-Path $resolvedInputDirectory 'summary.json'

$hiddenVsHover | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $hiddenVsHoverPath -Encoding UTF8
$stableHover | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $stableHoverPath -Encoding UTF8
$fieldCandidates | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $fieldCandidatesPath -Encoding UTF8
$scanEvidenceDocument | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $scanEvidencePath -Encoding UTF8
$screenshotGateDocument | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $screenshotGatePath -Encoding UTF8

$summary = [ordered]@{}
if (Test-Path -LiteralPath $summaryPath -PathType Leaf) {
    try {
        $existingSummary = Get-Content -LiteralPath $summaryPath -Raw | ConvertFrom-Json -Depth 32
        foreach ($property in $existingSummary.PSObject.Properties) {
            $summary[$property.Name] = $property.Value
        }
    }
    catch {
        $summary['previousSummaryParseError'] = $_.Exception.Message
    }
}

$summary['tooltipHoverDiffAnalysis'] = [ordered]@{
    generatedAtUtc = $common.generatedAtUtc
    analyzer = $common.analyzer
    sampleCount = $samples.Count
    hiddenSampleCount = $hiddenSamples.Count
    hoverSampleCount = $hoverSamples.Count
    baselineLabel = $BaselineLabel
    activeLabel = $ActiveLabel
    baselineStateRegex = $BaselineStateRegex
    activeStateRegex = $ActiveStateRegex
    requireVisualGate = [bool]$RequireVisualGate
    baseCandidate = $common.baseCandidate
    windowStart = $common.windowStart
    windowLength = $common.windowLength
    outputFiles = [ordered]@{
        hiddenVsHover = $hiddenVsHoverPath
        stableHoverFields = $stableHoverPath
        fieldCandidates = $fieldCandidatesPath
        scanEvidence = $scanEvidencePath
        screenshotGate = $screenshotGatePath
    }
    screenshotGate = $screenshotGate
    topCandidates = @($sortedCandidates | Select-Object -First 10)
    topScanEvidence = @($scanEvidence | Select-Object -First 10)
    rejectionCount = $sortedRejections.Count
    warnings = @($normalizationWarnings)
}

$summary | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $summaryPath -Encoding UTF8

$result = [ordered]@{
    inputDirectory = $resolvedInputDirectory
    outputFiles = [ordered]@{
        hiddenVsHover = $hiddenVsHoverPath
        stableHoverFields = $stableHoverPath
        fieldCandidates = $fieldCandidatesPath
        scanEvidence = $scanEvidencePath
        screenshotGate = $screenshotGatePath
        summary = $summaryPath
    }
    sampleCount = $samples.Count
    hiddenSampleCount = $hiddenSamples.Count
    hoverSampleCount = $hoverSamples.Count
    baselineLabel = $BaselineLabel
    activeLabel = $ActiveLabel
    candidateCount = $sortedCandidates.Count
    topCandidates = @($sortedCandidates | Select-Object -First 10)
    scanEvidenceCount = $scanEvidence.Count
    topScanEvidence = @($scanEvidence | Select-Object -First 10)
    screenshotGate = $screenshotGate
    warnings = @($normalizationWarnings)
}

if ($RequireVisualGate -and $screenshotGate.visualGateStatus -ne 'passed') {
    throw "Visual gate requirement failed: screenshotGate.visualGateStatus=$($screenshotGate.visualGateStatus). Wrote $screenshotGatePath"
}

if ($Json) {
    $result | ConvertTo-Json -Depth 12
}
else {
    Write-Host "Analyzed tooltip hover diff samples: hidden=$($hiddenSamples.Count), hover=$($hoverSamples.Count), candidates=$($sortedCandidates.Count)"
    Write-Host "Wrote $hiddenVsHoverPath"
    Write-Host "Wrote $stableHoverPath"
    Write-Host "Wrote $fieldCandidatesPath"
    Write-Host "Wrote $scanEvidencePath"
    Write-Host "Wrote $screenshotGatePath"
    Write-Host "Updated $summaryPath"
    if ($sortedCandidates.Count -gt 0) {
        $sortedCandidates | Select-Object -First 10 offset, address, type, subtype, score, classification, promotionStatus | Format-Table -AutoSize
    }
}
