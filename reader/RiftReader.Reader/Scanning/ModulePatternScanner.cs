using System.Diagnostics;
using Reloaded.Memory.Sigscan;
using RiftReader.Reader.Memory;

namespace RiftReader.Reader.Scanning;

public static class ModulePatternScanner
{
    public static ModulePatternScanResult Scan(
        Process process,
        ProcessMemoryReader reader,
        int processId,
        string processName,
        string moduleName,
        string moduleFileName,
        long moduleBaseAddress,
        int moduleMemorySize,
        string pattern,
        int contextBytes)
    {
        ArgumentNullException.ThrowIfNull(process);
        ArgumentNullException.ThrowIfNull(reader);
        ArgumentException.ThrowIfNullOrWhiteSpace(moduleName);
        ArgumentException.ThrowIfNullOrWhiteSpace(moduleFileName);
        ArgumentException.ThrowIfNullOrWhiteSpace(pattern);

        using var scanner = new Scanner(process, process.Modules.Cast<ProcessModule>().First(module =>
            string.Equals(module.ModuleName, moduleName, StringComparison.OrdinalIgnoreCase) &&
            string.Equals(module.FileName, moduleFileName, StringComparison.OrdinalIgnoreCase)));

        var scanResult = scanner.FindPattern(pattern);
        if (!scanResult.Found)
        {
            return new ModulePatternScanResult(
                Mode: "module-pattern-scan",
                ProcessId: processId,
                ProcessName: processName,
                ModuleName: moduleName,
                ModuleFileName: moduleFileName,
                ModuleBaseAddress: $"0x{moduleBaseAddress:X}",
                ModuleMemorySize: moduleMemorySize,
                Pattern: pattern,
                Found: false,
                RelativeOffset: null,
                RelativeOffsetHex: null,
                Address: null,
                ContextBytes: 0,
                ContextBytesHex: null);
        }

        var absoluteAddress = moduleBaseAddress + scanResult.Offset;
        string? contextHex = null;
        var effectiveContextBytes = Math.Max(0, contextBytes);

        if (effectiveContextBytes > 0)
        {
            if (reader.TryReadBytes(new nint(absoluteAddress), effectiveContextBytes, out var bytes, out _))
            {
                contextHex = Convert.ToHexString(bytes);
            }
        }

        return new ModulePatternScanResult(
            Mode: "module-pattern-scan",
            ProcessId: processId,
            ProcessName: processName,
            ModuleName: moduleName,
            ModuleFileName: moduleFileName,
            ModuleBaseAddress: $"0x{moduleBaseAddress:X}",
            ModuleMemorySize: moduleMemorySize,
            Pattern: pattern,
            Found: true,
            RelativeOffset: scanResult.Offset,
            RelativeOffsetHex: $"0x{scanResult.Offset:X}",
            Address: $"0x{absoluteAddress:X}",
            ContextBytes: effectiveContextBytes,
            ContextBytesHex: contextHex);
    }
}
