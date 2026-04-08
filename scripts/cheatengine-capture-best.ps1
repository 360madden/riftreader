param(
    [string]$Label = "sample",
    [string]$OutputFile = "C:\RIFT MODDING\RiftReader\scripts\cheat-engine\probe-samples.tsv"
)

$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$probeFile = Join-Path $repoRoot "scripts\cheat-engine\RiftReaderProbe.lua"

$escapedProbeFile = $probeFile -replace "'", "''"
$escapedLabel = $Label -replace "'", "''"
$escapedOutputFile = $OutputFile -replace "'", "''"

$luaCode = "local ok, result = pcall(dofile, [[${escapedProbeFile}]]); if not ok then print(result) return 0 end if RiftReaderProbe == nil then return 0 end return RiftReaderProbe.captureBestFamilySample([[${escapedLabel}]], [[${escapedOutputFile}]]) and 1 or 0"

& (Join-Path $PSScriptRoot "cheatengine-exec.ps1") -Code $luaCode
