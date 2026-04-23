[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

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
$sourceScript = Join-Path $repoRoot 'scripts\assert-actor-facing-truth.ps1'
$tempRoot = Join-Path ([System.IO.Path]::GetTempPath()) ('RiftReader-actor-facing-truth-proof-' + [System.Guid]::NewGuid().ToString('N'))
$tempScriptsRoot = Join-Path $tempRoot 'scripts'
$tempReaderRoot = Join-Path $tempRoot 'reader\RiftReader.Reader'
$capturesRoot = Join-Path $tempScriptsRoot 'captures'
$discoveryRoot = Join-Path $capturesRoot 'actor-facing-discovery'
$tempScriptFile = Join-Path $tempScriptsRoot 'assert-actor-facing-truth.ps1'
$tempCaptureScript = Join-Path $tempScriptsRoot 'capture-actor-orientation.ps1'
$leadFile = Join-Path $tempScriptsRoot 'actor-facing-behavior-backed-lead.json'
$discoverySessionFile = Join-Path $discoveryRoot 'session.json'
$sourceChainFile = Join-Path $capturesRoot 'player-source-chain.json'
$outputFile = Join-Path $capturesRoot 'actor-facing-truth-proof.json'
$fakeProjectFile = Join-Path $tempReaderRoot 'RiftReader.Reader.csproj'
$shimDirectory = Join-Path $tempRoot 'shim'
$fakeDotnetPath = Join-Path $shimDirectory 'dotnet.cmd'

New-Item -ItemType Directory -Path $tempScriptsRoot -Force | Out-Null
New-Item -ItemType Directory -Path $tempReaderRoot -Force | Out-Null
New-Item -ItemType Directory -Path $capturesRoot -Force | Out-Null
New-Item -ItemType Directory -Path $discoveryRoot -Force | Out-Null
New-Item -ItemType Directory -Path $shimDirectory -Force | Out-Null

$processStartUtc = '2026-04-23T06:10:11.1234567+00:00'
$leadValidatedUtc = '2026-04-23T06:20:21.7654321+00:00'
$proofSourceAddress = '0X123456789ABC'
$proofBasisOffset = '0XD4'
$proofPid = 4242

$scriptContent = Get-Content -LiteralPath $sourceScript -Raw
$fakeProcessFunction = @"
function Get-LiveProcessSnapshot {
    param(
        [Parameter(Mandatory = `$true)]
        [string]`$Name
    )

    return [pscustomobject]@{
        ProcessId = $proofPid
        ProcessName = [string]`$Name
        StartTimeUtc = [DateTimeOffset]::Parse('$processStartUtc', [System.Globalization.CultureInfo]::InvariantCulture, [System.Globalization.DateTimeStyles]::RoundtripKind)
        StartTimeUtcText = '$processStartUtc'
        MainWindowTitle = 'RIFT'
        MainWindowHandleHex = '0xBEEF'
        Responding = `$true
        SelectionNote = `$null
    }
}
"@

$pattern = 'function Get-LiveProcessSnapshot \{[\s\S]*?^function Get-OrientationSummary \{'
$replacement = $fakeProcessFunction + "`r`nfunction Get-OrientationSummary {"
$scriptContent = [regex]::Replace($scriptContent, $pattern, $replacement, [System.Text.RegularExpressions.RegexOptions]::Multiline)
Set-Content -LiteralPath $tempScriptFile -Value $scriptContent -Encoding UTF8

$captureJson = [ordered]@{
    Mode = 'player-actor-orientation-capture'
    GeneratedAtUtc = '2026-04-23T06:21:00.0000000+00:00'
    ReaderOrientation = [ordered]@{
        SelectedSourceAddress = $proofSourceAddress
        ResolutionMode = 'behavior-backed-lead'
        BasisForwardOffset = '0xD4'
        BasisDuplicateForwardOffset = $null
        ArtifactFile = $leadFile
        ArtifactGeneratedAtUtc = $leadValidatedUtc
        PreferredEstimate = [ordered]@{
            YawDegrees = 12.5
            PitchDegrees = -3.25
        }
    }
}

$captureScriptContent = @"
param(
    [switch]`$Json,
    [string]`$ProcessName = 'rift_x64'
)

Set-StrictMode -Version Latest
`$ErrorActionPreference = 'Stop'

`$document = @'
$($captureJson | ConvertTo-Json -Depth 12)
'@

if (`$Json) {
    Write-Output `$document
}
else {
    Write-Host 'capture-actor-orientation shim'
}
"@
Set-Content -LiteralPath $tempCaptureScript -Value $captureScriptContent -Encoding UTF8

$leadDocument = [ordered]@{
    Mode = 'actor-facing-behavior-backed-lead'
    GeneratedAtUtc = $leadValidatedUtc
    ValidatedAtUtc = $leadValidatedUtc
    ProcessName = 'rift_x64'
    SourceAddress = $proofSourceAddress
    BasisForwardOffset = $proofBasisOffset
    BasisDuplicateForwardOffset = $null
    Status = 'preferred-solved-lead'
    OperationalStatus = 'behavior-backed-lead'
    PreferredLead = $true
    SolvedActorFacing = $true
    CanonicalActorYaw = $true
    Notes = @('shim proof lead')
    CandidateDiagnostics = [ordered]@{
        ProcessId = $proofPid
        ProcessStartTimeUtc = $processStartUtc
        ForwardPeakYawDegrees = 40.0
        ReversePeakYawDegrees = 39.5
        PlayerCoordDeltaMagnitude = 0.0
    }
}
Set-Content -LiteralPath $leadFile -Value ($leadDocument | ConvertTo-Json -Depth 12) -Encoding UTF8

$discoverySession = [ordered]@{
    Mode = 'actor-facing-discovery-session'
    UpdatedAtUtc = '2026-04-23T06:22:00.0000000+00:00'
    Process = [ordered]@{
        ProcessId = $proofPid
        ProcessName = 'rift_x64'
        StartTimeUtc = $processStartUtc
    }
    LiveTruthStatus = 'confirmed'
    ProvenanceStatus = 'confirmed'
    SessionConsistency = 'consistent'
    Outcome = 'promoted'
    ExistingLead = [ordered]@{
        SourceAddress = $proofSourceAddress
        BasisForwardOffset = $proofBasisOffset
    }
    Stages = [ordered]@{
        Confirm = [ordered]@{
            Status = 'completed'
        }
    }
}
Set-Content -LiteralPath $discoverySessionFile -Value ($discoverySession | ConvertTo-Json -Depth 12) -Encoding UTF8

$sourceChainDocument = [ordered]@{
    Mode = 'player-source-chain'
    GeneratedAtUtc = '2026-04-23T06:23:00.0000000+00:00'
    ProcessId = $proofPid
    ProcessName = 'rift_x64'
    Recovery = [ordered]@{
        Mode = 'rebuild-from-suggested-source-chain-pattern'
        TriggerReason = 'Unable to locate required instruction: source container load'
        PatternScanAddress = '0x7FF70000AAA0'
    }
    SourceChain = [ordered]@{
        SourceResolveTarget = '7FF70000BBBB'
    }
}
Set-Content -LiteralPath $sourceChainFile -Value ($sourceChainDocument | ConvertTo-Json -Depth 12) -Encoding UTF8

$readerJson = @'
{
  "SelectedSourceAddress": "0x123456789ABC",
  "ResolutionMode": "live-behavior-backed-lead",
  "BasisForwardOffset": "0xD4",
  "BasisDuplicateForwardOffset": null,
  "ArtifactFile": "__LEAD_FILE__",
  "ArtifactGeneratedAtUtc": "2026-04-23T06:20:21.7654321+00:00",
  "PreferredEstimate": {
    "YawDegrees": 12.5,
    "PitchDegrees": -3.25
  }
}
'@.Replace('__LEAD_FILE__', ($leadFile -replace '\\', '\\'))

$fakeDotnetLines = @('@echo off', 'setlocal')
$fakeDotnetLines += ($readerJson.Trim().Split("`n") | ForEach-Object { 'echo ' + $_.TrimEnd("`r") })
$fakeDotnetLines += 'exit /b 0'
Set-Content -LiteralPath $fakeDotnetPath -Value $fakeDotnetLines -Encoding ASCII

$originalPath = $env:PATH

try {
    $env:PATH = "$shimDirectory;$originalPath"

    $resultJson = & pwsh `
        -NoLogo `
        -NoProfile `
        -ExecutionPolicy Bypass `
        -File $tempScriptFile `
        -Json `
        -ProcessName 'rift_x64' `
        -BehaviorBackedLeadFile $leadFile `
        -DiscoverySessionFile $discoverySessionFile `
        -SourceChainFile $sourceChainFile `
        -OutputFile $outputFile

    if ($LASTEXITCODE -ne 0) {
        throw "assert-actor-facing-truth.ps1 exited with code $LASTEXITCODE."
    }

    $result = $resultJson | ConvertFrom-Json -Depth 20
    Assert-True -Condition ($result.TruthStatus -eq 'confirmed') -Message 'Expected actor-facing truth proof to confirm the shimmed live truth.'
    Assert-True -Condition ($result.ProvenanceStatus -eq 'confirmed') -Message 'Expected provenance status to stay confirmed.'
    Assert-True -Condition ($result.LeadMatchesCapture) -Message 'Expected behavior-backed lead to match the capture output.'
    Assert-True -Condition ($result.LeadMatchesReader) -Message 'Expected behavior-backed lead to match the reader output.'
    Assert-True -Condition ($result.CaptureMatchesReader) -Message 'Expected capture and reader parity to pass.'
    Assert-True -Condition ([double]$result.YawDeltaDegrees -eq 0.0) -Message 'Expected zero yaw delta in the shimmed truth proof.'
    Assert-True -Condition ([double]$result.PitchDeltaDegrees -eq 0.0) -Message 'Expected zero pitch delta in the shimmed truth proof.'
    Assert-True -Condition ($result.DiscoverySession.SameProcessSession) -Message 'Expected discovery session to target the same process session.'
    Assert-True -Condition ($result.SourceChain.RecoveryMode -eq 'rebuild-from-suggested-source-chain-pattern') -Message 'Expected fresh provenance rebuild mode in the truth proof summary.'
    Assert-True -Condition (Test-Path -LiteralPath $outputFile) -Message 'Expected truth-proof artifact to be written.'

    Write-Host 'assert-actor-facing-truth regression check passed.' -ForegroundColor Green
}
finally {
    $env:PATH = $originalPath
    if (Test-Path -LiteralPath $tempRoot) {
        Remove-Item -LiteralPath $tempRoot -Recurse -Force
    }
}
