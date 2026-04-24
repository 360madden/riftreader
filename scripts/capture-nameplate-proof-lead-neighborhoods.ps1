[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$RunRoot,

    [string[]]$LeadAddresses = @(),

    [ValidateSet('pointer-hit', 'text-address', 'both')]
    [string]$LeadKind = 'pointer-hit',

    [int]$MinStateCount = 2,
    [int]$MaxLeads = 3,
    [int]$ReadLength = 256,
    [int]$FollowPointerDepth = 1,
    [int]$MaxPointersPerNode = 6,
    [int]$MaxNodes = 24,
    [string]$ProcessName = 'rift_x64',
    [string]$OutputFile,
    [switch]$AllowUngated,
    [switch]$PlanOnly,
    [switch]$Json
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$repoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$readerProject = Join-Path $repoRoot 'reader\RiftReader.Reader\RiftReader.Reader.csproj'
$leadExtractorScript = Join-Path $PSScriptRoot 'extract-nameplate-proof-leads.ps1'

function Normalize-Address {
    param([object]$Value)

    if ($null -eq $Value) {
        return $null
    }

    $text = ([string]$Value).Trim()
    if ([string]::IsNullOrWhiteSpace($text)) {
        return $null
    }

    if ($text.StartsWith('0x', [System.StringComparison]::OrdinalIgnoreCase)) {
        $text = $text.Substring(2)
    }

    if ($text -notmatch '^[0-9A-Fa-f]+$') {
        throw "Address is not hex: $Value"
    }

    return ('0X{0}' -f $text.ToUpperInvariant())
}

function Parse-HexUInt64 {
    param([Parameter(Mandatory = $true)][string]$Value)

    $normalized = (Normalize-Address -Value $Value).Substring(2)
    return [UInt64]::Parse($normalized, [System.Globalization.NumberStyles]::HexNumber, [System.Globalization.CultureInfo]::InvariantCulture)
}

function Format-HexUInt64 {
    param([Parameter(Mandatory = $true)][UInt64]$Value)
    return ('0X{0:X}' -f $Value)
}

function Invoke-ReaderJson {
    param([Parameter(Mandatory = $true)][string[]]$Arguments)

    $output = & dotnet run --project $readerProject -- @Arguments 2>&1
    $exitCode = $LASTEXITCODE
    if ($exitCode -ne 0) {
        throw "Reader command failed (`$LASTEXITCODE=$exitCode): $($output -join [Environment]::NewLine)"
    }

    return ($output -join [Environment]::NewLine) | ConvertFrom-Json -Depth 40
}

function Convert-HexToBytes {
    param([string]$Hex)

    $normalized = ([string]$Hex -replace '\s+', '').Trim()
    if ([string]::IsNullOrWhiteSpace($normalized)) {
        return [byte[]]@()
    }

    if (($normalized.Length % 2) -ne 0) {
        throw "Hex byte string has odd length."
    }

    $buffer = New-Object byte[] ($normalized.Length / 2)
    for ($index = 0; $index -lt $buffer.Length; $index++) {
        $buffer[$index] = [Convert]::ToByte($normalized.Substring($index * 2, 2), 16)
    }

    return $buffer
}

function Convert-BytesToHex {
    param([Parameter(Mandatory = $true)][byte[]]$Bytes)

    $builder = [System.Text.StringBuilder]::new($Bytes.Length * 2)
    foreach ($byte in $Bytes) {
        [void]$builder.AppendFormat('{0:X2}', $byte)
    }

    return $builder.ToString()
}

function Read-Bytes {
    param(
        [Parameter(Mandatory = $true)][UInt64]$Address,
        [Parameter(Mandatory = $true)][int]$Length
    )

    $result = Invoke-ReaderJson -Arguments @(
        '--process-name', $ProcessName,
        '--address', (Format-HexUInt64 -Value $Address),
        '--length', $Length.ToString([System.Globalization.CultureInfo]::InvariantCulture),
        '--json')

    return Convert-HexToBytes -Hex ([string]$result.BytesHex)
}

function Read-UInt64At {
    param(
        [Parameter(Mandatory = $true)][byte[]]$Bytes,
        [Parameter(Mandatory = $true)][int]$Offset
    )

    if (($Offset + 8) -gt $Bytes.Length) {
        return $null
    }

    return [BitConverter]::ToUInt64($Bytes, $Offset)
}

function Get-AsciiPreview {
    param(
        [Parameter(Mandatory = $true)][byte[]]$Bytes,
        [int]$MaxLength = 96
    )

    $length = [Math]::Min($Bytes.Length, [Math]::Max($MaxLength, 0))
    $builder = [System.Text.StringBuilder]::new()
    for ($index = 0; $index -lt $length; $index++) {
        $value = $Bytes[$index]
        if ($value -ge 32 -and $value -le 126) {
            [void]$builder.Append([char]$value)
        }
        elseif ($value -eq 0) {
            [void]$builder.Append('.')
        }
        else {
            [void]$builder.Append('?')
        }
    }

    return $builder.ToString()
}

function Test-PlausibleHeapPointer {
    param([Parameter(Mandatory = $true)][UInt64]$Value)

    $minAddress = Parse-HexUInt64 -Value '0x0000000100000000'
    $maxAddress = Parse-HexUInt64 -Value '0x00007FF000000000'
    return ($Value -ge $minAddress) -and ($Value -lt $maxAddress)
}

function Get-LeadLabels {
    param(
        [Parameter(Mandatory = $true)][hashtable]$KnownLeads,
        [Parameter(Mandatory = $true)][string]$Address
    )

    $normalized = (Normalize-Address -Value $Address)
    if ($KnownLeads.ContainsKey($normalized)) {
        return @($KnownLeads[$normalized])
    }

    return @()
}

function Get-QwordPreview {
    param(
        [Parameter(Mandatory = $true)][byte[]]$Bytes,
        [Parameter(Mandatory = $true)][hashtable]$KnownLeads,
        [int]$MaxCount = 24
    )

    $items = [System.Collections.Generic.List[object]]::new()
    for ($offset = 0; $offset -le ($Bytes.Length - 8); $offset += 8) {
        $value = Read-UInt64At -Bytes $Bytes -Offset $offset
        if ($null -eq $value -or $value -eq 0) {
            continue
        }

        $valueHex = Format-HexUInt64 -Value $value
        $items.Add([pscustomobject][ordered]@{
            offset = $offset
            offsetHex = ('0x{0:X}' -f $offset)
            value = $valueHex
            isPlausiblePointer = (Test-PlausibleHeapPointer -Value $value)
            leadLabels = @(Get-LeadLabels -KnownLeads $KnownLeads -Address $valueHex)
        }) | Out-Null

        if ($items.Count -ge $MaxCount) {
            break
        }
    }

    return @($items.ToArray())
}

function Get-CandidatePointers {
    param(
        [Parameter(Mandatory = $true)][byte[]]$Bytes,
        [Parameter(Mandatory = $true)][hashtable]$KnownLeads,
        [int]$MaxPointers = 6
    )

    $items = [System.Collections.Generic.List[object]]::new()
    $seen = [System.Collections.Generic.HashSet[string]]::new()
    for ($offset = 0; $offset -le ($Bytes.Length - 8); $offset += 8) {
        if ($items.Count -ge $MaxPointers) {
            break
        }

        $value = Read-UInt64At -Bytes $Bytes -Offset $offset
        if ($null -eq $value -or -not (Test-PlausibleHeapPointer -Value $value)) {
            continue
        }

        $valueHex = Format-HexUInt64 -Value $value
        $normalized = (Normalize-Address -Value $valueHex)
        if (-not $seen.Add($normalized)) {
            continue
        }

        $items.Add([pscustomobject][ordered]@{
            sourceOffset = $offset
            sourceOffsetHex = ('0x{0:X}' -f $offset)
            address = $normalized
            leadLabels = @(Get-LeadLabels -KnownLeads $KnownLeads -Address $normalized)
        }) | Out-Null
    }

    return @($items.ToArray())
}

function Get-NodeSummary {
    param(
        [Parameter(Mandatory = $true)][string]$Address,
        [Parameter(Mandatory = $true)][byte[]]$Bytes,
        [Parameter(Mandatory = $true)][hashtable]$KnownLeads,
        [Parameter(Mandatory = $true)][string[]]$RootLabels,
        [Parameter(Mandatory = $true)][int]$Depth
    )

    return [pscustomobject][ordered]@{
        address = (Normalize-Address -Value $Address)
        depth = $Depth
        rootLabels = @($RootLabels | Sort-Object -Unique)
        leadLabels = @(Get-LeadLabels -KnownLeads $KnownLeads -Address $Address)
        length = $Bytes.Length
        bytesHex = (Convert-BytesToHex -Bytes $Bytes)
        asciiPreview = (Get-AsciiPreview -Bytes $Bytes)
        qwordPreview = @(Get-QwordPreview -Bytes $Bytes -KnownLeads $KnownLeads)
        pointerCandidates = @(Get-CandidatePointers -Bytes $Bytes -KnownLeads $KnownLeads -MaxPointers $MaxPointersPerNode)
    }
}

function Build-PointerSubgraph {
    param(
        [Parameter(Mandatory = $true)][object[]]$Roots,
        [Parameter(Mandatory = $true)][hashtable]$KnownLeads
    )

    $queue = [System.Collections.Generic.Queue[object]]::new()
    $nodesByAddress = @{}
    $edgesByKey = @{}
    $seenRead = [System.Collections.Generic.HashSet[string]]::new()

    foreach ($root in @($Roots)) {
        $queue.Enqueue([pscustomobject][ordered]@{
            address = [string]$root.address
            depth = 0
            rootLabel = [string]$root.label
        })
    }

    while ($queue.Count -gt 0 -and $nodesByAddress.Count -lt $MaxNodes) {
        $item = $queue.Dequeue()
        $address = Normalize-Address -Value $item.address
        if (-not $seenRead.Add($address)) {
            if ($nodesByAddress.ContainsKey($address)) {
                $existingRoots = @($nodesByAddress[$address].rootLabels)
                if ($existingRoots -notcontains [string]$item.rootLabel) {
                    $nodesByAddress[$address].rootLabels = @($existingRoots + [string]$item.rootLabel | Sort-Object -Unique)
                }
            }
            continue
        }

        $bytes = $null
        try {
            $bytes = Read-Bytes -Address (Parse-HexUInt64 -Value $address) -Length $ReadLength
            $nodesByAddress[$address] = Get-NodeSummary -Address $address -Bytes $bytes -KnownLeads $KnownLeads -RootLabels @([string]$item.rootLabel) -Depth ([int]$item.depth)
        }
        catch {
            $nodesByAddress[$address] = [pscustomobject][ordered]@{
                address = $address
                depth = [int]$item.depth
                rootLabels = @([string]$item.rootLabel)
                leadLabels = @(Get-LeadLabels -KnownLeads $KnownLeads -Address $address)
                error = $_.Exception.Message
            }
            continue
        }

        if ([int]$item.depth -ge $FollowPointerDepth) {
            continue
        }

        foreach ($candidate in @(Get-CandidatePointers -Bytes $bytes -KnownLeads $KnownLeads -MaxPointers $MaxPointersPerNode)) {
            $childAddress = Normalize-Address -Value $candidate.address
            $edgeKey = '{0}|{1}|{2}' -f $address, $childAddress, [string]$candidate.sourceOffsetHex
            if (-not $edgesByKey.ContainsKey($edgeKey)) {
                $edgesByKey[$edgeKey] = [pscustomobject][ordered]@{
                    fromAddress = $address
                    toAddress = $childAddress
                    sourceOffset = [int]$candidate.sourceOffset
                    sourceOffsetHex = [string]$candidate.sourceOffsetHex
                    depth = ([int]$item.depth + 1)
                    rootLabel = [string]$item.rootLabel
                    leadLabels = @($candidate.leadLabels)
                }
            }

            if (($queue.Count + $nodesByAddress.Count) -ge $MaxNodes) {
                continue
            }

            $queue.Enqueue([pscustomobject][ordered]@{
                address = $childAddress
                depth = ([int]$item.depth + 1)
                rootLabel = [string]$item.rootLabel
            })
        }
    }

    return [pscustomobject][ordered]@{
        maxDepth = $FollowPointerDepth
        maxNodes = $MaxNodes
        readLength = $ReadLength
        maxPointersPerNode = $MaxPointersPerNode
        nodeCount = $nodesByAddress.Count
        edgeCount = $edgesByKey.Count
        nodes = @($nodesByAddress.Values | Sort-Object depth, address)
        edges = @($edgesByKey.Values | Sort-Object depth, fromAddress, sourceOffset)
    }
}

function Convert-LeadForOutput {
    param(
        [Parameter(Mandatory = $true)][object]$Lead,
        [string]$SelectionReason = 'extracted'
    )

    return [pscustomobject][ordered]@{
        kind = [string]$Lead.kind
        address = (Normalize-Address -Value $Lead.address)
        score = if ($null -ne $Lead.score) { [int]$Lead.score } else { $null }
        stateCount = if ($null -ne $Lead.stateCount) { [int]$Lead.stateCount } else { $null }
        states = @($Lead.states)
        stateRoles = @($Lead.stateRoles)
        baselineStates = @($Lead.baselineStates)
        activeStates = @($Lead.activeStates)
        sourceTextAddresses = @($Lead.sourceTextAddresses)
        pointerHitAddresses = @($Lead.pointerHitAddresses)
        pointerScanFiles = @($Lead.pointerScanFiles)
        selectionReason = $SelectionReason
    }
}

if ($MinStateCount -le 0) { throw 'MinStateCount must be greater than zero.' }
if ($MaxLeads -le 0) { throw 'MaxLeads must be greater than zero.' }
if ($ReadLength -le 0) { throw 'ReadLength must be greater than zero.' }
if ($FollowPointerDepth -lt 0) { throw 'FollowPointerDepth cannot be negative.' }
if ($MaxPointersPerNode -le 0) { throw 'MaxPointersPerNode must be greater than zero.' }
if ($MaxNodes -le 0) { throw 'MaxNodes must be greater than zero.' }

$resolvedRunRoot = (Resolve-Path -LiteralPath $RunRoot).Path
if ([string]::IsNullOrWhiteSpace($OutputFile)) {
    $OutputFile = Join-Path $resolvedRunRoot 'lead-neighborhoods\nameplate-proof-lead-neighborhoods.json'
}
$resolvedOutputFile = [System.IO.Path]::GetFullPath($OutputFile)

$extractArgs = @(
    '-NoProfile',
    '-ExecutionPolicy', 'Bypass',
    '-File', $leadExtractorScript,
    '-RunRoot', $resolvedRunRoot,
    '-MinStateCount', $MinStateCount.ToString([System.Globalization.CultureInfo]::InvariantCulture),
    '-Json'
)
if ($AllowUngated) {
    $extractArgs += '-AllowUngated'
}

$leadOutput = & pwsh @extractArgs 2>&1
$leadExitCode = $LASTEXITCODE
if ($leadExitCode -ne 0) {
    throw "Nameplate proof lead extraction failed (`$LASTEXITCODE=$leadExitCode): $($leadOutput -join [Environment]::NewLine)"
}
$leadResult = ($leadOutput -join [Environment]::NewLine) | ConvertFrom-Json -Depth 80

$allExtractedLeads = @(@($leadResult.pointerHitLeads) + @($leadResult.textLeads))
$leadsByAddress = @{}
foreach ($lead in $allExtractedLeads) {
    $normalizedLeadAddress = Normalize-Address -Value $lead.address
    if (-not $leadsByAddress.ContainsKey($normalizedLeadAddress)) {
        $leadsByAddress[$normalizedLeadAddress] = $lead
    }
}

$selectedLeads = [System.Collections.Generic.List[object]]::new()
$normalizedManualAddresses = @($LeadAddresses | ForEach-Object { Normalize-Address -Value $_ } | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })
if ($normalizedManualAddresses.Count -gt 0) {
    foreach ($address in @($normalizedManualAddresses | Select-Object -Unique | Select-Object -First $MaxLeads)) {
        if ($leadsByAddress.ContainsKey($address)) {
            $selectedLeads.Add((Convert-LeadForOutput -Lead $leadsByAddress[$address] -SelectionReason 'manual-extracted')) | Out-Null
        }
        else {
            $selectedLeads.Add([pscustomobject][ordered]@{
                kind = 'manual'
                address = $address
                score = $null
                stateCount = $null
                states = @()
                stateRoles = @()
                baselineStates = @()
                activeStates = @()
                sourceTextAddresses = @()
                pointerHitAddresses = @()
                pointerScanFiles = @()
                selectionReason = 'manual'
            }) | Out-Null
        }
    }
}
else {
    $candidateLeads = switch ($LeadKind) {
        'pointer-hit' { @($leadResult.pointerHitLeads) }
        'text-address' { @($leadResult.textLeads) }
        'both' { @(@($leadResult.pointerHitLeads) + @($leadResult.textLeads)) | Sort-Object @{ Expression = { [int]$_.score }; Descending = $true }, @{ Expression = { [int]$_.stateCount }; Descending = $true }, address }
    }

    foreach ($lead in @($candidateLeads | Select-Object -First $MaxLeads)) {
        $selectedLeads.Add((Convert-LeadForOutput -Lead $lead)) | Out-Null
    }
}

$selectedLeadArray = @($selectedLeads.ToArray())
if ($selectedLeadArray.Count -eq 0) {
    throw "No nameplate proof leads matched LeadKind=$LeadKind, MinStateCount=$MinStateCount, MaxLeads=$MaxLeads. RunRoot=$resolvedRunRoot"
}

$knownLeads = @{}
foreach ($lead in $selectedLeadArray) {
    $address = Normalize-Address -Value $lead.address
    $labels = [System.Collections.Generic.List[string]]::new()
    $labels.Add(('selected:{0}' -f [string]$lead.kind)) | Out-Null
    foreach ($state in @($lead.states)) {
        if (-not [string]::IsNullOrWhiteSpace([string]$state)) {
            $labels.Add(('state:{0}' -f [string]$state)) | Out-Null
        }
    }
    $knownLeads[$address] = @($labels.ToArray() | Select-Object -Unique)
}

$rootRecords = @($selectedLeadArray | ForEach-Object {
    [pscustomobject][ordered]@{
        label = ('{0}:{1}' -f [string]$_.kind, [string]$_.address)
        address = [string]$_.address
    }
})

$baseDocument = [pscustomobject][ordered]@{
    mode = if ($PlanOnly) { 'plan-only' } else { 'capture' }
    ok = $true
    controlsInput = $false
    attachesToProcess = -not [bool]$PlanOnly
    generatedAtUtc = [DateTimeOffset]::UtcNow.ToString('O', [System.Globalization.CultureInfo]::InvariantCulture)
    runRoot = $resolvedRunRoot
    outputFile = $resolvedOutputFile
    leadSelection = [pscustomobject][ordered]@{
        leadKind = $LeadKind
        minStateCount = $MinStateCount
        maxLeads = $MaxLeads
        manualLeadAddresses = @($normalizedManualAddresses)
        selectedLeadCount = $selectedLeadArray.Count
        selectedLeads = @($selectedLeadArray)
    }
    capturePlan = [pscustomobject][ordered]@{
        processName = $ProcessName
        readLength = $ReadLength
        followPointerDepth = $FollowPointerDepth
        maxPointersPerNode = $MaxPointersPerNode
        maxNodes = $MaxNodes
        rootCommands = @($rootRecords | ForEach-Object {
            [string[]]@(
                'dotnet', 'run', '--project', $readerProject, '--',
                '--process-name', $ProcessName,
                '--address', [string]$_.address,
                '--length', $ReadLength.ToString([System.Globalization.CultureInfo]::InvariantCulture),
                '--json'
            ) -join ' '
        })
    }
}

if ($PlanOnly) {
    if ($Json) {
        $baseDocument | ConvertTo-Json -Depth 80
    }
    else {
        $baseDocument
    }
    exit 0
}

$subgraph = Build-PointerSubgraph -Roots $rootRecords -KnownLeads $knownLeads
$document = $baseDocument
$document | Add-Member -NotePropertyName pointerSubgraph -NotePropertyValue $subgraph

$outputDirectory = Split-Path -Path $resolvedOutputFile -Parent
if (-not [string]::IsNullOrWhiteSpace($outputDirectory)) {
    New-Item -ItemType Directory -Path $outputDirectory -Force | Out-Null
}
$document | ConvertTo-Json -Depth 100 | Set-Content -LiteralPath $resolvedOutputFile -Encoding UTF8

$result = [pscustomobject][ordered]@{
    mode = 'capture'
    ok = $true
    controlsInput = $false
    outputFile = $resolvedOutputFile
    selectedLeadCount = $selectedLeadArray.Count
    pointerSubgraphNodeCount = [int]$subgraph.nodeCount
    pointerSubgraphEdgeCount = [int]$subgraph.edgeCount
}

if ($Json) {
    $result | ConvertTo-Json -Depth 16
}
else {
    $result
}
