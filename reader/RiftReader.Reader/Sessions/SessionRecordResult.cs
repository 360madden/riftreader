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
    string IntegrityStatus,
    IReadOnlyList<string> MissingFiles,
    IReadOnlyList<ProcessModuleInfo> Modules,
    IReadOnlyList<string> WatchsetWarnings,
    IReadOnlyList<string> Warnings);

public sealed record SessionSampleRecord(
    int SampleIndex,
    string RecordedAtUtc,
    long ElapsedMilliseconds,
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
    string? Label,
    string? Message);
