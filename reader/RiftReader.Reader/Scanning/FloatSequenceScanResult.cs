namespace RiftReader.Reader.Scanning;

public sealed record FloatSequenceScanResult(
    string Mode,
    int ProcessId,
    string ProcessName,
    string SearchLabel,
    string SearchValues,
    int ContextBytes,
    int MaxHits,
    int HitCount,
    IReadOnlyList<FloatSequenceScanHit> Hits);
