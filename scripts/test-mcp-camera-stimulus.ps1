# MCP Camera Stimulus Test Script
# Uses MCP for mouse control, reads memory via reader

$ErrorActionPreference = 'Stop'

$repoRoot = 'C:\RIFT MODDING\RiftReader'
$readerProject = Join-Path $repoRoot 'reader\RiftReader.Reader\RiftReader.Reader.csproj'

function Invoke-ReaderCommand {
    param([string[]]$Arguments)
    $output = & dotnet run --project $readerProject -- @Arguments 2>&1
    $exitCode = $LASTEXITCODE
    return [pscustomobject]@{
        ExitCode = $exitCode
        Output = ($output -join "`n")
    }
}

function Get-JsonOutput {
    param([string[]]$Arguments)
    $result = Invoke-ReaderCommand -Arguments $Arguments
    if ($result.ExitCode -ne 0) { throw "Reader failed: $($result.Output)" }
    
    # Extract JSON from output
    $jsonLines = $result.Output -split "`n" | Where-Object { $_ -match '^\s*\{' }
    $jsonText = $jsonLines -join ""
    return $jsonText | ConvertFrom-Json
}

# Get current player state to find owner address
Write-Host "=== Getting player state ===" -ForegroundColor Cyan
$playerState = Get-JsonOutput -Arguments @('--process-name', 'rift_x64', '--read-player-current', '--json')
Write-Host "Level: $($playerState.Memory.Level)"
Write-Host "Coords: $($playerState.Memory.CoordX), $($playerState.Memory.CoordY), $($playerState.Memory.CoordZ)"

# Get owner components from capture (we need to refresh this)
$ownerCompFile = Join-Path $repoRoot 'scripts\captures\player-owner-components.json'
if (-not (Test-Path $ownerCompFile)) {
    Write-Host "Owner components file not found, need to capture fresh" -ForegroundColor Yellow
    exit 1
}

$ownerComp = Get-Content $ownerCompFile | ConvertFrom-Json
$ownerAddress = $ownerComp.Owner.Address
$selectedSource = $ownerComp.Owner.SelectedSourceAddress

Write-Host "`n=== Owner Structure ===" -ForegroundColor Cyan
Write-Host "Owner: $ownerAddress"
Write-Host "Selected Source: $selectedSource"

# The lead A chain: owner +0xD0 -> wrapper +0x100 -> candidate
# We need to read owner at +0xD0 to get wrapper address
$ownerAddr = [UInt64]::Parse($ownerAddress.Substring(2), [System.Globalization.NumberStyles]::HexNumber)
$wrapperAddrOffset = 0xD0

# Read owner bytes at +0xD0 (wrapper pointer)
$wrapperRead = Get-JsonOutput -Arguments @(
    '--process-name', 'rift_x64',
    '--address', "0x$($ownerAddr.ToString('X'))",
    '--length', '256'
)

# Find pointer at +0xD0 - read raw bytes
Write-Host "`n=== Reading owner at +0xD0 for wrapper pointer ===" -ForegroundColor Cyan

# Read owner +0xD0 (8 bytes for pointer)
$wrapperPtrHex = "ERROR"
try {
    # Use memory read and extract the 8 bytes at offset 0xD0
    $ownerBytes = Get-JsonOutput -Arguments @(
        '--process-name', 'rift_x64',
        '--address', "0x$($ownerAddr.ToString('X'))",
        '--length', '256'
    )
    
    if ($ownerBytes.BytesHex) {
        $hex = $ownerBytes.BytesHex -replace ' ', ''
        # At +0xD0 = 208 bytes offset, that's 416 hex chars in (2 chars per byte)
        $offsetChars = 208 * 2
        $wrapperPtrStr = $hex.Substring($offsetChars, 16)  # 8 bytes = 16 hex chars
        $wrapperPtr = [UInt64]::Parse($wrapperPtrStr, [System.Globalization.NumberStyles]::HexNumber)
        $wrapperPtrHex = "0x$wrapperPtrStr"
        Write-Host "Wrapper pointer at owner+0xD0: $wrapperPtrHex"
    }
} catch {
    Write-Host "Error reading: $_"
}

# Now read wrapper at +0x100 for candidate object
if ($wrapperPtrHex -ne "ERROR" -and $wrapperPtrHex.StartsWith("0x1")) {
    $wrapperAddr = [UInt64]::Parse($wrapperPtrHex.Substring(2), [System.Globalization.NumberStyles]::HexNumber)
    
    Write-Host "`n=== Reading wrapper at +0x100 for candidate ===" -ForegroundColor Cyan
    
    try {
        $wrapperBytes = Invoke-ReaderJson -Arguments @(
            '--process-name', 'rift_x64',
            '--address', "0x$($wrapperAddr.ToString('X'))",
            '--length', '512'
        )
        
        if ($wrapperBytes.BytesHex) {
            $hex = $wrapperBytes.BytesHex -replace ' ', ''
            # At +0x100 = 256 bytes offset, 512 hex chars
            $candidateOffset = 256 * 2
            $candidatePtrStr = $hex.Substring($candidateOffset, 16)
            $candidatePtr = [UInt64]::Parse($candidatePtrStr, [System.Globalization.NumberStyles]::HexNumber)
            $candidatePtrHex = "0x$candidatePtrStr"
            Write-Host "Candidate pointer at wrapper+0x100: $candidatePtrHex"
            
            if ($candidatePtrHex.StartsWith("0x1")) {
                Write-Host "`n=== BEFORE STIMULUS: Reading candidate at +0xA0 for basis ===" -ForegroundColor Green
                $candidateAddr = [UInt64]::Parse($candidatePtrStr, [System.Globalization.NumberStyles]::HexNumber)
                
                # Read basis at +0xA0
                $basisBefore = Invoke-ReaderJson -Arguments @(
                    '--process-name', 'rift_x64',
                    '--address', "0x$((($candidateAddr + 0xA0)).ToString('X'))",
                    '--length', '48'
                )
                
                Write-Host "Basis before mouse move:"
                Write-Host "  Bytes: $($basisBefore.BytesHex)"
                
                # Now use MCP to move mouse (rotate camera)
                Write-Host "`n=== Applying MCP mouse stimulus ===" -ForegroundColor Yellow
                
                # Move mouse to rotate camera
                $currentPos = @{X=500; Y=300}  # Assume center-ish
                & "$env:LOCALAPPDATA\opencode\current\windows-mcp-server.exe" move --loc @(($currentPos.X + 200), $currentPos.Y) 2>$null
                
                # Alternative: use our existing window MCP
                # Just move the mouse a bit
                
                Start-Sleep -Milliseconds 500
                
                # Read again after stimulus
                Write-Host "`n=== AFTER STIMULUS: Reading candidate at +0xA0 for basis ===" -ForegroundColor Green
                $basisAfter = Invoke-ReaderJson -Arguments @(
                    '--process-name', 'rift_x64',
                    '--address', "0x$((($candidateAddr + 0xA0)).ToString('X'))",
                    '--length', '48'
                )
                
                Write-Host "Basis after mouse move:"
                Write-Host "  Bytes: $($basisAfter.BytesHex)"
            }
        }
    } catch {
        Write-Host "Error reading candidate: $_"
    }
}

Write-Host "`n=== Test complete ===" -ForegroundColor Cyan