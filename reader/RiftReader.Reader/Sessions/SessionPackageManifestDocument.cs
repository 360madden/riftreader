namespace RiftReader.Reader.Sessions;

public sealed record SessionPackageManifestDocument(
    int? SchemaVersion,
    string? Mode,
    string? Status,
    string? IntegrityStatus,
    string? GeneratedAtUtc,
    string? SessionId,
    string? Label,
    string? SessionDirectory,
    string? WatchsetFile,
    string? CaptureConsistencyFile,
    string? ReaderBridgeSnapshotFile,
    string? ArtifactDirectory,
    string? RecordingManifestFile,
    string? SamplesFile,
    string? MarkersFile,
    string? ModulesFile,
    bool? Interrupted,
    string? SessionMarkerInputFile,
    int? MarkerCount,
    IReadOnlyList<string>? MarkerKinds,
    int? RequestedRegionByteCount,
    long? TotalBytesRead,
    int? TotalRegionReadFailures,
    int? ProcessId,
    string? ProcessName,
    int? WatchsetRegionCount,
    int? SampleCount,
    int? IntervalMilliseconds,
    IReadOnlyList<string>? MissingFiles,
    string? FailureMessage,
    IReadOnlyList<SessionPackageCopiedArtifact>? CopiedArtifacts,
    IReadOnlyList<string>? Warnings);

public sealed record SessionPackageCopiedArtifact(
    string? Name,
    string? File);
