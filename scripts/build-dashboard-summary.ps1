[CmdletBinding()]
param(
    [string]$RepoPath = (Join-Path $PSScriptRoot '..'),
    [string]$OutputPath
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

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

    if (-not $Lines.Count) {
        return @()
    }

    $headingPattern = '^\s*#{1,6}\s+' + [Regex]::Escape($Heading) + '\s*$'
    $headingIndex = -1
    for ($i = 0; $i -lt $Lines.Count; $i++) {
        if ($Lines[$i] -match $headingPattern) {
            $headingIndex = $i
            break
        }
    }

    if ($headingIndex -lt 0) {
        return @()
    }

    $tableLines = New-Object System.Collections.Generic.List[string]
    for ($i = $headingIndex + 1; $i -lt $Lines.Count; $i++) {
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
        if (-not $cells.Count) {
            continue
        }

        $row = [ordered]@{}
        for ($cellIndex = 0; $cellIndex -lt $headers.Count; $cellIndex++) {
            $value = if ($cellIndex -lt $cells.Count) { $cells[$cellIndex] } else { '' }
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

    if (-not $Lines.Count) {
        return @()
    }

    $headingPattern = '^\s*#{1,6}\s+' + [Regex]::Escape($Heading) + '\s*$'
    $headingIndex = -1
    for ($i = 0; $i -lt $Lines.Count; $i++) {
        if ($Lines[$i] -match $headingPattern) {
            $headingIndex = $i
            break
        }
    }

    if ($headingIndex -lt 0) {
        return @()
    }

    $items = New-Object System.Collections.Generic.List[string]
    for ($i = $headingIndex + 1; $i -lt $Lines.Count; $i++) {
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
            screen   = [ordered]@{ at = $null; summary = 'No structured screen run data configured.' }
            recovery = [ordered]@{ at = $null; summary = 'No structured recovery data configured.' }
            probe    = [ordered]@{ at = $null; summary = 'No structured probe data configured.' }
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

    if (-not $truthRows.Count) { $warnings.Add('Current truth table could not be parsed.') }
    if (-not $nowRows.Count) { $warnings.Add('Workboard Now section could not be parsed.') }
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
    $handoffSummary = if ($recommendedActions.Count) { $recommendedActions[0] } else { 'Handoff doc present; next conversation can start from docs.' }

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
    $branchData.bottleneck = if ($nowRows.Count) { $nowRows[0].item } else { $branchData.bottleneck }
    $branchData.truth = $truthRows
    $branchData.latestRuns = [ordered]@{
        screen   = [ordered]@{ at = $(if ($screen) { $screen.GeneratedAtUtc } else { $null }); summary = $screenSummary }
        recovery = [ordered]@{ at = $(if ($recovery) { $recovery.GeneratedAtUtc } else { $null }); summary = $recoverySummary }
        probe    = [ordered]@{ at = $(if ($probe) { $probe.GeneratedAtUtc } else { $null }); summary = $probeSummary }
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

    if ($branch.name -ne 'codex/actor-yaw-pitch') {
        $base.warnings += 'No rich branch-local dashboard data is configured for this branch in v1.'
    }

    if ($branch.name -eq 'codex/actor-yaw-pitch') {
        $branchObjects.Add((Build-RichActorBranch -RepoRoot $repoRoot -BaseData $base))
        continue
    }

    $branchObjects.Add([pscustomobject]$base)
}

$worktreeArray = [object[]]$worktrees
$branchArray = $branchObjects.ToArray()
$meta = [ordered]@{
    generatedAt   = ([DateTimeOffset]::Now).ToString('o')
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
