# Version: 1.0.0
# TotalCharacters: 0
# Purpose: Replace unsupported ConvertFrom-Json -Depth usages with a PowerShell 5.1-compatible helper, then commit and push the changes.

[CmdletBinding()]
param(
    [string]$Branch = 'feature/camera-orientation-discovery',
    [switch]$SkipPush
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Set-Location $repoRoot

$targets = @(
    'scripts\run-evidence-first-session.ps1',
    'scripts\capture-promising-orientation-lead.ps1'
)

$helper = @'
function Convert-JsonTextToObject {
    param(
        [AllowNull()]
        [string]$JsonText
    )

    if ([string]::IsNullOrWhiteSpace($JsonText)) {
        return $null
    }

    if ($PSVersionTable.PSVersion.Major -ge 6) {
        return $JsonText | ConvertFrom-Json -Depth 80
    }

    return $JsonText | ConvertFrom-Json
}
'@

foreach ($relativePath in $targets) {
    $fullPath = Join-Path $repoRoot $relativePath
    if (-not (Test-Path -LiteralPath $fullPath)) {
        throw "Target script not found: $relativePath"
    }

    $content = Get-Content -LiteralPath $fullPath -Raw

    $content = [regex]::Replace(
        $content,
        'function Convert-JsonTextToObject \{.*?^\}',
        $helper,
        [System.Text.RegularExpressions.RegexOptions]::Singleline -bor [System.Text.RegularExpressions.RegexOptions]::Multiline
    )

    Set-Content -LiteralPath $fullPath -Value $content -Encoding UTF8
    Write-Host ("Patched {0}" -f $relativePath)

    git add $relativePath
    if ($LASTEXITCODE -ne 0) {
        throw "git add failed for $relativePath"
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

git commit -m "Fix PowerShell 5 ConvertFrom-Json depth compatibility"
if ($LASTEXITCODE -ne 0) {
    throw 'git commit failed'
}

if (-not $SkipPush) {
    git push origin $Branch
    if ($LASTEXITCODE -ne 0) {
        throw 'git push failed'
    }
}

Write-Host 'PowerShell 5 JSON compatibility repair complete.'

# End of script
