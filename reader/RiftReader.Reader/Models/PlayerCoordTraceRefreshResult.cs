namespace RiftReader.Reader.Models;

public sealed record PlayerCoordTraceRefreshResult(
    string Mode,
    int ProcessId,
    string ProcessName,
    string TraceSourceFile,
    bool RefreshPerformed,
    PlayerCoordAnchorReadResult Anchor);
