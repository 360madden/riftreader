[CmdletBinding()]
param(
    [switch]$Json,
    [string]$ProcessName = 'rift_x64',
    [int]$HoldMilliseconds = 700,
    [int]$WaitMilliseconds = 250,
    [switch]$RefreshReaderBridge,
    [switch]$NoAhkFallback,
    [string]$OutputFile
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$readerProject = Join-Path $repoRoot 'reader\RiftReader.Reader\RiftReader.Reader.csproj'
$captureScript = Join-Path $PSScriptRoot 'capture-actor-orientation.ps1'
$stimulusScript = Join-Path $PSScriptRoot 'test-actor-orientation-stimulus.ps1'

if ([string]::IsNullOrWhiteSpace($OutputFile)) {
    $OutputFile = Join-Path $PSScriptRoot 'captures\actor-orientation-recovery.json'
}

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

    $jsonText = $output -join [Environment]::NewLine
    if ((Get-Command Microsoft.PowerShell.Utility\ConvertFrom-Json).Parameters.ContainsKey('Depth')) {
        return ($jsonText | Microsoft.PowerShell.Utility\ConvertFrom-Json -Depth 80)
    }

    return ($jsonText | Microsoft.PowerShell.Utility\ConvertFrom-Json)
}

function Get-OptionalPropertyValue {
    param(
        [Parameter(Mandatory = $true)]
        $Object,

        [Parameter(Mandatory = $true)]
        [string]$Name
    )

    if ($null -eq $Object) {
        return $null
    }

    $property = $Object.PSObject.Properties[$Name]
    if ($null -eq $property) {
        return $null
    }

    return $property.Value
}

function Invoke-Capture {
    param([Parameter(Mandatory = $true)][string]$Label)

    $arguments = @{
        Json = $true
        Label = $Label
    }

    if ($RefreshReaderBridge) {
        $arguments['RefreshReaderBridge'] = $true
    }

    if ($NoAhkFallback) {
        $arguments['NoAhkFallback'] = $true
    }

    $jsonText = & $captureScript @arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Actor orientation capture failed for '$Label'."
    }

    if ((Get-Command Microsoft.PowerShell.Utility\ConvertFrom-Json).Parameters.ContainsKey('Depth')) {
        return ($jsonText | Microsoft.PowerShell.Utility\ConvertFrom-Json -Depth 80)
    }

    return ($jsonText | Microsoft.PowerShell.Utility\ConvertFrom-Json)
}

function Invoke-Stimulus {
    param([Parameter(Mandatory = $true)][string]$Key)

    $arguments = @{
        Key = $Key
        Json = $true
        HoldMilliseconds = $HoldMilliseconds
        WaitMilliseconds = $WaitMilliseconds
    }

    if ($RefreshReaderBridge) {
        $arguments['RefreshReaderBridge'] = $true
    }

    if ($NoAhkFallback) {
        $arguments['NoAhkFallback'] = $true
    }

    $jsonText = & $stimulusScript @arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Stimulus helper failed for key '$Key'."
    }

    if ((Get-Command Microsoft.PowerShell.Utility\ConvertFrom-Json).Parameters.ContainsKey('Depth')) {
        return ($jsonText | Microsoft.PowerShell.Utility\ConvertFrom-Json -Depth 80)
    }

    return ($jsonText | Microsoft.PowerShell.Utility\ConvertFrom-Json)
}

function Format-Nullable {
    param(
        $Value,
        [string]$Format = '0.000'
    )

    if ($null -eq $Value) {
        return 'n/a'
    }

    return ([double]$Value).ToString($Format, [System.Globalization.CultureInfo]::InvariantCulture)
}

function Get-OppositeSigns {
    param(
        [double]$Left,
        [double]$Right
    )

    if ([Math]::Abs($Left) -lt [double]::Epsilon -or [Math]::Abs($Right) -lt [double]::Epsilon) {
        return $false
    }

    return ($Left -gt 0 -and $Right -lt 0) -or ($Left -lt 0 -and $Right -gt 0)
}

function Get-OrientationProbeSnapshot {
    try {
        $snapshot = Invoke-ReaderJson -Arguments @('--readerbridge-snapshot', '--json')
        return $snapshot.Current.OrientationProbe
    }
    catch {
        return $null
    }
}

$baseline = Invoke-Capture -Label 'recovery-baseline'
$leftStimulus = Invoke-Stimulus -Key 'Left'
$rightStimulus = Invoke-Stimulus -Key 'Right'
$orientationProbe = Get-OrientationProbeSnapshot

$preferredBasis = $baseline.ReaderOrientation.PreferredBasis
$duplicateAgreement = $baseline.ReaderOrientation.DuplicateBasisAgreement
$preferredEstimate = $baseline.ReaderOrientation.PreferredEstimate
$resolutionMode = [string](Get-OptionalPropertyValue -Object $baseline.ReaderOrientation -Name 'ResolutionMode')

$basisRecovered =
    $null -ne $preferredBasis -and
    $preferredBasis.IsOrthonormal -eq $true -and
    ((
        $null -ne $duplicateAgreement -and
        $null -ne $duplicateAgreement.MaxRowDeltaMagnitude -and
        [double]$duplicateAgreement.MaxRowDeltaMagnitude -le 0.05
    ) -or $resolutionMode -eq 'read-only-pointer-hop-candidate-search')

$leftYaw = if ($null -ne $leftStimulus.Comparison.YawDeltaDegrees) { [double]$leftStimulus.Comparison.YawDeltaDegrees } else { 0.0 }
$rightYaw = if ($null -ne $rightStimulus.Comparison.YawDeltaDegrees) { [double]$rightStimulus.Comparison.YawDeltaDegrees } else { 0.0 }
$leftCoord = if ($null -ne $leftStimulus.Comparison.CoordDeltaMagnitude) { [double]$leftStimulus.Comparison.CoordDeltaMagnitude } else { 9999.0 }
$rightCoord = if ($null -ne $rightStimulus.Comparison.CoordDeltaMagnitude) { [double]$rightStimulus.Comparison.CoordDeltaMagnitude } else { 9999.0 }

$yawRecovered =
    $basisRecovered -and
    [Math]::Abs($leftYaw) -ge 15.0 -and
    [Math]::Abs($rightYaw) -ge 15.0 -and
    (Get-OppositeSigns -Left $leftYaw -Right $rightYaw) -and
    $leftCoord -le 0.25 -and
    $rightCoord -le 0.25

$pitchRecovered =
    $basisRecovered -and
    $null -ne $preferredEstimate -and
    $null -ne $preferredEstimate.PitchDegrees

$notes = New-Object System.Collections.Generic.List[string]
if (-not [string]::IsNullOrWhiteSpace($resolutionMode)) {
    $notes.Add("Resolution mode: $resolutionMode")
}
if ($resolutionMode -eq 'read-only-pointer-hop-candidate-search') {
    $notes.Add('Recovery used a pointer-hop candidate without duplicate-basis agreement; orthonormal basis quality was used as the basis gate instead.')
}
if ($yawRecovered) {
    $notes.Add('Yaw recovery passed the Left/Right stimulus gate.')
}
else {
    $notes.Add('Yaw recovery did not pass the Left/Right stimulus gate yet.')
}
if ($pitchRecovered) {
    $notes.Add('Pitch is available from the recovered orientation basis.')
}
if ($orientationProbe) {
    $orientationProbePlayer = Get-OptionalPropertyValue -Object $orientationProbe -Name 'Player'
    $playerDirectHeading = Get-OptionalPropertyValue -Object $orientationProbePlayer -Name 'DirectHeading'
    $playerDirectPitch = Get-OptionalPropertyValue -Object $orientationProbePlayer -Name 'DirectPitch'

    if ($null -ne $playerDirectHeading) {
        $notes.Add("Addon direct heading candidate: $playerDirectHeading")
    }
    if ($null -ne $playerDirectPitch) {
        $notes.Add("Addon direct pitch candidate: $playerDirectPitch")
    }
}

$document = [pscustomobject]@{
    Mode = 'actor-orientation-recovery'
    GeneratedAtUtc = [DateTimeOffset]::UtcNow.ToString('O')
    OutputFile = $resolvedOutputFile
    ProcessName = $ProcessName
    Recovery = [pscustomobject]@{
        BasisRecovered = $basisRecovered
        YawRecovered = $yawRecovered
        PitchRecovered = $pitchRecovered
    }
    Baseline = $baseline
    LeftStimulus = $leftStimulus
    RightStimulus = $rightStimulus
    OrientationProbe = $orientationProbe
    Notes = $notes
}

$outputDirectory = Split-Path -Path $resolvedOutputFile -Parent
if (-not [string]::IsNullOrWhiteSpace($outputDirectory)) {
    New-Item -ItemType Directory -Path $outputDirectory -Force | Out-Null
}

$jsonText = $document | ConvertTo-Json -Depth 80
[System.IO.File]::WriteAllText($resolvedOutputFile, $jsonText)

if ($Json) {
    Write-Output $jsonText
    exit 0
}

Write-Host "Actor orientation recovery"
Write-Host ("Process:                     {0}" -f $ProcessName)
Write-Host ("Resolution mode:             {0}" -f $(if (-not [string]::IsNullOrWhiteSpace($resolutionMode)) { $resolutionMode } else { 'n/a' }))
Write-Host ("Basis recovered:             {0}" -f $document.Recovery.BasisRecovered)
Write-Host ("Yaw recovered:               {0}" -f $document.Recovery.YawRecovered)
Write-Host ("Pitch recovered:             {0}" -f $document.Recovery.PitchRecovered)
Write-Host ("Baseline yaw/pitch (deg):    {0} / {1}" -f (Format-Nullable $preferredEstimate.YawDegrees '0.000'), (Format-Nullable $preferredEstimate.PitchDegrees '0.000'))
Write-Host ("Left yaw delta / coord:      {0} / {1}" -f (Format-Nullable $leftYaw '0.000'), (Format-Nullable $leftCoord '0.000000'))
Write-Host ("Right yaw delta / coord:     {0} / {1}" -f (Format-Nullable $rightYaw '0.000'), (Format-Nullable $rightCoord '0.000000'))
if ($orientationProbe) {
    $orientationProbePlayer = Get-OptionalPropertyValue -Object $orientationProbe -Name 'Player'
    $playerDirectHeading = Get-OptionalPropertyValue -Object $orientationProbePlayer -Name 'DirectHeading'
    $playerDirectPitch = Get-OptionalPropertyValue -Object $orientationProbePlayer -Name 'DirectPitch'
    Write-Host ("Addon direct heading/pitch:  {0} / {1}" -f (Format-Nullable $playerDirectHeading '0.000'), (Format-Nullable $playerDirectPitch '0.000'))
}
Write-Host ("Output file:                 {0}" -f $resolvedOutputFile)
