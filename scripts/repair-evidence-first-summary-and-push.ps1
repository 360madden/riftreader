# Version: 1.0.0
# TotalCharacters: 0
# Purpose: Automatically patch the broken Get-ClassificationCounts function, optionally add ignored session outputs, then commit and push the changes.

[CmdletBinding()]
param(
    [string]$Branch = 'feature/camera-orientation-discovery',
    [switch]$IncludeSessions,
    [switch]$SkipPush
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Set-Location $repoRoot

$path = Join-Path $repoRoot 'scripts\run-evidence-first-session.ps1'
if (-not (Test-Path -LiteralPath $path)) {
    throw "Target script not found: $path"
}

$replacement = @'
function Get-ClassificationCounts {
    param(
        [AllowNull()]
        $ProfileDocument
    )

    $counts = [ordered]@{}
    if ($null -eq $ProfileDocument -or $null -eq $ProfileDocument.Results) {
        return $counts
    }

    foreach ($entry in @($ProfileDocument.Results)) {
        $classification = $null
        $errorText = $null

        if ($null -ne $entry -and $null -ne $entry.PSObject) {
            $classificationProperty = $entry.PSObject.Properties['Classification']
            if ($null -ne $classificationProperty) {
                $classification = [string]$classificationProperty.Value
            }

            $errorProperty = $entry.PSObject.Properties['Error']
            if ($null -ne $errorProperty) {
                $errorText = [string]$errorProperty.Value
            }
        }

        $name = if (-not [string]::IsNullOrWhiteSpace($classification)) {
            $classification
        }
        elseif (-not [string]::IsNullOrWhiteSpace($errorText)) {
            'error'
        }
        else {
            'unknown'
        }

        if (-not $counts.Contains($name)) {
            $counts[$name] = 0
        }

        $counts[$name]++
    }

    return $counts
}
'@

$content = Get-Content -LiteralPath $path -Raw
$pattern = 'function Get-ClassificationCounts \{.*?^\}'
$newContent = [regex]::Replace(
    $content,
    $pattern,
    $replacement,
    [System.Text.RegularExpressions.RegexOptions]::Singleline -bor [System.Text.RegularExpressions.RegexOptions]::Multiline
)

if ($newContent -eq $content) {
    throw 'Patch failed: Get-ClassificationCounts was not replaced.'
}

Set-Content -LiteralPath $path -Value $newContent -Encoding UTF8
Write-Host 'Patched scripts\run-evidence-first-session.ps1'

git add scripts\run-evidence-first-session.ps1
if ($LASTEXITCODE -ne 0) {
    throw 'git add failed for run-evidence-first-session.ps1'
}

if ($IncludeSessions) {
    git add -f scripts\sessions
    if ($LASTEXITCODE -ne 0) {
        throw 'git add -f failed for scripts\sessions'
    }
}

$status = git status --porcelain
if ($LASTEXITCODE -ne 0) {
    throw 'git status failed'
}

if ([string]::IsNullOrWhiteSpace(($status | Out-String))) {
    Write-Host 'No changes staged or pending after patch.'
    exit 0
}

git commit -m "Fix evidence-first summary classification handling"
if ($LASTEXITCODE -ne 0) {
    throw 'git commit failed'
}

if (-not $SkipPush) {
    git push origin $Branch
    if ($LASTEXITCODE -ne 0) {
        throw 'git push failed'
    }
}

Write-Host 'Repair workflow complete.'

# End of script
