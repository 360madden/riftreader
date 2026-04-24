[CmdletBinding()]
param(
    [string]$ProcessName = 'rift_x64',
    [int]$ProcessId,
    [string]$RunLabel = 'tooltip-hover-diff',
    [string]$OutputRoot,
    [Parameter(Mandatory = $true)]
    [string]$CandidateAddress,
    [int]$CandidateLength = 1024,
    [string]$TooltipText = 'Send and receive mail here.',
    [string[]]$States = @('hidden', 'hover', 'hidden2', 'hover2'),
    [int]$ScanContextBytes = 192,
    [int]$MaxHits = 24,
    [string[]]$ExtraPointerTargets = @(),
    [string[]]$ScanInt32Values = @(),
    [string[]]$ScanFloatValues = @(),
    [string[]]$ScanDoubleValues = @(),
    [double]$ScanTolerance = 0.5,
    [ValidateSet('hoverOnly', 'allHits', 'none')]
    [string]$TextPointerScanMode = 'hoverOnly',
    [switch]$SkipTargetRead,
    [switch]$SkipTextScan,
    [switch]$SkipPointerScan,
    [switch]$CaptureScreenshot,
    [switch]$RequireUsableScreenshot,
    [ValidateRange(1, 20)]
    [int]$ScreenshotAttempts = 3,
    [switch]$AnalyzeAfterCapture,
    [string]$AnalyzerBaselineStateRegex = 'hidden|baseline',
    [string]$AnalyzerActiveStateRegex = 'hover|active|zoom',
    [string]$AnalyzerBaselineLabel = 'baseline',
    [string]$AnalyzerActiveLabel = 'active',
    [switch]$AnalyzerRequireVisualGate,
    [string[]]$AnalyzerExpectedStates = @(),
    [string[]]$AnalyzerExpectedStateRoles = @(),
    [switch]$PlanOnly,
    [switch]$Json,
    [switch]$NonInteractive
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$repoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$readerProject = Join-Path $repoRoot 'reader\RiftReader.Reader\RiftReader.Reader.csproj'
if ([string]::IsNullOrWhiteSpace($OutputRoot)) {
    $OutputRoot = Join-Path $repoRoot 'artifacts\tooltip-projection'
}
elseif (-not [System.IO.Path]::IsPathRooted($OutputRoot)) {
    $OutputRoot = Join-Path $repoRoot $OutputRoot
}

function ConvertTo-NdjsonLine {
    param(
        [Parameter(Mandatory = $true, ValueFromPipeline = $true)]
        [object]$InputObject
    )

    process {
        return ($InputObject | ConvertTo-Json -Depth 40 -Compress)
    }
}

function Write-JsonFile {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path,
        [Parameter(Mandatory = $true)]
        [object]$Value
    )

    $parent = Split-Path -Parent $Path
    if (-not [string]::IsNullOrWhiteSpace($parent)) {
        New-Item -ItemType Directory -Force -Path $parent | Out-Null
    }

    $Value | ConvertTo-Json -Depth 40 | Set-Content -LiteralPath $Path -Encoding UTF8
}

function Add-NdjsonEvent {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path,
        [Parameter(Mandatory = $true)]
        [string]$Event,
        [hashtable]$Data = @{}
    )

    $row = [ordered]@{
        timestampUtc = (Get-Date).ToUniversalTime().ToString('o')
        event = $Event
    }

    foreach ($key in $Data.Keys) {
        $row[$key] = $Data[$key]
    }

    Add-Content -LiteralPath $Path -Value ([pscustomobject]$row | ConvertTo-NdjsonLine) -Encoding UTF8
}

function Add-NdjsonObject {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path,
        [Parameter(Mandatory = $true)]
        [object]$Value
    )

    Add-Content -LiteralPath $Path -Value ($Value | ConvertTo-NdjsonLine) -Encoding UTF8
}

function ConvertTo-AddressInt64 {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Value
    )

    $trimmed = $Value.Trim()
    if ($trimmed.StartsWith('0x', [System.StringComparison]::OrdinalIgnoreCase)) {
        return [Convert]::ToInt64($trimmed.Substring(2), 16)
    }

    return [Convert]::ToInt64($trimmed, 10)
}

function Format-Address {
    param([long]$Value)
    return ('0x{0:X}' -f $Value)
}

function Get-ProcessArguments {
    if ($PSBoundParameters.ContainsKey('ProcessId')) {
        return @('--pid', ([string]$ProcessId))
    }

    return @('--process-name', $ProcessName)
}

function Invoke-ReaderJson {
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$Arguments,
        [Parameter(Mandatory = $true)]
        [string]$OutFile
    )

    $startedUtc = (Get-Date).ToUniversalTime().ToString('o')
    $output = & dotnet run --project $readerProject -- @Arguments 2>&1
    $exitCode = $LASTEXITCODE
    $text = $output -join [Environment]::NewLine

    $parsed = $null
    $parseError = $null
    if (-not [string]::IsNullOrWhiteSpace($text)) {
        try {
            $parsed = $text | ConvertFrom-Json -Depth 40
        }
        catch {
            $parseError = $_.Exception.Message
        }
    }

    $record = [ordered]@{
        timestampUtc = $startedUtc
        exitCode = $exitCode
        command = @('dotnet', 'run', '--project', $readerProject, '--') + $Arguments
        stdout = $text
        json = $parsed
        jsonParseError = $parseError
    }

    Write-JsonFile -Path $OutFile -Value ([pscustomobject]$record)

    if ($exitCode -ne 0) {
        throw "Reader CLI failed with exit code $exitCode. Output file: $OutFile`n$text"
    }

    if ($null -ne $parseError) {
        throw "Reader CLI output was not valid JSON. Output file: $OutFile`n$parseError"
    }

    return [pscustomobject]$record
}

function Invoke-StateScreenshot {
    param(
        [Parameter(Mandatory = $true)]
        [string]$StateRoot,
        [Parameter(Mandatory = $true)]
        [string]$StateName
    )

    $captureScript = Join-Path $PSScriptRoot 'capture-rift-window-wgc.ps1'
    if (-not (Test-Path -LiteralPath $captureScript)) {
        throw "Screenshot capture helper was not found: $captureScript"
    }

    $screenshotRoot = Join-Path $StateRoot 'screenshots'
    New-Item -ItemType Directory -Force -Path $screenshotRoot | Out-Null
    $safeState = $StateName -replace '[^A-Za-z0-9_.-]', '-'
    $imagePath = Join-Path $screenshotRoot ('{0}.bmp' -f $safeState)
    $recordPath = Join-Path $screenshotRoot ('{0}.capture.json' -f $safeState)

    $captureArgs = @(
        '-NoProfile',
        '-ExecutionPolicy', 'Bypass',
        '-File', $captureScript,
        '-DesktopDuplication',
        '-Attempts', $ScreenshotAttempts.ToString([Globalization.CultureInfo]::InvariantCulture),
        '-Json'
    )

    if ($RequireUsableScreenshot) {
        $captureArgs += '-RequireUsable'
    }

    if ($PSBoundParameters.ContainsKey('ProcessId')) {
        $captureArgs += @('-ProcessId', $ProcessId.ToString([Globalization.CultureInfo]::InvariantCulture))
    }
    else {
        $captureArgs += @('-ProcessName', $ProcessName)
    }

    $startedUtc = (Get-Date).ToUniversalTime().ToString('o')
    $output = & pwsh @captureArgs 2>&1
    $exitCode = $LASTEXITCODE
    $text = $output -join [Environment]::NewLine
    $parsed = $null
    $parseError = $null
    if (-not [string]::IsNullOrWhiteSpace($text)) {
        try {
            $parsed = $text | ConvertFrom-Json -Depth 40
        }
        catch {
            $parseError = $_.Exception.Message
        }
    }

    $record = [ordered]@{
        timestampUtc = $startedUtc
        exitCode = $exitCode
        command = @('pwsh') + $captureArgs
        stdout = $text
        json = $parsed
        jsonParseError = $parseError
        outputPath = if ($null -ne $parsed -and -not [string]::IsNullOrWhiteSpace([string]$parsed.Output)) { [string]$parsed.Output } else { $imagePath }
        requiredUsable = [bool]$RequireUsableScreenshot
    }

    Write-JsonFile -Path $recordPath -Value ([pscustomobject]$record)

    if ($exitCode -ne 0) {
        throw "Screenshot capture failed with exit code $exitCode. Output file: $recordPath`n$text"
    }

    if ($null -ne $parseError) {
        throw "Screenshot capture output was not valid JSON. Output file: $recordPath`n$parseError"
    }

    if ($RequireUsableScreenshot -and ($null -eq $parsed -or -not [bool]$parsed.Usable)) {
        throw "Screenshot capture was not usable. Output file: $recordPath"
    }

    $sourceOutputPath = if ($null -ne $parsed -and -not [string]::IsNullOrWhiteSpace([string]$parsed.Output)) { [string]$parsed.Output } else { $null }
    if (-not [string]::IsNullOrWhiteSpace($sourceOutputPath) -and (Test-Path -LiteralPath $sourceOutputPath)) {
        Copy-Item -LiteralPath $sourceOutputPath -Destination $imagePath -Force
        $record['outputPath'] = $imagePath
        $record['sourceOutputPath'] = $sourceOutputPath
        Write-JsonFile -Path $recordPath -Value ([pscustomobject]$record)
    }

    return [pscustomobject]$record
}

function Invoke-PostCaptureAnalyzer {
    param([Parameter(Mandatory = $true)][string]$InputDirectory)

    $analyzerScript = Join-Path $PSScriptRoot 'analyze-tooltip-hover-diff.ps1'
    if (-not (Test-Path -LiteralPath $analyzerScript)) {
        throw "Analyzer helper was not found: $analyzerScript"
    }

    $recordPath = Join-Path $InputDirectory 'post-capture-analysis.json'
    $analyzerArgs = @(
        '-NoProfile',
        '-ExecutionPolicy', 'Bypass',
        '-File', $analyzerScript,
        '-InputDirectory', $InputDirectory,
        '-BaselineStateRegex', $AnalyzerBaselineStateRegex,
        '-ActiveStateRegex', $AnalyzerActiveStateRegex,
        '-BaselineLabel', $AnalyzerBaselineLabel,
        '-ActiveLabel', $AnalyzerActiveLabel,
        '-Json'
    )

    if ($AnalyzerRequireVisualGate) {
        $analyzerArgs += '-RequireVisualGate'
    }

    $expectedStates = @(Normalize-CommaList -Value $AnalyzerExpectedStates)
    if ($expectedStates.Count -gt 0) {
        $analyzerArgs += @('-ExpectedStates', ($expectedStates -join ','))
    }

    $expectedStateRoles = @(Normalize-CommaList -Value $AnalyzerExpectedStateRoles)
    if ($expectedStateRoles.Count -gt 0) {
        $analyzerArgs += @('-ExpectedStateRoles', ($expectedStateRoles -join ','))
    }

    $startedUtc = (Get-Date).ToUniversalTime().ToString('o')
    $output = & pwsh @analyzerArgs 2>&1
    $exitCode = $LASTEXITCODE
    $text = $output -join [Environment]::NewLine
    $parsed = $null
    $parseError = $null
    if (-not [string]::IsNullOrWhiteSpace($text)) {
        try {
            $parsed = $text | ConvertFrom-Json -Depth 40
        }
        catch {
            $parseError = $_.Exception.Message
        }
    }

    $record = [ordered]@{
        timestampUtc = $startedUtc
        exitCode = $exitCode
        command = @('pwsh') + $analyzerArgs
        stdout = $text
        json = $parsed
        jsonParseError = $parseError
    }

    Write-JsonFile -Path $recordPath -Value ([pscustomobject]$record)

    if ($exitCode -ne 0) {
        throw "Post-capture analyzer failed with exit code $exitCode. Output file: $recordPath`n$text"
    }

    if ($null -ne $parseError) {
        throw "Post-capture analyzer output was not valid JSON. Output file: $recordPath`n$parseError"
    }

    return [pscustomobject]$record
}

function Get-JsonAddressStrings {
    param([object]$Value)

    $addresses = New-Object 'System.Collections.Generic.List[string]'

    function Visit-JsonValue {
        param([object]$Node)

        if ($null -eq $Node) {
            return
        }

        if ($Node -is [string]) {
            if ($Node -match '^0x[0-9A-Fa-f]+$') {
                $addresses.Add($Node.ToUpperInvariant())
            }
            return
        }

        if ($Node -is [System.Collections.IDictionary]) {
            foreach ($key in $Node.Keys) {
                Visit-JsonValue -Node $Node[$key]
            }
            return
        }

        if ($Node -is [System.Collections.IEnumerable] -and -not ($Node -is [string])) {
            foreach ($item in $Node) {
                Visit-JsonValue -Node $item
            }
            return
        }

        $properties = $Node.PSObject.Properties
        foreach ($property in $properties) {
            Visit-JsonValue -Node $property.Value
        }
    }

    Visit-JsonValue -Node $Value
    return @($addresses | Select-Object -Unique)
}

function Get-ScanHitAddressStrings {
    param([object]$Value)

    if ($null -eq $Value) {
        return @()
    }

    $hitsProperty = $Value.PSObject.Properties | Where-Object { $_.Name -ieq 'Hits' } | Select-Object -First 1
    if ($null -eq $hitsProperty) {
        return @(Get-JsonAddressStrings -Value $Value)
    }

    $addresses = New-Object 'System.Collections.Generic.List[string]'
    foreach ($hit in @($hitsProperty.Value)) {
        if ($null -eq $hit) {
            continue
        }

        $addressValue = $null
        foreach ($propertyName in @('AddressHex', 'addressHex', 'Address', 'address')) {
            $property = $hit.PSObject.Properties | Where-Object { $_.Name -ceq $propertyName } | Select-Object -First 1
            if ($null -ne $property) {
                $addressValue = $property.Value
                break
            }
        }

        if ($null -eq $addressValue) {
            continue
        }

        if ($addressValue -is [string]) {
            $trimmed = $addressValue.Trim()
            if ($trimmed -match '^0x[0-9A-Fa-f]+$') {
                $addresses.Add($trimmed.ToUpperInvariant())
            }
            elseif ($trimmed -match '^[0-9]+$') {
                $addresses.Add((Format-Address -Value ([Convert]::ToInt64($trimmed, 10))).ToUpperInvariant())
            }
        }
        else {
            $addresses.Add((Format-Address -Value ([Convert]::ToInt64($addressValue))).ToUpperInvariant())
        }
    }

    $hitAddresses = @($addresses | Select-Object -Unique)
    if ($hitAddresses.Count -gt 0) {
        return $hitAddresses
    }

    return @(Get-JsonAddressStrings -Value $Value)
}

function Get-TargetPresence {
    param([object]$TargetJson)

    if ($null -eq $TargetJson) {
        return $false
    }

    $serialized = $TargetJson | ConvertTo-Json -Depth 20 -Compress
    if ([string]::IsNullOrWhiteSpace($serialized)) {
        return $false
    }

    return ($serialized -notmatch '"hasTarget"\s*:\s*false' -and $serialized -notmatch '"target"\s*:\s*null')
}

function Normalize-StateList {
    param([string[]]$Value)

    return @(Normalize-CommaList -Value $Value)
}

function Normalize-CommaList {
    param([string[]]$Value)

    if ($null -eq $Value) {
        return @()
    }

    $normalized = New-Object System.Collections.Generic.List[string]
    foreach ($entry in $Value) {
        if ([string]::IsNullOrWhiteSpace($entry)) {
            continue
        }

        foreach ($stateName in ($entry -split ',')) {
            $trimmed = $stateName.Trim()
            if (-not [string]::IsNullOrWhiteSpace($trimmed)) {
                $normalized.Add($trimmed)
            }
        }
    }

    return @($normalized)
}

function Get-SafeToken {
    param([string]$Value)

    if ([string]::IsNullOrWhiteSpace($Value)) {
        return 'blank'
    }

    return (($Value.Trim() -replace '^0X', '0x') -replace '[^A-Za-z0-9_.-]', '_')
}

$candidateAddressInt = ConvertTo-AddressInt64 -Value $CandidateAddress
if ($candidateAddressInt -lt 0) {
    throw 'CandidateAddress must be non-negative.'
}

if ($CandidateLength -le 0) {
    throw 'CandidateLength must be greater than zero.'
}

if ($ScanContextBytes -lt 0) {
    throw 'ScanContextBytes must be non-negative.'
}

if ($MaxHits -le 0) {
    throw 'MaxHits must be greater than zero.'
}

if ($RequireUsableScreenshot -and -not $CaptureScreenshot) {
    throw 'RequireUsableScreenshot requires CaptureScreenshot.'
}

if ($AnalyzerRequireVisualGate -and -not $AnalyzeAfterCapture) {
    throw 'AnalyzerRequireVisualGate requires AnalyzeAfterCapture.'
}

if ($ScanTolerance -le 0) {
    throw 'ScanTolerance must be greater than zero.'
}

$States = @(Normalize-StateList -Value $States)
$ExtraPointerTargets = @(Normalize-CommaList -Value $ExtraPointerTargets)
$ScanInt32Values = @(Normalize-CommaList -Value $ScanInt32Values)
$ScanFloatValues = @(Normalize-CommaList -Value $ScanFloatValues)
$ScanDoubleValues = @(Normalize-CommaList -Value $ScanDoubleValues)
if (@($States).Count -eq 0) {
    throw 'At least one state is required.'
}

$halfLength = [int][Math]::Floor($CandidateLength / 2)
$windowBaseInt = [Math]::Max(0L, $candidateAddressInt - [long]$halfLength)
$windowEndInt = $windowBaseInt + [long]$CandidateLength - 1L
$timestamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$runId = '{0}-{1}' -f $timestamp, ($RunLabel -replace '[^A-Za-z0-9_.-]', '-')
$runRoot = Join-Path $OutputRoot $runId

$plan = [ordered]@{
    mode = if ($PlanOnly) { 'plan-only' } else { 'capture' }
    runLabel = $RunLabel
    runId = $runId
    runRoot = $runRoot
    process = if ($PSBoundParameters.ContainsKey('ProcessId')) { [ordered]@{ pid = $ProcessId } } else { [ordered]@{ name = $ProcessName } }
    readerProject = $readerProject
    candidateAddress = Format-Address -Value $candidateAddressInt
    candidateLength = $CandidateLength
    windowBaseAddress = Format-Address -Value $windowBaseInt
    windowEndAddress = Format-Address -Value $windowEndInt
    tooltipText = $TooltipText
    states = @($States)
    scanContextBytes = $ScanContextBytes
    maxHits = $MaxHits
    extraPointerTargets = @($ExtraPointerTargets)
    scanInt32Values = @($ScanInt32Values)
    scanFloatValues = @($ScanFloatValues)
    scanDoubleValues = @($ScanDoubleValues)
    scanTolerance = $ScanTolerance
    textPointerScanMode = $TextPointerScanMode
    skipTargetRead = [bool]$SkipTargetRead
    skipTextScan = [bool]$SkipTextScan
    skipPointerScan = [bool]$SkipPointerScan
    captureScreenshot = [bool]$CaptureScreenshot
    requireUsableScreenshot = [bool]$RequireUsableScreenshot
    screenshotAttempts = $ScreenshotAttempts
    analyzeAfterCapture = [bool]$AnalyzeAfterCapture
    analyzerBaselineStateRegex = $AnalyzerBaselineStateRegex
    analyzerActiveStateRegex = $AnalyzerActiveStateRegex
    analyzerBaselineLabel = $AnalyzerBaselineLabel
    analyzerActiveLabel = $AnalyzerActiveLabel
    analyzerRequireVisualGate = [bool]$AnalyzerRequireVisualGate
    analyzerExpectedStates = @(Normalize-CommaList -Value $AnalyzerExpectedStates)
    analyzerExpectedStateRoles = @(Normalize-CommaList -Value $AnalyzerExpectedStateRoles)
    nonInteractive = [bool]$NonInteractive
    controlsInput = $false
    notes = @(
        'This helper only invokes RiftReader.Reader read/scan modes.',
        'It does not move the mouse, click, cast, move, focus a window, or send keyboard input.',
        'PlanOnly does not attach to the process and does not create live run artifacts.'
    )
}

if ($PlanOnly) {
    $planObject = [pscustomobject]$plan
    if ($Json) {
        $planObject | ConvertTo-Json -Depth 40
    }
    else {
        Write-Host '# Tooltip hover diff capture plan'
        $planObject | ConvertTo-Json -Depth 40
    }
    return
}

New-Item -ItemType Directory -Force -Path $runRoot | Out-Null
$statesRoot = Join-Path $runRoot 'states'
New-Item -ItemType Directory -Force -Path $statesRoot | Out-Null
$manifestPath = Join-Path $runRoot 'manifest.json'
$eventsPath = Join-Path $runRoot 'events.ndjson'
$samplesPath = Join-Path $runRoot 'samples.ndjson'

$manifest = [ordered]@{}
foreach ($key in $plan.Keys) {
    $manifest[$key] = $plan[$key]
}
$manifest['createdUtc'] = (Get-Date).ToUniversalTime().ToString('o')
$manifest['eventsFile'] = $eventsPath
$manifest['samplesFile'] = $samplesPath
Write-JsonFile -Path $manifestPath -Value ([pscustomobject]$manifest)
Add-NdjsonEvent -Path $eventsPath -Event 'run-started' -Data @{ runRoot = $runRoot; manifest = $manifestPath }

$hiddenTextAddresses = @()
$allSamples = New-Object 'System.Collections.Generic.List[object]'
$stateIndex = 0

foreach ($state in $States) {
    if ([string]::IsNullOrWhiteSpace($state)) {
        throw 'State names cannot be blank.'
    }

    $stateIndex++
    $stateSafe = $state -replace '[^A-Za-z0-9_.-]', '-'
    $stateRoot = Join-Path $statesRoot $stateSafe
    New-Item -ItemType Directory -Force -Path $stateRoot | Out-Null
    $isActiveState = $state -match $AnalyzerActiveStateRegex
    $stateRole = if ($isActiveState) { 'active' } elseif ($state -match $AnalyzerBaselineStateRegex) { 'baseline' } else { 'other' }
    Add-NdjsonEvent -Path $eventsPath -Event 'state-started' -Data @{ state = $state; index = $stateIndex; role = $stateRole }

    if (-not $NonInteractive) {
        Write-Host ''
        Write-Host "Prepare proof state '$state' ($stateRole, $stateIndex/$(@($States).Count))." -ForegroundColor Cyan
        Write-Host 'This script will not touch mouse, keyboard, window focus, movement, or casting.' -ForegroundColor DarkGray
        Read-Host 'Press Enter when the operator-visible state is ready' | Out-Null
    }

    $screenshotRecord = $null
    if ($CaptureScreenshot) {
        $screenshotRecord = Invoke-StateScreenshot -StateRoot $stateRoot -StateName $state
        Add-NdjsonEvent -Path $eventsPath -Event 'state-screenshot-captured' -Data @{
            state = $state
            index = $stateIndex
            usable = if ($null -ne $screenshotRecord.json) { [bool]$screenshotRecord.json.Usable } else { $false }
            output = $screenshotRecord.outputPath
        }
    }

    $targetRecord = $null
    if (-not $SkipTargetRead) {
        $targetArgs = @(Get-ProcessArguments) + @('--read-target-current', '--scan-context', ([string]$ScanContextBytes), '--max-hits', ([string]$MaxHits), '--json')
        $targetRecord = Invoke-ReaderJson -Arguments $targetArgs -OutFile (Join-Path $stateRoot 'read-target-current.json')
    }
    else {
        Write-JsonFile -Path (Join-Path $stateRoot 'read-target-current.json') -Value ([pscustomobject][ordered]@{
            skipped = $true
            reason = 'SkipTargetRead was set.'
            timestampUtc = (Get-Date).ToUniversalTime().ToString('o')
        })
    }

    $memoryArgs = @(Get-ProcessArguments) + @('--address', (Format-Address -Value $windowBaseInt), '--length', ([string]$CandidateLength), '--json')
    $memoryRecord = Invoke-ReaderJson -Arguments $memoryArgs -OutFile (Join-Path $stateRoot 'candidate-memory.json')

    $scanRecord = $null
    $textAddresses = @()
    if (-not $SkipTextScan) {
        $scanArgs = @(Get-ProcessArguments) + @('--scan-string', $TooltipText, '--scan-encoding', 'both', '--scan-context', ([string]$ScanContextBytes), '--max-hits', ([string]$MaxHits), '--json')
        $scanRecord = Invoke-ReaderJson -Arguments $scanArgs -OutFile (Join-Path $stateRoot 'scan-tooltip-text.json')
        $textAddresses = @(Get-ScanHitAddressStrings -Value $scanRecord.json)

        if ($stateRole -eq 'baseline') {
            $hiddenTextAddresses = @($hiddenTextAddresses + $textAddresses | Select-Object -Unique)
        }
    }
    else {
        Write-JsonFile -Path (Join-Path $stateRoot 'scan-tooltip-text.json') -Value ([pscustomobject][ordered]@{
            skipped = $true
            reason = 'SkipTextScan was set.'
            timestampUtc = (Get-Date).ToUniversalTime().ToString('o')
        })
    }

    $knownTextPointers = @()
    if (-not $SkipPointerScan -and -not $SkipTextScan -and $TextPointerScanMode -ne 'none') {
        $textPointerTargets = switch ($TextPointerScanMode) {
            'allHits' {
                @($textAddresses)
                break
            }
            'hoverOnly' {
                if ($isActiveState) {
                    @($textAddresses | Where-Object { $hiddenTextAddresses -notcontains $_ })
                }
                else {
                    @()
                }
                break
            }
        }

        foreach ($textAddress in @($textPointerTargets | Select-Object -Unique)) {
            $pointerFileSafeAddress = Get-SafeToken -Value $textAddress
            $pointerFile = Join-Path $stateRoot ('scan-pointer-{0}.json' -f $pointerFileSafeAddress)
            $pointerArgs = @(Get-ProcessArguments) + @('--scan-pointer', $textAddress, '--pointer-width', '8', '--scan-context', ([string]$ScanContextBytes), '--max-hits', ([string]$MaxHits), '--json')
            $pointerRecord = Invoke-ReaderJson -Arguments $pointerArgs -OutFile $pointerFile
            $knownTextPointers += [pscustomobject][ordered]@{
                tooltipTextAddress = $textAddress
                pointerScanFile = $pointerFile
                pointerHitAddresses = @(Get-ScanHitAddressStrings -Value $pointerRecord.json)
            }
        }
    }

    $extraPointerScans = @()
    if (-not $SkipPointerScan -and @($ExtraPointerTargets).Count -gt 0) {
        foreach ($pointerTarget in $ExtraPointerTargets) {
            $pointerFileSafeAddress = Get-SafeToken -Value $pointerTarget
            $pointerFile = Join-Path $stateRoot ('scan-pointer-extra-{0}.json' -f $pointerFileSafeAddress)
            $pointerArgs = @(Get-ProcessArguments) + @('--scan-pointer', $pointerTarget, '--pointer-width', '8', '--scan-context', ([string]$ScanContextBytes), '--max-hits', ([string]$MaxHits), '--json')
            $pointerRecord = Invoke-ReaderJson -Arguments $pointerArgs -OutFile $pointerFile
            $extraPointerScans += [pscustomobject][ordered]@{
                pointerTarget = $pointerTarget
                pointerScanFile = $pointerFile
                pointerHitAddresses = @(Get-ScanHitAddressStrings -Value $pointerRecord.json)
            }
        }
    }

    $numericScans = @()
    foreach ($scanValue in $ScanInt32Values) {
        $scanFile = Join-Path $stateRoot ('scan-int32-{0}.json' -f (Get-SafeToken -Value $scanValue))
        $scanArgs = @(Get-ProcessArguments) + @('--scan-int32', $scanValue, '--scan-context', ([string]$ScanContextBytes), '--max-hits', ([string]$MaxHits), '--json')
        $scanRecord = Invoke-ReaderJson -Arguments $scanArgs -OutFile $scanFile
        $numericScans += [pscustomobject][ordered]@{
            type = 'int32'
            value = $scanValue
            scanFile = $scanFile
            hitAddresses = @(Get-ScanHitAddressStrings -Value $scanRecord.json)
        }
    }

    foreach ($scanValue in $ScanFloatValues) {
        $scanFile = Join-Path $stateRoot ('scan-float-{0}.json' -f (Get-SafeToken -Value $scanValue))
        $scanArgs = @(Get-ProcessArguments) + @('--scan-float', $scanValue, '--scan-tolerance', ([string]$ScanTolerance), '--scan-context', ([string]$ScanContextBytes), '--max-hits', ([string]$MaxHits), '--json')
        $scanRecord = Invoke-ReaderJson -Arguments $scanArgs -OutFile $scanFile
        $numericScans += [pscustomobject][ordered]@{
            type = 'float'
            value = $scanValue
            tolerance = $ScanTolerance
            scanFile = $scanFile
            hitAddresses = @(Get-ScanHitAddressStrings -Value $scanRecord.json)
        }
    }

    foreach ($scanValue in $ScanDoubleValues) {
        $scanFile = Join-Path $stateRoot ('scan-double-{0}.json' -f (Get-SafeToken -Value $scanValue))
        $scanArgs = @(Get-ProcessArguments) + @('--scan-double', $scanValue, '--scan-tolerance', ([string]$ScanTolerance), '--scan-context', ([string]$ScanContextBytes), '--max-hits', ([string]$MaxHits), '--json')
        $scanRecord = Invoke-ReaderJson -Arguments $scanArgs -OutFile $scanFile
        $numericScans += [pscustomobject][ordered]@{
            type = 'double'
            value = $scanValue
            tolerance = $ScanTolerance
            scanFile = $scanFile
            hitAddresses = @(Get-ScanHitAddressStrings -Value $scanRecord.json)
        }
    }

    $bytesHex = $null
    if ($null -ne $memoryRecord.json -and $memoryRecord.json.PSObject.Properties.Name -contains 'BytesHex') {
        $bytesHex = $memoryRecord.json.BytesHex
    }

    $hasTarget = $false
    if ($null -ne $targetRecord) {
        $hasTarget = Get-TargetPresence -TargetJson $targetRecord.json
    }

    $hoverOnlyTooltipTextAddresses = if ($isActiveState) {
        @($textAddresses | Where-Object { $hiddenTextAddresses -notcontains $_ })
    }
    else {
        @()
    }

    $sample = [pscustomobject][ordered]@{
        state = $state
        stateRole = $stateRole
        isActiveState = $isActiveState
        timestampUtc = (Get-Date).ToUniversalTime().ToString('o')
        candidateAddress = Format-Address -Value $candidateAddressInt
        baseAddress = Format-Address -Value $windowBaseInt
        windowEndAddress = Format-Address -Value $windowEndInt
        candidateLength = $CandidateLength
        bytesHex = $bytesHex
        tooltipTextHitAddresses = @($textAddresses)
        hoverOnlyTooltipTextAddresses = @($hoverOnlyTooltipTextAddresses)
        knownTextPointers = @($knownTextPointers)
        extraPointerScans = @($extraPointerScans)
        numericScans = @($numericScans)
        hasTarget = $hasTarget
        files = [ordered]@{
            stateRoot = $stateRoot
            screenshotCapture = if ($null -eq $screenshotRecord) { $null } else { Join-Path (Join-Path $stateRoot 'screenshots') ('{0}.capture.json' -f $stateSafe) }
            screenshotOutput = if ($null -eq $screenshotRecord) { $null } else { $screenshotRecord.outputPath }
            candidateMemory = Join-Path $stateRoot 'candidate-memory.json'
            scanTooltipText = Join-Path $stateRoot 'scan-tooltip-text.json'
            readTargetCurrent = if ($SkipTargetRead) { $null } else { Join-Path $stateRoot 'read-target-current.json' }
        }
    }

    Add-NdjsonObject -Path $samplesPath -Value $sample
    $allSamples.Add($sample) | Out-Null
    Add-NdjsonEvent -Path $eventsPath -Event 'state-completed' -Data @{ state = $state; index = $stateIndex; hasTarget = $hasTarget; textHitCount = @($textAddresses).Count; pointerScanCount = (@($knownTextPointers).Count + @($extraPointerScans).Count); numericScanCount = @($numericScans).Count }
}

$sampleArray = @($allSamples.ToArray())
$summary = [pscustomobject][ordered]@{
    runRoot = $runRoot
    manifest = $manifestPath
    events = $eventsPath
    samples = $samplesPath
    states = $sampleArray
}
Write-JsonFile -Path (Join-Path $runRoot 'summary.json') -Value $summary
Add-NdjsonEvent -Path $eventsPath -Event 'run-completed' -Data @{ sampleCount = $allSamples.Count; summary = (Join-Path $runRoot 'summary.json') }

$analysisRecord = $null
if ($AnalyzeAfterCapture) {
    Add-NdjsonEvent -Path $eventsPath -Event 'post-capture-analysis-started' -Data @{
        analyzerBaselineStateRegex = $AnalyzerBaselineStateRegex
        analyzerActiveStateRegex = $AnalyzerActiveStateRegex
        analyzerRequireVisualGate = [bool]$AnalyzerRequireVisualGate
    }
    $analysisRecord = Invoke-PostCaptureAnalyzer -InputDirectory $runRoot
    Add-NdjsonEvent -Path $eventsPath -Event 'post-capture-analysis-completed' -Data @{
        exitCode = $analysisRecord.exitCode
        outputFile = Join-Path $runRoot 'post-capture-analysis.json'
    }

    if ($null -ne $analysisRecord.json) {
        $summary = Get-Content -LiteralPath (Join-Path $runRoot 'summary.json') -Raw | ConvertFrom-Json -Depth 40
    }
}

if ($Json) {
    $summary | ConvertTo-Json -Depth 40
}
else {
    Write-Host ''
    Write-Host "Tooltip hover diff capture complete: $runRoot" -ForegroundColor Green
    Write-Host "Manifest: $manifestPath"
    Write-Host "Samples:  $samplesPath"
    if ($AnalyzeAfterCapture) {
        Write-Host "Analysis: $(Join-Path $runRoot 'post-capture-analysis.json')"
    }
}
