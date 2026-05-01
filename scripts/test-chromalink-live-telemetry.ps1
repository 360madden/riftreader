[CmdletBinding()]
param(
    [string]$SnapshotPath = (Join-Path $env:LOCALAPPDATA 'ChromaLink\DesktopDotNet\out\chromalink-live-telemetry.json'),

    [string]$WorldStateUrl = '',

    [string]$WorldStatePath = '',

    [int]$MaxFreshAgeMilliseconds = 2000,

    [switch]$Watch,

    [int]$IntervalMilliseconds = 250,

    [int]$DurationSeconds = 0,

    [switch]$AllowStale,

    [switch]$Json
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$schemaVersion = 1

if ($MaxFreshAgeMilliseconds -lt 0) {
    throw 'MaxFreshAgeMilliseconds must be zero or greater.'
}

if ($IntervalMilliseconds -lt 50) {
    throw 'IntervalMilliseconds must be at least 50.'
}

if ($DurationSeconds -lt 0) {
    throw 'DurationSeconds must be zero or greater.'
}

$useWorldStateUrl = -not [string]::IsNullOrWhiteSpace($WorldStateUrl)
$useWorldStatePath = -not [string]::IsNullOrWhiteSpace($WorldStatePath)
if ($useWorldStateUrl -and $useWorldStatePath) {
    throw 'Specify only one of WorldStateUrl or WorldStatePath.'
}

function ConvertTo-DateTimeOffsetOrNull {
    param([object]$Value)

    if ($null -eq $Value) {
        return $null
    }

    if ($Value -is [DateTimeOffset]) {
        return $Value.ToUniversalTime()
    }

    if ($Value -is [DateTime]) {
        return ([DateTimeOffset]$Value).ToUniversalTime()
    }

    $text = [string]$Value
    if ([string]::IsNullOrWhiteSpace($text)) {
        return $null
    }

    try {
        return ([DateTimeOffset]::Parse(
                $text,
                [System.Globalization.CultureInfo]::InvariantCulture,
                [System.Globalization.DateTimeStyles]::RoundtripKind)).ToUniversalTime()
    }
    catch {
        return $null
    }
}

function Get-PropertyValue {
    param(
        [object]$InputObject,

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
    if ($null -eq $property) {
        return $null
    }

    return $property.Value
}

function Get-NestedValue {
    param(
        [object]$InputObject,

        [Parameter(Mandatory = $true)]
        [string]$Path
    )

    $current = $InputObject
    foreach ($segment in $Path.Split('.')) {
        $current = Get-PropertyValue -InputObject $current -Name $segment
        if ($null -eq $current) {
            return $null
        }
    }

    return $current
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

function Format-UtcOrNull {
    param([object]$Value)

    $date = ConvertTo-DateTimeOffsetOrNull -Value $Value
    if ($null -eq $date) {
        return $null
    }

    return $date.ToUniversalTime().ToString('O', [System.Globalization.CultureInfo]::InvariantCulture)
}

function Test-SnapshotFreshness {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path
    )

    $resolvedPath = [System.IO.Path]::GetFullPath($Path)
    $nowUtc = [DateTimeOffset]::UtcNow

    if (-not (Test-Path -LiteralPath $resolvedPath)) {
        return [ordered]@{
            schemaVersion = $schemaVersion
            mode = 'chromalink-live-telemetry-freshness'
            status = 'missing'
            snapshotPath = $resolvedPath
            exists = $false
            generatedAtUtc = $nowUtc.ToString('O', [System.Globalization.CultureInfo]::InvariantCulture)
            maxFreshAgeMs = $MaxFreshAgeMilliseconds
            fresh = $false
            stale = $true
            failures = @("ChromaLink telemetry snapshot not found: $resolvedPath")
        }
    }

    $file = Get-Item -LiteralPath $resolvedPath
    $document = Get-Content -LiteralPath $resolvedPath -Raw | ConvertFrom-Json -Depth 64
    $position = Get-NestedValue -InputObject $document -Path 'aggregate.playerPosition'

    $failures = [System.Collections.Generic.List[string]]::new()
    if ($null -eq $position) {
        $failures.Add('ChromaLink snapshot does not contain aggregate.playerPosition.') | Out-Null
    }

    $snapshotGeneratedAtUtc = ConvertTo-DateTimeOffsetOrNull (Get-PropertyValue -InputObject $document -Name 'generatedAtUtc')
    $snapshotAgeBasisUtc = if ($null -ne $snapshotGeneratedAtUtc) { $snapshotGeneratedAtUtc } else { [DateTimeOffset]::new($file.LastWriteTimeUtc).ToUniversalTime() }
    $snapshotAgeMs = [Math]::Round(($nowUtc - $snapshotAgeBasisUtc).TotalMilliseconds, 3)
    $snapshotWithinFreshWindow = $snapshotAgeMs -le $MaxFreshAgeMilliseconds

    $observedAtUtc = ConvertTo-DateTimeOffsetOrNull (Get-PropertyValue -InputObject $position -Name 'observedAtUtc')
    $ageMs = ConvertTo-DoubleOrNull (Get-PropertyValue -InputObject $position -Name 'ageMs')
    if ($null -eq $ageMs -and $null -ne $observedAtUtc) {
        $ageMs = [Math]::Round(($nowUtc - $observedAtUtc).TotalMilliseconds, 3)
    }

    $sourceFrameFresh = Get-PropertyValue -InputObject $position -Name 'fresh'
    $sourceFrameStale = Get-PropertyValue -InputObject $position -Name 'stale'
    $frameWithinFreshWindow = if ($null -ne $ageMs) { $ageMs -le $MaxFreshAgeMilliseconds } else { $null }
    $fresh = $failures.Count -eq 0 -and $snapshotWithinFreshWindow -and ($frameWithinFreshWindow -ne $false) -and ($sourceFrameFresh -ne $false)
    $stale = -not $fresh

    if (-not $snapshotWithinFreshWindow) {
        $failures.Add("Snapshot age exceeds MaxFreshAgeMilliseconds; snapshotAgeMs=$snapshotAgeMs maxFreshAgeMs=$MaxFreshAgeMilliseconds.") | Out-Null
    }
    if ($frameWithinFreshWindow -eq $false) {
        $failures.Add("Player-position frame age exceeds MaxFreshAgeMilliseconds; ageMs=$ageMs maxFreshAgeMs=$MaxFreshAgeMilliseconds.") | Out-Null
    }
    if ($sourceFrameFresh -eq $false -or $sourceFrameStale -eq $true) {
        $failures.Add("Player-position frame is marked stale by source; fresh=$sourceFrameFresh stale=$sourceFrameStale.") | Out-Null
    }

    return [ordered]@{
        schemaVersion = $schemaVersion
        mode = 'chromalink-live-telemetry-freshness'
        status = if ($fresh) { 'pass' } else { 'stale' }
        snapshotPath = $resolvedPath
        exists = $true
        generatedAtUtc = $nowUtc.ToString('O', [System.Globalization.CultureInfo]::InvariantCulture)
        sourceSnapshotLastWriteUtc = ([DateTimeOffset]::new($file.LastWriteTimeUtc).ToUniversalTime().ToString('O', [System.Globalization.CultureInfo]::InvariantCulture))
        snapshotGeneratedAtUtc = Format-UtcOrNull $snapshotGeneratedAtUtc
        snapshotAgeMs = $snapshotAgeMs
        snapshotWithinFreshWindow = $snapshotWithinFreshWindow
        observedAtUtc = Format-UtcOrNull $observedAtUtc
        ageMs = $ageMs
        maxFreshAgeMs = $MaxFreshAgeMilliseconds
        sourceFrameFresh = $sourceFrameFresh
        sourceFrameStale = $sourceFrameStale
        frameWithinFreshWindow = $frameWithinFreshWindow
        fresh = $fresh
        stale = $stale
        aggregateReady = Get-NestedValue -InputObject $document -Path 'aggregate.ready'
        aggregateHealthy = Get-NestedValue -InputObject $document -Path 'aggregate.healthy'
        aggregateStale = Get-NestedValue -InputObject $document -Path 'aggregate.stale'
        aggregateAcceptedFrames = ConvertTo-IntOrNull (Get-NestedValue -InputObject $document -Path 'aggregate.acceptedFrames')
        frameType = [string](Get-PropertyValue -InputObject $position -Name 'frameType')
        schemaId = ConvertTo-IntOrNull (Get-PropertyValue -InputObject $position -Name 'schemaId')
        sequence = ConvertTo-IntOrNull (Get-PropertyValue -InputObject $position -Name 'sequence')
        x = ConvertTo-DoubleOrNull (Get-PropertyValue -InputObject $position -Name 'x')
        y = ConvertTo-DoubleOrNull (Get-PropertyValue -InputObject $position -Name 'y')
        z = ConvertTo-DoubleOrNull (Get-PropertyValue -InputObject $position -Name 'z')
        failures = $failures.ToArray()
    }
}

function Read-WorldStateDocument {
    param(
        [string]$Url,
        [string]$Path
    )

    if (-not [string]::IsNullOrWhiteSpace($Path)) {
        $resolvedPath = [System.IO.Path]::GetFullPath($Path)
        if (-not (Test-Path -LiteralPath $resolvedPath)) {
            return [pscustomobject]@{
                Exists = $false
                InputMode = 'world-state-file'
                WorldStatePath = $resolvedPath
                WorldStateUrl = $null
                StatusCode = 503
                LastWriteTimeUtc = $null
                Document = $null
            }
        }

        $file = Get-Item -LiteralPath $resolvedPath
        return [pscustomobject]@{
            Exists = $true
            InputMode = 'world-state-file'
            WorldStatePath = $resolvedPath
            WorldStateUrl = $null
            StatusCode = 200
            LastWriteTimeUtc = [DateTimeOffset]::new($file.LastWriteTimeUtc).ToUniversalTime()
            Document = Get-Content -LiteralPath $resolvedPath -Raw | ConvertFrom-Json -Depth 64
        }
    }

    $response = Invoke-WebRequest -Method Get -Uri $Url -UseBasicParsing -SkipHttpErrorCheck -TimeoutSec 5
    $document = if ([string]::IsNullOrWhiteSpace($response.Content)) { $null } else { $response.Content | ConvertFrom-Json -Depth 64 }
    return [pscustomobject]@{
        Exists = $true
        InputMode = 'world-state-url'
        WorldStatePath = $null
        WorldStateUrl = [string]$Url
        StatusCode = [int]$response.StatusCode
        LastWriteTimeUtc = $null
        Document = $document
    }
}

function Test-WorldStateFreshness {
    param(
        [string]$Url,
        [string]$Path
    )

    $nowUtc = [DateTimeOffset]::UtcNow
    $reader = Read-WorldStateDocument -Url $Url -Path $Path
    $failures = [System.Collections.Generic.List[string]]::new()

    if ($reader.Exists -ne $true -or $null -eq $reader.Document) {
        $location = if (-not [string]::IsNullOrWhiteSpace($Path)) { $reader.WorldStatePath } else { $Url }
        return [ordered]@{
            schemaVersion = $schemaVersion
            mode = 'chromalink-live-telemetry-freshness'
            inputMode = $reader.InputMode
            status = 'missing'
            snapshotPath = $null
            worldStateUrl = $reader.WorldStateUrl
            worldStatePath = $reader.WorldStatePath
            exists = $false
            generatedAtUtc = $nowUtc.ToString('O', [System.Globalization.CultureInfo]::InvariantCulture)
            maxFreshAgeMs = $MaxFreshAgeMilliseconds
            fresh = $false
            stale = $true
            failures = @("ChromaLink RiftReader world-state not found or empty: $location")
        }
    }

    if ($reader.InputMode -eq 'world-state-url' -and ([int]$reader.StatusCode -lt 200 -or [int]$reader.StatusCode -gt 299)) {
        $failures.Add("ChromaLink RiftReader world-state HTTP status is not successful; status=$($reader.StatusCode).") | Out-Null
    }

    $document = $reader.Document
    $position = Get-NestedValue -InputObject $document -Path 'player.position'
    $navigationPlayerAvailable = Get-NestedValue -InputObject $document -Path 'navigation.playerPositionAvailable'

    if ($null -eq $position) {
        $failures.Add('ChromaLink RiftReader world-state does not contain player.position.') | Out-Null
    }
    else {
        foreach ($axis in @('x', 'y', 'z')) {
            if ($null -eq (ConvertTo-DoubleOrNull (Get-PropertyValue -InputObject $position -Name $axis))) {
                $failures.Add("ChromaLink RiftReader world-state player.position is missing numeric $axis.") | Out-Null
            }
        }
    }
    if ($navigationPlayerAvailable -ne $true) {
        $failures.Add("ChromaLink RiftReader world-state navigation.playerPositionAvailable is not true; value=$navigationPlayerAvailable.") | Out-Null
    }

    $rootOk = Get-PropertyValue -InputObject $document -Name 'ok'
    $rootReady = Get-PropertyValue -InputObject $document -Name 'ready'
    $rootFresh = Get-PropertyValue -InputObject $document -Name 'fresh'
    $rootStale = Get-PropertyValue -InputObject $document -Name 'stale'
    if ($rootOk -ne $true) {
        $failures.Add("ChromaLink RiftReader world-state ok is not true; value=$rootOk.") | Out-Null
    }
    if ($rootReady -ne $true) {
        $failures.Add("ChromaLink RiftReader world-state ready is not true; value=$rootReady.") | Out-Null
    }
    if ($rootFresh -ne $true -or $rootStale -eq $true) {
        $failures.Add("ChromaLink RiftReader world-state is marked stale by source; fresh=$rootFresh stale=$rootStale.") | Out-Null
    }

    $snapshotAgeSeconds = ConvertTo-DoubleOrNull (Get-PropertyValue -InputObject $document -Name 'snapshotAgeSeconds')
    $snapshotAgeMs = if ($null -ne $snapshotAgeSeconds) {
        [Math]::Round($snapshotAgeSeconds * 1000.0, 3)
    }
    elseif ($null -ne $reader.LastWriteTimeUtc) {
        [Math]::Round(($nowUtc - $reader.LastWriteTimeUtc).TotalMilliseconds, 3)
    }
    else {
        $null
    }
    $snapshotWithinFreshWindow = if ($null -ne $snapshotAgeMs) { $snapshotAgeMs -le $MaxFreshAgeMilliseconds } else { $false }

    $observedAtUtc = ConvertTo-DateTimeOffsetOrNull (Get-PropertyValue -InputObject $position -Name 'observedAtUtc')
    $ageMs = ConvertTo-DoubleOrNull (Get-PropertyValue -InputObject $position -Name 'ageMs')
    if ($null -eq $ageMs -and $null -ne $observedAtUtc) {
        $ageMs = [Math]::Round(($nowUtc - $observedAtUtc).TotalMilliseconds, 3)
    }

    $sourceFrameFresh = Get-PropertyValue -InputObject $position -Name 'fresh'
    $sourceFrameStale = Get-PropertyValue -InputObject $position -Name 'stale'
    $frameWithinFreshWindow = if ($null -ne $ageMs) { $ageMs -le $MaxFreshAgeMilliseconds } else { $null }

    if ($null -eq $snapshotAgeMs) {
        $failures.Add('World-state snapshot age is unavailable.') | Out-Null
    }
    elseif ($snapshotWithinFreshWindow -eq $false) {
        $failures.Add("World-state snapshot age exceeds MaxFreshAgeMilliseconds; snapshotAgeMs=$snapshotAgeMs maxFreshAgeMs=$MaxFreshAgeMilliseconds.") | Out-Null
    }
    if ($frameWithinFreshWindow -eq $false) {
        $failures.Add("Player-position frame age exceeds MaxFreshAgeMilliseconds; ageMs=$ageMs maxFreshAgeMs=$MaxFreshAgeMilliseconds.") | Out-Null
    }
    if ($sourceFrameFresh -eq $false -or $sourceFrameStale -eq $true) {
        $failures.Add("Player-position frame is marked stale by source; fresh=$sourceFrameFresh stale=$sourceFrameStale.") | Out-Null
    }

    $fresh = $failures.Count -eq 0

    return [ordered]@{
        schemaVersion = $schemaVersion
        mode = 'chromalink-live-telemetry-freshness'
        inputMode = $reader.InputMode
        status = if ($fresh) { 'pass' } else { 'stale' }
        snapshotPath = [string](Get-PropertyValue -InputObject $document -Name 'snapshotPath')
        worldStateUrl = $reader.WorldStateUrl
        worldStatePath = $reader.WorldStatePath
        httpStatusCode = $(if ($reader.InputMode -eq 'world-state-url') { [int]$reader.StatusCode } else { $null })
        exists = $true
        generatedAtUtc = $nowUtc.ToString('O', [System.Globalization.CultureInfo]::InvariantCulture)
        sourceSnapshotLastWriteUtc = $(if ($null -ne $reader.LastWriteTimeUtc) { $reader.LastWriteTimeUtc.ToString('O', [System.Globalization.CultureInfo]::InvariantCulture) } else { $null })
        snapshotGeneratedAtUtc = $null
        snapshotAgeMs = $snapshotAgeMs
        snapshotWithinFreshWindow = $snapshotWithinFreshWindow
        observedAtUtc = Format-UtcOrNull $observedAtUtc
        ageMs = $ageMs
        maxFreshAgeMs = $MaxFreshAgeMilliseconds
        sourceFrameFresh = $sourceFrameFresh
        sourceFrameStale = $sourceFrameStale
        frameWithinFreshWindow = $frameWithinFreshWindow
        fresh = $fresh
        stale = -not $fresh
        sourceContractName = [string](Get-NestedValue -InputObject $document -Path 'sourceContract.name')
        sourceContractSchemaVersion = ConvertTo-IntOrNull (Get-NestedValue -InputObject $document -Path 'sourceContract.schemaVersion')
        worldStateContractName = [string](Get-NestedValue -InputObject $document -Path 'contract.name')
        worldStateContractSchemaVersion = ConvertTo-IntOrNull (Get-NestedValue -InputObject $document -Path 'contract.schemaVersion')
        aggregateReady = $rootReady
        aggregateHealthy = Get-PropertyValue -InputObject $document -Name 'healthy'
        aggregateStale = $rootStale
        aggregateAcceptedFrames = $null
        frameType = $null
        schemaId = $null
        sequence = $null
        x = ConvertTo-DoubleOrNull (Get-PropertyValue -InputObject $position -Name 'x')
        y = ConvertTo-DoubleOrNull (Get-PropertyValue -InputObject $position -Name 'y')
        z = ConvertTo-DoubleOrNull (Get-PropertyValue -InputObject $position -Name 'z')
        failures = $failures.ToArray()
    }
}

$startedAtUtc = [DateTimeOffset]::UtcNow
$result = $null
do {
    try {
        if ($useWorldStateUrl -or $useWorldStatePath) {
            $result = Test-WorldStateFreshness -Url $WorldStateUrl -Path $WorldStatePath
        }
        else {
            $result = Test-SnapshotFreshness -Path $SnapshotPath
        }
    }
    catch {
        $result = [ordered]@{
            schemaVersion = $schemaVersion
            mode = 'chromalink-live-telemetry-freshness'
            status = 'fail'
            snapshotPath = $(if ($useWorldStateUrl -or $useWorldStatePath) { $null } else { [System.IO.Path]::GetFullPath($SnapshotPath) })
            worldStateUrl = $(if ($useWorldStateUrl) { $WorldStateUrl } else { $null })
            worldStatePath = $(if ($useWorldStatePath) { [System.IO.Path]::GetFullPath($WorldStatePath) } else { $null })
            generatedAtUtc = [DateTimeOffset]::UtcNow.ToString('O', [System.Globalization.CultureInfo]::InvariantCulture)
            maxFreshAgeMs = $MaxFreshAgeMilliseconds
            fresh = $false
            stale = $true
            failures = @($_.Exception.Message)
        }
    }

    if (-not $Watch -or [string]$result.status -eq 'pass') {
        break
    }

    if ($DurationSeconds -gt 0 -and ([DateTimeOffset]::UtcNow - $startedAtUtc).TotalSeconds -ge $DurationSeconds) {
        break
    }

    Start-Sleep -Milliseconds $IntervalMilliseconds
} while ($true)

if ($Json) {
    $result | ConvertTo-Json -Depth 16
}
else {
    $color = if ([string]$result.status -eq 'pass') { 'Green' } else { 'Red' }
    Write-Host ("ChromaLink telemetry freshness: {0}" -f $result.status) -ForegroundColor $color
    Write-Host ("Snapshot: {0}" -f $result.snapshotPath)
    if ($result.PSObject.Properties['worldStateUrl'] -and -not [string]::IsNullOrWhiteSpace([string]$result.worldStateUrl)) {
        Write-Host ("WorldStateUrl: {0}" -f $result.worldStateUrl)
    }
    if ($result.PSObject.Properties['worldStatePath'] -and -not [string]::IsNullOrWhiteSpace([string]$result.worldStatePath)) {
        Write-Host ("WorldStatePath: {0}" -f $result.worldStatePath)
    }
    Write-Host ("Fresh:    {0}" -f $result.fresh)
    if ($result.PSObject.Properties['snapshotAgeMs']) {
        Write-Host ("Age ms:   {0}" -f $result.snapshotAgeMs)
    }
    foreach ($failure in @($result.failures)) {
        Write-Host ("- {0}" -f $failure) -ForegroundColor Red
    }
}

if ([string]$result.status -ne 'pass' -and -not $AllowStale) {
    exit 1
}
