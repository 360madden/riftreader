[CmdletBinding()]
param(
    [switch]$Json,
    [switch]$RefreshSelectorTrace,
    [int]$MaxEntries = 16,
    [string]$SelectorTraceFile = (Join-Path $PSScriptRoot 'captures\player-selector-owner-trace.json'),
    [string]$OutputFile = (Join-Path $PSScriptRoot 'captures\player-owner-components.json')
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$readerProject = Join-Path $repoRoot 'reader\RiftReader.Reader\RiftReader.Reader.csproj'
$selectorTraceScript = Join-Path $PSScriptRoot 'trace-player-selector-owner.ps1'
$resolvedSelectorTraceFile = [System.IO.Path]::GetFullPath($SelectorTraceFile)
$resolvedOutputFile = [System.IO.Path]::GetFullPath($OutputFile)

function Invoke-ReaderJson {
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$Arguments
    )

    $output = & dotnet run --project $readerProject -- @Arguments 2>&1
    $exitCode = $LASTEXITCODE
    if ($exitCode -ne 0) {
        throw "Reader command failed (`$LASTEXITCODE=$exitCode): $($output -join [Environment]::NewLine)"
    }

    return ($output -join [Environment]::NewLine) | ConvertFrom-Json -Depth 20
}

function Parse-HexUInt64 {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Value
    )

    $normalized = $Value.Trim()
    if ($normalized.StartsWith('0x', [System.StringComparison]::OrdinalIgnoreCase)) {
        $normalized = $normalized.Substring(2)
    }

    return [UInt64]::Parse($normalized, [System.Globalization.NumberStyles]::HexNumber, [System.Globalization.CultureInfo]::InvariantCulture)
}

function Read-Bytes {
    param(
        [Parameter(Mandatory = $true)]
        [UInt64]$Address,

        [Parameter(Mandatory = $true)]
        [int]$Length
    )

    $result = Invoke-ReaderJson -Arguments @(
        '--process-name', 'rift_x64',
        '--address', ('0x{0:X}' -f $Address),
        '--length', $Length.ToString([System.Globalization.CultureInfo]::InvariantCulture),
        '--json')

    $hex = ([string]$result.BytesHex -replace '\s+', '').Trim()
    $bytes = New-Object byte[] ($hex.Length / 2)
    for ($index = 0; $index -lt $bytes.Length; $index++) {
        $bytes[$index] = [Convert]::ToByte($hex.Substring($index * 2, 2), 16)
    }

    return $bytes
}

function Read-UInt64At {
    param(
        [Parameter(Mandatory = $true)]
        [byte[]]$Bytes,

        [Parameter(Mandatory = $true)]
        [int]$Offset
    )

    if (($Offset + 8) -gt $Bytes.Length) {
        return $null
    }

    return [BitConverter]::ToUInt64($Bytes, $Offset)
}

function Read-SingleAt {
    param(
        [Parameter(Mandatory = $true)]
        [byte[]]$Bytes,

        [Parameter(Mandatory = $true)]
        [int]$Offset
    )

    if (($Offset + 4) -gt $Bytes.Length) {
        return $null
    }

    return [BitConverter]::ToSingle($Bytes, $Offset)
}

function Test-TripletMatch {
    param(
        [double[]]$Expected,
        [double[]]$Actual,
        [double]$Tolerance
    )

    if ($Expected.Count -lt 3 -or $Actual.Count -lt 3) {
        return $false
    }

    for ($index = 0; $index -lt 3; $index++) {
        if ([math]::Abs($Expected[$index] - $Actual[$index]) -gt $Tolerance) {
            return $false
        }
    }

    return $true
}

if ($RefreshSelectorTrace -or -not (Test-Path -LiteralPath $resolvedSelectorTraceFile)) {
    & $selectorTraceScript -Json | Out-Null
}

if (-not (Test-Path -LiteralPath $resolvedSelectorTraceFile)) {
    throw "Selector trace file not found: $resolvedSelectorTraceFile"
}

$selectorTrace = Get-Content -LiteralPath $resolvedSelectorTraceFile -Raw | ConvertFrom-Json -Depth 30
$ownerAddress = Parse-HexUInt64 -Value ([string]$selectorTrace.Owner.ObjectAddress)
$containerAddress = Parse-HexUInt64 -Value ([string]$selectorTrace.Owner.ContainerAddress)
$selectedSourceAddress = Parse-HexUInt64 -Value ([string]$selectorTrace.SelectedSource.Address)
$stateRecordAddress = $ownerAddress + 0xC8

$expectedCoord48 = [double[]]@(
    [double]$selectorTrace.SelectedSource.Coord48.X,
    [double]$selectorTrace.SelectedSource.Coord48.Y,
    [double]$selectorTrace.SelectedSource.Coord48.Z)

$sourceBytes = Read-Bytes -Address $selectedSourceAddress -Length 0xA0
$expectedCoord88 = [double[]]@(
    [double](Read-SingleAt -Bytes $sourceBytes -Offset 0x88),
    [double](Read-SingleAt -Bytes $sourceBytes -Offset 0x8C),
    [double](Read-SingleAt -Bytes $sourceBytes -Offset 0x90))
$expectedOrientation60 = [double[]]@(
    [double](Read-SingleAt -Bytes $sourceBytes -Offset 0x60),
    [double](Read-SingleAt -Bytes $sourceBytes -Offset 0x64),
    [double](Read-SingleAt -Bytes $sourceBytes -Offset 0x68))
$expectedOrientation94 = [double[]]@(
    [double](Read-SingleAt -Bytes $sourceBytes -Offset 0x94),
    [double](Read-SingleAt -Bytes $sourceBytes -Offset 0x98),
    [double](Read-SingleAt -Bytes $sourceBytes -Offset 0x9C))

$containerBytes = Read-Bytes -Address $containerAddress -Length ($MaxEntries * 8)
$entries = New-Object System.Collections.Generic.List[object]

for ($index = 0; $index -lt $MaxEntries; $index++) {
    $entryAddress = Read-UInt64At -Bytes $containerBytes -Offset ($index * 8)
    if ($null -eq $entryAddress -or $entryAddress -eq 0) {
        continue
    }

    $entryBytes = Read-Bytes -Address $entryAddress -Length 0x140
    $q8 = Read-UInt64At -Bytes $entryBytes -Offset 0x8
    $q68 = Read-UInt64At -Bytes $entryBytes -Offset 0x68
    $q100 = Read-UInt64At -Bytes $entryBytes -Offset 0x100

    $coord48 = [double[]]@(
        [double](Read-SingleAt -Bytes $entryBytes -Offset 0x48),
        [double](Read-SingleAt -Bytes $entryBytes -Offset 0x4C),
        [double](Read-SingleAt -Bytes $entryBytes -Offset 0x50))
    $coord88 = [double[]]@(
        [double](Read-SingleAt -Bytes $entryBytes -Offset 0x88),
        [double](Read-SingleAt -Bytes $entryBytes -Offset 0x8C),
        [double](Read-SingleAt -Bytes $entryBytes -Offset 0x90))
    $orientation60 = [double[]]@(
        [double](Read-SingleAt -Bytes $entryBytes -Offset 0x60),
        [double](Read-SingleAt -Bytes $entryBytes -Offset 0x64),
        [double](Read-SingleAt -Bytes $entryBytes -Offset 0x68))
    $orientation94 = [double[]]@(
        [double](Read-SingleAt -Bytes $entryBytes -Offset 0x94),
        [double](Read-SingleAt -Bytes $entryBytes -Offset 0x98),
        [double](Read-SingleAt -Bytes $entryBytes -Offset 0x9C))

    $ownerRefCount = 0
    $sourceRefCount = 0
    for ($offset = 0; $offset -le ($entryBytes.Length - 8); $offset += 8) {
        $pointerValue = Read-UInt64At -Bytes $entryBytes -Offset $offset
        if ($pointerValue -eq $ownerAddress) {
            $ownerRefCount++
        }
        elseif ($pointerValue -eq $selectedSourceAddress) {
            $sourceRefCount++
        }
    }

    $roleHints = New-Object System.Collections.Generic.List[string]
    if ($entryAddress -eq $selectedSourceAddress) {
        $roleHints.Add('selected-source')
    }
    if ($q8 -eq $selectedSourceAddress -and $q100 -eq $ownerAddress) {
        $roleHints.Add('source-wrapper')
    }
    if ($q68 -eq $ownerAddress) {
        $roleHints.Add('owner-backref-wrapper')
    }
    if ($q8 -eq $stateRecordAddress) {
        $roleHints.Add('state-wrapper')
    }
    if (Test-TripletMatch -Expected $expectedCoord48 -Actual $coord48 -Tolerance 0.25) {
        $roleHints.Add('coord48-match')
    }
    if (Test-TripletMatch -Expected $expectedCoord88 -Actual $coord88 -Tolerance 0.25) {
        $roleHints.Add('coord88-match')
    }
    if (Test-TripletMatch -Expected $expectedOrientation60 -Actual $orientation60 -Tolerance 0.02) {
        $roleHints.Add('orientation60-match')
    }
    if (Test-TripletMatch -Expected $expectedOrientation94 -Actual $orientation94 -Tolerance 0.02) {
        $roleHints.Add('orientation94-match')
    }

    $entries.Add([ordered]@{
        Index = $index
        Address = ('0x{0:X}' -f $entryAddress)
        RoleHints = $roleHints.ToArray()
        Q8 = if ($q8) { ('0x{0:X}' -f $q8) } else { $null }
        Q68 = if ($q68) { ('0x{0:X}' -f $q68) } else { $null }
        Q100 = if ($q100) { ('0x{0:X}' -f $q100) } else { $null }
        OwnerRefCount = $ownerRefCount
        SourceRefCount = $sourceRefCount
        Coord48 = [ordered]@{
            X = $coord48[0]
            Y = $coord48[1]
            Z = $coord48[2]
        }
        Coord88 = [ordered]@{
            X = $coord88[0]
            Y = $coord88[1]
            Z = $coord88[2]
        }
        Orientation60 = [ordered]@{
            X = $orientation60[0]
            Y = $orientation60[1]
            Z = $orientation60[2]
        }
        Orientation94 = [ordered]@{
            X = $orientation94[0]
            Y = $orientation94[1]
            Z = $orientation94[2]
        }
    })
}

$result = [ordered]@{
    Mode = 'player-owner-components'
    GeneratedAtUtc = [DateTimeOffset]::UtcNow.ToString('O', [System.Globalization.CultureInfo]::InvariantCulture)
    SelectorTraceFile = $resolvedSelectorTraceFile
    Owner = [ordered]@{
        Address = ('0x{0:X}' -f $ownerAddress)
        ContainerAddress = ('0x{0:X}' -f $containerAddress)
        SelectedSourceAddress = ('0x{0:X}' -f $selectedSourceAddress)
        StateRecordAddress = ('0x{0:X}' -f $stateRecordAddress)
    }
    EntryCount = $entries.Count
    Entries = $entries.ToArray()
}

$outputDirectory = Split-Path -Parent $resolvedOutputFile
if (-not [string]::IsNullOrWhiteSpace($outputDirectory)) {
    New-Item -ItemType Directory -Path $outputDirectory -Force | Out-Null
}

$jsonText = $result | ConvertTo-Json -Depth 20
Set-Content -LiteralPath $resolvedOutputFile -Value $jsonText -Encoding UTF8

if ($Json) {
    Write-Output $jsonText
}
else {
    Write-Host "Owner component file:  $resolvedOutputFile"
    Write-Host "Owner object:          0x$('{0:X}' -f $ownerAddress)"
    Write-Host "Component container:   0x$('{0:X}' -f $containerAddress)"
    Write-Host "Selected source:       0x$('{0:X}' -f $selectedSourceAddress)"
    foreach ($entry in $entries) {
        $hintText = if ($entry.RoleHints.Count -gt 0) { $entry.RoleHints -join ', ' } else { 'unclassified' }
        Write-Host ("  [{0}] {1} :: {2}" -f $entry.Index, $entry.Address, $hintText)
    }
}
