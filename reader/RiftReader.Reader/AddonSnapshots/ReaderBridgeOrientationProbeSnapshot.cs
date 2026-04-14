namespace RiftReader.Reader.AddonSnapshots;

public sealed record ReaderBridgeOrientationProbeSnapshot(
    ReaderBridgeOrientationProbeUnitSnapshot? Player,
    ReaderBridgeOrientationProbeUnitSnapshot? Target,
    IReadOnlyList<ReaderBridgeOrientationProbeFieldSnapshot> StatCandidates);

public sealed record ReaderBridgeOrientationProbeUnitSnapshot(
    double? DirectHeading,
    double? DirectPitch,
    double? Yaw,
    string? Facing,
    IReadOnlyList<ReaderBridgeOrientationProbeFieldSnapshot> DetailCandidates,
    IReadOnlyList<ReaderBridgeOrientationProbeFieldSnapshot> StateCandidates);

public sealed record ReaderBridgeOrientationProbeFieldSnapshot(
    string? Key,
    string? Value,
    string? Kind);
