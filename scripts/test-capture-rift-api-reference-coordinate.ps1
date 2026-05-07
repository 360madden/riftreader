[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Assert-Equal {
    param(
        [Parameter(Mandatory = $true)]
        $Actual,

        [Parameter(Mandatory = $true)]
        $Expected,

        [Parameter(Mandatory = $true)]
        [string]$Message
    )

    if ($Actual -ne $Expected) {
        throw "$Message Expected '$Expected', got '$Actual'."
    }
}

function Assert-True {
    param(
        [Parameter(Mandatory = $true)]
        [bool]$Condition,

        [Parameter(Mandatory = $true)]
        [string]$Message
    )

    if (-not $Condition) {
        throw $Message
    }
}

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$script = Join-Path $repoRoot 'scripts\capture-rift-api-reference-coordinate.ps1'
$tempRoot = Join-Path ([System.IO.Path]::GetTempPath()) ('RiftReader-api-reference-capture-' + [System.Guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $tempRoot -Force | Out-Null

try {
    $scanFile = Join-Path $tempRoot 'scan.json'
    $referenceFile = Join-Path $tempRoot 'reference.json'

    $oldMarker = 'RRAPICOORD1|schema=1|seq=100|sampledAt=10.5|source=rift-api|view=Inspect.Unit.Detail(player)|status=pass|x=1.25|y=2.5|z=3.75|playerId=uOld|name=Old|zone=zOld|location=Old Place|savedVariablesUse=none'
    $failedNewerMarker = 'RRAPICOORD1|schema=1|seq=300|sampledAt=30.5|source=rift-api|view=Inspect.Unit.Detail(player)|status=fail|x=9.25|y=9.5|z=9.75|playerId=uFail|name=Fail|zone=zFail|location=Fail Place|savedVariablesUse=none'
    $bestMarker = 'RRAPICOORD1|schema=1|seq=200|sampledAt=20.5|source=rift-api|view=Inspect.Unit.Detail(player)|status=pass|x=4.25|y=5.5|z=6.75|playerId=uBest|name=Atank|zone=zBest|location=Sanctum of the Vigil|savedVariablesUse=none'

    $scan = [ordered]@{
        Mode = 'string-scan'
        ProcessId = 4242
        ProcessName = 'rift_x64'
        SearchText = 'savedVariablesUse=none'
        HitCount = 3
        Hits = @(
            [ordered]@{
                AddressHex = '0x1000'
                Encoding = 'ascii'
                Classification = 'clustered identity record'
                Context = [ordered]@{
                    AsciiPreview = "prefix $oldMarker suffix"
                }
            },
            [ordered]@{
                AddressHex = '0x2000'
                Encoding = 'ascii'
                Classification = 'clustered identity record'
                Context = [ordered]@{
                    AsciiPreview = "prefix $failedNewerMarker suffix"
                }
            },
            [ordered]@{
                AddressHex = '0x3000'
                Encoding = 'ascii'
                Classification = 'clustered identity record'
                Context = [ordered]@{
                    AsciiPreview = "prefix $bestMarker suffix"
                }
            }
        )
    }
    $scan | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath $scanFile -Encoding UTF8

    $summaryJson = & $script `
        -ScanResultFile $scanFile `
        -OutputFile $referenceFile `
        -TargetWindowHandle 0x1234 `
        -ReferenceTolerance 0.125 `
        -Json

    $summary = $summaryJson | ConvertFrom-Json -Depth 30
    Assert-Equal -Actual $summary.Mode -Expected 'rift-api-reference-coordinate-capture' -Message 'Unexpected summary mode.'
    Assert-Equal -Actual $summary.Status -Expected 'captured' -Message 'Reference capture should succeed.'
    Assert-True -Condition ([bool]$summary.NoCheatEngine) -Message 'Reference capture must be marked no-CE.'
    Assert-True -Condition (-not [bool]$summary.MovementSent) -Message 'Reference capture must not send movement.'
    Assert-True -Condition (-not [bool]$summary.SavedVariablesUsedAsLiveTruth) -Message 'Reference capture must not use SavedVariables as live truth.'
    Assert-Equal -Actual $summary.MarkerCount -Expected 3 -Message 'All fixture markers should be counted.'
    Assert-Equal -Actual $summary.UsableMarkerCount -Expected 2 -Message 'Only pass/source/savedVariables=none markers should be usable.'
    Assert-Equal -Actual $summary.SelectedMarkerSeq -Expected 200 -Message 'Highest usable marker sequence should be selected.'
    Assert-Equal -Actual $summary.Coordinate.X -Expected 4.25 -Message 'Selected X mismatch.'
    Assert-Equal -Actual $summary.Coordinate.Y -Expected 5.5 -Message 'Selected Y mismatch.'
    Assert-Equal -Actual $summary.Coordinate.Z -Expected 6.75 -Message 'Selected Z mismatch.'

    $referenceRaw = Get-Content -LiteralPath $referenceFile -Raw
    Assert-True -Condition ($referenceRaw -match '"captured_at_utc":\s*"[^"]+Z"') -Message 'Reference timestamp should be emitted as an explicit UTC Z string.'

    $reference = $referenceRaw | ConvertFrom-Json -Depth 30
    Assert-Equal -Actual $reference.source -Expected 'rrapicoord1-memory-scan' -Message 'Unexpected reference source.'
    Assert-Equal -Actual $reference.tolerance -Expected 0.125 -Message 'Reference tolerance should be preserved.'
    Assert-Equal -Actual $reference.coordinate.x -Expected 4.25 -Message 'Reference X mismatch.'
    Assert-Equal -Actual $reference.coordinate.y -Expected 5.5 -Message 'Reference Y mismatch.'
    Assert-Equal -Actual $reference.coordinate.z -Expected 6.75 -Message 'Reference Z mismatch.'
    Assert-Equal -Actual $reference.marker.seq -Expected 200 -Message 'Reference marker sequence mismatch.'
    Assert-Equal -Actual $reference.marker.hitAddressHex -Expected '0x3000' -Message 'Reference marker hit address mismatch.'
    Assert-Equal -Actual $reference.savedVariablesUse -Expected 'none' -Message 'Reference must record SavedVariables exclusion.'
    Assert-True -Condition ([bool]$reference.noCheatEngine) -Message 'Reference must record no-CE boundary.'
    Assert-True -Condition (-not [bool]$reference.movementSent) -Message 'Reference must record no movement.'

    $fallbackScanFile = Join-Path $tempRoot 'scan-fallback.json'
    $fallbackReferenceFile = Join-Path $tempRoot 'reference-fallback.json'
    $fallbackScan = [ordered]@{
        Mode = 'string-scan'
        ProcessId = 4242
        ProcessName = 'rift_x64'
        SearchText = 'RRAPICOORD1'
        HitCount = 2
        Hits = @(
            [ordered]@{
                AddressHex = '0x4000'
                Encoding = 'ascii'
                Classification = 'clustered identity record'
                Context = [ordered]@{
                    AsciiPreview = 'prefix RRAPICOORD1 config schema=1 sampledAt=123.5 source=rift-api view=Inspect.Unit.Detail(player) suffix'
                }
            },
            [ordered]@{
                AddressHex = '0x5000'
                Encoding = 'ascii'
                Classification = 'clustered identity record'
                Context = [ordered]@{
                    AsciiPreview = "A7EA|00000002|0000021E|00000097|03|`nP000000ADname=5:Atank;level=45;calling=7:warrior;guild=14:The Regulators;hp=18208;hpMax=18208;hpPct=100;resKind=5:power;resCur=100;resMax=100;resPct=100;x=7437.73;y=885.22;z=3050.81;T00000037name=12:Temple Guard;level=52"
                }
            }
        )
    }
    $fallbackScan | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath $fallbackScanFile -Encoding UTF8

    $fallbackSummaryJson = & $script `
        -ScanResultFile $fallbackScanFile `
        -OutputFile $fallbackReferenceFile `
        -TargetWindowHandle 0x1234 `
        -ReferenceTolerance 0.25 `
        -Json

    $fallbackSummary = $fallbackSummaryJson | ConvertFrom-Json -Depth 30
    Assert-Equal -Actual $fallbackSummary.Status -Expected 'captured' -Message 'Companion live unit payload fallback should succeed.'
    Assert-Equal -Actual $fallbackSummary.SelectedReferenceKind -Expected 'rift-api-unit-payload-companion' -Message 'Fallback reference kind mismatch.'
    Assert-Equal -Actual $fallbackSummary.Coordinate.X -Expected 7437.73 -Message 'Fallback X mismatch.'
    Assert-Equal -Actual $fallbackSummary.Coordinate.Y -Expected 885.22 -Message 'Fallback Y mismatch.'
    Assert-Equal -Actual $fallbackSummary.Coordinate.Z -Expected 3050.81 -Message 'Fallback Z mismatch.'

    $fallbackReference = Get-Content -LiteralPath $fallbackReferenceFile -Raw | ConvertFrom-Json -Depth 30
    Assert-Equal -Actual $fallbackReference.marker.referenceKind -Expected 'rift-api-unit-payload-companion' -Message 'Fallback reference marker kind mismatch.'
    Assert-Equal -Actual $fallbackReference.savedVariablesUse -Expected 'none' -Message 'Fallback reference must still exclude SavedVariables.'
    Assert-True -Condition ([bool]$fallbackReference.noCheatEngine) -Message 'Fallback reference must record no-CE boundary.'
    Assert-True -Condition (-not [bool]$fallbackReference.movementSent) -Message 'Fallback reference must record no movement.'

    Write-Host 'Rift API reference coordinate capture regression passed.' -ForegroundColor Green
}
finally {
    if (Test-Path -LiteralPath $tempRoot) {
        Remove-Item -LiteralPath $tempRoot -Recurse -Force
    }
}
