param(
    [string]$Code,
    [string]$LuaFile,
    [UInt64]$Parameter = 0,
    [string]$PipeName = "RiftReader",
    [switch]$Async
)

$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($Code) -and [string]::IsNullOrWhiteSpace($LuaFile)) {
    throw "Provide -Code or -LuaFile."
}

$dllPath = "C:\Program Files\Cheat Engine\luaclient-x86_64.dll"

if (-not (Test-Path -LiteralPath $dllPath)) {
    throw "Cheat Engine Lua client DLL not found: $dllPath"
}

if (-not [string]::IsNullOrWhiteSpace($LuaFile)) {
    $resolvedLuaFile = (Resolve-Path -LiteralPath $LuaFile).Path
    $escapedLuaFile = $resolvedLuaFile -replace "'", "''"
    $Code = "local ok, result = pcall(dofile, [[${escapedLuaFile}]]); if not ok then print(result) return 0 end return 1"
}

$typeDefinition = @"
using System;
using System.Runtime.InteropServices;

public static class RiftReaderCheatEngineClient
{
    [DllImport(@"$dllPath", CallingConvention = CallingConvention.StdCall, CharSet = CharSet.Ansi)]
    [return: MarshalAs(UnmanagedType.Bool)]
    public static extern bool CELUA_Initialize(string name);

    [DllImport(@"$dllPath", CallingConvention = CallingConvention.StdCall, CharSet = CharSet.Ansi)]
    public static extern UIntPtr CELUA_ExecuteFunction(string luacode, UIntPtr parameter);

    [DllImport(@"$dllPath", CallingConvention = CallingConvention.StdCall, CharSet = CharSet.Ansi)]
    public static extern UIntPtr CELUA_ExecuteFunctionAsync(string luacode, UIntPtr parameter);
}
"@

Add-Type -TypeDefinition $typeDefinition | Out-Null

if (-not [RiftReaderCheatEngineClient]::CELUA_Initialize($PipeName)) {
    throw "Unable to connect to Cheat Engine Lua server '$PipeName'. Restart Cheat Engine after installing the RiftReader autorun bootstrap."
}

$result = if ($Async) {
    [RiftReaderCheatEngineClient]::CELUA_ExecuteFunctionAsync($Code, [UIntPtr]::new($Parameter))
} else {
    [RiftReaderCheatEngineClient]::CELUA_ExecuteFunction($Code, [UIntPtr]::new($Parameter))
}

[UInt64]$resultValue = $result.ToUInt64()
Write-Output $resultValue
