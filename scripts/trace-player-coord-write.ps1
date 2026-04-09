[CmdletBinding()]
param(
    [switch]$Json,
    [switch]$SkipRefresh,
    [switch]$SkipCleanup,
    [int]$MovementHoldMilliseconds = 1000,
    [int]$TimeoutSeconds = 8,
    [int]$MaxCandidates = 8,
    [string]$ConfirmationFile = (Join-Path $PSScriptRoot 'captures\ce-smart-player-family.json'),
    [string]$OutputFile = (Join-Path $PSScriptRoot 'captures\player-coord-write-trace.json'),
    [string]$TraceStatusFile = (Join-Path $PSScriptRoot 'captures\player-coord-write-trace.status.txt')
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$readerProject = Join-Path $repoRoot 'reader\RiftReader.Reader\RiftReader.Reader.csproj'
$refreshScript = Join-Path $PSScriptRoot 'refresh-readerbridge-export.ps1'
$postKeyScript = Join-Path $PSScriptRoot 'post-rift-key.ps1'
$ceExecScript = Join-Path $PSScriptRoot 'cheatengine-exec.ps1'
$traceLuaFile = Join-Path $PSScriptRoot 'cheat-engine\RiftReaderWriteTrace.lua'
$resolvedConfirmationFile = [System.IO.Path]::GetFullPath($ConfirmationFile)
$resolvedOutputFile = [System.IO.Path]::GetFullPath($OutputFile)
$resolvedStatusFile = [System.IO.Path]::GetFullPath($TraceStatusFile)

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

function Invoke-ReaderJsonWithRetry {
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$Arguments,

        [int]$MaxAttempts = 3,

        [int]$RetryDelayMilliseconds = 750
    )

    $lastError = $null

    for ($attempt = 1; $attempt -le $MaxAttempts; $attempt++) {
        try {
            return Invoke-ReaderJson -Arguments $Arguments
        }
        catch {
            $lastError = $_.Exception
            if ($attempt -lt $MaxAttempts) {
                Start-Sleep -Milliseconds $RetryDelayMilliseconds
            }
        }
    }

    if ($lastError) {
        throw $lastError
    }

    throw "Reader command failed after $MaxAttempts attempts."
}

function Parse-HexAddress {
    param(
        [Parameter(Mandatory = $true)]
        [string]$AddressHex
    )

    $normalized = $AddressHex
    if ($normalized.StartsWith('0x', [System.StringComparison]::OrdinalIgnoreCase)) {
        $normalized = $normalized.Substring(2)
    }

    return [UInt64]::Parse($normalized, [System.Globalization.NumberStyles]::HexNumber, [System.Globalization.CultureInfo]::InvariantCulture)
}

function Convert-ToModulePattern {
    param(
        [Parameter(Mandatory = $true)]
        [string]$ByteText
    )

    $hex = ($ByteText -replace '\s+', '').Trim()
    if ([string]::IsNullOrWhiteSpace($hex) -or ($hex.Length % 2) -ne 0) {
        return $null
    }

    if ($hex -notmatch '^[0-9A-Fa-f]+$') {
        return $null
    }

    $pairs = for ($index = 0; $index -lt $hex.Length; $index += 2) {
        $hex.Substring($index, 2).ToUpperInvariant()
    }

    return ($pairs -join ' ')
}

function Read-KeyValueFile {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path
    )

    $map = [ordered]@{}
    foreach ($line in [System.IO.File]::ReadAllLines($Path)) {
        if ([string]::IsNullOrWhiteSpace($line)) {
            continue
        }

        $separator = $line.IndexOf('=')
        if ($separator -lt 0) {
            continue
        }

        $key = $line.Substring(0, $separator)
        $value = $line.Substring($separator + 1)
        $map[$key] = $value
    }

    return [pscustomobject]$map
}

function Get-ObjectValue {
    param(
        [Parameter(Mandatory = $true)]
        [psobject]$Object,

        [Parameter(Mandatory = $true)]
        [string]$Name
    )

    $property = $Object.PSObject.Properties[$Name]
    if ($null -eq $property) {
        return $null
    }

    return $property.Value
}

function Convert-StatusToTraceAttempt {
    param(
        [Parameter(Mandatory = $true)]
        [pscustomobject]$Status,

        [Parameter(Mandatory = $true)]
        [string]$AddressHex,

        [Parameter(Mandatory = $true)]
        [string]$Source,

        [Parameter(Mandatory = $true)]
        [bool]$Success
    )

    return [pscustomobject]@{
        Success = $Success
        Status = [string](Get-ObjectValue -Object $Status -Name 'status')
        CandidateAddress = $AddressHex
        CandidateSource = $Source
        VerificationMethod = Get-ObjectValue -Object $Status -Name 'verificationMethod'
        TargetAddress = Get-ObjectValue -Object $Status -Name 'targetAddress'
        HitCount = if (Get-ObjectValue -Object $Status -Name 'hitCount') { [int](Get-ObjectValue -Object $Status -Name 'hitCount') } else { 0 }
        InstructionAddress = Get-ObjectValue -Object $Status -Name 'rip'
        InstructionSymbol = Get-ObjectValue -Object $Status -Name 'instructionSymbol'
        Instruction = Get-ObjectValue -Object $Status -Name 'instruction'
        InstructionBytes = Get-ObjectValue -Object $Status -Name 'instructionBytes'
        InstructionOpcode = Get-ObjectValue -Object $Status -Name 'instructionOpcode'
        InstructionExtra = Get-ObjectValue -Object $Status -Name 'instructionExtra'
        InstructionSize = Get-ObjectValue -Object $Status -Name 'instructionSize'
        WriteOperand = Get-ObjectValue -Object $Status -Name 'writeOperand'
        AccessOperand = Get-ObjectValue -Object $Status -Name 'accessOperand'
        AccessType = Get-ObjectValue -Object $Status -Name 'accessType'
        EffectiveAddress = Get-ObjectValue -Object $Status -Name 'effectiveAddress'
        AccessMatchesTarget = Get-ObjectValue -Object $Status -Name 'accessMatchesTarget'
        MatchedOffset = Get-ObjectValue -Object $Status -Name 'matchedOffset'
        ModuleName = Get-ObjectValue -Object $Status -Name 'moduleName'
        ModuleBase = Get-ObjectValue -Object $Status -Name 'moduleBase'
        ModuleOffset = Get-ObjectValue -Object $Status -Name 'moduleOffset'
        Error = Get-ObjectValue -Object $Status -Name 'error'
        Registers = [ordered]@{
            RAX = Get-ObjectValue -Object $Status -Name 'rax'
            RBX = Get-ObjectValue -Object $Status -Name 'rbx'
            RCX = Get-ObjectValue -Object $Status -Name 'rcx'
            RDX = Get-ObjectValue -Object $Status -Name 'rdx'
            RSI = Get-ObjectValue -Object $Status -Name 'rsi'
            RDI = Get-ObjectValue -Object $Status -Name 'rdi'
            RBP = Get-ObjectValue -Object $Status -Name 'rbp'
            RSP = Get-ObjectValue -Object $Status -Name 'rsp'
            R8 = Get-ObjectValue -Object $Status -Name 'r8'
            R9 = Get-ObjectValue -Object $Status -Name 'r9'
            R10 = Get-ObjectValue -Object $Status -Name 'r10'
            R11 = Get-ObjectValue -Object $Status -Name 'r11'
            R12 = Get-ObjectValue -Object $Status -Name 'r12'
            R13 = Get-ObjectValue -Object $Status -Name 'r13'
            R14 = Get-ObjectValue -Object $Status -Name 'r14'
            R15 = Get-ObjectValue -Object $Status -Name 'r15'
        }
    }
}

function Invoke-TraceStimulus {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Key,

        [Parameter(Mandatory = $true)]
        [int]$HoldMilliseconds
    )

    & $postKeyScript -Key $Key -HoldMilliseconds $HoldMilliseconds
}

function Get-CoordTraceResult {
    param(
        [Parameter(Mandatory = $true)]
        [string]$AddressHex,

        [Parameter(Mandatory = $true)]
        [string]$Source
    )

    $coordAddress = Parse-HexAddress -AddressHex $AddressHex

    if (Test-Path -LiteralPath $resolvedStatusFile) {
        Remove-Item -LiteralPath $resolvedStatusFile -Force
    }

    & $ceExecScript -LuaFile $traceLuaFile | Out-Null

    $luaCode = @"
return RiftReaderWriteTrace.arm('rift_x64', $coordAddress, 4, [[$resolvedStatusFile]])
"@
    & $ceExecScript -Code $luaCode | Out-Null

    $deadline = [DateTime]::UtcNow.AddSeconds($TimeoutSeconds)
    $lastStatus = $null
    $stimuli = @(
        [pscustomobject]@{ Key = 'w'; HoldMilliseconds = $MovementHoldMilliseconds },
        [pscustomobject]@{ Key = 'space'; HoldMilliseconds = 120 },
        [pscustomobject]@{ Key = 'a'; HoldMilliseconds = [Math]::Min($MovementHoldMilliseconds, 350) }
    )
    $stimulusIndex = 0
    $nextStimulusAt = [DateTime]::UtcNow

    while ([DateTime]::UtcNow -lt $deadline) {
        if ($stimulusIndex -lt $stimuli.Count -and [DateTime]::UtcNow -ge $nextStimulusAt) {
            $stimulus = $stimuli[$stimulusIndex]
            Invoke-TraceStimulus -Key $stimulus.Key -HoldMilliseconds $stimulus.HoldMilliseconds
            $stimulusIndex++
            $nextStimulusAt = [DateTime]::UtcNow.AddMilliseconds([Math]::Max($stimulus.HoldMilliseconds + 400, 750))
        }

        if (Test-Path -LiteralPath $resolvedStatusFile) {
            $status = Read-KeyValueFile -Path $resolvedStatusFile
            $lastStatus = $status

            if ($status.status -eq 'hit') {
                return Convert-StatusToTraceAttempt -Status $status -AddressHex $AddressHex -Source $Source -Success $true
            }

            if ($status.status -eq 'error') {
                return Convert-StatusToTraceAttempt -Status $status -AddressHex $AddressHex -Source $Source -Success $false
            }
        }

        Start-Sleep -Milliseconds 200
    }

    if ($lastStatus) {
        return Convert-StatusToTraceAttempt -Status $lastStatus -AddressHex $AddressHex -Source $Source -Success $false
    }

    return [pscustomobject]@{
        Success = $false
        Status = 'timeout'
        CandidateAddress = $AddressHex
        CandidateSource = $Source
        VerificationMethod = $null
        TargetAddress = $AddressHex
        HitCount = 0
        InstructionAddress = $null
        InstructionSymbol = $null
        Instruction = $null
        InstructionBytes = $null
        InstructionOpcode = $null
        InstructionExtra = $null
        InstructionSize = $null
        WriteOperand = $null
        EffectiveAddress = $null
        AccessMatchesTarget = $null
        ModuleName = $null
        ModuleBase = $null
        ModuleOffset = $null
        Error = $null
        Registers = [ordered]@{}
    }
}

function Add-TraceCandidate {
    param(
        [AllowNull()]
        [System.Collections.Generic.List[object]]$Candidates,

        [AllowNull()]
        [System.Collections.Generic.HashSet[string]]$Seen,

        [string]$AddressHex,

        [string]$Source,

        [string]$FamilyId
    )

    if ($null -eq $Candidates -or $null -eq $Seen) {
        return
    }

    if ([string]::IsNullOrWhiteSpace($AddressHex)) {
        return
    }

    if (-not $Seen.Add($AddressHex)) {
        return
    }

    $Candidates.Add([pscustomobject]@{
        AddressHex = $AddressHex
        Source = $Source
        FamilyId = $FamilyId
    }) | Out-Null
}

function Get-TraceCandidates {
    param(
        [AllowNull()]
        [pscustomobject]$PlayerRead,

        [AllowNull()]
        [pscustomobject]$ProbeCapture,

        [AllowNull()]
        [pscustomobject]$SignatureScan,

        [AllowNull()]
        [string]$ExpectedFamilyId
    )

    $candidates = New-Object System.Collections.Generic.List[object]
    $seen = New-Object 'System.Collections.Generic.HashSet[string]' ([System.StringComparer]::OrdinalIgnoreCase)

    if ($ProbeCapture -and $ProbeCapture.PSObject.Properties['Samples']) {
        $sampleIndex = 0
        foreach ($sample in @($ProbeCapture.Samples)) {
            $sampleIndex++
            Add-TraceCandidate `
                -Candidates $candidates `
                -Seen $seen `
                -AddressHex ([string]$sample.AddressHex) `
                -Source ("capture-sample-{0}" -f $sampleIndex) `
                -FamilyId ([string]$ProbeCapture.FamilyId)
        }
    }

    if ($PlayerRead -and $PlayerRead.PSObject.Properties['Memory']) {
        Add-TraceCandidate `
            -Candidates $candidates `
            -Seen $seen `
            -AddressHex ([string]$PlayerRead.Memory.AddressHex) `
            -Source 'player-current' `
            -FamilyId ([string]$PlayerRead.FamilyId)
    }

    if ($SignatureScan -and $SignatureScan.PSObject.Properties['Families']) {
        foreach ($family in @($SignatureScan.Families)) {
            foreach ($address in @($family.SampleAddresses)) {
                Add-TraceCandidate `
                    -Candidates $candidates `
                    -Seen $seen `
                    -AddressHex ([string]$address) `
                    -Source 'readerbridge-player-signature' `
                    -FamilyId ([string]$family.FamilyId)
            }
        }
    }

    if (Test-Path -LiteralPath $resolvedConfirmationFile) {
        try {
            $confirmation = Get-Content -Path $resolvedConfirmationFile -Raw | ConvertFrom-Json -Depth 20
            $winnerFamilyId = [string]$confirmation.WinnerFamilyId
            if (-not [string]::IsNullOrWhiteSpace($ExpectedFamilyId) -and
                -not [string]::IsNullOrWhiteSpace($winnerFamilyId) -and
                $winnerFamilyId -ne $ExpectedFamilyId) {
                return @($candidates | Select-Object -First $MaxCandidates)
            }

            $winnerAddresses = @($confirmation.Winner.CeConfirmedSampleAddresses)

            foreach ($address in $winnerAddresses) {
                $addressHex = [string]$address
                if ([string]::IsNullOrWhiteSpace($addressHex)) {
                    continue
                }

                Add-TraceCandidate `
                    -Candidates $candidates `
                    -Seen $seen `
                    -AddressHex $addressHex `
                    -Source 'ce-confirmed' `
                    -FamilyId $winnerFamilyId
            }
        }
        catch {
            Write-Warning ("Unable to load CE confirmation candidates from '{0}': {1}" -f $resolvedConfirmationFile, $_.Exception.Message)
        }
    }

    return @($candidates | Select-Object -First $MaxCandidates)
}

function Cleanup-Trace {
    if ($SkipCleanup) {
        return
    }

    try {
        & $ceExecScript -Code "return RiftReaderWriteTrace.cleanup()" | Out-Null
    }
    catch {
        Write-Warning ("Unable to clean up the CE trace helper cleanly: {0}" -f $_.Exception.Message)
    }
}

try {
    if (-not $SkipRefresh) {
        & $refreshScript -NoReader
    }

    $playerRead = $null
    $playerReadError = $null
    try {
        $playerRead = Invoke-ReaderJsonWithRetry -Arguments @('--process-name', 'rift_x64', '--read-player-current', '--json')
    }
    catch {
        $playerReadError = $_.Exception.Message
        Write-Warning ("Unable to resolve --read-player-current; falling back to best-family capture candidates. {0}" -f $playerReadError)
    }

    $probeCapture = $null
    $probeCaptureError = $null
    try {
        $probeCapture = Invoke-ReaderJsonWithRetry -Arguments @('--process-name', 'rift_x64', '--capture-readerbridge-best-family', '--json')
    }
    catch {
        $probeCaptureError = $_.Exception.Message
        if ($null -eq $playerRead) {
            Write-Warning ("Unable to capture best-family candidates after --read-player-current failed. {0}" -f $probeCaptureError)
        }
        else {
            Write-Warning ("Unable to capture live best-family candidates for coord tracing. {0}" -f $probeCaptureError)
        }
    }

    $signatureScan = $null
    $signatureScanError = $null
    if ($null -eq $probeCapture -or @($probeCapture.Samples).Count -le 0) {
        try {
            $signatureScan = Invoke-ReaderJsonWithRetry -Arguments @(
                '--process-name', 'rift_x64',
                '--scan-readerbridge-player-signature',
                '--scan-context', '96',
                '--max-hits', ([Math]::Max($MaxCandidates, 8)).ToString([System.Globalization.CultureInfo]::InvariantCulture),
                '--json')
        }
        catch {
            $signatureScanError = $_.Exception.Message
            Write-Warning ("Unable to load ReaderBridge player-signature candidates for coord tracing. {0}" -f $signatureScanError)
        }
    }

    $expectedFamilyId = if ($probeCapture -and -not [string]::IsNullOrWhiteSpace([string]$probeCapture.FamilyId)) {
        [string]$probeCapture.FamilyId
    }
    elseif ($playerRead -and -not [string]::IsNullOrWhiteSpace([string]$playerRead.FamilyId)) {
        [string]$playerRead.FamilyId
    }
    else {
        $null
    }

    $traceCandidates = @(Get-TraceCandidates -PlayerRead $playerRead -ProbeCapture $probeCapture -SignatureScan $signatureScan -ExpectedFamilyId $expectedFamilyId)
    if ($traceCandidates.Count -le 0) {
        $detailParts = New-Object System.Collections.Generic.List[string]
        if ($playerReadError) {
            $detailParts.Add("player-current: $playerReadError") | Out-Null
        }
        if ($probeCaptureError) {
            $detailParts.Add("best-family: $probeCaptureError") | Out-Null
        }
        if ($signatureScanError) {
            $detailParts.Add("player-signature-scan: $signatureScanError") | Out-Null
        }

        $detail = if ($detailParts.Count -gt 0) { ' ' + ($detailParts -join ' | ') } else { '' }
        throw ("No coord trace candidates were available.{0}" -f $detail)
    }

    $attempts = New-Object System.Collections.Generic.List[object]
    $traceStatus = $null

    foreach ($candidate in $traceCandidates) {
        Write-Host ("[CoordTrace] Attempting candidate {0} ({1})..." -f $candidate.AddressHex, $candidate.Source) -ForegroundColor Cyan
        $attempt = $null
        try {
            $attempt = Get-CoordTraceResult -AddressHex $candidate.AddressHex -Source $candidate.Source
            $attempts.Add($attempt) | Out-Null
        }
        finally {
            Cleanup-Trace
        }

        if ($attempt.Success) {
            $traceStatus = $attempt
            break
        }
    }

    if ($null -eq $traceStatus) {
        $attemptSummary = $attempts | ForEach-Object {
            $summary = "{0}:{1}" -f $_.CandidateAddress, $_.Status
            if ($_.Instruction) {
                $summary += " -> $($_.Instruction)"
            }

            if ($_.AccessOperand) {
                $summary += " [operand=$($_.AccessOperand)"
                if ($_.AccessType) {
                    $summary += ", type=$($_.AccessType)"
                }
                $summary += "]"
            }

            if ($_.EffectiveAddress) {
                $summary += " [ea=$($_.EffectiveAddress)]"
            }

            if ($null -ne $_.MatchedOffset -and $_.MatchedOffset -ne '') {
                $summary += " [offset=$($_.MatchedOffset)]"
            }

            $summary
        }

        throw ("Timed out waiting for a verified coord write trace hit across {0} candidates. {1}" -f $traceCandidates.Count, ($attemptSummary -join '; '))
    }

    $modulePattern = $null
    $normalizedPattern = $null
    if (-not [string]::IsNullOrWhiteSpace($traceStatus.ModuleName) -and -not [string]::IsNullOrWhiteSpace($traceStatus.InstructionBytes)) {
        $normalizedPattern = Convert-ToModulePattern -ByteText $traceStatus.InstructionBytes
        try {
            if ([string]::IsNullOrWhiteSpace($normalizedPattern)) {
                throw "Unable to normalize instruction bytes '$($traceStatus.InstructionBytes)' into an AOB pattern."
            }

            $modulePattern = Invoke-ReaderJson -Arguments @(
                '--process-name', 'rift_x64',
                '--scan-module-pattern', $normalizedPattern,
                '--scan-module-name', $traceStatus.ModuleName,
                '--scan-context', '16',
                '--json')
        }
        catch {
            $modulePattern = [pscustomobject]@{
                Mode = 'module-pattern-scan'
                Error = $_.Exception.Message
            }
        }
    }

    $result = [ordered]@{
        Mode = 'player-coord-write-trace'
        GeneratedAtUtc = [DateTimeOffset]::UtcNow.ToString('O', [System.Globalization.CultureInfo]::InvariantCulture)
        Reader = if ($playerRead) {
            $playerRead
        }
        elseif ($probeCapture) {
            [ordered]@{
                Mode = [string]$probeCapture.Mode
                ProcessId = [int]$probeCapture.ProcessId
                ProcessName = [string]$probeCapture.ProcessName
            }
        }
        else {
            [ordered]@{
                Mode = 'coord-trace-reader'
                ProcessId = $null
                ProcessName = 'rift_x64'
            }
        }
        PlayerRead = $playerRead
        ReaderError = $playerReadError
        ProbeCapture = $probeCapture
        ProbeCaptureError = $probeCaptureError
        SignatureScan = $signatureScan
        SignatureScanError = $signatureScanError
        Candidates = [ordered]@{
            ConfirmationFile = $resolvedConfirmationFile
            Count = $traceCandidates.Count
            Attempts = @($attempts.ToArray())
            SelectedAddress = $traceStatus.CandidateAddress
            SelectedSource = $traceStatus.CandidateSource
        }
        Trace = [ordered]@{
            Status = $traceStatus.Status
            VerificationMethod = $traceStatus.VerificationMethod
            CandidateAddress = $traceStatus.CandidateAddress
            CandidateSource = $traceStatus.CandidateSource
            TargetAddress = $traceStatus.TargetAddress
            HitCount = $traceStatus.HitCount
            InstructionAddress = $traceStatus.InstructionAddress
            InstructionSymbol = $traceStatus.InstructionSymbol
            Instruction = $traceStatus.Instruction
            InstructionBytes = $traceStatus.InstructionBytes
            NormalizedPattern = $normalizedPattern
            InstructionOpcode = $traceStatus.InstructionOpcode
            InstructionExtra = $traceStatus.InstructionExtra
            InstructionSize = $traceStatus.InstructionSize
            WriteOperand = $traceStatus.WriteOperand
            AccessOperand = $traceStatus.AccessOperand
            AccessType = $traceStatus.AccessType
            EffectiveAddress = $traceStatus.EffectiveAddress
            AccessMatchesTarget = $traceStatus.AccessMatchesTarget
            MatchedOffset = $traceStatus.MatchedOffset
            ModuleName = $traceStatus.ModuleName
            ModuleBase = $traceStatus.ModuleBase
            ModuleOffset = $traceStatus.ModuleOffset
            Registers = $traceStatus.Registers
        }
        ModulePattern = $modulePattern
        OutputFile = $resolvedOutputFile
    }

    $outputDirectory = Split-Path -Parent $resolvedOutputFile
    if (-not [string]::IsNullOrWhiteSpace($outputDirectory)) {
        New-Item -ItemType Directory -Path $outputDirectory -Force | Out-Null
    }

    $jsonText = $result | ConvertTo-Json -Depth 10
    Set-Content -Path $resolvedOutputFile -Value $jsonText -Encoding UTF8

    if ($Json) {
        Write-Output $jsonText
    }
    else {
        Write-Host "Trace file:           $resolvedOutputFile"
        if ($playerRead) {
            Write-Host "Player sample:        $($playerRead.Memory.AddressHex)"
        }
        elseif ($probeCapture -and @($probeCapture.Samples).Count -gt 0) {
            Write-Host "Capture sample:       $($probeCapture.Samples[0].AddressHex)"
        }
        Write-Host "Trace candidate:      $($traceStatus.CandidateAddress) [$($traceStatus.CandidateSource)]"
        Write-Host "Coord write target:   $($traceStatus.TargetAddress)"
        if ($traceStatus.VerificationMethod) {
            Write-Host "Verification:         $($traceStatus.VerificationMethod)"
        }
        Write-Host "Writer RIP:           $($traceStatus.InstructionAddress)"
        Write-Host "Writer symbol:        $($traceStatus.InstructionSymbol)"
        Write-Host "Instruction:          $($traceStatus.Instruction)"
        if ($traceStatus.WriteOperand) {
            Write-Host "Write operand:        $($traceStatus.WriteOperand)"
        }
        if ($traceStatus.AccessOperand) {
            Write-Host "Access operand:       $($traceStatus.AccessOperand)"
        }
        if ($traceStatus.AccessType) {
            Write-Host "Access type:          $($traceStatus.AccessType)"
        }
        if ($traceStatus.EffectiveAddress) {
            Write-Host "Effective address:    $($traceStatus.EffectiveAddress)"
        }
        if ($null -ne $traceStatus.MatchedOffset -and $traceStatus.MatchedOffset -ne '') {
            Write-Host "Matched offset:       $($traceStatus.MatchedOffset)"
        }
        Write-Host "Module pattern bytes: $($traceStatus.InstructionBytes)"
        if ($modulePattern -and $modulePattern.Found -eq $true) {
            Write-Host "Pattern match:        $($modulePattern.Address) in $($modulePattern.ModuleName)"
        }
    }
}
finally {
    Cleanup-Trace
}
