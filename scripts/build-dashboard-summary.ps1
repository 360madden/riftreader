[CmdletBinding()]
param(
    [string]$RepoPath = '',
    [string]$OutputPath
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$scriptRoot = if ($PSScriptRoot) { $PSScriptRoot } else { Split-Path -Parent $MyInvocation.MyCommand.Path }
if ([string]::IsNullOrWhiteSpace($RepoPath)) {
    $RepoPath = Join-Path $scriptRoot '..'
}

function Convert-ToDashboardPath {
    param([string]$Path)

    if ([string]::IsNullOrWhiteSpace($Path)) {
        return ''
    }

    return ($Path -replace '\\', '/')
}

function Get-ResolvedPath {
    param([string]$Path)

    return (Resolve-Path -LiteralPath $Path).Path
}

function Invoke-GitLines {
    param(
        [string]$RepoRoot,
        [string[]]$Arguments
    )

    $lines = & git -C $RepoRoot @Arguments 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "git $($Arguments -join ' ') failed.`n$($lines -join [Environment]::NewLine)"
    }

    return [string[]]@($lines)
}

function Try-GetFileLastWrite {
    param([string]$Path)

    if (-not $Path -or -not (Test-Path -LiteralPath $Path)) {
        return $null
    }

    return ([DateTimeOffset](Get-Item -LiteralPath $Path).LastWriteTime).ToString('o')
}

function New-SourceReference {
    param(
        [string]$Label,
        [string]$Path,
        [string]$Note = ''
    )

    $present = $false
    $updatedAt = $null
    if (-not [string]::IsNullOrWhiteSpace($Path) -and (Test-Path -LiteralPath $Path)) {
        $present = $true
        $updatedAt = Try-GetFileLastWrite -Path $Path
    }

    return [pscustomobject]@{
        label     = $Label
        path      = (Convert-ToDashboardPath $Path)
        note      = $Note
        present   = $present
        updatedAt = $updatedAt
    }
}

function Read-JsonFile {
    param([string]$Path)

    if (-not (Test-Path -LiteralPath $Path)) {
        return $null
    }

    return (Get-Content -LiteralPath $Path -Raw | ConvertFrom-Json)
}

function Read-TextLines {
    param([string]$Path)

    if (-not (Test-Path -LiteralPath $Path)) {
        return @()
    }

    return @(Get-Content -LiteralPath $Path)
}

function Get-ItemCount {
    param($Value)

    if ($null -eq $Value) {
        return 0
    }

    return @($Value).Count
}

function Read-KeyValueFile {
    param([string]$Path)

    if (-not (Test-Path -LiteralPath $Path)) {
        return $null
    }

    $map = [ordered]@{}
    foreach ($line in Get-Content -LiteralPath $Path) {
        if ($line -match '^(?<key>[^=]+)=(?<value>.*)$') {
            $map[$matches.key.Trim()] = $matches.value.Trim()
        }
    }

    return [pscustomobject]$map
}

function Split-MarkdownRow {
    param([string]$Line)

    $trimmed = $Line.Trim()
    $trimmed = $trimmed.Trim('|')
    if ([string]::IsNullOrWhiteSpace($trimmed)) {
        return @()
    }

    return @($trimmed.Split('|') | ForEach-Object { $_.Trim() })
}

function Get-MarkdownTableAfterHeading {
    param(
        [string[]]$Lines,
        [string]$Heading
    )

    $lineCount = Get-ItemCount -Value $Lines
    if ($lineCount -le 0) {
        return @()
    }

    $headingPattern = '^\s*#{1,6}\s+' + [Regex]::Escape($Heading) + '\s*$'
    $headingIndex = -1
    for ($i = 0; $i -lt $lineCount; $i++) {
        if ($Lines[$i] -match $headingPattern) {
            $headingIndex = $i
            break
        }
    }

    if ($headingIndex -lt 0) {
        return @()
    }

    $tableLines = New-Object System.Collections.Generic.List[string]
    for ($i = $headingIndex + 1; $i -lt $lineCount; $i++) {
        $line = $Lines[$i]
        if ($line -match '^\s*\|') {
            $tableLines.Add($line)
            continue
        }

        if ($tableLines.Count -gt 0) {
            break
        }
    }

    if ($tableLines.Count -lt 3) {
        return @()
    }

    $headers = Split-MarkdownRow -Line $tableLines[0]
    $rows = New-Object System.Collections.Generic.List[object]

    for ($i = 2; $i -lt $tableLines.Count; $i++) {
        $cells = Split-MarkdownRow -Line $tableLines[$i]
        if ((Get-ItemCount -Value $cells) -le 0) {
            continue
        }

        $row = [ordered]@{}
        $headerCount = Get-ItemCount -Value $headers
        $cellCount = Get-ItemCount -Value $cells
        for ($cellIndex = 0; $cellIndex -lt $headerCount; $cellIndex++) {
            $value = if ($cellIndex -lt $cellCount) { $cells[$cellIndex] } else { '' }
            $row[$headers[$cellIndex]] = $value
        }
        $rows.Add([pscustomobject]$row)
    }

    return $rows.ToArray()
}

function Get-MarkdownListAfterHeading {
    param(
        [string[]]$Lines,
        [string]$Heading
    )

    $lineCount = Get-ItemCount -Value $Lines
    if ($lineCount -le 0) {
        return @()
    }

    $headingPattern = '^\s*#{1,6}\s+' + [Regex]::Escape($Heading) + '\s*$'
    $headingIndex = -1
    for ($i = 0; $i -lt $lineCount; $i++) {
        if ($Lines[$i] -match $headingPattern) {
            $headingIndex = $i
            break
        }
    }

    if ($headingIndex -lt 0) {
        return @()
    }

    $items = New-Object System.Collections.Generic.List[string]
    for ($i = $headingIndex + 1; $i -lt $lineCount; $i++) {
        $line = $Lines[$i]
        if ($line -match '^\s*#{1,6}\s+') {
            break
        }

        if ($line -match '^\s*(?:[-*]|\d+\.)\s+(?<item>.+?)\s*$') {
            $items.Add($matches.item.Trim())
            continue
        }

        if ($items.Count -gt 0 -and [string]::IsNullOrWhiteSpace($line)) {
            break
        }
    }

    return $items.ToArray()
}

function Get-GitWorktrees {
    param([string]$RepoRoot)

    $lines = Invoke-GitLines -RepoRoot $RepoRoot -Arguments @('worktree', 'list', '--porcelain')
    $worktrees = New-Object System.Collections.Generic.List[object]
    $current = [ordered]@{}

    foreach ($line in @($lines + '')) {
        if ([string]::IsNullOrWhiteSpace($line)) {
            if ($current.Contains('path')) {
                $worktrees.Add([pscustomobject]@{
                        path      = (Convert-ToDashboardPath $current.path)
                        head      = $current.head
                        branch    = $current.branch
                        isCurrent = ((Convert-ToDashboardPath $current.path) -eq (Convert-ToDashboardPath $RepoRoot))
                    })
            }

            $current = [ordered]@{}
            continue
        }

        if ($line -match '^worktree (?<path>.+)$') {
            $current.path = $matches.path
            continue
        }

        if ($line -match '^HEAD (?<head>[0-9a-f]+)$') {
            $current.head = $matches.head
            continue
        }

        if ($line -match '^branch refs/heads/(?<branch>.+)$') {
            $current.branch = $matches.branch
            continue
        }
    }

    return $worktrees.ToArray()
}

function Get-GitBranches {
    param([string]$RepoRoot)

    $lines = Invoke-GitLines -RepoRoot $RepoRoot -Arguments @('branch', '--all', '--verbose', '--no-abbrev')
    $branches = New-Object System.Collections.Generic.List[object]

    foreach ($line in $lines) {
        if ($line -match '^\s*remotes/' -or $line -match '->') {
            continue
        }

        if ($line -match '^(?<marker>[\*\+ ])\s+(?<name>\S+)\s+(?<sha>[0-9a-f]{40})\s*(?<subject>.*)$') {
            $branches.Add([pscustomobject]@{
                    marker  = $matches.marker
                    name    = $matches.name
                    sha     = $matches.sha
                    subject = $matches.subject.Trim()
                })
        }
    }

    return $branches.ToArray()
}

function Get-GitStatusSummary {
    param([string]$RepoRoot)

    $lines = @((Invoke-GitLines -RepoRoot $RepoRoot -Arguments @('status', '--short')) | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })
    $modified = 0
    $added = 0
    $deleted = 0
    $renamed = 0
    $untracked = 0

    foreach ($line in $lines) {
        if ($line.StartsWith('??')) {
            $untracked += 1
            continue
        }

        $x = if ($line.Length -ge 1) { $line.Substring(0, 1) } else { ' ' }
        $y = if ($line.Length -ge 2) { $line.Substring(1, 1) } else { ' ' }
        $statusCode = "$x$y"

        if ($statusCode -match 'M') { $modified += 1 }
        if ($statusCode -match 'A') { $added += 1 }
        if ($statusCode -match 'D') { $deleted += 1 }
        if ($statusCode -match 'R') { $renamed += 1 }
    }

    return [pscustomobject]@{
        lines      = $lines
        modified   = $modified
        added      = $added
        deleted    = $deleted
        renamed    = $renamed
        untracked  = $untracked
        total      = (Get-ItemCount -Value $lines)
        observedAt = ([DateTimeOffset]::Now).ToString('o')
    }
}

function Get-GitHeadCommitInfo {
    param([string]$RepoRoot)

    $lines = Invoke-GitLines -RepoRoot $RepoRoot -Arguments @('log', '-1', '--format=%H%n%s%n%cI')
    return [pscustomobject]@{
        sha         = if ((Get-ItemCount -Value $lines) -ge 1) { $lines[0].Trim() } else { '' }
        subject     = if ((Get-ItemCount -Value $lines) -ge 2) { $lines[1].Trim() } else { '' }
        committedAt = if ((Get-ItemCount -Value $lines) -ge 3) { $lines[2].Trim() } else { $null }
    }
}

function Get-BranchRole {
    param([string]$BranchName)

    switch ($BranchName) {
        'codex/actor-yaw-pitch' { return 'actor-recovery' }
        'codex/dashboard-hud' { return 'dashboard' }
        'feature/camera-orientation-discovery' { return 'camera-discovery' }
        'main' { return 'baseline' }
        default {
            if ($BranchName -like 'codex/camera*' -or $BranchName -like '*camera*') { return 'camera-branch' }
            if ($BranchName -like 'codex/*') { return 'codex-branch' }
            return 'branch'
        }
    }
}

function Get-BranchBottleneck {
    param(
        [string]$BranchName,
        [string]$Role,
        [bool]$IsCurrent,
        [string]$CommitSubject
    )

    switch ($BranchName) {
        'codex/actor-yaw-pitch' { return 'No trusted surviving yaw candidate after the latest merge.' }
        'codex/dashboard-hud' { return 'Implement the display-only branch-aware dashboard v1.' }
        'feature/camera-orientation-discovery' { return 'Camera workflow is isolated here and still needs post-update revalidation.' }
        'main' { return 'Reference baseline only; not the active recovery branch.' }
        default {
            if ($IsCurrent) {
                return 'Current working branch with no branch-specific dashboard summary yet.'
            }

            if ($CommitSubject) {
                return $CommitSubject
            }

            return 'No rich dashboard data configured for this branch in v1.'
        }
    }
}

function Convert-MarkdownTruthRows {
    param([object[]]$Rows)

    return @(
        foreach ($row in $Rows) {
            [pscustomobject]@{
                label  = $row.Area
                status = $row.Status
            }
        }
    )
}

function Convert-WorkboardRows {
    param([object[]]$Rows)

    return @(
        foreach ($row in $Rows) {
            $item = if ($row.PSObject.Properties.Name -contains 'Item') { $row.Item } else { '' }
            $lane = if ($row.PSObject.Properties.Name -contains 'Lane') { $row.Lane } else { '' }
            $note =
            if ($row.PSObject.Properties.Name -contains 'Why now') { $row.'Why now' }
            elseif ($row.PSObject.Properties.Name -contains 'Output required') { $row.'Output required' }
            elseif ($row.PSObject.Properties.Name -contains 'Trigger') { $row.Trigger }
            elseif ($row.PSObject.Properties.Name -contains 'Reason parked') { $row.'Reason parked' }
            else { '' }

            [pscustomobject]@{
                item = $item
                lane = $lane
                note = $note
            }
        }
    )
}

function Convert-ClassificationsToMap {
    param([object[]]$Rows)

    $map = [ordered]@{}
    foreach ($row in $Rows) {
        $map[$row.Name] = $row.Count
    }
    return [pscustomobject]$map
}

function Convert-ListToWorkboardRows {
    param(
        [string[]]$Items,
        [string]$Lane = '',
        [string]$Note = ''
    )

    return @(
        foreach ($item in $Items) {
            if ([string]::IsNullOrWhiteSpace($item)) {
                continue
            }

            [pscustomobject]@{
                item = $item.Trim()
                lane = $Lane
                note = $Note
            }
        }
    )
}

function Convert-CameraActionRows {
    param([object[]]$Rows)

    return @(
        foreach ($row in $Rows) {
            $preferredEntrypoint = if ($row.PSObject.Properties.Name -contains 'Preferred entrypoint') { $row.'Preferred entrypoint' } else { '' }
            $why = if ($row.PSObject.Properties.Name -contains 'Why') { $row.Why } else { '' }
            $noteParts = @($preferredEntrypoint, $why) | Where-Object { -not [string]::IsNullOrWhiteSpace($_) }

            [pscustomobject]@{
                item = if ($row.PSObject.Properties.Name -contains 'Action') { $row.Action } else { '' }
                lane = if ($row.PSObject.Properties.Name -contains 'Priority') { "P$($row.Priority)" } else { 'camera' }
                note = ($noteParts -join ' — ')
            }
        }
    )
}

function Format-CandidateLabel {
    param(
        [string]$SourceAddress,
        [string]$BasisForwardOffset
    )

    if ($SourceAddress -and $BasisForwardOffset) {
        return "$SourceAddress@$BasisForwardOffset"
    }

    return $SourceAddress
}

function Get-ClassificationSortKey {
    param([string]$Classification)

    switch ($Classification) {
        'drifting' { return 0 }
        'basis-unresolved' { return 1 }
        'dead-nonresponsive' { return 2 }
        default { return 3 }
    }
}

function Try-ParseSortableDate {
    param([string]$Value)

    if ([string]::IsNullOrWhiteSpace($Value)) {
        return [DateTime]::MinValue
    }

    $parsed = [DateTime]::MinValue
    if ([DateTime]::TryParse($Value, [ref]$parsed)) {
        return $parsed
    }

    return [DateTime]::MinValue
}

function Get-TopCandidates {
    param([object[]]$States)

    if (-not $States) {
        return @()
    }

    $selected = New-Object System.Collections.Generic.List[object]
    $seenKeys = New-Object System.Collections.Generic.HashSet[string]

    $candidateGroups = @(
        @($States | Where-Object { $_.LatestClassification -eq 'drifting' } | Sort-Object @{ Expression = { Try-ParseSortableDate $_.LatestObservedAtUtc }; Descending = $true }),
        @($States | Where-Object { $_.LatestClassification -eq 'basis-unresolved' } | Sort-Object @{ Expression = { Try-ParseSortableDate $_.LatestObservedAtUtc }; Descending = $true }),
        @($States | Where-Object { $_.DiscoveryMode -eq 'pointer-hop' } | Sort-Object @{ Expression = { $_.SearchScore }; Descending = $true }, @{ Expression = { Try-ParseSortableDate $_.LatestObservedAtUtc }; Descending = $true }),
        @($States | Sort-Object @{ Expression = { Get-ClassificationSortKey $_.LatestClassification } }, @{ Expression = { $_.SearchScore }; Descending = $true }, @{ Expression = { Try-ParseSortableDate $_.LatestObservedAtUtc }; Descending = $true })
    )

    foreach ($group in $candidateGroups) {
        foreach ($state in $group) {
            if (-not $seenKeys.Add($state.CandidateKey)) {
                continue
            }

            $selected.Add([pscustomobject]@{
                    label          = (Format-CandidateLabel -SourceAddress $state.SourceAddress -BasisForwardOffset $state.BasisForwardOffset)
                    classification = $state.LatestClassification
                    reason         = $state.LatestRejectedReason
                    discoveryMode  = $state.DiscoveryMode
                    searchScore    = $state.SearchScore
                })

            if ($selected.Count -ge 4) {
                return $selected.ToArray()
            }
        }
    }

    return $selected.ToArray()
}

function Get-CandidateRows {
    param([object[]]$States)

    if (-not $States) {
        return @()
    }

    return @(
        foreach ($state in ($States | Sort-Object @{ Expression = { Get-ClassificationSortKey $_.LatestClassification } }, @{ Expression = { $_.SearchScore }; Descending = $true }, @{ Expression = { Try-ParseSortableDate $_.LatestObservedAtUtc }; Descending = $true })) {
            [pscustomobject]@{
                candidate      = (Format-CandidateLabel -SourceAddress $state.SourceAddress -BasisForwardOffset $state.BasisForwardOffset)
                sourceAddress  = $state.SourceAddress
                basisOffset    = $state.BasisForwardOffset
                classification = $state.LatestClassification
                rejectedReason = $state.LatestRejectedReason
                discoveryMode  = $state.DiscoveryMode
                rootAddress    = $state.RootAddress
                responsive     = $state.LatestResponsive
                basisRecovered = $state.BasisRecovered
                yawRecovered   = $state.YawRecovered
                searchScore    = $state.SearchScore
                ledgerPenalty  = $state.SearchLedgerPenalty
                observedAt     = $state.LatestObservedAtUtc
            }
        }
    )
}

function New-EmptyBranchData {
    param(
        [string]$Id,
        [string]$Name,
        [string]$Path,
        [bool]$IsCurrent,
        [string]$Role,
        [string]$Status,
        [string]$Bottleneck
    )

    return [ordered]@{
        id         = $Id
        name       = $Name
        path       = (Convert-ToDashboardPath $Path)
        isCurrent  = $IsCurrent
        role       = $Role
        status     = $Status
        bottleneck = $Bottleneck
        truth      = @()
        latestRuns = [ordered]@{
            screen   = [ordered]@{ label = 'Latest screen run'; at = $null; summary = 'No structured screen run data configured.' }
            recovery = [ordered]@{ label = 'Latest recovery run'; at = $null; summary = 'No structured recovery data configured.' }
            probe    = [ordered]@{ label = 'Latest addon probe'; at = $null; summary = 'No structured probe data configured.' }
        }
        workboard  = [ordered]@{
            now         = @()
            parallelNow = @()
            next        = @()
            parked      = @()
        }
        candidates = [ordered]@{
            counts = [ordered]@{}
            top    = @()
            rows   = @()
        }
        handoff    = [ordered]@{
            ready   = $false
            path    = ''
            summary = 'No branch handoff doc configured in v1.'
        }
        docs       = [ordered]@{
            truthUpdatedAt      = $null
            workboardUpdatedAt  = $null
            handoffUpdatedAt    = $null
        }
        sources    = @()
        warnings   = @()
    }
}

function Build-RichActorBranch {
    param(
        [string]$RepoRoot,
        [hashtable]$BaseData
    )

    $truthPath = Join-Path $RepoRoot 'docs\recovery\current-truth.md'
    $workboardPath = Join-Path $RepoRoot 'docs\branch-workboard-codex-actor-yaw-pitch.md'
    $handoffPath = Join-Path $RepoRoot 'docs\handoffs\2026-04-15-codex-actor-yaw-pitch.md'
    $offlinePath = Join-Path $RepoRoot 'scripts\captures\actor-orientation-offline-analysis.json'
    $screenPath = Join-Path $RepoRoot 'scripts\captures\actor-orientation-candidate-screen.json'
    $recoveryPath = Join-Path $RepoRoot 'scripts\captures\actor-orientation-recovery.json'
    $probePath = Join-Path $RepoRoot 'scripts\captures\readerbridge-orientation-probe.json'

    $warnings = New-Object System.Collections.Generic.List[string]
    foreach ($warning in @($BaseData.warnings)) {
        if (-not [string]::IsNullOrWhiteSpace($warning)) {
            $warnings.Add($warning)
        }
    }
    $branchData = [ordered]@{} + $BaseData

    $truthLines = Read-TextLines -Path $truthPath
    $workboardLines = Read-TextLines -Path $workboardPath
    $handoffLines = Read-TextLines -Path $handoffPath

    $truthRows = Convert-MarkdownTruthRows (Get-MarkdownTableAfterHeading -Lines $truthLines -Heading 'Current status')
    $nowRows = Convert-WorkboardRows (Get-MarkdownTableAfterHeading -Lines $workboardLines -Heading 'Now')
    $parallelRows = Convert-WorkboardRows (Get-MarkdownTableAfterHeading -Lines $workboardLines -Heading 'Parallel now')
    $nextRows = Convert-WorkboardRows (Get-MarkdownTableAfterHeading -Lines $workboardLines -Heading 'Next')
    $parkedRows = Convert-WorkboardRows (Get-MarkdownTableAfterHeading -Lines $workboardLines -Heading 'Parked')

    $offline = Read-JsonFile -Path $offlinePath
    $screen = Read-JsonFile -Path $screenPath
    $recovery = Read-JsonFile -Path $recoveryPath
    $probe = Read-JsonFile -Path $probePath

    if ((Get-ItemCount -Value $truthRows) -le 0) { $warnings.Add('Current truth table could not be parsed.') }
    if ((Get-ItemCount -Value $nowRows) -le 0) { $warnings.Add('Workboard Now section could not be parsed.') }
    if (-not $offline) { $warnings.Add('Offline candidate analysis JSON is missing.') }
    if (-not $screen) { $warnings.Add('Current candidate screen JSON is missing.') }
    if (-not $recovery) { $warnings.Add('Recovery JSON is missing.') }
    if (-not $probe) { $warnings.Add('ReaderBridge probe JSON is missing.') }

    $classificationCounts = if ($offline) { Convert-ClassificationsToMap -Rows $offline.LatestClassificationSummary } else { [pscustomobject]@{} }
    $candidateStates = if ($offline) { @($offline.LatestCandidateStates) } else { @() }
    $topCandidates = Get-TopCandidates -States $candidateStates
    $candidateRows = Get-CandidateRows -States $candidateStates

    $screenSummary = 'No structured screen run data configured.'
    if ($screen) {
        $screenSummary = "Screened $($screen.ScreenedCandidateCount) candidates; responsive=$($screen.ResponsiveCandidateCount); dead=$($screen.DeadCandidateCount); recoveryRuns=$($screen.RecoveryRunCount)."
    }

    $recoverySummary = 'No structured recovery data configured.'
    if ($recovery) {
        $recoverySummary = "BasisRecovered=$($recovery.Recovery.BasisRecovered); YawRecovered=$($recovery.Recovery.YawRecovered); PitchRecovered=$($recovery.Recovery.PitchRecovered); IdleConsistencyPass=$($recovery.Recovery.IdleConsistencyPass)."
    }

    $probeSummary = 'No structured probe data configured.'
    if ($probe) {
        $probeSummary = "PlayerSignal=$($probe.Player.HasAnySignal); directHeadingApiAvailable=$($probe.Player.DirectHeadingApiAvailable); detailCandidates=$($probe.Player.DetailCandidateCount); stateCandidates=$($probe.Player.StateCandidateCount)."
    }

    $recommendedActions = Get-MarkdownListAfterHeading -Lines $handoffLines -Heading 'Recommended first action in the next conversation'
    $handoffSummary = if ((Get-ItemCount -Value $recommendedActions) -gt 0) { $recommendedActions[0] } else { 'Handoff doc present; next conversation can start from docs.' }

    if ($offline -and (($offline.Notes | Out-String) -match 'no candidate currently has surviving positive evidence')) {
        $warnings.Add('No candidate currently has surviving positive evidence after the latest merge.')
    }

    if ($probe -and -not $probe.Player.HasAnySignal) {
        $warnings.Add('ReaderBridge orientation probe currently reports no player-facing signal.')
    }

    if ($truthRows | Where-Object { $_.label -eq 'Source-chain refresh' -and $_.status -match 'broken' }) {
        $warnings.Add('Source-chain refresh is still broken after the update.')
    }

    $branchData.status = 'active'
    $branchData.bottleneck = if ((Get-ItemCount -Value $nowRows) -gt 0) { $nowRows[0].item } else { $branchData.bottleneck }
    $branchData.truth = $truthRows
    $branchData.latestRuns = [ordered]@{
        screen   = [ordered]@{ label = 'Latest screen run'; at = $(if ($screen) { $screen.GeneratedAtUtc } else { $null }); summary = $screenSummary }
        recovery = [ordered]@{ label = 'Latest recovery run'; at = $(if ($recovery) { $recovery.GeneratedAtUtc } else { $null }); summary = $recoverySummary }
        probe    = [ordered]@{ label = 'Latest addon probe'; at = $(if ($probe) { $probe.GeneratedAtUtc } else { $null }); summary = $probeSummary }
    }
    $branchData.workboard = [ordered]@{
        now         = $nowRows
        parallelNow = $parallelRows
        next        = $nextRows
        parked      = $parkedRows
    }
    $branchData.candidates = [ordered]@{
        counts = $classificationCounts
        top    = $topCandidates
        rows   = $candidateRows
    }
    $branchData.handoff = [ordered]@{
        ready   = ((Test-Path -LiteralPath $handoffPath) -and (Test-Path -LiteralPath $workboardPath))
        path    = (Convert-ToDashboardPath $handoffPath)
        summary = $handoffSummary
    }
    $branchData.docs = [ordered]@{
        truthUpdatedAt     = (Try-GetFileLastWrite -Path $truthPath)
        workboardUpdatedAt = (Try-GetFileLastWrite -Path $workboardPath)
        handoffUpdatedAt   = (Try-GetFileLastWrite -Path $handoffPath)
    }
    $branchData.sources = @(
        (New-SourceReference -Label 'Current truth doc' -Path $truthPath -Note 'Parsed for the truth rows shown in the branch overview.'),
        (New-SourceReference -Label 'Branch workboard' -Path $workboardPath -Note 'Parsed for Now / Parallel now / Next sections.'),
        (New-SourceReference -Label 'Branch handoff' -Path $handoffPath -Note 'Used for handoff readiness and next-conversation summary.'),
        (New-SourceReference -Label 'Offline analysis JSON' -Path $offlinePath -Note 'Drives candidate counts, ranking, and the detailed table.'),
        (New-SourceReference -Label 'Candidate screen JSON' -Path $screenPath -Note 'Feeds the latest screen-run summary.'),
        (New-SourceReference -Label 'Recovery JSON' -Path $recoveryPath -Note 'Feeds the latest recovery summary.'),
        (New-SourceReference -Label 'ReaderBridge probe JSON' -Path $probePath -Note 'Feeds the latest addon-probe summary.')
    )
    $branchData.warnings = @($warnings)

    return [pscustomobject]$branchData
}

function Build-RichDashboardBranch {
    param(
        [string]$RepoRoot,
        [hashtable]$BaseData,
        [object[]]$AllBranches,
        [object[]]$Worktrees,
        [string]$GeneratedAt
    )

    $workboardPath = Join-Path $RepoRoot 'docs\branch-workboard-codex-dashboard-hud.md'
    $handoffPath = Join-Path $RepoRoot 'docs\handoffs\2026-04-15-codex-dashboard-hud.md'
    $dashboardReadmePath = Join-Path $RepoRoot 'tools\dashboard\README.md'
    $dashboardHtmlPath = Join-Path $RepoRoot 'tools\dashboard\index.html'
    $dashboardAppPath = Join-Path $RepoRoot 'tools\dashboard\app.js'
    $dashboardStylesPath = Join-Path $RepoRoot 'tools\dashboard\styles.css'
    $dashboardDataPath = Join-Path $RepoRoot 'tools\dashboard\dashboard-data.js'
    $buildScriptPath = Join-Path $RepoRoot 'scripts\build-dashboard-summary.ps1'
    $openDashboardScriptPath = Join-Path $RepoRoot 'scripts\open-dashboard.ps1'
    $openDashboardCmdPath = Join-Path $RepoRoot 'scripts\open-dashboard.cmd'

    $warnings = New-Object System.Collections.Generic.List[string]
    foreach ($warning in @($BaseData.warnings)) {
        if (-not [string]::IsNullOrWhiteSpace($warning)) {
            $warnings.Add($warning)
        }
    }

    $branchData = [ordered]@{} + $BaseData
    $workboardLines = Read-TextLines -Path $workboardPath
    $handoffLines = Read-TextLines -Path $handoffPath
    $gitStatus = Get-GitStatusSummary -RepoRoot $RepoRoot
    $headCommit = Get-GitHeadCommitInfo -RepoRoot $RepoRoot

    $nowRows = Convert-WorkboardRows (Get-MarkdownTableAfterHeading -Lines $workboardLines -Heading 'Now')
    $parallelRows = Convert-WorkboardRows (Get-MarkdownTableAfterHeading -Lines $workboardLines -Heading 'Parallel now')
    $nextRows = Convert-WorkboardRows (Get-MarkdownTableAfterHeading -Lines $workboardLines -Heading 'Next')
    $parkedRows = Convert-WorkboardRows (Get-MarkdownTableAfterHeading -Lines $workboardLines -Heading 'Parked')
    $recommendedActions = Get-MarkdownListAfterHeading -Lines $handoffLines -Heading 'Recommended first action in the next conversation'

    if ((Get-ItemCount -Value $workboardLines) -le 0) { $warnings.Add('Dashboard branch workboard doc is missing.') }
    if ((Get-ItemCount -Value $handoffLines) -le 0) { $warnings.Add('Dashboard branch handoff doc is missing.') }
    if ((Get-ItemCount -Value $nowRows) -le 0) { $warnings.Add('Dashboard workboard Now section could not be parsed.') }
    if (-not (Test-Path -LiteralPath $dashboardReadmePath)) { $warnings.Add('Dashboard README is missing.') }
    if (-not (Test-Path -LiteralPath $openDashboardScriptPath)) { $warnings.Add('Dashboard launcher PowerShell script is missing.') }
    if (-not (Test-Path -LiteralPath $openDashboardCmdPath)) { $warnings.Add('Dashboard launcher CMD wrapper is missing.') }

    if ($gitStatus.total -gt 0) {
        $warnings.Add("Current worktree has $($gitStatus.total) pending change(s).")
    }

    $richBranchNames = @('codex/dashboard-hud', 'codex/actor-yaw-pitch', 'feature/camera-orientation-discovery')
    $richBranchCount = @($AllBranches | Where-Object { $_.name -in $richBranchNames }).Count

    $sourceReferences = @(
        (New-SourceReference -Label 'Dashboard app shell' -Path $dashboardHtmlPath -Note 'Static HTML entrypoint that loads the generated dashboard data and UI bundle.'),
        (New-SourceReference -Label 'Dashboard UI bundle' -Path $dashboardAppPath -Note 'Vanilla JS renderer for the branch list, overview cards, metrics, and details.'),
        (New-SourceReference -Label 'Dashboard stylesheet' -Path $dashboardStylesPath -Note 'Dark responsive layout and component styling for the dashboard shell.'),
        (New-SourceReference -Label 'Compiled dashboard data' -Path $dashboardDataPath -Note 'Generated snapshot consumed directly by the browser.'),
        (New-SourceReference -Label 'Dashboard generator' -Path $buildScriptPath -Note 'Compiles git, docs, and capture artifacts into dashboard-data.js.'),
        (New-SourceReference -Label 'Dashboard README' -Path $dashboardReadmePath -Note 'Usage and maintenance notes for the dashboard workflow.'),
        (New-SourceReference -Label 'Launcher script' -Path $openDashboardScriptPath -Note 'Rebuilds and opens the dashboard in the default browser.'),
        (New-SourceReference -Label 'Launcher CMD wrapper' -Path $openDashboardCmdPath -Note 'Convenience entrypoint for cmd.exe users.'),
        (New-SourceReference -Label 'Branch workboard' -Path $workboardPath -Note 'Parsed for the dashboard branch Now / Parallel now / Next sections.'),
        (New-SourceReference -Label 'Branch handoff' -Path $handoffPath -Note 'Used for handoff readiness and next-conversation summary.')
    )
    $presentSourceCount = @($sourceReferences | Where-Object { $_.present }).Count

    $truthRows = @(
        [pscustomobject]@{ label = 'Dashboard shell'; status = $(if ((Test-Path -LiteralPath $dashboardHtmlPath) -and (Test-Path -LiteralPath $dashboardAppPath) -and (Test-Path -LiteralPath $dashboardStylesPath)) { 'working' } else { 'missing pieces' }) },
        [pscustomobject]@{ label = 'Snapshot generator'; status = $(if (Test-Path -LiteralPath $buildScriptPath) { 'working' } else { 'missing' }) },
        [pscustomobject]@{ label = 'Open-in-browser launcher'; status = $(if ((Test-Path -LiteralPath $openDashboardScriptPath) -and (Test-Path -LiteralPath $openDashboardCmdPath)) { 'working' } else { 'missing pieces' }) },
        [pscustomobject]@{ label = 'Rich branch coverage'; status = "$richBranchCount configured" },
        [pscustomobject]@{ label = 'Refresh model'; status = 'manual snapshot' },
        [pscustomobject]@{ label = 'Current worktree'; status = $(if ($gitStatus.total -gt 0) { 'dirty' } else { 'clean' }) }
    )

    $buildSummary = "Compiled $((Get-ItemCount -Value $AllBranches)) branches across $((Get-ItemCount -Value $Worktrees)) worktree(s) into dashboard-data.js."
    $commitSummary = if ($headCommit.subject) {
        $shortSha = if ($headCommit.sha.Length -ge 7) { $headCommit.sha.Substring(0, 7) } else { $headCommit.sha }
        "$($headCommit.subject) ($shortSha)"
    } else {
        'No commit summary available.'
    }
    $worktreeSummary = "dirty=$($gitStatus.total); modified=$($gitStatus.modified); added=$($gitStatus.added); deleted=$($gitStatus.deleted); renamed=$($gitStatus.renamed); untracked=$($gitStatus.untracked)."
    $handoffSummary = if ((Get-ItemCount -Value $recommendedActions) -gt 0) { $recommendedActions[0] } else { 'Keep the dashboard branch aligned with real source files, rich branch inputs, and the launcher flow.' }

    $branchData.status = if ($gitStatus.total -gt 0) { 'partial' } else { 'active' }
    $branchData.bottleneck = if ((Get-ItemCount -Value $nowRows) -gt 0) { $nowRows[0].item } else { $branchData.bottleneck }
    $branchData.truth = $truthRows
    $branchData.latestRuns = [ordered]@{
        screen   = [ordered]@{ label = 'Latest dashboard build'; at = $GeneratedAt; summary = $buildSummary }
        recovery = [ordered]@{ label = 'Latest branch commit'; at = $headCommit.committedAt; summary = $commitSummary }
        probe    = [ordered]@{ label = 'Working tree state'; at = $gitStatus.observedAt; summary = $worktreeSummary }
    }
    $branchData.workboard = [ordered]@{
        now         = $nowRows
        parallelNow = $parallelRows
        next        = $nextRows
        parked      = $parkedRows
    }
    $branchData.candidates = [ordered]@{
        counts = [ordered]@{
            branches    = (Get-ItemCount -Value $AllBranches)
            richBranches = $richBranchCount
            worktrees   = (Get-ItemCount -Value $Worktrees)
            sources     = $presentSourceCount
            dirtyFiles  = $gitStatus.total
        }
        top    = @(
            [pscustomobject]@{
                label          = 'Dashboard toolchain'
                classification = 'active'
                reason         = "$presentSourceCount dashboard source file(s) are present, including the generator and launcher."
                discoveryMode  = 'codex/dashboard-hud'
                searchScore    = $presentSourceCount
            },
            [pscustomobject]@{
                label          = 'Cross-branch coverage'
                classification = $(if ($richBranchCount -ge 3) { 'active' } else { 'partial' })
                reason         = "$richBranchCount rich branch view(s) are configured in the current snapshot."
                discoveryMode  = 'branch coverage'
                searchScore    = $richBranchCount
            },
            [pscustomobject]@{
                label          = 'Worktree visibility'
                classification = $(if ((Get-ItemCount -Value $Worktrees) -gt 0) { 'active' } else { 'partial' })
                reason         = "$((Get-ItemCount -Value $Worktrees)) checked-out worktree(s) are visible to the dashboard generator."
                discoveryMode  = 'git worktree'
                searchScore    = (Get-ItemCount -Value $Worktrees)
            },
            [pscustomobject]@{
                label          = 'Current worktree state'
                classification = $(if ($gitStatus.total -gt 0) { 'dirty' } else { 'clean' })
                reason         = $worktreeSummary
                discoveryMode  = 'git status'
                searchScore    = $gitStatus.total
            }
        )
        rows   = @()
    }
    $branchData.handoff = [ordered]@{
        ready   = ((Test-Path -LiteralPath $handoffPath) -and (Test-Path -LiteralPath $workboardPath))
        path    = (Convert-ToDashboardPath $handoffPath)
        summary = $handoffSummary
    }
    $branchData.docs = [ordered]@{
        truthUpdatedAt     = (Try-GetFileLastWrite -Path $buildScriptPath)
        workboardUpdatedAt = (Try-GetFileLastWrite -Path $workboardPath)
        handoffUpdatedAt   = (Try-GetFileLastWrite -Path $handoffPath)
    }
    $branchData.sources = $sourceReferences
    $branchData.warnings = @($warnings)

    return [pscustomobject]$branchData
}

function Build-RichCameraBranch {
    param(
        [string]$BranchRoot,
        [hashtable]$BaseData
    )

    $workflowPath = Join-Path $BranchRoot 'docs\camera-orientation-discovery.md'
    $inputWorkflowPath = Join-Path $BranchRoot 'docs\input-control-workflow.md'
    $historicalHandoffPath = Join-Path $BranchRoot 'docs\camera-discovery-handoff.md'
    $anchorPath = Join-Path $BranchRoot 'scripts\captures\player-current-anchor.json'
    $coordWriteTraceStatusPath = Join-Path $BranchRoot 'scripts\captures\player-coord-write-trace.status.txt'

    $warnings = New-Object System.Collections.Generic.List[string]
    foreach ($warning in @($BaseData.warnings)) {
        if (-not [string]::IsNullOrWhiteSpace($warning)) {
            $warnings.Add($warning)
        }
    }

    $branchData = [ordered]@{} + $BaseData
    $workflowLines = Read-TextLines -Path $workflowPath
    $inputWorkflowLines = Read-TextLines -Path $inputWorkflowPath
    $workflowDoc = Read-TextLines -Path $historicalHandoffPath
    $anchor = Read-JsonFile -Path $anchorPath
    $coordWriteTraceStatus = Read-KeyValueFile -Path $coordWriteTraceStatusPath

    $recommendedActions = Convert-CameraActionRows (Get-MarkdownTableAfterHeading -Lines $inputWorkflowLines -Heading 'Recommended action order')
    $engineeringTargets = Get-MarkdownListAfterHeading -Lines $workflowLines -Heading 'Engineering target from here'

    if ((Get-ItemCount -Value $workflowLines) -le 0) { $warnings.Add('Camera workflow doc is missing from the camera worktree.') }
    if ((Get-ItemCount -Value $inputWorkflowLines) -le 0) { $warnings.Add('Input-control workflow doc is missing from the camera worktree.') }
    if (-not $anchor) { $warnings.Add('Player current anchor capture is missing for the camera branch.') }
    if (-not $coordWriteTraceStatus) { $warnings.Add('Coord write-trace status capture is missing for the camera branch.') }

    if ($coordWriteTraceStatus -and $coordWriteTraceStatus.status -and $coordWriteTraceStatus.status -ne 'ok') {
        $traceError = if ($coordWriteTraceStatus.error) { $coordWriteTraceStatus.error } else { 'non-ok status recorded' }
        $warnings.Add("Latest coord write trace recorded $($coordWriteTraceStatus.status): $traceError")
    }

    $truthRows = @(
        [pscustomobject]@{ label = 'Live yaw path'; status = 'verified' },
        [pscustomobject]@{ label = 'Derived pitch path'; status = 'usable' },
        [pscustomobject]@{ label = 'Direct standalone pitch scalar'; status = 'unresolved' },
        [pscustomobject]@{ label = 'Controller object'; status = 'unresolved' },
        [pscustomobject]@{ label = 'Input/control workflow'; status = 'canonical' }
    )

    $anchorSummary = 'No structured anchor capture is configured.'
    if ($anchor) {
        $selectionSource = if ($anchor.SelectionSource) { $anchor.SelectionSource } else { 'unknown source' }
        $anchorSummary = "Anchor $($anchor.AddressHex); family=$($anchor.FamilyId); selection=$selectionSource; coords=[$($anchor.CoordXOffset), $($anchor.CoordYOffset), $($anchor.CoordZOffset)]."
    }

    $traceSummary = 'No coord write-trace status is configured.'
    $traceSavedAt = $null
    if ($coordWriteTraceStatus) {
        $traceSavedAt = if ($coordWriteTraceStatus.savedAtUtc) { $coordWriteTraceStatus.savedAtUtc } else { Try-GetFileLastWrite -Path $coordWriteTraceStatusPath }
        $statusParts = @(
            $(if ($coordWriteTraceStatus.status) { "status=$($coordWriteTraceStatus.status)" }),
            $(if ($coordWriteTraceStatus.stage) { "stage=$($coordWriteTraceStatus.stage)" }),
            $(if ($coordWriteTraceStatus.error) { "error=$($coordWriteTraceStatus.error)" })
        ) | Where-Object { -not [string]::IsNullOrWhiteSpace($_) }
        $traceSummary = ($statusParts -join '; ')
    }

    $workflowSummary = 'Workflow doc is missing.'
    if ((Get-ItemCount -Value $workflowLines) -gt 0) {
        $workflowSummary = 'Live yaw verified; derived pitch usable via orbit derivation; direct pitch scalar unresolved.'
    }

    $handoffSummary = if ((Get-ItemCount -Value $engineeringTargets) -ge 2) {
        $engineeringTargets[1]
    } elseif ((Get-ItemCount -Value $engineeringTargets) -ge 1) {
        $engineeringTargets[0]
    } else {
        'Preserve the working live read path and trace toward the authoritative controller object.'
    }

    $branchData.status = 'partial'
    $branchData.bottleneck = $handoffSummary
    $branchData.truth = $truthRows
    $branchData.latestRuns = [ordered]@{
        screen   = [ordered]@{ label = 'Latest anchor capture'; at = $(if ($anchor) { $anchor.SavedAtUtc } else { $null }); summary = $anchorSummary }
        recovery = [ordered]@{ label = 'Latest coord write trace'; at = $traceSavedAt; summary = $traceSummary }
        probe    = [ordered]@{ label = 'Workflow freshness'; at = (Try-GetFileLastWrite -Path $workflowPath); summary = $workflowSummary }
    }
    $branchData.workboard = [ordered]@{
        now         = @($recommendedActions | Select-Object -First 3)
        parallelNow = (Convert-ListToWorkboardRows -Items $engineeringTargets -Lane 'workflow')
        next        = @($recommendedActions | Select-Object -Skip 3 -First 3)
        parked      = @()
    }
    $branchData.candidates = [ordered]@{
        counts = [ordered]@{
            workflowDocs = $(if ((Get-ItemCount -Value $workflowLines) -gt 0) { 2 } else { 0 })
            captures     = $(if ($anchor) { 1 } else { 0 }) + $(if ($coordWriteTraceStatus) { 1 } else { 0 })
        }
        top    = @()
        rows   = @()
    }
    $branchData.handoff = [ordered]@{
        ready   = ((Test-Path -LiteralPath $workflowPath) -and (Test-Path -LiteralPath $inputWorkflowPath))
        path    = (Convert-ToDashboardPath $workflowPath)
        summary = $handoffSummary
    }
    $branchData.docs = [ordered]@{
        truthUpdatedAt     = (Try-GetFileLastWrite -Path $workflowPath)
        workboardUpdatedAt = (Try-GetFileLastWrite -Path $inputWorkflowPath)
        handoffUpdatedAt   = (Try-GetFileLastWrite -Path $workflowPath)
    }
    $branchData.sources = @(
        (New-SourceReference -Label 'Active camera workflow doc' -Path $workflowPath -Note 'Primary source for the current camera-branch truth and bottleneck.'),
        (New-SourceReference -Label 'Input/control workflow doc' -Path $inputWorkflowPath -Note 'Parsed for the recommended action order shown in the workboard.'),
        (New-SourceReference -Label 'Historical handoff doc' -Path $historicalHandoffPath -Note 'Background-only handoff retained for context; not the active workflow.'),
        (New-SourceReference -Label 'Current anchor capture' -Path $anchorPath -Note 'Feeds the latest anchor-capture summary.'),
        (New-SourceReference -Label 'Coord write-trace status' -Path $coordWriteTraceStatusPath -Note 'Feeds the latest coord write-trace summary and warnings.')
    )
    $branchData.warnings = @($warnings)

    return [pscustomobject]$branchData
}

$repoRoot = Get-ResolvedPath -Path $RepoPath
if (-not $OutputPath) {
    $OutputPath = Join-Path $repoRoot 'tools\dashboard\dashboard-data.js'
}

$outputDirectory = Split-Path -Parent $OutputPath
if (-not (Test-Path -LiteralPath $outputDirectory)) {
    New-Item -ItemType Directory -Path $outputDirectory -Force | Out-Null
}

$worktrees = @(Get-GitWorktrees -RepoRoot $repoRoot)
$branches = @(Get-GitBranches -RepoRoot $repoRoot)
$worktreeByBranch = @{}
foreach ($worktree in $worktrees) {
    if ($worktree.branch) {
        $worktreeByBranch[$worktree.branch] = $worktree
    }
}

$currentBranchLines = @(Invoke-GitLines -RepoRoot $repoRoot -Arguments @('branch', '--show-current'))
$currentBranch = ([string]($currentBranchLines | Select-Object -First 1)).Trim()
$dashboardGeneratedAt = ([DateTimeOffset]::Now).ToString('o')
$knownBranchWeights = @{
    'codex/dashboard-hud' = 20
    'codex/actor-yaw-pitch' = 10
    'main' = 30
    'feature/camera-orientation-discovery' = 40
}

$branchObjects = New-Object System.Collections.Generic.List[object]
foreach ($branch in $branches | Sort-Object @{ Expression = { if ($_.name -eq $currentBranch) { -100 } elseif ($knownBranchWeights.ContainsKey($_.name)) { $knownBranchWeights[$_.name] } else { 100 } } }, @{ Expression = { $_.name } }) {
    $worktree = if ($worktreeByBranch.ContainsKey($branch.name)) { $worktreeByBranch[$branch.name] } else { $null }
    $role = Get-BranchRole -BranchName $branch.name
    $isCurrent = ($branch.name -eq $currentBranch)
    $status = if ($branch.name -eq 'codex/actor-yaw-pitch') { 'active' } elseif ($isCurrent -or $worktree) { 'partial' } else { 'minimal' }
    $path = if ($worktree) { $worktree.path } else { $repoRoot }

    $base = New-EmptyBranchData `
        -Id $branch.name `
        -Name $branch.name `
        -Path $path `
        -IsCurrent $isCurrent `
        -Role $role `
        -Status $status `
        -Bottleneck (Get-BranchBottleneck -BranchName $branch.name -Role $role -IsCurrent $isCurrent -CommitSubject $branch.subject)

    if ($worktree -and -not $isCurrent) {
        $base.warnings = @("Checked out in a separate worktree: $($worktree.path)")
    } elseif (-not $worktree) {
        $base.warnings = @('No dedicated worktree is currently checked out for this branch.')
    }

    if ($branch.name -notin @('codex/dashboard-hud', 'codex/actor-yaw-pitch', 'feature/camera-orientation-discovery')) {
        $base.warnings += 'No rich branch-local dashboard data is configured for this branch in v1.'
    }

    if ($branch.name -eq 'codex/dashboard-hud') {
        $branchObjects.Add((Build-RichDashboardBranch -RepoRoot $repoRoot -BaseData $base -AllBranches $branches -Worktrees $worktrees -GeneratedAt $dashboardGeneratedAt))
        continue
    }

    if ($branch.name -eq 'codex/actor-yaw-pitch') {
        $branchObjects.Add((Build-RichActorBranch -RepoRoot $repoRoot -BaseData $base))
        continue
    }

    if ($branch.name -eq 'feature/camera-orientation-discovery') {
        $branchObjects.Add((Build-RichCameraBranch -BranchRoot $path -BaseData $base))
        continue
    }

    $branchObjects.Add([pscustomobject]$base)
}

$worktreeArray = [object[]]$worktrees
$branchArray = $branchObjects.ToArray()
$meta = [ordered]@{
    generatedAt   = $dashboardGeneratedAt
    repoPath      = (Convert-ToDashboardPath $repoRoot)
    currentBranch = $currentBranch
    worktrees     = $worktreeArray
}

$dashboardData = [ordered]@{
    meta            = $meta
    branches        = $branchArray
    defaultBranchId = $currentBranch
}

$json = $dashboardData | ConvertTo-Json -Depth 12
$content = "window.DASHBOARD_DATA = $json;`n"
Set-Content -LiteralPath $OutputPath -Value $content -Encoding UTF8

Write-Host "Wrote dashboard data to $OutputPath"
