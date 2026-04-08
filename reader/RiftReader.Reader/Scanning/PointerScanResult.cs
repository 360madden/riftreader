namespace RiftReader.Reader.Scanning;

public sealed record PointerScanResult(
    string Mode,
    int ProcessId,
    string ProcessName,
    string PointerTarget,
    int PointerWidth,
    int ContextBytes,
    int MaxHits,
    int HitCount,
    IReadOnlyList<PointerScanHit> Hits);
