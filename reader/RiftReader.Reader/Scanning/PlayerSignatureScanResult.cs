namespace RiftReader.Reader.Scanning;

public sealed record PlayerSignatureScanResult(
    string Mode,
    int ProcessId,
    string ProcessName,
    string SearchLabel,
    int InspectionRadius,
    int CandidateCount,
    int MaxHits,
    int HitCount,
    IReadOnlyList<PlayerSignatureScanHit> Hits);
