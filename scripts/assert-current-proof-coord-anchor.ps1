[CmdletBinding()]
param(
    [string]$ProcessName = 'rift_x64',
    [int]$ProcessId,
    [string]$TargetWindowHandle,
    [string]$ProofCoordAnchorFile,
    [int]$MaxAgeSeconds = 60,
    [switch]$UseCacheOnly,
    [switch]$Json
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$resolverScript = Join-Path $PSScriptRoot 'resolve-proof-coord-anchor.ps1'
if ([string]::IsNullOrWhiteSpace($ProofCoordAnchorFile)) {
    $ProofCoordAnchorFile = Join-Path $PSScriptRoot 'captures\telemetry-proof-coord-anchor.json'
}
$resolvedProofCoordAnchorFile = [System.IO.Path]::GetFullPath($ProofCoordAnchorFile)

Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;

public static class RiftProofCoordPreflightNative
{
    [DllImport("user32.dll", SetLastError = true)]
    public static extern bool IsWindow(IntPtr hWnd);

    [DllImport("user32.dll", SetLastError = true)]
    public static extern uint GetWindowThreadProcessId(IntPtr hWnd, out uint processId);
}
"@

function Get-NormalizedProcessName {
    param([string]$Name)

    if ([string]::IsNullOrWhiteSpace($Name)) {
        return $Name
    }

    $trimmed = $Name.Trim()
    if ($trimmed.EndsWith('.exe', [System.StringComparison]::OrdinalIgnoreCase)) {
        return $trimmed.Substring(0, $trimmed.Length - 4)
    }

    return $trimmed
}

function ConvertTo-WindowHandle {
    param([string]$HandleText)

    if ([string]::IsNullOrWhiteSpace($HandleText)) {
        return [IntPtr]::Zero
    }

    if ($HandleText.StartsWith('0x', [System.StringComparison]::OrdinalIgnoreCase)) {
        $raw = [UInt64]::Parse($HandleText.Substring(2), [System.Globalization.NumberStyles]::AllowHexSpecifier, [System.Globalization.CultureInfo]::InvariantCulture)
        return [IntPtr]([Int64]$raw)
    }

    return [IntPtr]([Int64]::Parse($HandleText, [System.Globalization.CultureInfo]::InvariantCulture))
}

function Format-WindowHandle {
    param([IntPtr]$Handle)

    if ($Handle -eq [IntPtr]::Zero) {
        return $null
    }

    return ('0x{0:X}' -f $Handle.ToInt64())
}

function Resolve-TargetProcess {
    $normalizedName = Get-NormalizedProcessName -Name $ProcessName
    $handle = ConvertTo-WindowHandle -HandleText $TargetWindowHandle

    if ($handle -ne [IntPtr]::Zero) {
        if (-not [RiftProofCoordPreflightNative]::IsWindow($handle)) {
            throw "Target window handle '$TargetWindowHandle' is not a valid window."
        }

        $ownerProcessId = [uint32]0
        [void][RiftProofCoordPreflightNative]::GetWindowThreadProcessId($handle, [ref]$ownerProcessId)
        if ($ownerProcessId -eq 0) {
            throw "Target window handle '$TargetWindowHandle' did not resolve to an owning process."
        }

        if ($ProcessId -gt 0 -and [int]$ownerProcessId -ne $ProcessId) {
            throw "Target window handle '$TargetWindowHandle' belongs to PID $ownerProcessId, not PID $ProcessId."
        }

        $process = Get-Process -Id ([int]$ownerProcessId) -ErrorAction Stop
        if (-not [string]::IsNullOrWhiteSpace($normalizedName) -and
            -not [string]::Equals($process.ProcessName, $normalizedName, [System.StringComparison]::OrdinalIgnoreCase)) {
            throw "Target window handle '$TargetWindowHandle' belongs to process '$($process.ProcessName)' [PID $ownerProcessId], not '$ProcessName'."
        }

        return [pscustomobject]@{
            Process = $process
            Handle = $handle
        }
    }

    if ($ProcessId -gt 0) {
        $process = Get-Process -Id $ProcessId -ErrorAction Stop
        if (-not [string]::IsNullOrWhiteSpace($normalizedName) -and
            -not [string]::Equals($process.ProcessName, $normalizedName, [System.StringComparison]::OrdinalIgnoreCase)) {
            throw "Target PID $ProcessId is process '$($process.ProcessName)', not '$ProcessName'."
        }

        return [pscustomobject]@{
            Process = $process
            Handle = $process.MainWindowHandle
        }
    }

    $matches = @(Get-Process -Name $normalizedName -ErrorAction Stop | Sort-Object StartTime -Descending)
    if ($matches.Count -ne 1) {
        throw "Expected exactly one '$ProcessName' process when no PID/HWND is supplied; found $($matches.Count). Pass -ProcessId or -TargetWindowHandle."
    }

    return [pscustomobject]@{
        Process = $matches[0]
        Handle = $matches[0].MainWindowHandle
    }
}

function ConvertFrom-JsonCompat {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Text,
        [int]$Depth = 80
    )

    $command = Get-Command -Name ConvertFrom-Json -CommandType Cmdlet
    if ($command.Parameters.ContainsKey('Depth')) {
        return $Text | ConvertFrom-Json -Depth $Depth
    }

    return $Text | ConvertFrom-Json
}

function Get-DocumentPropertyValue {
    param(
        $Document,
        [Parameter(Mandatory = $true)]
        [string]$Name,
        $Default = $null
    )

    if ($null -eq $Document) {
        return $Default
    }

    $property = $Document.PSObject.Properties[$Name]
    if ($null -eq $property) {
        return $Default
    }

    return $property.Value
}

function Test-AnchorBool {
    param(
        $Value,
        [bool]$Expected
    )

    if ($null -eq $Value) {
        return $false
    }

    try {
        return [bool]$Value -eq $Expected
    }
    catch {
        return $false
    }
}

function Invoke-ProofAnchorResolverNoRefresh {
    param(
        [Parameter(Mandatory = $true)]
        [int]$TargetProcessId,

        [Parameter(Mandatory = $true)]
        [string]$TargetProcessName,

        [string]$TargetHandleHex
    )

    if (-not (Test-Path -LiteralPath $resolverScript)) {
        throw "Proof coord anchor resolver script was not found: $resolverScript"
    }

    $arguments = @(
        '-NoLogo',
        '-NoProfile',
        '-ExecutionPolicy',
        'Bypass',
        '-File',
        $resolverScript,
        '-ProcessName',
        $TargetProcessName,
        '-ProcessId',
        $TargetProcessId.ToString([System.Globalization.CultureInfo]::InvariantCulture),
        '-ProofCoordAnchorFile',
        $resolvedProofCoordAnchorFile,
        '-SkipRefresh',
        '-Json'
    )

    if (-not [string]::IsNullOrWhiteSpace($TargetHandleHex)) {
        $arguments += @('-TargetWindowHandle', $TargetHandleHex)
    }

    $shell = if (Get-Command -Name pwsh -CommandType Application -ErrorAction SilentlyContinue) {
        'pwsh'
    }
    else {
        'powershell'
    }

    $output = & $shell @arguments 2>&1
    $exitCode = $LASTEXITCODE
    return [pscustomobject]@{
        ExitCode = $exitCode
        Output = ($output -join [Environment]::NewLine)
    }
}

function Test-NoCeRiftScanReferenceProofAnchorDocument {
    param($Document)

    $canonicalCoordSourceKind = [string](Get-DocumentPropertyValue -Document $Document -Name 'CanonicalCoordSourceKind')
    $proofMethod = [string](Get-DocumentPropertyValue -Document $Document -Name 'ProofMethod')

    return [string]::Equals($canonicalCoordSourceKind, 'riftscan-reference-validated-candidate', [System.StringComparison]::OrdinalIgnoreCase) -or
        [string]::Equals($proofMethod, 'no-ce-riftscan-reference-multisample', [System.StringComparison]::OrdinalIgnoreCase)
}

function Read-ProofAnchorDocument {
    param(
        [Parameter(Mandatory = $true)]
        [int]$TargetProcessId,

        [Parameter(Mandatory = $true)]
        [string]$TargetProcessName,

        [string]$TargetHandleHex
    )

    if ($UseCacheOnly) {
        if (-not (Test-Path -LiteralPath $resolvedProofCoordAnchorFile)) {
            throw "Proof coord anchor file not found: $resolvedProofCoordAnchorFile"
        }

        return [pscustomobject]@{
            Source = 'cache'
            ExitCode = 0
            Document = ConvertFrom-JsonCompat -Text (Get-Content -LiteralPath $resolvedProofCoordAnchorFile -Raw) -Depth 80
            RawOutput = $null
        }
    }

    if (Test-Path -LiteralPath $resolvedProofCoordAnchorFile) {
        $cachedDocument = ConvertFrom-JsonCompat -Text (Get-Content -LiteralPath $resolvedProofCoordAnchorFile -Raw) -Depth 80
        if (Test-NoCeRiftScanReferenceProofAnchorDocument -Document $cachedDocument) {
            return [pscustomobject]@{
                Source = 'cache'
                ExitCode = 0
                Document = $cachedDocument
                RawOutput = $null
            }
        }
    }

    $resolve = Invoke-ProofAnchorResolverNoRefresh -TargetProcessId $TargetProcessId -TargetProcessName $TargetProcessName -TargetHandleHex $TargetHandleHex
    $document = if ([string]::IsNullOrWhiteSpace($resolve.Output)) {
        $null
    }
    else {
        ConvertFrom-JsonCompat -Text $resolve.Output -Depth 80
    }

    return [pscustomobject]@{
        Source = 'resolve-skip-refresh'
        ExitCode = $resolve.ExitCode
        Document = $document
        RawOutput = $resolve.Output
    }
}

function Test-ProofAnchorDocument {
    param(
        $Anchor,
        [Parameter(Mandatory = $true)]
        [int]$TargetProcessId,
        [Parameter(Mandatory = $true)]
        [string]$TargetProcessName
    )

    $issues = [System.Collections.Generic.List[string]]::new()

    if ($null -eq $Anchor) {
        $issues.Add('proof_anchor_document_missing') | Out-Null
        return $issues.ToArray()
    }

    $status = [string](Get-DocumentPropertyValue -Document $Anchor -Name 'Status')
    if ([string]::Equals($status, 'failed', [System.StringComparison]::OrdinalIgnoreCase)) {
        $errorText = [string](Get-DocumentPropertyValue -Document $Anchor -Name 'Error')
        $issues.Add(("proof_anchor_resolver_failed:{0}" -f $errorText)) | Out-Null
        return $issues.ToArray()
    }

    $mode = [string](Get-DocumentPropertyValue -Document $Anchor -Name 'Mode')
    if (-not [string]::Equals($mode, 'proof-coord-anchor', [System.StringComparison]::OrdinalIgnoreCase)) {
        $issues.Add(("proof_anchor_mode_invalid:{0}" -f $mode)) | Out-Null
    }

    $anchorProcessId = Get-DocumentPropertyValue -Document $Anchor -Name 'ProcessId'
    if ($null -eq $anchorProcessId -or [int]$anchorProcessId -ne $TargetProcessId) {
        $issues.Add(("proof_anchor_pid_mismatch:anchor={0};target={1}" -f $anchorProcessId, $TargetProcessId)) | Out-Null
    }

    $anchorProcessName = [string](Get-DocumentPropertyValue -Document $Anchor -Name 'ProcessName')
    if (-not [string]::Equals((Get-NormalizedProcessName -Name $anchorProcessName), (Get-NormalizedProcessName -Name $TargetProcessName), [System.StringComparison]::OrdinalIgnoreCase)) {
        $issues.Add(("proof_anchor_process_mismatch:anchor={0};target={1}" -f $anchorProcessName, $TargetProcessName)) | Out-Null
    }

    $canonicalCoordSourceKind = [string](Get-DocumentPropertyValue -Document $Anchor -Name 'CanonicalCoordSourceKind')
    $proofMethod = [string](Get-DocumentPropertyValue -Document $Anchor -Name 'ProofMethod')
    $isNoCeRiftScanReferenceProof =
        [string]::Equals($canonicalCoordSourceKind, 'riftscan-reference-validated-candidate', [System.StringComparison]::OrdinalIgnoreCase) -or
        [string]::Equals($proofMethod, 'no-ce-riftscan-reference-multisample', [System.StringComparison]::OrdinalIgnoreCase)

    if ($isNoCeRiftScanReferenceProof) {
        if (-not [string]::Equals($proofMethod, 'no-ce-riftscan-reference-multisample', [System.StringComparison]::OrdinalIgnoreCase)) {
            $issues.Add(("proof_anchor_no_ce_proof_method_invalid:{0}" -f $proofMethod)) | Out-Null
        }

        if (-not (Test-AnchorBool -Value (Get-DocumentPropertyValue -Document $Anchor -Name 'NoCheatEngine') -Expected $true)) {
            $issues.Add('proof_anchor_no_ce_flag_missing_or_false') | Out-Null
        }

        if (-not (Test-AnchorBool -Value (Get-DocumentPropertyValue -Document $Anchor -Name 'ProofProcessMatchesProcess') -Expected $true)) {
            $issues.Add('proof_anchor_no_ce_process_proof_does_not_match_process') | Out-Null
        }

        $proofValidationStatus = [string](Get-DocumentPropertyValue -Document $Anchor -Name 'ProofValidationStatus')
        if (-not [string]::Equals($proofValidationStatus, 'validated', [System.StringComparison]::OrdinalIgnoreCase)) {
            $issues.Add(("proof_anchor_no_ce_validation_status_invalid:{0}" -f $proofValidationStatus)) | Out-Null
        }

        $evidence = Get-DocumentPropertyValue -Document $Anchor -Name 'Evidence'
        $poseCount = Get-DocumentPropertyValue -Document $evidence -Name 'PoseCount'
        if ($null -eq $poseCount -or [int]$poseCount -lt 2) {
            $issues.Add(("proof_anchor_no_ce_pose_count_insufficient:{0}" -f $poseCount)) | Out-Null
        }

        $maxReferencePlanarDisplacement = Get-DocumentPropertyValue -Document $evidence -Name 'MaxReferencePlanarDisplacement'
        if ($null -eq $maxReferencePlanarDisplacement -or [double]$maxReferencePlanarDisplacement -le 0.0) {
            $issues.Add(("proof_anchor_no_ce_reference_displacement_missing:{0}" -f $maxReferencePlanarDisplacement)) | Out-Null
        }
    }
    elseif (-not (Test-AnchorBool -Value (Get-DocumentPropertyValue -Document $Anchor -Name 'TraceMatchesProcess') -Expected $true)) {
        $issues.Add('proof_anchor_trace_does_not_match_process') | Out-Null
    }

    $match = Get-DocumentPropertyValue -Document $Anchor -Name 'Match'
    if (-not (Test-AnchorBool -Value (Get-DocumentPropertyValue -Document $match -Name 'CoordMatchesWithinTolerance') -Expected $true)) {
        $issues.Add('proof_anchor_match_not_within_tolerance') | Out-Null
    }

    foreach ($propertyName in @('CanonicalCoordSourceKind', 'ObjectBaseAddress', 'CoordRegionAddress')) {
        if ([string]::IsNullOrWhiteSpace([string](Get-DocumentPropertyValue -Document $Anchor -Name $propertyName))) {
            $issues.Add(("proof_anchor_{0}_missing" -f $propertyName)) | Out-Null
        }
    }

    $xOffset = Get-DocumentPropertyValue -Document $Anchor -Name 'CoordXRelativeOffset'
    $yOffset = Get-DocumentPropertyValue -Document $Anchor -Name 'CoordYRelativeOffset'
    $zOffset = Get-DocumentPropertyValue -Document $Anchor -Name 'CoordZRelativeOffset'
    if ($null -eq $xOffset -or [int]$xOffset -ne 0 -or
        $null -eq $yOffset -or [int]$yOffset -ne 4 -or
        $null -eq $zOffset -or [int]$zOffset -ne 8) {
        $issues.Add(("proof_anchor_coord_offsets_not_normalized:x={0};y={1};z={2}" -f $xOffset, $yOffset, $zOffset)) | Out-Null
    }

    $generatedAtValue = Get-DocumentPropertyValue -Document $Anchor -Name 'GeneratedAtUtc'
    if ($null -eq $generatedAtValue) {
        $issues.Add('proof_anchor_generated_at_missing') | Out-Null
    }
    elseif ($MaxAgeSeconds -gt 0) {
        try {
            $generatedAt = [DateTimeOffset]::Parse([string]$generatedAtValue, [System.Globalization.CultureInfo]::InvariantCulture)
            $ageSeconds = ([DateTimeOffset]::UtcNow - $generatedAt.ToUniversalTime()).TotalSeconds
            if ($ageSeconds -lt -5 -or $ageSeconds -gt $MaxAgeSeconds) {
                $issues.Add(("proof_anchor_age_out_of_range_seconds:{0:0.000}" -f $ageSeconds)) | Out-Null
            }
        }
        catch {
            $issues.Add(("proof_anchor_generated_at_invalid:{0}" -f $generatedAtValue)) | Out-Null
        }
    }

    return $issues.ToArray()
}

function New-PreflightResult {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Status,
        [Parameter(Mandatory = $true)]
        [bool]$MovementAllowed,
        [string[]]$Issues = @(),
        $Anchor = $null,
        [string]$Source = '',
        [int]$ResolveExitCode = 0,
        [int]$TargetProcessId = 0,
        [string]$TargetProcessName = '',
        [string]$TargetHandleHex = $null
    )

    return [pscustomobject][ordered]@{
        SchemaVersion = 1
        Mode = 'proof-coord-anchor-movement-preflight'
        GeneratedAtUtc = [DateTimeOffset]::UtcNow.ToString('O')
        Status = $Status
        MovementAllowed = $MovementAllowed
        NoCheatEngine = $true
        MovementSent = $false
        ProcessName = $TargetProcessName
        ProcessId = if ($TargetProcessId -gt 0) { $TargetProcessId } else { $null }
        TargetWindowHandle = $TargetHandleHex
        ProofCoordAnchorFile = $resolvedProofCoordAnchorFile
        AnchorSource = $Source
        ResolverExitCode = $ResolveExitCode
        MaxAgeSeconds = $MaxAgeSeconds
        Issues = @($Issues)
        Anchor = $Anchor
        Notes = @(
            'This preflight is read-only and uses no Cheat Engine path.',
            'Movement is allowed only when Status=valid and MovementAllowed=true.',
            'Candidate-only RiftScan watchsets do not satisfy this gate.'
        )
    }
}

try {
    $target = Resolve-TargetProcess
    $targetProcess = $target.Process
    $targetProcessId = [int]$targetProcess.Id
    $targetProcessName = $targetProcess.ProcessName
    $targetHandleHex = Format-WindowHandle -Handle $target.Handle

    $readResult = Read-ProofAnchorDocument -TargetProcessId $targetProcessId -TargetProcessName $targetProcessName -TargetHandleHex $targetHandleHex
    $issues = @(Test-ProofAnchorDocument -Anchor $readResult.Document -TargetProcessId $targetProcessId -TargetProcessName $targetProcessName)
    $isValid = $readResult.ExitCode -eq 0 -and $issues.Count -eq 0

    $result = New-PreflightResult `
        -Status $(if ($isValid) { 'valid' } else { 'failed' }) `
        -MovementAllowed:$isValid `
        -Issues $issues `
        -Anchor $readResult.Document `
        -Source $readResult.Source `
        -ResolveExitCode $readResult.ExitCode `
        -TargetProcessId $targetProcessId `
        -TargetProcessName $targetProcessName `
        -TargetHandleHex $targetHandleHex

    if ($Json) {
        $result | ConvertTo-Json -Depth 32
    }
    elseif ($isValid) {
        Write-Host 'Proof coord anchor movement preflight passed.' -ForegroundColor Green
        Write-Host ("PID/HWND:        {0} / {1}" -f $targetProcessId, $targetHandleHex)
        Write-Host ("Coord region:    {0}" -f $readResult.Document.CoordRegionAddress)
        Write-Host 'Movement:        allowed by proof-anchor gate'
        Write-Host 'CE usage:        none'
    }
    else {
        Write-Host 'Proof coord anchor movement preflight failed.' -ForegroundColor Red
        foreach ($issue in $issues) {
            Write-Host ("- {0}" -f $issue) -ForegroundColor Red
        }
        Write-Host 'Movement:        blocked'
        Write-Host 'CE usage:        none'
    }

    if (-not $isValid) {
        exit 1
    }
}
catch {
    $result = New-PreflightResult `
        -Status 'failed' `
        -MovementAllowed:$false `
        -Issues @($_.Exception.Message)

    if ($Json) {
        $result | ConvertTo-Json -Depth 32
        exit 1
    }

    throw
}
