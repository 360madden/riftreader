[CmdletBinding()]
param(
    [string]$RepoPath = (Join-Path $PSScriptRoot '..'),
    [string]$OutputPath,
    [switch]$Watch,
    [int]$PollSeconds = 2
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

if ($PollSeconds -lt 1) {
    throw "PollSeconds must be 1 or greater."
}

$script:RepoRoot = (Resolve-Path -LiteralPath $RepoPath).Path
$script:ReaderProject = Join-Path $script:RepoRoot 'reader\RiftReader.Reader\RiftReader.Reader.csproj'
$script:ReaderBuilt = $false
$script:CurrentPayload = $null
$script:WriteCount = 0
$script:LastAnnouncedStatus = $null

if (-not $OutputPath) {
    $OutputPath = Join-Path $script:RepoRoot 'tools\dashboard\dashboard-live-data.js'
}

function Convert-ToDashboardPath {
    param([string]$Path)

    if ([string]::IsNullOrWhiteSpace($Path)) {
        return ''
    }

    return ($Path -replace '\\', '/')
}

function Get-CoalescedValue {
    param([Parameter(ValueFromRemainingArguments = $true)] $Values)

    foreach ($value in $Values) {
        if ($null -eq $value) {
            continue
        }

        if ($value -is [string] -and [string]::IsNullOrWhiteSpace($value)) {
            continue
        }

        return $value
    }

    return $null
}

function Ensure-OutputDirectory {
    param([string]$Path)

    $directory = Split-Path -Parent $Path
    if (-not [string]::IsNullOrWhiteSpace($directory) -and -not (Test-Path -LiteralPath $directory)) {
        New-Item -ItemType Directory -Path $directory -Force | Out-Null
    }
}

function Get-PreviousPayload {
    param([string]$Path)

    if (-not (Test-Path -LiteralPath $Path)) {
        return $null
    }

    try {
        $raw = Get-Content -LiteralPath $Path -Raw
        $json = $raw -replace '^\s*window\.DASHBOARD_LIVE_DATA\s*=\s*', '' -replace ';\s*$', ''
        if ([string]::IsNullOrWhiteSpace($json)) {
            return $null
        }

        return ($json | ConvertFrom-Json)
    }
    catch {
        return $null
    }
}

function Get-PayloadSection {
    param(
        [object]$Payload,
        [string]$Name
    )

    if (-not $Payload) {
        return $null
    }

    if ($Payload.PSObject.Properties.Name -contains $Name) {
        return $Payload.$Name
    }

    return $null
}

function Get-ObjectPropertyValue {
    param(
        [object]$Object,
        [string]$Name
    )

    if (-not $Object) {
        return $null
    }

    if ($Object -is [System.Collections.IDictionary] -and $Object.Contains($Name)) {
        return $Object[$Name]
    }

    if ($Object.PSObject.Properties.Name -contains $Name) {
        return $Object.$Name
    }

    return $null
}

function Write-LivePayload {
    param(
        [string]$Path,
        [object]$Payload
    )

    Ensure-OutputDirectory -Path $Path
    $json = $Payload | ConvertTo-Json -Depth 16
    $content = "window.DASHBOARD_LIVE_DATA = $json;`n"
    Set-Content -LiteralPath $Path -Value $content -Encoding UTF8
}

function Ensure-ReaderBuilt {
    if ($script:ReaderBuilt) {
        return
    }

    $buildOutput = @(& dotnet build $script:ReaderProject -v quiet 2>&1)
    if ($LASTEXITCODE -ne 0) {
        $message = ($buildOutput | ForEach-Object { $_.ToString() }) -join [Environment]::NewLine
        throw "Unable to build RiftReader.Reader.`n$message"
    }

    $script:ReaderBuilt = $true
}

function Invoke-ReaderJsonCommand {
    param(
        [string[]]$Arguments,
        [string]$CommandName
    )

    try {
        Ensure-ReaderBuilt
    }
    catch {
        return [pscustomobject]@{
            success = $false
            data    = $null
            error   = $_.Exception.Message
        }
    }

    $command = @('run', '--project', $script:ReaderProject, '--no-build', '--') + $Arguments
    $outputLines = @(& dotnet @command 2>&1)
    $exitCode = $LASTEXITCODE
    $outputText = ($outputLines | ForEach-Object { $_.ToString() }) -join [Environment]::NewLine
    $outputText = $outputText.Trim()

    if ($exitCode -ne 0) {
        $message = if ($outputText) { $outputText } else { "$CommandName failed." }
        return [pscustomobject]@{
            success = $false
            data    = $null
            error   = $message
        }
    }

    try {
        $data = $outputText | ConvertFrom-Json
        return [pscustomobject]@{
            success = $true
            data    = $data
            error   = $null
        }
    }
    catch {
        return [pscustomobject]@{
            success = $false
            data    = $null
            error   = "$CommandName returned invalid JSON. $($_.Exception.Message)"
        }
    }
}

function Get-GitRepoState {
    try {
        $branchLines = @(& git -C $script:RepoRoot branch --show-current 2>&1)
        if ($LASTEXITCODE -ne 0) {
            throw (($branchLines | ForEach-Object { $_.ToString() }) -join [Environment]::NewLine)
        }

        $statusLines = @(& git -C $script:RepoRoot status --short 2>&1)
        if ($LASTEXITCODE -ne 0) {
            throw (($statusLines | ForEach-Object { $_.ToString() }) -join [Environment]::NewLine)
        }

        $cleanLines = @($statusLines | ForEach-Object { $_.ToString() } | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })
        $modified = 0
        $added = 0
        $deleted = 0
        $renamed = 0
        $untracked = 0

        foreach ($line in $cleanLines) {
            if ($line.StartsWith('??')) {
                $untracked += 1
                continue
            }

            $statusCode = if ($line.Length -ge 2) { $line.Substring(0, 2) } else { $line }
            if ($statusCode -match 'M') { $modified += 1 }
            if ($statusCode -match 'A') { $added += 1 }
            if ($statusCode -match 'D') { $deleted += 1 }
            if ($statusCode -match 'R') { $renamed += 1 }
        }

        return [pscustomobject]@{
            success = $true
            data    = [pscustomobject]@{
                repoPath         = (Convert-ToDashboardPath $script:RepoRoot)
                currentBranch    = ([string]($branchLines | Select-Object -First 1)).Trim()
                changedFileCount = @($cleanLines).Count
                dirty            = (@($cleanLines).Count -gt 0)
                dirtyCounts      = [pscustomobject]@{
                    modified  = $modified
                    added     = $added
                    deleted   = $deleted
                    renamed   = $renamed
                    untracked = $untracked
                }
                changes          = $cleanLines
            }
            error   = $null
        }
    }
    catch {
        return [pscustomobject]@{
            success = $false
            data    = $null
            error   = $_.Exception.Message
        }
    }
}

function New-SourceState {
    param(
        [string]$Status,
        [object]$Section,
        [string]$Error = $null,
        [bool]$UsingPrevious = $false,
        [string]$Fallback = $null
    )

    return [ordered]@{
        status        = $Status
        updatedAt     = (Get-ObjectPropertyValue -Object $Section -Name 'updatedAt')
        usingPrevious = $UsingPrevious
        fallback      = $Fallback
        error         = $Error
    }
}

function New-CoordsPayload {
    param(
        [object]$SnapshotCoord,
        [object]$MemoryX,
        [object]$MemoryY,
        [object]$MemoryZ,
        [object]$ExpectedX,
        [object]$ExpectedY,
        [object]$ExpectedZ
    )

    $snapshotX = if ($SnapshotCoord) { $SnapshotCoord.X } else { $null }
    $snapshotY = if ($SnapshotCoord) { $SnapshotCoord.Y } else { $null }
    $snapshotZ = if ($SnapshotCoord) { $SnapshotCoord.Z } else { $null }

    return [ordered]@{
        x         = (Get-CoalescedValue $snapshotX $MemoryX $ExpectedX)
        y         = (Get-CoalescedValue $snapshotY $MemoryY $ExpectedY)
        z         = (Get-CoalescedValue $snapshotZ $MemoryZ $ExpectedZ)
        memoryX   = $MemoryX
        memoryY   = $MemoryY
        memoryZ   = $MemoryZ
        expectedX = $ExpectedX
        expectedY = $ExpectedY
        expectedZ = $ExpectedZ
    }
}

function New-HealthPayload {
    param(
        [object]$SnapshotUnit,
        [object]$MemoryValue,
        [object]$ExpectedValue,
        [object]$ExpectedMax,
        [object]$Matches
    )

    $snapshotCurrent = if ($SnapshotUnit) { $SnapshotUnit.Hp } else { $null }
    $snapshotMax = if ($SnapshotUnit) { $SnapshotUnit.HpMax } else { $null }
    $snapshotPercent = if ($SnapshotUnit) { $SnapshotUnit.HpPct } else { $null }

    return [ordered]@{
        current  = (Get-CoalescedValue $snapshotCurrent $MemoryValue $ExpectedValue)
        max      = (Get-CoalescedValue $snapshotMax $ExpectedMax)
        percent  = $snapshotPercent
        memory   = $MemoryValue
        expected = $ExpectedValue
        matches  = $Matches
    }
}

function New-LevelPayload {
    param(
        [object]$SnapshotValue,
        [object]$MemoryValue,
        [object]$ExpectedValue,
        [object]$Matches
    )

    return [ordered]@{
        current  = (Get-CoalescedValue $SnapshotValue $MemoryValue $ExpectedValue)
        memory   = $MemoryValue
        expected = $ExpectedValue
        matches  = $Matches
    }
}

function New-ResourcePayload {
    param([object]$SnapshotUnit)

    if (-not $SnapshotUnit) {
        return [ordered]@{
            kind    = $null
            current = $null
            max     = $null
            percent = $null
        }
    }

    return [ordered]@{
        kind    = $SnapshotUnit.ResourceKind
        current = $SnapshotUnit.Resource
        max     = $SnapshotUnit.ResourceMax
        percent = $SnapshotUnit.ResourcePct
    }
}

function New-MatchPayload {
    param([object]$Match)

    if (-not $Match) {
        return $null
    }

    $payload = [ordered]@{}
    foreach ($property in $Match.PSObject.Properties) {
        $payload[$property.Name] = $property.Value
    }

    return $payload
}

function Build-PlayerSection {
    param(
        [object]$SnapshotUnit,
        [object]$PlayerRead,
        [string]$GeneratedAt,
        [string]$Mode
    )

    $playerExpected = Get-ObjectPropertyValue -Object $PlayerRead -Name 'Expected'
    $playerMemory = Get-ObjectPropertyValue -Object $PlayerRead -Name 'Memory'
    $playerMatch = Get-ObjectPropertyValue -Object $PlayerRead -Name 'Match'
    $snapshotName = if ($SnapshotUnit) { $SnapshotUnit.Name } else { $null }
    $snapshotRole = if ($SnapshotUnit) { $SnapshotUnit.Role } else { $null }
    $snapshotLocation = if ($SnapshotUnit) { $SnapshotUnit.LocationName } else { $null }
    $snapshotLevel = if ($SnapshotUnit) { $SnapshotUnit.Level } else { $null }
    $snapshotCoord = if ($SnapshotUnit) { $SnapshotUnit.Coord } else { $null }

    return [ordered]@{
        available     = $true
        updatedAt     = $GeneratedAt
        sourceMode    = $Mode
        sourceFile    = (Get-ObjectPropertyValue -Object $PlayerRead -Name 'ReaderBridgeSourceFile')
        name          = (Get-CoalescedValue $snapshotName (Get-ObjectPropertyValue -Object $playerExpected -Name 'Name') (Get-ObjectPropertyValue -Object $playerMemory -Name 'Name'))
        role          = $snapshotRole
        location      = (Get-CoalescedValue $snapshotLocation (Get-ObjectPropertyValue -Object $playerExpected -Name 'Location') (Get-ObjectPropertyValue -Object $playerMemory -Name 'Location'))
        level         = (New-LevelPayload -SnapshotValue $snapshotLevel -MemoryValue (Get-ObjectPropertyValue -Object $playerMemory -Name 'Level') -ExpectedValue (Get-ObjectPropertyValue -Object $playerExpected -Name 'Level') -Matches (Get-ObjectPropertyValue -Object $playerMatch -Name 'LevelMatches'))
        health        = (New-HealthPayload -SnapshotUnit $SnapshotUnit -MemoryValue (Get-ObjectPropertyValue -Object $playerMemory -Name 'Health') -ExpectedValue (Get-ObjectPropertyValue -Object $playerExpected -Name 'Health') -ExpectedMax (Get-ObjectPropertyValue -Object $playerExpected -Name 'HealthMax') -Matches (Get-ObjectPropertyValue -Object $playerMatch -Name 'HealthMatches'))
        resource      = (New-ResourcePayload -SnapshotUnit $SnapshotUnit)
        coords        = (New-CoordsPayload -SnapshotCoord $snapshotCoord -MemoryX (Get-ObjectPropertyValue -Object $playerMemory -Name 'CoordX') -MemoryY (Get-ObjectPropertyValue -Object $playerMemory -Name 'CoordY') -MemoryZ (Get-ObjectPropertyValue -Object $playerMemory -Name 'CoordZ') -ExpectedX (Get-ObjectPropertyValue -Object $playerExpected -Name 'CoordX') -ExpectedY (Get-ObjectPropertyValue -Object $playerExpected -Name 'CoordY') -ExpectedZ (Get-ObjectPropertyValue -Object $playerExpected -Name 'CoordZ'))
        memoryMatch   = (New-MatchPayload -Match $playerMatch)
        anchor        = [ordered]@{
            address            = (Get-ObjectPropertyValue -Object $playerMemory -Name 'AddressHex')
            familyId           = (Get-ObjectPropertyValue -Object $PlayerRead -Name 'FamilyId')
            familyNotes        = (Get-ObjectPropertyValue -Object $PlayerRead -Name 'FamilyNotes')
            signature          = (Get-ObjectPropertyValue -Object $PlayerRead -Name 'Signature')
            selectionSource    = (Get-ObjectPropertyValue -Object $PlayerRead -Name 'SelectionSource')
            anchorProvenance   = (Get-ObjectPropertyValue -Object $PlayerRead -Name 'AnchorProvenance')
            anchorCacheFile    = (Get-ObjectPropertyValue -Object $PlayerRead -Name 'AnchorCacheFile')
            anchorCacheUsed    = (Get-ObjectPropertyValue -Object $PlayerRead -Name 'AnchorCacheUsed')
            anchorCacheUpdated = (Get-ObjectPropertyValue -Object $PlayerRead -Name 'AnchorCacheUpdated')
            confirmationFile   = (Get-ObjectPropertyValue -Object $PlayerRead -Name 'ConfirmationFile')
        }
        process       = [ordered]@{
            processId   = (Get-ObjectPropertyValue -Object $PlayerRead -Name 'ProcessId')
            processName = (Get-ObjectPropertyValue -Object $PlayerRead -Name 'ProcessName')
        }
    }
}

function Build-PlayerSnapshotOnlySection {
    param(
        [object]$SnapshotUnit,
        [object]$SnapshotDocument,
        [string]$GeneratedAt
    )

    $snapshotCoord = if ($SnapshotUnit) { $SnapshotUnit.Coord } else { $null }

    return [ordered]@{
        available   = $true
        updatedAt   = $GeneratedAt
        sourceMode  = 'snapshot-only'
        sourceFile  = $SnapshotDocument.SourceFile
        name        = $SnapshotUnit.Name
        role        = $SnapshotUnit.Role
        location    = $SnapshotUnit.LocationName
        level       = (New-LevelPayload -SnapshotValue $SnapshotUnit.Level -MemoryValue $null -ExpectedValue $SnapshotUnit.Level -Matches $null)
        health      = (New-HealthPayload -SnapshotUnit $SnapshotUnit -MemoryValue $null -ExpectedValue $SnapshotUnit.Hp -ExpectedMax $SnapshotUnit.HpMax -Matches $null)
        resource    = (New-ResourcePayload -SnapshotUnit $SnapshotUnit)
        coords      = (New-CoordsPayload -SnapshotCoord $snapshotCoord -MemoryX $null -MemoryY $null -MemoryZ $null -ExpectedX $(if ($snapshotCoord) { $snapshotCoord.X } else { $null }) -ExpectedY $(if ($snapshotCoord) { $snapshotCoord.Y } else { $null }) -ExpectedZ $(if ($snapshotCoord) { $snapshotCoord.Z } else { $null }))
        memoryMatch = $null
        anchor      = $null
        process     = $null
    }
}

function Build-TargetSection {
    param(
        [object]$SnapshotUnit,
        [object]$TargetRead,
        [string]$GeneratedAt,
        [string]$Mode
    )

    $hasTarget = Get-ObjectPropertyValue -Object $TargetRead -Name 'HasTarget'
    $targetExpected = Get-ObjectPropertyValue -Object $TargetRead -Name 'Expected'
    $targetMemory = Get-ObjectPropertyValue -Object $TargetRead -Name 'Memory'
    $targetMatch = Get-ObjectPropertyValue -Object $TargetRead -Name 'Match'
    $snapshotName = if ($SnapshotUnit) { $SnapshotUnit.Name } else { $null }
    $snapshotRole = if ($SnapshotUnit) { $SnapshotUnit.Role } else { $null }
    $snapshotLocation = if ($SnapshotUnit) { $SnapshotUnit.LocationName } else { $null }
    $snapshotLevel = if ($SnapshotUnit) { $SnapshotUnit.Level } else { $null }
    $snapshotCoord = if ($SnapshotUnit) { $SnapshotUnit.Coord } else { $null }
    $snapshotDistance = if ($SnapshotUnit) { $SnapshotUnit.Distance } else { $null }

    if ($TargetRead -and $hasTarget -eq $false) {
        return [ordered]@{
            available   = $true
            hasTarget   = $false
            updatedAt   = $GeneratedAt
            sourceMode  = $Mode
            sourceFile  = (Get-ObjectPropertyValue -Object $TargetRead -Name 'ReaderBridgeSourceFile')
            note        = 'No target selected.'
            anchor      = [ordered]@{
                familyId         = (Get-ObjectPropertyValue -Object $TargetRead -Name 'FamilyId')
                familyNotes      = (Get-ObjectPropertyValue -Object $TargetRead -Name 'FamilyNotes')
                selectionSource  = (Get-ObjectPropertyValue -Object $TargetRead -Name 'SelectionSource')
                anchorProvenance = (Get-ObjectPropertyValue -Object $TargetRead -Name 'AnchorProvenance')
            }
            process     = [ordered]@{
                processId   = (Get-ObjectPropertyValue -Object $TargetRead -Name 'ProcessId')
                processName = (Get-ObjectPropertyValue -Object $TargetRead -Name 'ProcessName')
            }
        }
    }

    return [ordered]@{
        available     = $true
        hasTarget     = $true
        updatedAt     = $GeneratedAt
        sourceMode    = $Mode
        sourceFile    = (Get-ObjectPropertyValue -Object $TargetRead -Name 'ReaderBridgeSourceFile')
        name          = (Get-CoalescedValue $snapshotName (Get-ObjectPropertyValue -Object $targetExpected -Name 'Name') (Get-ObjectPropertyValue -Object $targetMemory -Name 'Name'))
        role          = $snapshotRole
        location      = (Get-CoalescedValue $snapshotLocation (Get-ObjectPropertyValue -Object $targetExpected -Name 'Location') (Get-ObjectPropertyValue -Object $targetMemory -Name 'Location'))
        level         = (New-LevelPayload -SnapshotValue $snapshotLevel -MemoryValue (Get-ObjectPropertyValue -Object $targetMemory -Name 'Level') -ExpectedValue (Get-ObjectPropertyValue -Object $targetExpected -Name 'Level') -Matches (Get-ObjectPropertyValue -Object $targetMatch -Name 'LevelMatches'))
        health        = (New-HealthPayload -SnapshotUnit $SnapshotUnit -MemoryValue (Get-ObjectPropertyValue -Object $targetMemory -Name 'Health') -ExpectedValue (Get-ObjectPropertyValue -Object $targetExpected -Name 'Health') -ExpectedMax (Get-ObjectPropertyValue -Object $targetExpected -Name 'HealthMax') -Matches (Get-ObjectPropertyValue -Object $targetMatch -Name 'HealthMatches'))
        resource      = (New-ResourcePayload -SnapshotUnit $SnapshotUnit)
        coords        = (New-CoordsPayload -SnapshotCoord $snapshotCoord -MemoryX (Get-ObjectPropertyValue -Object $targetMemory -Name 'CoordX') -MemoryY (Get-ObjectPropertyValue -Object $targetMemory -Name 'CoordY') -MemoryZ (Get-ObjectPropertyValue -Object $targetMemory -Name 'CoordZ') -ExpectedX (Get-ObjectPropertyValue -Object $targetExpected -Name 'CoordX') -ExpectedY (Get-ObjectPropertyValue -Object $targetExpected -Name 'CoordY') -ExpectedZ (Get-ObjectPropertyValue -Object $targetExpected -Name 'CoordZ'))
        distance      = [ordered]@{
            current  = (Get-CoalescedValue $snapshotDistance (Get-ObjectPropertyValue -Object $targetMemory -Name 'Distance') (Get-ObjectPropertyValue -Object $targetExpected -Name 'Distance'))
            memory   = (Get-ObjectPropertyValue -Object $targetMemory -Name 'Distance')
            expected = (Get-ObjectPropertyValue -Object $targetExpected -Name 'Distance')
            matches  = (Get-ObjectPropertyValue -Object $targetMatch -Name 'DistanceMatchesWithinTolerance')
            delta    = (Get-ObjectPropertyValue -Object $targetMatch -Name 'DeltaDistance')
        }
        memoryMatch   = (New-MatchPayload -Match $targetMatch)
        anchor        = [ordered]@{
            address            = (Get-ObjectPropertyValue -Object $targetMemory -Name 'AddressHex')
            familyId           = (Get-ObjectPropertyValue -Object $TargetRead -Name 'FamilyId')
            familyNotes        = (Get-ObjectPropertyValue -Object $TargetRead -Name 'FamilyNotes')
            signature          = (Get-ObjectPropertyValue -Object $TargetRead -Name 'Signature')
            selectionSource    = (Get-ObjectPropertyValue -Object $TargetRead -Name 'SelectionSource')
            anchorProvenance   = (Get-ObjectPropertyValue -Object $TargetRead -Name 'AnchorProvenance')
            anchorCacheFile    = (Get-ObjectPropertyValue -Object $TargetRead -Name 'AnchorCacheFile')
            anchorCacheUsed    = (Get-ObjectPropertyValue -Object $TargetRead -Name 'AnchorCacheUsed')
            anchorCacheUpdated = (Get-ObjectPropertyValue -Object $TargetRead -Name 'AnchorCacheUpdated')
            confirmationFile   = (Get-ObjectPropertyValue -Object $TargetRead -Name 'ConfirmationFile')
        }
        process       = [ordered]@{
            processId   = (Get-ObjectPropertyValue -Object $TargetRead -Name 'ProcessId')
            processName = (Get-ObjectPropertyValue -Object $TargetRead -Name 'ProcessName')
        }
    }
}

function Build-TargetSnapshotOnlySection {
    param(
        [object]$SnapshotUnit,
        [object]$SnapshotDocument,
        [string]$GeneratedAt
    )

    if (-not $SnapshotUnit) {
        return [ordered]@{
            available  = $true
            hasTarget  = $false
            updatedAt  = $GeneratedAt
            sourceMode = 'snapshot-only'
            sourceFile = $SnapshotDocument.SourceFile
            note       = 'No target selected.'
        }
    }

    $snapshotCoord = if ($SnapshotUnit) { $SnapshotUnit.Coord } else { $null }

    return [ordered]@{
        available   = $true
        hasTarget   = $true
        updatedAt   = $GeneratedAt
        sourceMode  = 'snapshot-only'
        sourceFile  = $SnapshotDocument.SourceFile
        name        = $SnapshotUnit.Name
        role        = $SnapshotUnit.Role
        location    = $SnapshotUnit.LocationName
        level       = (New-LevelPayload -SnapshotValue $SnapshotUnit.Level -MemoryValue $null -ExpectedValue $SnapshotUnit.Level -Matches $null)
        health      = (New-HealthPayload -SnapshotUnit $SnapshotUnit -MemoryValue $null -ExpectedValue $SnapshotUnit.Hp -ExpectedMax $SnapshotUnit.HpMax -Matches $null)
        resource    = (New-ResourcePayload -SnapshotUnit $SnapshotUnit)
        coords      = (New-CoordsPayload -SnapshotCoord $snapshotCoord -MemoryX $null -MemoryY $null -MemoryZ $null -ExpectedX $(if ($snapshotCoord) { $snapshotCoord.X } else { $null }) -ExpectedY $(if ($snapshotCoord) { $snapshotCoord.Y } else { $null }) -ExpectedZ $(if ($snapshotCoord) { $snapshotCoord.Z } else { $null }))
        distance    = [ordered]@{
            current  = $SnapshotUnit.Distance
            memory   = $null
            expected = $SnapshotUnit.Distance
            matches  = $null
            delta    = $null
        }
        memoryMatch = $null
        anchor      = $null
        process     = $null
    }
}

function Build-SnapshotSection {
    param(
        [object]$SnapshotDocument,
        [string]$GeneratedAt
    )

    $current = Get-ObjectPropertyValue -Object $SnapshotDocument -Name 'Current'
    $player = Get-ObjectPropertyValue -Object $current -Name 'Player'
    $target = Get-ObjectPropertyValue -Object $current -Name 'Target'

    return [ordered]@{
        available        = $true
        updatedAt        = $GeneratedAt
        sourceFile       = (Get-ObjectPropertyValue -Object $SnapshotDocument -Name 'SourceFile')
        loadedAt         = (Get-ObjectPropertyValue -Object $SnapshotDocument -Name 'LoadedAtUtc')
        exportCount      = (Get-ObjectPropertyValue -Object $SnapshotDocument -Name 'ExportCount')
        lastReason       = (Get-ObjectPropertyValue -Object $SnapshotDocument -Name 'LastReason')
        status           = (Get-ObjectPropertyValue -Object $current -Name 'Status')
        exportReason     = (Get-ObjectPropertyValue -Object $current -Name 'ExportReason')
        sourceMode       = (Get-ObjectPropertyValue -Object $current -Name 'SourceMode')
        sourceAddon      = (Get-ObjectPropertyValue -Object $current -Name 'SourceAddon')
        sourceVersion    = (Get-ObjectPropertyValue -Object $current -Name 'SourceVersion')
        generatedAtReal  = (Get-ObjectPropertyValue -Object $current -Name 'GeneratedAtRealtime')
        playerName       = (Get-ObjectPropertyValue -Object $player -Name 'Name')
        targetName       = (Get-ObjectPropertyValue -Object $target -Name 'Name')
    }
}

function Resolve-RepoSection {
    param(
        [object]$RepoResult,
        [object]$PreviousSection,
        [string]$GeneratedAt
    )

    if ($RepoResult.success) {
        $section = [ordered]@{}
        foreach ($property in $RepoResult.data.PSObject.Properties) {
            $section[$property.Name] = $property.Value
        }
        $section.updatedAt = $GeneratedAt

        return [pscustomobject]@{
            section = $section
            state   = (New-SourceState -Status 'active' -Section $section)
        }
    }

    if ($PreviousSection) {
        return [pscustomobject]@{
            section = $PreviousSection
            state   = (New-SourceState -Status 'stale' -Section $PreviousSection -Error $RepoResult.error -UsingPrevious $true)
        }
    }

    $section = [ordered]@{
        available        = $false
        updatedAt        = $null
        repoPath         = (Convert-ToDashboardPath $script:RepoRoot)
        currentBranch    = $null
        changedFileCount = 0
        dirty            = $false
        dirtyCounts      = [ordered]@{
            modified  = 0
            added     = 0
            deleted   = 0
            renamed   = 0
            untracked = 0
        }
        changes          = @()
    }

    return [pscustomobject]@{
        section = $section
        state   = (New-SourceState -Status 'error' -Section $section -Error $RepoResult.error)
    }
}

function Resolve-SnapshotSection {
    param(
        [object]$SnapshotResult,
        [object]$PreviousSection,
        [string]$GeneratedAt
    )

    if ($SnapshotResult.success) {
        $section = Build-SnapshotSection -SnapshotDocument $SnapshotResult.data -GeneratedAt $GeneratedAt
        return [pscustomobject]@{
            section = $section
            state   = (New-SourceState -Status 'active' -Section $section)
        }
    }

    if ($PreviousSection) {
        return [pscustomobject]@{
            section = $PreviousSection
            state   = (New-SourceState -Status 'stale' -Section $PreviousSection -Error $SnapshotResult.error -UsingPrevious $true)
        }
    }

    $section = [ordered]@{
        available     = $false
        updatedAt     = $null
        sourceFile    = ''
        loadedAt      = $null
        exportCount   = $null
        lastReason    = $null
        status        = 'missing'
        exportReason  = $null
        sourceMode    = $null
        sourceAddon   = $null
        sourceVersion = $null
        playerName    = $null
        targetName    = $null
    }

    return [pscustomobject]@{
        section = $section
        state   = (New-SourceState -Status 'error' -Section $section -Error $SnapshotResult.error)
    }
}

function Resolve-PlayerSection {
    param(
        [object]$PlayerResult,
        [object]$SnapshotDocument,
        [object]$PreviousSection,
        [string]$GeneratedAt
    )

    $snapshotCurrent = Get-ObjectPropertyValue -Object $SnapshotDocument -Name 'Current'
    $snapshotPlayer = Get-ObjectPropertyValue -Object $snapshotCurrent -Name 'Player'

    if ($PlayerResult.success) {
        $section = Build-PlayerSection -SnapshotUnit $snapshotPlayer -PlayerRead $PlayerResult.data -GeneratedAt $GeneratedAt -Mode 'memory+snapshot'
        return [pscustomobject]@{
            section = $section
            state   = (New-SourceState -Status 'active' -Section $section)
        }
    }

    if ($snapshotPlayer) {
        $section = Build-PlayerSnapshotOnlySection -SnapshotUnit $snapshotPlayer -SnapshotDocument $SnapshotDocument -GeneratedAt $GeneratedAt
        return [pscustomobject]@{
            section = $section
            state   = (New-SourceState -Status 'partial' -Section $section -Error $PlayerResult.error -Fallback 'snapshot-only')
        }
    }

    if ($PreviousSection) {
        return [pscustomobject]@{
            section = $PreviousSection
            state   = (New-SourceState -Status 'stale' -Section $PreviousSection -Error $PlayerResult.error -UsingPrevious $true)
        }
    }

    return [pscustomobject]@{
        section = [ordered]@{
            available = $false
            updatedAt = $null
        }
        state   = (New-SourceState -Status 'error' -Section $null -Error $PlayerResult.error)
    }
}

function Resolve-TargetSection {
    param(
        [object]$TargetResult,
        [object]$SnapshotDocument,
        [object]$PreviousSection,
        [string]$GeneratedAt
    )

    $snapshotCurrent = Get-ObjectPropertyValue -Object $SnapshotDocument -Name 'Current'
    $snapshotTarget = Get-ObjectPropertyValue -Object $snapshotCurrent -Name 'Target'

    if ($TargetResult.success) {
        $section = Build-TargetSection -SnapshotUnit $snapshotTarget -TargetRead $TargetResult.data -GeneratedAt $GeneratedAt -Mode 'memory+snapshot'
        return [pscustomobject]@{
            section = $section
            state   = (New-SourceState -Status 'active' -Section $section)
        }
    }

    if ($SnapshotDocument) {
        $section = Build-TargetSnapshotOnlySection -SnapshotUnit $snapshotTarget -SnapshotDocument $SnapshotDocument -GeneratedAt $GeneratedAt
        return [pscustomobject]@{
            section = $section
            state   = (New-SourceState -Status 'partial' -Section $section -Error $TargetResult.error -Fallback 'snapshot-only')
        }
    }

    if ($PreviousSection) {
        return [pscustomobject]@{
            section = $PreviousSection
            state   = (New-SourceState -Status 'stale' -Section $PreviousSection -Error $TargetResult.error -UsingPrevious $true)
        }
    }

    return [pscustomobject]@{
        section = [ordered]@{
            available = $false
            updatedAt = $null
            hasTarget = $null
        }
        state   = (New-SourceState -Status 'error' -Section $null -Error $TargetResult.error)
    }
}

function Get-OverallStatus {
    param([object[]]$States)

    $statuses = @($States | ForEach-Object { $_.status })
    if (@($statuses).Count -eq 0) {
        return 'error'
    }

    if (@($statuses | Where-Object { $_ -eq 'error' }).Count -eq @($statuses).Count) {
        return 'error'
    }

    if (@($statuses | Where-Object { $_ -ne 'active' }).Count -eq 0) {
        return 'active'
    }

    return 'partial'
}

function Build-LivePayload {
    param(
        [object]$PreviousPayload,
        [string]$GeneratedAt
    )

    $previousRepo = Get-PayloadSection -Payload $PreviousPayload -Name 'repo'
    $previousSnapshot = Get-PayloadSection -Payload $PreviousPayload -Name 'snapshot'
    $previousPlayer = Get-PayloadSection -Payload $PreviousPayload -Name 'player'
    $previousTarget = Get-PayloadSection -Payload $PreviousPayload -Name 'target'

    $repoResult = Get-GitRepoState
    $snapshotResult = Invoke-ReaderJsonCommand -Arguments @('--readerbridge-snapshot', '--json') -CommandName 'readerbridge-snapshot'
    $snapshotDocument = if ($snapshotResult.success) { $snapshotResult.data } else { $null }
    $playerResult = Invoke-ReaderJsonCommand -Arguments @('--process-name', 'rift_x64', '--read-player-current', '--json') -CommandName 'read-player-current'
    $targetResult = Invoke-ReaderJsonCommand -Arguments @('--process-name', 'rift_x64', '--read-target-current', '--json') -CommandName 'read-target-current'

    $repoSection = Resolve-RepoSection -RepoResult $repoResult -PreviousSection $previousRepo -GeneratedAt $GeneratedAt
    $snapshotSection = Resolve-SnapshotSection -SnapshotResult $snapshotResult -PreviousSection $previousSnapshot -GeneratedAt $GeneratedAt
    $playerSection = Resolve-PlayerSection -PlayerResult $playerResult -SnapshotDocument $snapshotDocument -PreviousSection $previousPlayer -GeneratedAt $GeneratedAt
    $targetSection = Resolve-TargetSection -TargetResult $targetResult -SnapshotDocument $snapshotDocument -PreviousSection $previousTarget -GeneratedAt $GeneratedAt

    $sourceStates = [ordered]@{
        repo     = $repoSection.state
        snapshot = $snapshotSection.state
        player   = $playerSection.state
        target   = $targetSection.state
    }

    return [ordered]@{
        meta     = [ordered]@{
            generatedAt      = $GeneratedAt
            staleAfterSeconds = 10
            status           = (Get-OverallStatus -States @($sourceStates.Values))
            sources          = $sourceStates
        }
        repo     = $repoSection.section
        snapshot = $snapshotSection.section
        player   = $playerSection.section
        target   = $targetSection.section
        errors   = [ordered]@{
            repo     = $repoResult.error
            snapshot = $snapshotResult.error
            player   = $playerResult.error
            target   = $targetResult.error
        }
    }
}

function New-FallbackPayload {
    param(
        [object]$PreviousPayload,
        [string]$GeneratedAt,
        [string]$Error
    )

    $previousRepo = Get-PayloadSection -Payload $PreviousPayload -Name 'repo'
    $previousSnapshot = Get-PayloadSection -Payload $PreviousPayload -Name 'snapshot'
    $previousPlayer = Get-PayloadSection -Payload $PreviousPayload -Name 'player'
    $previousTarget = Get-PayloadSection -Payload $PreviousPayload -Name 'target'

    if (-not $previousRepo) {
        $previousRepo = [ordered]@{
            available        = $false
            updatedAt        = $null
            repoPath         = (Convert-ToDashboardPath $script:RepoRoot)
            currentBranch    = $null
            changedFileCount = 0
            dirty            = $false
            dirtyCounts      = [ordered]@{
                modified  = 0
                added     = 0
                deleted   = 0
                renamed   = 0
                untracked = 0
            }
            changes          = @()
        }
    }

    if (-not $previousSnapshot) {
        $previousSnapshot = [ordered]@{
            available     = $false
            updatedAt     = $null
            sourceFile    = ''
            loadedAt      = $null
            exportCount   = $null
            lastReason    = $null
            status        = 'missing'
            exportReason  = $null
            sourceMode    = $null
            sourceAddon   = $null
            sourceVersion = $null
            playerName    = $null
            targetName    = $null
        }
    }

    if (-not $previousPlayer) {
        $previousPlayer = [ordered]@{
            available = $false
            updatedAt = $null
        }
    }

    if (-not $previousTarget) {
        $previousTarget = [ordered]@{
            available = $false
            updatedAt = $null
            hasTarget = $null
        }
    }

    $sourceStates = [ordered]@{
        repo     = (New-SourceState -Status $(if ($PreviousPayload) { 'stale' } else { 'error' }) -Section $previousRepo -Error $Error -UsingPrevious ([bool]$PreviousPayload))
        snapshot = (New-SourceState -Status $(if ($PreviousPayload) { 'stale' } else { 'error' }) -Section $previousSnapshot -Error $Error -UsingPrevious ([bool]$PreviousPayload))
        player   = (New-SourceState -Status $(if ($PreviousPayload) { 'stale' } else { 'error' }) -Section $previousPlayer -Error $Error -UsingPrevious ([bool]$PreviousPayload))
        target   = (New-SourceState -Status $(if ($PreviousPayload) { 'stale' } else { 'error' }) -Section $previousTarget -Error $Error -UsingPrevious ([bool]$PreviousPayload))
    }

    return [ordered]@{
        meta     = [ordered]@{
            generatedAt       = $GeneratedAt
            staleAfterSeconds = 10
            status            = $(if ($PreviousPayload) { 'partial' } else { 'error' })
            sources           = $sourceStates
        }
        repo     = $previousRepo
        snapshot = $previousSnapshot
        player   = $previousPlayer
        target   = $previousTarget
        errors   = [ordered]@{
            repo     = $Error
            snapshot = $Error
            player   = $Error
            target   = $Error
        }
    }
}

function Write-LiveStatus {
    param(
        [object]$Payload,
        [string]$Path,
        [bool]$Watching
    )

    $script:WriteCount += 1

    $meta = Get-ObjectPropertyValue -Object $Payload -Name 'meta'
    $status = Get-ObjectPropertyValue -Object $meta -Name 'status'
    $generatedAt = Get-ObjectPropertyValue -Object $meta -Name 'generatedAt'

    $shouldAnnounce = -not $Watching `
        -or $script:WriteCount -eq 1 `
        -or $status -ne $script:LastAnnouncedStatus `
        -or ($script:WriteCount % 30 -eq 0)

    if ($shouldAnnounce) {
        $modeLabel = if ($Watching) { 'watch' } else { 'oneshot' }
        Write-Host "[DashboardLive][$modeLabel] status=$status generatedAt=$generatedAt path=$Path" -ForegroundColor Green
    }

    $script:LastAnnouncedStatus = $status
}

Ensure-OutputDirectory -Path $OutputPath
$script:CurrentPayload = Get-PreviousPayload -Path $OutputPath

do {
    $generatedAt = ([DateTimeOffset]::Now).ToString('o')

    try {
        $payload = Build-LivePayload -PreviousPayload $script:CurrentPayload -GeneratedAt $generatedAt
    }
    catch {
        $payload = New-FallbackPayload -PreviousPayload $script:CurrentPayload -GeneratedAt $generatedAt -Error $_.Exception.Message
    }

    Write-LivePayload -Path $OutputPath -Payload $payload
    $script:CurrentPayload = $payload
    Write-LiveStatus -Payload $payload -Path $OutputPath -Watching ([bool]$Watch)

    if ($Watch) {
        Start-Sleep -Seconds $PollSeconds
    }
} while ($Watch)

$global:LASTEXITCODE = 0
