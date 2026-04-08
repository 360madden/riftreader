namespace RiftReader.Reader.Scanning;

public sealed record PlayerSignatureScanResult(
    string Mode,
    int ProcessId,
    string ProcessName,
    string SearchLabel,
    int InspectionRadius,
    int CandidateCount,
    int RawHitCount,
    int FamilyCount,
    int MaxHits,
    int HitCount,
    IReadOnlyList<PlayerSignatureFamilySummary> Families,
    IReadOnlyList<PlayerSignatureScanHit> Hits);
