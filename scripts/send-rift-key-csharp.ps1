# Version: riftreader-sendinput-csharp-wrapper-v0.1.0
# Total-Character-Count: 587
# Purpose: Thin PowerShell wrapper that launches the pure C# RiftReader.SendInput tool. All input logic lives in C#.

$ErrorActionPreference = "Stop"

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Project = Join-Path $RepoRoot "tools\RiftReader.SendInput\RiftReader.SendInput.csproj"

if (-not (Test-Path -LiteralPath $Project -PathType Leaf)) {
    throw "C# SendInput project not found: $Project"
}

& dotnet run --project $Project -- @args
exit $LASTEXITCODE

# END_OF_SCRIPT_MARKER
