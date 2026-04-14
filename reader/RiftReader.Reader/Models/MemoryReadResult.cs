namespace RiftReader.Reader.Models;

public sealed record MemoryReadResult(
    string Mode,
    int ProcessId,
    string ProcessName,
    string? ModuleName,
    string? MainWindowTitle,
    string Address,
    int RequestedLength,
    bool CompleteRead,
    int Length,
    string BytesHex,
    string? Warning);
