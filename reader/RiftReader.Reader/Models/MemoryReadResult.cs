namespace RiftReader.Reader.Models;

public sealed record MemoryReadResult(
    string Mode,
    int ProcessId,
    string ProcessName,
    string? ModuleName,
    string? MainWindowTitle,
    string Address,
    int Length,
    string BytesHex);
