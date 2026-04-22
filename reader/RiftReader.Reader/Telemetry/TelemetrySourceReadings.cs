using RiftReader.Reader.AddonSnapshots;

namespace RiftReader.Reader.Telemetry;

public sealed record TelemetryContextSourceReading(
    bool Available,
    bool Valid,
    DateTimeOffset SampledAtUtc,
    string SourceKind,
    string? Reason,
    string? SnapshotFile,
    double? SnapshotFileAgeSeconds,
    ReaderBridgeSnapshotDocument? SnapshotDocument,
    TelemetryPositionValue? AddonPosition,
    string? PlayerId,
    string? TargetId,
    string? Zone,
    string? LocationName,
    bool? Combat,
    string? SourceAddon,
    string? SourceMode);

public sealed record TelemetryPositionSourceReading(
    bool Available,
    bool Valid,
    DateTimeOffset SampledAtUtc,
    string SourceKind,
    string? Reason,
    TelemetryPositionValue? Position,
    TelemetryProofAnchorDiagnostics? ProofAnchor,
    TelemetryDeltaDiagnostics? CoordMismatch,
    object? Discovery);

public sealed record TelemetryFacingSourceReading(
    bool Available,
    bool Valid,
    DateTimeOffset SampledAtUtc,
    string SourceKind,
    string? Reason,
    TelemetryFacingEnvelope Facing,
    TelemetryFacingLeadDiagnostics? LeadDiagnostics,
    object? Discovery);

public sealed record TelemetryHostOptions(
    string ProcessName,
    int? ProcessId,
    int PollIntervalMilliseconds,
    bool DiagnosticsEnabled,
    string? ReaderBridgeSnapshotFile,
    string? PlayerCoordTraceFile,
    string LatestSnapshotFile,
    string EventLogFile,
    string? DiscoveryLogFile,
    string ProofCoordAnchorScript,
    TimeSpan ProofAnchorRevalidationInterval,
    TimeSpan ProofAnchorMaxAge);
