namespace RiftReader.Reader.Models;

public sealed record ProcessAttachResult(
    string Mode,
    int ProcessId,
    string ProcessName,
    string? ModuleName,
    string? MainWindowTitle);
