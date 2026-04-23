[CmdletBinding()]
param(
    [switch]$Json,
    [switch]$SkipRefresh,
    [switch]$SkipCleanup,
    [switch]$ProofReacquisition,
    [string]$CandidateAddressHex,
    [string]$CandidateSource = 'explicit-candidate',
    [string]$StimulusKey = 'w',
    [int]$MovementHoldMilliseconds = 1000,
    [ValidateSet('PostMessage', 'SendInput', 'AutoHotkey')]
    [string]$StimulusMode = 'PostMessage',
    [int]$TimeoutSeconds = 8,
    [int]$MaxCandidates = 8,
    [int]$BreakpointSize = 4,
    [ValidateSet('write', 'access')]
    [string]$WatchMode = 'write',
    [string]$ConfirmationFile = (Join-Path $PSScriptRoot 'captures\ce-smart-player-family.json'),
    [string]$SourceChainFile = (Join-Path $PSScriptRoot 'captures\player-source-chain.json'),
    [string]$SelectorOwnerTraceFile = (Join-Path $PSScriptRoot 'captures\player-selector-owner-trace.json'),
    [string]$OutputFile = (Join-Path $PSScriptRoot 'captures\player-coord-write-trace.json'),
    [string]$TraceStatusFile = (Join-Path $PSScriptRoot 'captures\player-coord-write-trace.status.txt')
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$readerProject = Join-Path $repoRoot 'reader\RiftReader.Reader\RiftReader.Reader.csproj'
$refreshScript = Join-Path $PSScriptRoot 'refresh-readerbridge-export.ps1'
$smartCaptureScript = Join-Path $PSScriptRoot 'smart-capture-player-family.ps1'
$postKeyScript = Join-Path $PSScriptRoot 'post-rift-key.ps1'
$sendKeyScript = Join-Path $PSScriptRoot 'send-rift-key.ps1'
$sendKeyAhkScript = Join-Path $PSScriptRoot 'send-rift-key-ahk.ps1'
$ceExecScript = Join-Path $PSScriptRoot 'cheatengine-exec.ps1'
$traceLuaFile = Join-Path $PSScriptRoot 'cheat-engine\RiftReaderWriteTrace.lua'
$resolvedConfirmationFile = [System.IO.Path]::GetFullPath($ConfirmationFile)
$resolvedSourceChainFile = [System.IO.Path]::GetFullPath($SourceChainFile)
$resolvedSelectorOwnerTraceFile = [System.IO.Path]::GetFullPath($SelectorOwnerTraceFile)
$resolvedOutputFile = [System.IO.Path]::GetFullPath($OutputFile)
$resolvedStatusFile = [System.IO.Path]::GetFullPath($TraceStatusFile)

if ($ProofReacquisition -and $WatchMode -eq 'access' -and -not $PSBoundParameters.ContainsKey('BreakpointSize')) {
    $BreakpointSize = 12
}

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

function Format-HexAddress {
    param(
        [Parameter(Mandatory = $true)]
        [UInt64]$Value
    )

    return ('0x{0:X}' -f $Value)
}

function Try-ConvertToUInt64 {
    param(
        [string]$AddressHex
    )

    if ([string]::IsNullOrWhiteSpace($AddressHex)) {
        return $null
    }

    try {
        return (Parse-HexAddress -AddressHex $AddressHex)
    }
    catch {
        return $null
    }
}

function Test-LikelyPointerHex {
    param(
        [string]$AddressHex
    )

    $value = Try-ConvertToUInt64 -AddressHex $AddressHex
    if ($null -eq $value) {
        return $false
    }

    if ($value -lt 0x0000010000000000) {
        return $false
    }

    if ($value -gt 0x00007FFFFFFFFFFF) {
        return $false
    }

    return $true
}

function Convert-HexAddressWithOffset {
    param(
        [string]$AddressHex,
        [int]$Offset
    )

    $baseValue = Try-ConvertToUInt64 -AddressHex $AddressHex
    if ($null -eq $baseValue) {
        return $null
    }

    return Format-HexAddress -Value ([UInt64]($baseValue + [UInt64]$Offset))
}

function Get-CurrentTargetProcessId {
    try {
        return [int](Get-Process -Name 'rift_x64' -ErrorAction Stop | Sort-Object StartTime -Descending | Select-Object -First 1 -ExpandProperty Id)
    }
    catch {
        return $null
    }
}

function Get-ConcurrentDebuggerProcesses {
    $processNamePattern = '^(windbg|windbgx|x64dbg|x32dbg|ollydbg|ida|ida64|ghidra|processhacker|procexp|procmon)$'
    return @(
        Get-Process -ErrorAction SilentlyContinue |
            Where-Object {
                $_.Id -ne $PID -and
                $_.ProcessName -match $processNamePattern
            } |
            Sort-Object ProcessName, Id |
            Select-Object ProcessName, Id, Path
    )
}

function Add-BreakpointWorkflowNotes {
    param(
        $Notes
    )

    if ($null -eq $Notes) {
        return
    }

    $breakpointNote = 'Coord trace proof uses live debugger-backed breakpoints. The current preferred proof path is CE debug-register breakpoints with access watch mode; treat VEH/page-exception as exploratory only.'
    $Notes.Add($breakpointNote) | Out-Null

    if (-not $Json) {
        Write-Host "[CoordTrace] $breakpointNote" -ForegroundColor Yellow
    }

    $concurrentDebuggerProcesses = @(Get-ConcurrentDebuggerProcesses)
    if ($concurrentDebuggerProcesses.Count -le 0) {
        return
    }

    $processSummary = ($concurrentDebuggerProcesses | ForEach-Object {
            if ([string]::IsNullOrWhiteSpace($_.Path)) {
                "{0} ({1})" -f $_.ProcessName, $_.Id
            }
            else {
                "{0} ({1}) @ {2}" -f $_.ProcessName, $_.Id, $_.Path
            }
        }) -join '; '

    $warningMessage = "Detected other debugger-class tools while arming CE breakpoint tracing: $processSummary. Avoid concurrent debugger attaches during proof runs."
    $Notes.Add($warningMessage) | Out-Null
    Write-Warning $warningMessage
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
    $fileShare = [System.IO.FileShare]::ReadWrite -bor [System.IO.FileShare]::Delete
    $fileMode = [System.IO.FileMode]::Open
    $fileAccess = [System.IO.FileAccess]::Read
    $lines = @()

    $stream = [System.IO.FileStream]::new($Path, $fileMode, $fileAccess, $fileShare)
    try {
        $reader = [System.IO.StreamReader]::new($stream)
        try {
            while (-not $reader.EndOfStream) {
                $lines += $reader.ReadLine()
            }
        }
        finally {
            $reader.Dispose()
        }
    }
    finally {
        $stream.Dispose()
    }

    foreach ($line in $lines) {
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

function Add-UniqueTraceCandidate {
    param(
        [Parameter(Mandatory = $true)]
        $Candidates,

        [Parameter(Mandatory = $true)]
        $Seen,

        [string]$AddressHex,

        [Parameter(Mandatory = $true)]
        [string]$Source,

        [string]$FamilyId
    )

    if ([string]::IsNullOrWhiteSpace($AddressHex)) {
        return
    }

    if ($Seen.Add($AddressHex)) {
        $Candidates.Add([pscustomobject]@{
                AddressHex = $AddressHex
                Source = $Source
                FamilyId = $FamilyId
            }) | Out-Null
    }
}

function Add-ProofReacquisitionSeeds {
    param(
        [Parameter(Mandatory = $true)]
        $Candidates,

        [Parameter(Mandatory = $true)]
        $Seen,

        [Parameter(Mandatory = $true)]
        $Notes
    )

    $currentProcessId = Get-CurrentTargetProcessId

    if (Test-Path -LiteralPath $resolvedOutputFile) {
        try {
            $traceDocument = Get-Content -LiteralPath $resolvedOutputFile -Raw | ConvertFrom-Json -Depth 40
            $documentMode = if ($traceDocument.PSObject.Properties['Mode']) { [string]$traceDocument.Mode } else { $null }
            $documentStatus = if ($traceDocument.PSObject.Properties['Status']) { [string]$traceDocument.Status } else { $null }
            if ($documentMode -eq 'player-coord-write-trace' -and $documentStatus -ne 'failed') {
                $traceProcessId = $null
                if ($traceDocument.PSObject.Properties['Reader'] -and $traceDocument.Reader -and $traceDocument.Reader.PSObject.Properties['ProcessId']) {
                    $traceProcessId = [int]$traceDocument.Reader.ProcessId
                }

                if ($null -ne $currentProcessId -and $null -ne $traceProcessId -and $traceProcessId -ne $currentProcessId) {
                    $Notes.Add(("Skipped last-good trace seeds because trace PID {0} does not match live PID {1}." -f $traceProcessId, $currentProcessId)) | Out-Null
                }
                else {
                    $sourceObjectAddress = if ($traceDocument.PSObject.Properties['SourceObjectRegisterValue']) {
                        [string]$traceDocument.SourceObjectRegisterValue
                    }
                    elseif ($traceDocument.PSObject.Properties['Trace'] -and $traceDocument.Trace.PSObject.Properties['Registers']) {
                        [string]$traceDocument.Trace.Registers.RDI
                    }
                    else {
                        $null
                    }

                    if (Test-LikelyPointerHex -AddressHex $sourceObjectAddress) {
                        $sourceCoordAddress = Convert-HexAddressWithOffset -AddressHex $sourceObjectAddress -Offset 0x48
                        Add-UniqueTraceCandidate -Candidates $Candidates -Seen $Seen -AddressHex $sourceCoordAddress -Source 'last-good-trace-source-object-coord-region'
                    }
                    else {
                        $Notes.Add(("Skipped last-good trace source-object seed because source register '{0}' did not look like a valid pointer." -f $sourceObjectAddress)) | Out-Null
                    }

                    $traceTargetAddress = if ($traceDocument.PSObject.Properties['Trace']) { [string]$traceDocument.Trace.TargetAddress } else { $null }
                    Add-UniqueTraceCandidate -Candidates $Candidates -Seen $Seen -AddressHex $traceTargetAddress -Source 'last-good-trace-target'

                    $traceCandidateAddress = if ($traceDocument.PSObject.Properties['Trace']) { [string]$traceDocument.Trace.CandidateAddress } else { $null }
                    Add-UniqueTraceCandidate -Candidates $Candidates -Seen $Seen -AddressHex $traceCandidateAddress -Source 'last-good-trace-candidate'
                }
            }
            else {
                $Notes.Add('Skipped canonical trace seeds because the saved trace artifact is not a successful trace document.') | Out-Null
            }
        }
        catch {
            $Notes.Add(("Unable to load canonical trace seeds from '{0}': {1}" -f $resolvedOutputFile, $_.Exception.Message)) | Out-Null
        }
    }
    else {
        $Notes.Add(("Canonical trace artifact not found: {0}" -f $resolvedOutputFile)) | Out-Null
    }

    if (Test-Path -LiteralPath $resolvedSourceChainFile) {
        try {
            $sourceChain = Get-Content -LiteralPath $resolvedSourceChainFile -Raw | ConvertFrom-Json -Depth 30
            $selectedSourceAddress = if ($sourceChain.PSObject.Properties['SelectedSourceAddress']) {
                [string]$sourceChain.SelectedSourceAddress
            }
            else {
                [string]$sourceChain.SourceObjectAddress
            }

            $returnOffset = $null
            if ($sourceChain.PSObject.Properties['Accessor'] -and $sourceChain.Accessor.PSObject.Properties['ReturnOffset']) {
                $returnOffset = [int]$sourceChain.Accessor.ReturnOffset
            }

            if (-not [string]::IsNullOrWhiteSpace($selectedSourceAddress) -and $null -ne $returnOffset) {
                $sourceChainCoordAddress = Convert-HexAddressWithOffset -AddressHex $selectedSourceAddress -Offset $returnOffset
                Add-UniqueTraceCandidate -Candidates $Candidates -Seen $Seen -AddressHex $sourceChainCoordAddress -Source 'debug-scan-source-chain-coord-region'
            }
            else {
                $Notes.Add(("Skipped debug-scan source-chain seed because '{0}' did not expose SelectedSourceAddress + Accessor.ReturnOffset." -f $resolvedSourceChainFile)) | Out-Null
            }
        }
        catch {
            $Notes.Add(("Unable to load debug-scan source-chain seeds from '{0}': {1}" -f $resolvedSourceChainFile, $_.Exception.Message)) | Out-Null
        }
    }
    else {
        $Notes.Add(("Debug-scan source-chain file not found: {0}" -f $resolvedSourceChainFile)) | Out-Null
    }

    if (Test-Path -LiteralPath $resolvedSelectorOwnerTraceFile) {
        try {
            $selectorOwnerTrace = Get-Content -LiteralPath $resolvedSelectorOwnerTraceFile -Raw | ConvertFrom-Json -Depth 30
            $selectedSourceAddress = if ($selectorOwnerTrace.PSObject.Properties['SelectedSource'] -and $selectorOwnerTrace.SelectedSource.PSObject.Properties['Address']) {
                [string]$selectorOwnerTrace.SelectedSource.Address
            }
            else {
                $null
            }

            if (-not [string]::IsNullOrWhiteSpace($selectedSourceAddress)) {
                $selectorCoord48Address = Convert-HexAddressWithOffset -AddressHex $selectedSourceAddress -Offset 0x48
                Add-UniqueTraceCandidate -Candidates $Candidates -Seen $Seen -AddressHex $selectorCoord48Address -Source 'debug-scan-selector-owner-coord48'
            }
            else {
                $Notes.Add(("Skipped selector-owner debug-scan seed because '{0}' did not expose SelectedSource.Address." -f $resolvedSelectorOwnerTraceFile)) | Out-Null
            }
        }
        catch {
            $Notes.Add(("Unable to load selector-owner debug-scan seeds from '{0}': {1}" -f $resolvedSelectorOwnerTraceFile, $_.Exception.Message)) | Out-Null
        }
    }
    else {
        $Notes.Add(("Selector-owner debug-scan file not found: {0}" -f $resolvedSelectorOwnerTraceFile)) | Out-Null
    }
}

function Test-CanUsePlayerReadAsProofSeed {
    param(
        $PlayerRead,
        [ref]$Reason
    )

    $Reason.Value = $null

    if ($null -eq $PlayerRead -or $null -eq $PlayerRead.Memory -or [string]::IsNullOrWhiteSpace([string]$PlayerRead.Memory.AddressHex)) {
        $Reason.Value = 'Current-player read did not expose a usable coordinate address.'
        return $false
    }

    $selectionSource = if ($PlayerRead.PSObject.Properties['SelectionSource']) { [string]$PlayerRead.SelectionSource } else { $null }
    $anchorCacheUsed = if ($PlayerRead.PSObject.Properties['AnchorCacheUsed']) { [bool]$PlayerRead.AnchorCacheUsed } else { $false }

    if ($anchorCacheUsed) {
        $Reason.Value = ("Blocked current-player proof seed because AnchorCacheUsed=true (selection source '{0}')." -f $selectionSource)
        return $false
    }

    if ($selectionSource -in @('heuristic', 'cached-anchor')) {
        $Reason.Value = ("Blocked current-player proof seed because SelectionSource='{0}' is not proof-safe." -f $selectionSource)
        return $false
    }

    return $true
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
        WatchMode = Get-ObjectValue -Object $Status -Name 'watchMode'
        BreakpointMethod = Get-ObjectValue -Object $Status -Name 'breakpointMethod'
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

    $watchModeLiteral = "[[$WatchMode]]"
    $luaCode = @"
return RiftReaderWriteTrace.arm('rift_x64', $coordAddress, $BreakpointSize, [[$resolvedStatusFile]], nil, nil, $watchModeLiteral)
"@
    & $ceExecScript -Code $luaCode | Out-Null

    switch ($StimulusMode) {
        'PostMessage' {
            & $postKeyScript -Key $StimulusKey -HoldMilliseconds $MovementHoldMilliseconds
        }
        'SendInput' {
            & $sendKeyScript -Key $StimulusKey -HoldMilliseconds $MovementHoldMilliseconds -NoRefocus
        }
        'AutoHotkey' {
            & $sendKeyAhkScript -Key $StimulusKey -HoldMilliseconds $MovementHoldMilliseconds -NoRefocus
        }
        default {
            throw "Unsupported stimulus mode '$StimulusMode'."
        }
    }

    if ($LASTEXITCODE -ne 0) {
        throw "Stimulus key '$StimulusKey' failed via mode '$StimulusMode'."
    }

    $deadline = [DateTime]::UtcNow.AddSeconds($TimeoutSeconds)
    $lastStatus = $null

    while ([DateTime]::UtcNow -lt $deadline) {
        if (Test-Path -LiteralPath $resolvedStatusFile) {
            $status = Read-KeyValueFile -Path $resolvedStatusFile
            $lastStatus = $status
            $statusKind = [string](Get-ObjectValue -Object $status -Name 'status')

            if ($statusKind -eq 'hit') {
                return Convert-StatusToTraceAttempt -Status $status -AddressHex $AddressHex -Source $Source -Success $true
            }

            if ($statusKind -eq 'error') {
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
        WatchMode = $WatchMode
        BreakpointMethod = $null
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

function Test-IsReadLikeCoordTraceAttempt {
    param(
        [Parameter(Mandatory = $true)]
        $Attempt,

        [ref]$Reason
    )

    $Reason.Value = $null

    if ($null -eq $Attempt) {
        $Reason.Value = 'Trace attempt result was null.'
        return $false
    }

    if (-not $Attempt.Success) {
        $Reason.Value = 'Trace attempt did not succeed.'
        return $false
    }

    $opcodeText = [string]$Attempt.InstructionOpcode
    if ([string]::IsNullOrWhiteSpace($opcodeText)) {
        $opcodeText = [string]$Attempt.Instruction
    }

    if ([string]::IsNullOrWhiteSpace($opcodeText)) {
        $Reason.Value = 'Trace hit did not expose an instruction opcode.'
        return $false
    }

    $normalizedOpcode = $opcodeText.Trim().ToLowerInvariant()
    if ($normalizedOpcode -notmatch '\[[^]]+\]') {
        $Reason.Value = 'Trace hit did not expose a memory operand.'
        return $false
    }

    if ($normalizedOpcode -match '^[a-z0-9]+\s+\[[^]]+\]\s*,') {
        $Reason.Value = 'Trace hit used a memory-destination/write-like instruction.'
        return $false
    }

    return $true
}

function Get-TraceCandidates {
    param(
        [pscustomobject]$PlayerRead,
        [System.Collections.Generic.List[string]]$Notes
    )

    $candidates = New-Object System.Collections.Generic.List[object]
    $seen = New-Object 'System.Collections.Generic.HashSet[string]' ([System.StringComparer]::OrdinalIgnoreCase)

    if (-not [string]::IsNullOrWhiteSpace($CandidateAddressHex)) {
        $candidates.Add([pscustomobject]@{
                AddressHex = $CandidateAddressHex
                Source = $CandidateSource
                FamilyId = $null
            }) | Out-Null

        return @($candidates.ToArray())
    }

    if ($ProofReacquisition) {
        if ($null -eq $Notes) {
            $Notes = New-Object System.Collections.Generic.List[string]
        }

        Add-ProofReacquisitionSeeds -Candidates $candidates -Seen $seen -Notes $Notes

        if ($null -ne $PlayerRead) {
            $proofSeedReason = $null
            if (Test-CanUsePlayerReadAsProofSeed -PlayerRead $PlayerRead -Reason ([ref]$proofSeedReason)) {
                Add-UniqueTraceCandidate -Candidates $candidates -Seen $seen -AddressHex ([string]$PlayerRead.Memory.AddressHex) -Source 'player-current-proof-safe' -FamilyId ([string]$PlayerRead.FamilyId)
            }
            elseif (-not [string]::IsNullOrWhiteSpace($proofSeedReason)) {
                $Notes.Add($proofSeedReason) | Out-Null
            }
        }

        $Notes.Add('Proof reacquisition intentionally skipped CE family scan candidates to prefer non-heuristic last-good trace and debug-scan seeds first.') | Out-Null
        return @($candidates | Select-Object -First $MaxCandidates)
    }

    if ($null -ne $PlayerRead -and $null -ne $PlayerRead.Memory) {
        Add-UniqueTraceCandidate -Candidates $candidates -Seen $seen -AddressHex ([string]$PlayerRead.Memory.AddressHex) -Source 'player-current' -FamilyId ([string]$PlayerRead.FamilyId)
    }

    if (Test-Path -LiteralPath $resolvedConfirmationFile) {
        try {
            $confirmation = Get-Content -Path $resolvedConfirmationFile -Raw | ConvertFrom-Json -Depth 20
            $winnerFamilyId = [string]$confirmation.WinnerFamilyId
            $candidateBuckets = @(
                [pscustomobject]@{
                    Source = 'ce-confirmed'
                    FamilyId = $winnerFamilyId
                    Addresses = @($confirmation.Winner.CeConfirmedSampleAddresses)
                },
                [pscustomobject]@{
                    Source = 'ce-triplet-confirmed'
                    FamilyId = $winnerFamilyId
                    Addresses = @($confirmation.TripletConfirmedAddresses)
                },
                [pscustomobject]@{
                    Source = 'ce-ranked-family'
                    FamilyId = $winnerFamilyId
                    Addresses = @($confirmation.Winner.SampleAddresses)
                }
            )

            foreach ($family in @($confirmation.Families)) {
                $candidateBuckets += [pscustomobject]@{
                    Source = 'ce-family-sample'
                    FamilyId = [string]$family.FamilyId
                    Addresses = @($family.SampleAddresses)
                }
            }

            foreach ($attempt in @($confirmation.Attempts | Where-Object { $_.MotionObserved })) {
                $candidateBuckets += [pscustomobject]@{
                    Source = ('ce-axis-{0}' -f ([string]$attempt.Axis).ToLowerInvariant())
                    FamilyId = $winnerFamilyId
                    Addresses = @($attempt.RetrievedCeAddresses)
                }
            }

            foreach ($bucket in $candidateBuckets) {
                foreach ($address in @($bucket.Addresses)) {
                    Add-UniqueTraceCandidate -Candidates $candidates -Seen $seen -AddressHex ([string]$address) -Source ([string]$bucket.Source) -FamilyId ([string]$bucket.FamilyId)
                }
            }
        }
        catch {
            Write-Warning ("Unable to load CE confirmation candidates from '{0}': {1}" -f $resolvedConfirmationFile, $_.Exception.Message)
        }
    }

    return @($candidates | Select-Object -First $MaxCandidates)
}

function Test-HasUsableConfirmation {
    if (-not (Test-Path -LiteralPath $resolvedConfirmationFile)) {
        return $false
    }

    try {
        $confirmation = Get-Content -LiteralPath $resolvedConfirmationFile -Raw | ConvertFrom-Json -Depth 20
        if (@($confirmation.Winner.CeConfirmedSampleAddresses).Count -gt 0) {
            return $true
        }

        if (@($confirmation.TripletConfirmedAddresses).Count -gt 0) {
            return $true
        }

        if (@($confirmation.Winner.SampleAddresses).Count -gt 0) {
            return $true
        }

        foreach ($attempt in @($confirmation.Attempts)) {
            if ($attempt.MotionObserved -and @($attempt.RetrievedCeAddresses).Count -gt 0) {
                return $true
            }
        }

        return $false
    }
    catch {
        Write-Warning ("Unable to evaluate CE confirmation file '{0}': {1}" -f $resolvedConfirmationFile, $_.Exception.Message)
        return $false
    }
}

function Ensure-CeConfirmation {
    if (Test-HasUsableConfirmation) {
        return
    }

    try {
        Write-Host "[CoordTrace] No usable CE-confirmed family sample is available; attempting a fresh smart capture first..." -ForegroundColor Yellow
        & $smartCaptureScript -MovementHoldMilliseconds $MovementHoldMilliseconds | Out-Null
    }
    catch {
        Write-Warning ("CE-backed smart capture failed before trace; continuing with current-player candidates only. {0}" -f $_.Exception.Message)
    }
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

function Write-TraceArtifact {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path,

        [Parameter(Mandatory = $true)]
        $Document
    )

    $outputDirectory = Split-Path -Parent $Path
    if (-not [string]::IsNullOrWhiteSpace($outputDirectory)) {
        New-Item -ItemType Directory -Path $outputDirectory -Force | Out-Null
    }

    $jsonText = $Document | ConvertTo-Json -Depth 10
    Set-Content -Path $Path -Value $jsonText -Encoding UTF8
    return $jsonText
}

function Get-FailureTraceArtifactPath {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path
    )

    $directory = Split-Path -Parent $Path
    $fileName = [System.IO.Path]::GetFileNameWithoutExtension($Path)
    $extension = [System.IO.Path]::GetExtension($Path)
    if ([string]::IsNullOrWhiteSpace($extension)) {
        $extension = '.json'
    }

    return Join-Path $directory ("{0}.failed{1}" -f $fileName, $extension)
}

function Move-CanonicalFailureArtifactAside {
    param(
        [Parameter(Mandatory = $true)]
        [string]$CanonicalPath
    )

    if (-not (Test-Path -LiteralPath $CanonicalPath)) {
        return
    }

    $document = $null
    try {
        $document = Get-Content -LiteralPath $CanonicalPath -Raw | ConvertFrom-Json -Depth 20
    }
    catch {
        return
    }

    $documentMode = if ($document.PSObject.Properties['Mode']) { [string]$document.Mode } else { $null }
    $documentStatus = if ($document.PSObject.Properties['Status']) { [string]$document.Status } else { $null }

    if ($documentMode -ne 'player-coord-write-trace' -or $documentStatus -ne 'failed') {
        return
    }

    $failurePath = Get-FailureTraceArtifactPath -Path $CanonicalPath
    Move-Item -LiteralPath $CanonicalPath -Destination $failurePath -Force
}

$playerRead = $null
$playerReadError = $null
$traceCandidates = @()
$attempts = New-Object System.Collections.Generic.List[object]
$candidateGenerationNotes = New-Object System.Collections.Generic.List[string]
$traceStatus = $null

Move-CanonicalFailureArtifactAside -CanonicalPath $resolvedOutputFile
Add-BreakpointWorkflowNotes -Notes $candidateGenerationNotes

try {
    if (-not $SkipRefresh) {
        & $refreshScript -NoReader
    }

    try {
        $playerRead = Invoke-ReaderJson -Arguments @('--process-name', 'rift_x64', '--read-player-current', '--json')
    }
    catch {
        $playerReadError = $_.Exception.Message
        Write-Warning ("Unable to refresh the current-player snapshot before trace; continuing with CE-derived candidates only. {0}" -f $playerReadError)
    }

    if ($null -eq $playerRead -and -not [string]::IsNullOrWhiteSpace($playerReadError) -and
        $playerReadError.Contains('No grouped player-signature families were found', [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Current player snapshot is not ready after refresh; ReaderBridge/Validator exports do not yet contain grouped player-signature families. Wait until the character is fully loaded in-world, then rerun trace-player-coord-write.ps1."
    }

    Ensure-CeConfirmation

    $traceCandidates = @(Get-TraceCandidates -PlayerRead $playerRead -Notes $candidateGenerationNotes)
    if ($traceCandidates.Count -le 0) {
        if ($ProofReacquisition) {
            $notesText = if ($candidateGenerationNotes.Count -gt 0) { ' ' + (($candidateGenerationNotes.ToArray()) -join ' ') } else { '' }
            throw ("No proof-safe non-heuristic trace seeds were available for proof reacquisition.{0} Refresh debug-scanned source artifacts (player-source-chain / player-coord-trace-cluster) or supply -CandidateAddressHex explicitly." -f $notesText)
        }

        if (-not [string]::IsNullOrWhiteSpace($playerReadError)) {
            throw "No coord trace candidates were available after the current-player snapshot failed. $playerReadError"
        }

        throw "No coord trace candidates were available."
    }

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
            $rejectedReason = $null
            if (-not (Test-IsReadLikeCoordTraceAttempt -Attempt $attempt -Reason ([ref]$rejectedReason))) {
                $attempt | Add-Member -NotePropertyName 'RejectedReason' -NotePropertyValue $rejectedReason -Force
                $attempt.Success = $false
                $attempt.Status = 'rejected'
                $attempt.Error = $rejectedReason
                Write-Warning ("Rejected trace hit at {0}: {1}" -f $candidate.AddressHex, $rejectedReason)
                continue
            }

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

        $timeoutMessage = "Timed out waiting for a verified coord {0} trace hit across {1} candidates. {2}" -f $WatchMode, $traceCandidates.Count, ($attemptSummary -join '; ')
        if ($WatchMode -eq 'write') {
            $timeoutMessage += " Try rerunning with -WatchMode access"
            if ($StimulusMode -ne 'AutoHotkey') {
                $timeoutMessage += " -StimulusMode AutoHotkey"
            }
            $timeoutMessage += '.'
        }

        throw $timeoutMessage
    }

    $modulePattern = $null
    $normalizedPattern = $null
    $postTracePlayerRead = $null
    $postTracePlayerReadError = $null
    $postTracePlayerReadCapturedAtUtc = $null

    try {
        $postTracePlayerRead = Invoke-ReaderJson -Arguments @('--process-name', 'rift_x64', '--read-player-current', '--json')
        $postTracePlayerReadCapturedAtUtc = [DateTimeOffset]::UtcNow.ToString('O', [System.Globalization.CultureInfo]::InvariantCulture)
    }
    catch {
        $postTracePlayerReadError = $_.Exception.Message
        Write-Warning ("Unable to capture a post-trace current-player snapshot immediately after the coord trace hit. {0}" -f $postTracePlayerReadError)
    }

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
        SourceObjectRegisterValue = $(if ($null -ne $traceStatus.Registers) { [string]$traceStatus.Registers.RDI } else { $null })
        ReaderError = $playerReadError
        Reader = $playerRead
        ProofReacquisition = [bool]$ProofReacquisition
        CandidateGenerationNotes = @($candidateGenerationNotes.ToArray())
        PostTraceReaderCapturedAtUtc = $postTracePlayerReadCapturedAtUtc
        PostTraceReaderError = $postTracePlayerReadError
        PostTraceReader = $postTracePlayerRead
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
            WatchMode = $traceStatus.WatchMode
            BreakpointMethod = $traceStatus.BreakpointMethod
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

    $jsonText = Write-TraceArtifact -Path $resolvedOutputFile -Document $result

    if ($Json) {
        Write-Output $jsonText
    }
    else {
        Write-Host "Trace file:           $resolvedOutputFile"
        Write-Host "Player sample:        $($playerRead.Memory.AddressHex)"
        Write-Host "Trace candidate:      $($traceStatus.CandidateAddress) [$($traceStatus.CandidateSource)]"
        Write-Host "Coord write target:   $($traceStatus.TargetAddress)"
        if ($traceStatus.VerificationMethod) {
            Write-Host "Verification:         $($traceStatus.VerificationMethod)"
        }
        if ($traceStatus.WatchMode) {
            Write-Host "Watch mode:           $($traceStatus.WatchMode)"
        }
        if ($traceStatus.BreakpointMethod) {
            Write-Host "Breakpoint method:    $($traceStatus.BreakpointMethod)"
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
catch {
    $failureArtifactPath = Get-FailureTraceArtifactPath -Path $resolvedOutputFile
    $failureDocument = [ordered]@{
        Mode = 'player-coord-write-trace'
        Status = 'failed'
        GeneratedAtUtc = [DateTimeOffset]::UtcNow.ToString('O', [System.Globalization.CultureInfo]::InvariantCulture)
        FailureMessage = $_.Exception.Message
        ReaderError = $playerReadError
        Reader = $playerRead
        ProofReacquisition = [bool]$ProofReacquisition
        CandidateGenerationNotes = @($candidateGenerationNotes.ToArray())
        Candidates = [ordered]@{
            ConfirmationFile = $resolvedConfirmationFile
            Count = @($traceCandidates).Count
            Attempts = @($attempts.ToArray())
        }
        OutputFile = $resolvedOutputFile
        FailureArtifactFile = $failureArtifactPath
    }

    $jsonText = Write-TraceArtifact -Path $failureArtifactPath -Document $failureDocument
    if ($Json) {
        Write-Output $jsonText
    }

    throw
}
finally {
    Cleanup-Trace
}
