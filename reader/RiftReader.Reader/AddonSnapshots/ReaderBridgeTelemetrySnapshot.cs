namespace RiftReader.Reader.AddonSnapshots;

public sealed record ReaderBridgeTelemetrySnapshot(
    int? Version,
    long? Sequence,
    double? GeneratedAtRealtime,
    ReaderBridgeTelemetryCapabilitiesSnapshot? Capabilities,
    ReaderBridgeTelemetryPositionSnapshot? Position,
    ReaderBridgeTelemetryMovementSnapshot? Movement,
    ReaderBridgeTelemetryContextSnapshot? Context);

public sealed record ReaderBridgeTelemetryCapabilitiesSnapshot(
    bool? ApiFacingAvailable,
    bool? ApiYawAvailable,
    bool? ReaderBridgeAvailable,
    bool? DirectApiAvailable,
    bool? NearbyUnitsAvailable,
    bool? TargetAvailable);

public sealed record ReaderBridgeTelemetryPositionSnapshot(
    ValidatorCoordinateSnapshot? Coord,
    string? Zone,
    string? LocationName,
    string? SourceMode);

public sealed record ReaderBridgeTelemetryMovementSnapshot(
    double? Dx,
    double? Dy,
    double? Dz,
    double? Distance,
    double? Dt,
    double? Speed);

public sealed record ReaderBridgeTelemetryContextSnapshot(
    string? PlayerId,
    string? TargetId,
    bool? Combat,
    bool? TargetPresent,
    string? Zone,
    string? LocationName,
    string? SourceAddon,
    string? SourceMode,
    string? SourceVersion,
    string? ExportAddon,
    string? ExportVersion);
