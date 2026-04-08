namespace RiftReader.Reader.Scanning;

public sealed record NumericScanResult(
    string Mode,
    int ProcessId,
    string ProcessName,
    string ValueType,
    string SearchValue,
    string? Tolerance,
    int ContextBytes,
    int MaxHits,
    int HitCount,
    IReadOnlyList<NumericScanHit> Hits);
