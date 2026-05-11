# Version: riftreader-sendinput-csharp-wrapper-v0.2.0
# Total-Character-Count: 3578
# Purpose: Thin PowerShell wrapper that launches the built C# RiftReader.SendInput tool. Uses the compiled DLL by default, builds only when missing or requested, and injects a 250 ms focus delay unless the caller supplies one.

$ErrorActionPreference = "Stop"

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Project = Join-Path $RepoRoot "tools\RiftReader.SendInput\RiftReader.SendInput.csproj"

if (-not (Test-Path -LiteralPath $Project -PathType Leaf)) {
    throw "C# SendInput project not found: $Project"
}

$Configuration = "Debug"
$BuildRequested = $false
$NoBuild = $false
$ToolArgs = New-Object System.Collections.Generic.List[string]

for ($Index = 0; $Index -lt $args.Length; $Index++) {
    $Argument = [string]$args[$Index]

    if ([string]::Equals($Argument, "--wrapper-build", [System.StringComparison]::OrdinalIgnoreCase)) {
        $BuildRequested = $true
        continue
    }

    if ([string]::Equals($Argument, "--wrapper-no-build", [System.StringComparison]::OrdinalIgnoreCase)) {
        $NoBuild = $true
        continue
    }

    if ([string]::Equals($Argument, "--wrapper-configuration", [System.StringComparison]::OrdinalIgnoreCase)) {
        if ($Index + 1 -ge $args.Length) {
            throw "Missing value for --wrapper-configuration. Use Debug or Release."
        }

        $Configuration = [string]$args[$Index + 1]
        $Index++
        continue
    }

    $ToolArgs.Add($Argument) | Out-Null
}

if ($Configuration -notin @("Debug", "Release")) {
    throw "Invalid wrapper configuration '$Configuration'. Use Debug or Release."
}

[xml]$ProjectXml = Get-Content -LiteralPath $Project -Raw
$TargetFramework = [string]($ProjectXml.Project.PropertyGroup | Select-Object -First 1).TargetFramework
if ([string]::IsNullOrWhiteSpace($TargetFramework)) {
    throw "Could not resolve TargetFramework from $Project."
}

$Dll = Join-Path $RepoRoot ("tools\RiftReader.SendInput\bin\{0}\{1}\RiftReader.SendInput.dll" -f $Configuration, $TargetFramework)

if (($BuildRequested -or -not (Test-Path -LiteralPath $Dll -PathType Leaf)) -and -not $NoBuild) {
    $BuildOutput = & dotnet build $Project --configuration $Configuration --nologo 2>&1
    if ($LASTEXITCODE -ne 0) {
        $BuildOutput | ForEach-Object { [Console]::Error.WriteLine([string]$_) }
        exit $LASTEXITCODE
    }
}

if (-not (Test-Path -LiteralPath $Dll -PathType Leaf)) {
    throw "Built C# SendInput DLL not found: $Dll. Run with --wrapper-build or remove --wrapper-no-build."
}

function Test-HasOption {
    param(
        [Parameter(Mandatory = $true)]
        [System.Collections.Generic.List[string]]$Arguments,
        [Parameter(Mandatory = $true)]
        [string]$Name
    )

    foreach ($Item in $Arguments) {
        if ([string]::Equals($Item, $Name, [System.StringComparison]::OrdinalIgnoreCase)) {
            return $true
        }

        if ($Item.StartsWith($Name + "=", [System.StringComparison]::OrdinalIgnoreCase)) {
            return $true
        }
    }

    return $false
}

$EffectiveArgs = New-Object System.Collections.Generic.List[string]
foreach ($Item in $ToolArgs) {
    $EffectiveArgs.Add($Item) | Out-Null
}

if (-not (Test-HasOption -Arguments $EffectiveArgs -Name "--focus-delay-ms") -and
    -not (Test-HasOption -Arguments $EffectiveArgs -Name "--help")) {
    $EffectiveArgs.Add("--focus-delay-ms") | Out-Null
    $EffectiveArgs.Add("250") | Out-Null
}

& dotnet $Dll @EffectiveArgs
exit $LASTEXITCODE

# END_OF_SCRIPT_MARKER
