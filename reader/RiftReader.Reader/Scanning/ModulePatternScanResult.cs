namespace RiftReader.Reader.Scanning;

public sealed record ModulePatternScanResult(
    string Mode,
    int ProcessId,
    string ProcessName,
    string ModuleName,
    string ModuleFileName,
    string ModuleBaseAddress,
    int ModuleMemorySize,
    string Pattern,
    bool Found,
    int? RelativeOffset,
    string? RelativeOffsetHex,
    string? Address,
    int ContextBytes,
    string? ContextBytesHex);
