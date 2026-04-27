namespace RiftReader.Reader.AddonSnapshots;

public sealed record ReaderBridgeSnapshot(
    int? SchemaVersion,
    string? Status,
    string? ExportReason,
    int? ExportCount,
    double? GeneratedAtRealtime,
    string? SourceMode,
    string? SourceAddon,
    string? SourceVersion,
    ReaderBridgeHudSnapshot? Hud,
    ReaderBridgeUnitSnapshot? Player,
    ReaderBridgeUnitSnapshot? Target,
    ReaderBridgeOrientationProbeSnapshot? OrientationProbe,
    IReadOnlyList<string> PlayerBuffLines,
    IReadOnlyList<string> PlayerDebuffLines,
    IReadOnlyList<string> TargetBuffLines,
    IReadOnlyList<string> TargetDebuffLines);
