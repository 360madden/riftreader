[CmdletBinding()]
param(
    [string]$PythonExe = 'python',
    [switch]$SkipLiveSmoke,
    [switch]$SkipGuiSmoke,
    [int]$GuiSmokeSeconds = 5
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$toolPath = Join-Path $PSScriptRoot 'game_debug_scanner_hub.py'
if (-not (Test-Path -LiteralPath $toolPath)) {
    throw "Hub tool not found: $toolPath"
}

function Invoke-PythonStep {
    param(
        [string[]]$Arguments,
        [string]$Label
    )

    Write-Host "[HubTest] $Label" -ForegroundColor Cyan
    & $PythonExe @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "$Label failed with exit code $LASTEXITCODE."
    }
}

Invoke-PythonStep -Label 'Running built-in self-test...' -Arguments @($toolPath, '--self-test')

if (-not $SkipLiveSmoke) {
    $liveSmokeCode = @'
import importlib.util
import json
import pathlib
import sys

tool_path = pathlib.Path(r"__TOOL_PATH__")
spec = importlib.util.spec_from_file_location("scanner_hub", tool_path)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)

logger = module.setup_logger()
bridge = module.RiftReaderBridge(logger)
snapshot, raw_output = bridge.read_current_player()

scanner = module.GameDebugScanner(logger)
process_name = snapshot.process_name if snapshot.process_name.endswith('.exe') else snapshot.process_name + '.exe'
info = scanner.attach(process_name)

first_float = None
hex_preview = None
if snapshot.address_hex:
    address = int(snapshot.address_hex, 16)
    first_float = scanner.read_value(address, 'float')
    hex_preview = scanner.read_bytes(address, 16).hex().upper()

scanner.detach(log_if_missing=False)

summary = {
    "process_name": snapshot.process_name,
    "process_id": snapshot.process_id,
    "address_hex": snapshot.address_hex,
    "level": snapshot.level,
    "health": snapshot.health,
    "coord_x": snapshot.coord_x,
    "coord_y": snapshot.coord_y,
    "coord_z": snapshot.coord_z,
    "generic_attach_pid": info.process_id,
    "generic_pointer_size": info.pointer_size,
    "generic_first_float": first_float,
    "hex_preview": hex_preview,
}
print(json.dumps(summary, ensure_ascii=True))
'@.Replace('__TOOL_PATH__', ($toolPath -replace '\\', '\\'))

    Write-Host "[HubTest] Running live Rift/generic smoke test..." -ForegroundColor Cyan
    $liveOutput = $liveSmokeCode | & $PythonExe -
    if ($LASTEXITCODE -ne 0) {
        throw "Live smoke test failed with exit code $LASTEXITCODE."
    }

    Write-Host $liveOutput
}

if (-not $SkipGuiSmoke) {
    Write-Host "[HubTest] Launching GUI smoke test for $GuiSmokeSeconds second(s)..." -ForegroundColor Cyan
    $windowTitle = 'Game Debug Scanner Hub - Generic + RiftReader (Read-only)'
    $baselineIds = @(
        Get-Process -Name python, pythonw -ErrorAction SilentlyContinue |
            Where-Object { $_.MainWindowTitle -eq $windowTitle } |
            Select-Object -ExpandProperty Id
    )

    $pythonw = Get-Command pythonw.exe -ErrorAction SilentlyContinue
    $guiPython = if ($pythonw) { $pythonw.Source } else { $PythonExe }

    $quotedToolPath = '"' + $toolPath + '"'
    $process = Start-Process -FilePath $guiPython -ArgumentList @($quotedToolPath) -PassThru
    try {
        Start-Sleep -Seconds $GuiSmokeSeconds

        $windowProcesses = @(
            Get-Process -Name python, pythonw -ErrorAction SilentlyContinue |
                Where-Object {
                    $_.MainWindowTitle -eq $windowTitle -and
                    $_.Id -notin $baselineIds
                }
        )

        if ($windowProcesses.Count -eq 0) {
            $process.Refresh()
            if ($process.HasExited) {
                throw "GUI process exited early with code $($process.ExitCode)."
            }

            throw "GUI process stayed alive but no window titled '$windowTitle' was detected."
        }

        Write-Host "[HubTest] GUI smoke test passed; process stayed alive long enough to show the window." -ForegroundColor Green
    }
    finally {
        $cleanupIds = @(
            Get-Process -Name python, pythonw -ErrorAction SilentlyContinue |
                Where-Object {
                    $_.MainWindowTitle -eq $windowTitle -and
                    $_.Id -notin $baselineIds
                } |
                Select-Object -ExpandProperty Id
        )

        foreach ($id in $cleanupIds) {
            Stop-Process -Id $id -Force -ErrorAction SilentlyContinue
        }

        if (-not $process.HasExited) {
            Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
        }
    }
}

Write-Host "[HubTest] All requested checks passed." -ForegroundColor Green
