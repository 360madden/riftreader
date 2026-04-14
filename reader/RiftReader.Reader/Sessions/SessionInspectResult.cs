namespace RiftReader.Reader.Sessions;

public sealed record SessionPackageManifest(
    string? Mode,
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
    int? ProcessId,
    string? ProcessName,
    int? WatchsetRegionCount,
    int? SampleCount,
    int? IntervalMilliseconds,
    IReadOnlyList<SessionPackageArtifact>? CopiedArtifacts,
    IReadOnlyList<string>? Warnings);

public sealed record SessionPackageArtifact(
    string? Name,
    string? File);

public sealed record SessionInspectResult(
    string Mode,
    string SessionId,
    string SessionDirectory,
    string? Label,
    string? ProcessName,
    int? ProcessId,
    int WatchsetRegionCount,
    int DeclaredSampleCount,
    int RecordedSampleCount,
    int MarkerCount,
    int PackageWarningCount,
    int ManifestWarningCount,
    int RequiredRegionCount,
    int OptionalRegionCount,
    int RequiredRegionsAlwaysReadable,
    int RequiredRegionsEverReadable,
    int OptionalRegionsEverReadable,
    IReadOnlyList<string> PackageWarnings,
    IReadOnlyList<string> ManifestWarnings,
    IReadOnlyList<SessionRegionInspectResult> TopReadableRegionsByChange,
    IReadOnlyList<SessionRegionInspectResult> TopRequiredFailureRegions,
    IReadOnlyList<SessionMarkerSummary> Markers);

public sealed record SessionRegionInspectResult(
    string Name,
    string Category,
    bool Required,
    int SuccessCount,
    int FailureCount,
    int DistinctValueCount,
    string? FirstAddress,
    int? Length,
    string? LastError);

public sealed record SessionMarkerSummary(
    string Kind,
    string RecordedAtUtc,
    long? ElapsedMilliseconds,
    string? Label,
    string? Message);
