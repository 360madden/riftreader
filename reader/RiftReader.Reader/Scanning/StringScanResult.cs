namespace RiftReader.Reader.Scanning;

public sealed record StringScanResult(
    string Mode,
    int ProcessId,
    string ProcessName,
    string SearchText,
    string SearchSource,
    string Encoding,
    int ContextBytes,
    int MaxHits,
    int HitCount,
    IReadOnlyList<StringScanHit> Hits);
