using RiftReader.Reader.Processes;

namespace RiftReader.Reader.Sessions;

public sealed record SessionRecordResult(
    int SchemaVersion,
    string Mode,
    string SessionId,
    string OutputDirectory,
    int ProcessId,
    string ProcessName,
    string? ModuleName,
    string? MainWindowTitle,
    string WatchsetFile,
    int WatchsetRegionCount,
    int RequestedSampleCount,
    int RecordedSampleCount,
    int IntervalMilliseconds,
    string? Label,
    string StartedAtUtc,
    string CompletedAtUtc,
    string ManifestFile,
    string SamplesFile,
    string MarkersFile,
    string ModulesFile,
    bool Interrupted,
    string? SessionMarkerInputFile,
    int MarkerCount,
    IReadOnlyList<string> MarkerKinds,
    int RequestedRegionByteCount,
    long TotalBytesRead,
    int TotalRegionReadFailures,
    string IntegrityStatus,
    IReadOnlyList<string> MissingFiles,
    IReadOnlyList<SessionRegionSummaryRecord> RegionSummaries,
    IReadOnlyList<ProcessModuleInfo> Modules,
    IReadOnlyList<string> WatchsetWarnings,
    IReadOnlyList<string> Warnings);

public sealed record SessionSampleRecord(
    int SampleIndex,
    string RecordedAtUtc,
    long ElapsedMilliseconds,
    long ExpectedElapsedMilliseconds,
    long TimingDriftMilliseconds,
    long CaptureDurationMilliseconds,
    IReadOnlyList<SessionRegionSampleRecord> Regions);

public sealed record SessionRegionSampleRecord(
    string Name,
    string Category,
    string Address,
    int Length,
    bool Required,
    bool ReadSucceeded,
    int BytesRead,
    string? BytesHex,
    string? Error);

public sealed record SessionMarkerRecord(
    string Kind,
    string RecordedAtUtc,
    long? ElapsedMilliseconds,
    int? SampleIndex,
    string? Label,
    string? Message,
    string? Source,
    IReadOnlyDictionary<string, string>? Metadata);

public sealed record SessionRegionSummaryRecord(
    string Name,
    string Category,
    string Address,
    int Length,
    bool Required,
    int SampleCount,
    int SuccessfulReadCount,
    int FailedReadCount,
    long TotalBytesRead,
    int ChangedSampleCount,
    string? LastError);

public sealed record SessionMarkerKindSummaryRecord(
    string Kind,
    int Count);

public sealed record SessionExternalMarkerInputRecord(
    string? Kind,
    string? Label,
    string? Message,
    string? Source,
    IReadOnlyDictionary<string, string>? Metadata);
