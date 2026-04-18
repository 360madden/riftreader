namespace RiftReader.Reader.AddonSnapshots;

public sealed record ReaderBridgeUnitCollectionSummarySnapshot(
    int? ScannedCount,
    int? ExportedCount,
    int? PlayerCount,
    int? CombatCount,
    int? PvpCount,
    double? NearestDistance,
    string? NearestName,
    double? FarthestDistance,
    string? FarthestName,
    IReadOnlyDictionary<string, int> RelationCounts);
