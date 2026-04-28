namespace RiftReader.Reader.Telemetry;

public sealed record TelemetryHostSnapshot(
    int SchemaVersion,
    long Sequence,
    DateTimeOffset GeneratedAtUtc,
    TelemetryProcessInfo Process,
    TelemetryMeta Meta,
    TelemetryPositionEnvelope Position,
    TelemetryFacingEnvelope Facing,
    TelemetryMovementEnvelope Movement,
    TelemetryStateEnvelope State,
    TelemetryDiagnosticsEnvelope Diagnostics);

public sealed record TelemetryProcessInfo(
    int ProcessId,
    string ProcessName,
    string? ModuleName,
    string? MainWindowTitle,
    DateTimeOffset? StartedAtUtc);

public sealed record TelemetryMeta(
    string HostVersion,
    int PollIntervalMilliseconds,
    bool DiagnosticsEnabled,
    TelemetrySourceAvailability SourceAvailability,
    TelemetrySourceFreshness Freshness,
    TelemetrySourceValidity Validity,
    string EffectivePositionSource,
    string EffectiveFacingSource);

public sealed record TelemetrySourceAvailability(
    bool AddonContextAvailable,
    bool MemoryCoordAvailable,
    bool MemoryFacingAvailable);

public sealed record TelemetrySourceFreshness(
    double? AddonSnapshotFileAgeSeconds,
    double? ProofAnchorAgeSeconds,
    double? FacingLeadAgeSeconds);

public sealed record TelemetrySourceValidity(
    bool AddonPositionValid,
    bool MemoryCoordValid,
    bool FacingValid);

public sealed record TelemetryPositionEnvelope(
    TelemetryPositionValue? Addon,
    TelemetryPositionValue? Memory,
    TelemetryPositionValue? Effective,
    string EffectiveSource);

public sealed record TelemetryPositionValue(
    bool Valid,
    string SourceKind,
    DateTimeOffset SampledAtUtc,
    TelemetryVector3? Coord,
    string? Zone,
    string? LocationName,
    string? Address,
    string? Reason,
    string? Provenance);

public sealed record TelemetryFacingEnvelope(
    bool Valid,
    string SourceKind,
    double? YawRadians,
    double? YawDegrees,
    double? PitchRadians,
    double? PitchDegrees,
    TelemetryVector3? Forward,
    string? SourceAddress,
    string? BasisForwardOffset,
    string? BasisDuplicateForwardOffset,
    string? Reason,
    string? Provenance);

public sealed record TelemetryVector3(
    double X,
    double Y,
    double Z);

public sealed record TelemetryMovementEnvelope(
    double? Dx,
    double? Dy,
    double? Dz,
    double? Distance,
    double? Dt,
    double? Speed,
    double? TravelHeadingRadians,
    double? TravelHeadingDegrees,
    double? YawRateDegreesPerSecond,
    bool IsMoving,
    bool IsTurning);

public sealed record TelemetryStateEnvelope(
    string? PlayerId,
    string? TargetId,
    string? Zone,
    string? LocationName,
    bool? Combat);

public sealed record TelemetryDiagnosticsEnvelope(
    string? PositionReason,
    string? FacingReason,
    TelemetryProofAnchorDiagnostics? ProofAnchor,
    TelemetryFacingLeadDiagnostics? FacingLead,
    TelemetryDeltaDiagnostics? CoordMismatch,
    object? Discovery);

public sealed record TelemetryProofAnchorDiagnostics(
    bool Valid,
    string? SourceKind,
    string? MatchSource,
    string? TraceSourceFile,
    string? CoordRegionAddress,
    double? AgeSeconds,
    IReadOnlyList<string> Notes);

public sealed record TelemetryFacingLeadDiagnostics(
    bool Valid,
    string? LeadFile,
    double? AgeSeconds,
    string? SourceAddress,
    string? BasisForwardOffset,
    string? BasisDuplicateForwardOffset,
    IReadOnlyList<string> Notes);

public sealed record TelemetryDeltaDiagnostics(
    double? Dx,
    double? Dy,
    double? Dz);

public sealed record TelemetryLogEvent(
    DateTimeOffset GeneratedAtUtc,
    string Category,
    string Message,
    object? Data);
