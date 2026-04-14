using RiftReader.Reader.AddonSnapshots;

namespace RiftReader.Reader.Sessions;

public sealed record SessionInspectResult(
    int SchemaVersion,
    string Mode,
    string SessionDirectory,
    SessionPackageManifestDocument Package,
    SessionRecordResult? RecordingManifest,
    ReaderBridgeSnapshotDocument? ReaderBridgeSnapshot,
    IReadOnlyList<SessionSampleRecord> Samples,
    int LoadedSampleCount,
    int LoadedMarkerCount,
    long? MaxTimingDriftMilliseconds,
    long? MaxCaptureDurationMilliseconds,
    long? AverageCaptureDurationMilliseconds,
    IReadOnlyList<SessionMarkerKindSummaryRecord> MarkerKinds,
    IReadOnlyList<SessionMarkerRecord> Markers,
    IReadOnlyList<SessionRegionSummaryRecord> Regions,
    IReadOnlyList<string> Warnings);
