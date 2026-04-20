using RiftReader.Reader.Processes;

namespace RiftReader.Reader.Debugging;

public sealed record DebugTraceRequest(
    int SchemaVersion,
    string Mode,
    DebugTraceTargetSpec Target,
    DebugTraceBreakpointSpec Breakpoint,
    DebugTraceCaptureOptions Capture,
    DebugTraceLimits Limits,
    DebugTraceCapabilities Capabilities,
    string OutputDirectory,
    string? Label,
    string? MarkerInputFile,
    string? PresetName,
    string? PlayerCoordTraceFile,
    string? ReaderBridgeSnapshotFile,
    bool JsonOutput);

public sealed record DebugTraceTargetSpec(
    int ProcessId,
    string ProcessName,
    string? ModuleName,
    string? MainWindowTitle,
    string? ProcessStartTimeUtc);

public sealed record DebugTraceBreakpointSpec(
    string Kind,
    string ResolutionMode,
    string? Address,
    string? ModuleName,
    string? ModuleOffset,
    int? Width,
    string? Pattern,
    string? SourceFile,
    string? AccessType,
    IReadOnlyDictionary<string, string>? Metadata);

public sealed record DebugTraceCaptureOptions(
    int StackBytes,
    int MemoryWindowBytes);

public sealed record DebugTraceLimits(
    int TimeoutMilliseconds,
    int MaxHits,
    int MaxEvents);

public sealed record DebugTraceCapabilities(
    bool PreflightValidation = true,
    bool RegisterCapture = true,
    bool StackCapture = true,
    bool MemoryWindows = true,
    bool InstructionDecode = true,
    bool InstructionFingerprint = true,
    bool HitClustering = true,
    bool FollowUpSuggestions = true,
    bool Artifacts = true);

public sealed record DebugTracePackageManifestDocument(
    int? SchemaVersion,
    string? Mode,
    string? Status,
    string? IntegrityStatus,
    string? GeneratedAtUtc,
    string? TraceId,
    string? Label,
    string? TraceDirectory,
    string? RequestFile,
    string? RecordingManifestFile,
    string? EventsFile,
    string? HitsFile,
    string? MarkersFile,
    string? ModulesFile,
    string? FailureLedgerFile,
    string? InstructionFingerprintsFile,
    string? HitClustersFile,
    string? FollowUpSuggestionsFile,
    int? ProcessId,
    string? ProcessName,
    int? HitCount,
    int? EventCount,
    bool? Interrupted,
    bool? AbnormalExit,
    IReadOnlyList<string>? MissingFiles,
    string? FailureMessage,
    IReadOnlyList<string>? Warnings);

public sealed record DebugTraceResult(
    int SchemaVersion,
    string Mode,
    string TraceId,
    string OutputDirectory,
    int ProcessId,
    string ProcessName,
    string? ModuleName,
    string? MainWindowTitle,
    string? ProcessStartTimeUtc,
    string BreakpointKind,
    string BreakpointResolutionMode,
    string? BreakpointAddress,
    string? BreakpointModuleName,
    string? BreakpointModuleOffset,
    int? BreakpointWidth,
    string? PresetName,
    string? Label,
    string StartedAtUtc,
    string CompletedAtUtc,
    long ElapsedMilliseconds,
    string ManifestFile,
    string PackageManifestFile,
    string EventsFile,
    string HitsFile,
    string MarkersFile,
    string ModulesFile,
    string FailureLedgerFile,
    string? InstructionFingerprintsFile,
    string? HitClustersFile,
    string? FollowUpSuggestionsFile,
    bool Interrupted,
    bool AbnormalExit,
    string IntegrityStatus,
    string AttachOutcome,
    string DetachOutcome,
    string CleanupOutcome,
    string PrivilegeState,
    string TargetArchitecture,
    DebugTraceCapabilities Capabilities,
    int RequestedHitCount,
    int RecordedHitCount,
    int EventCount,
    string? FailureMessage,
    IReadOnlyList<string> MissingFiles,
    IReadOnlyList<ProcessModuleInfo> Modules,
    IReadOnlyList<string> Warnings);

public sealed record DebugTraceEventRecord(
    int EventIndex,
    string TraceId,
    string RecordedAtUtc,
    long ElapsedMilliseconds,
    string Phase,
    string EventKind,
    int? ThreadId,
    uint? DebugEventCode,
    uint? ExceptionCode,
    bool? FirstChance,
    string? BreakpointId,
    int? HitIndex,
    string? ModuleRelativeRip,
    string? RawRip,
    string? ModuleName,
    string? ModuleOffset,
    string? StatusCode,
    string? Message);

public sealed record DebugTraceHitRecord(
    int HitIndex,
    string TraceId,
    string RecordedAtUtc,
    long ElapsedMilliseconds,
    string BreakpointKind,
    int ThreadId,
    string? ModuleRelativeRip,
    string? RawRip,
    string? InstructionText,
    string? InstructionBytes,
    string? InstructionWindowBytes,
    IReadOnlyDictionary<string, string>? Registers,
    string? StackWindowBytes,
    string? EffectiveAddress,
    string? WatchedAddress,
    int? WatchedWidth,
    IReadOnlyList<DebugMemoryWindowRecord>? MemoryWindows,
    string? ValueBefore,
    string? ValueAfter,
    string? CallerFingerprint,
    string? StackFingerprint,
    string? InstructionFingerprint,
    IReadOnlyDictionary<string, string>? PointerClassifications,
    IReadOnlyList<string>? Warnings,
    IReadOnlyList<string>? ConfidenceNotes);

public sealed record DebugMemoryWindowRecord(
    string Label,
    string Address,
    int Length,
    string? BytesHex,
    string? Classification,
    string? Error);

public sealed record DebugTraceMarkerRecord(
    string Kind,
    string RecordedAtUtc,
    long? ElapsedMilliseconds,
    int? EventIndex,
    int? HitIndex,
    string? Label,
    string? Message,
    string? Source,
    IReadOnlyDictionary<string, string>? Metadata);

public sealed record DebugInstructionFingerprintRecord(
    string TraceId,
    string ModuleName,
    string ModuleOffset,
    string ModuleRelativeRip,
    string? InstructionText,
    string? InstructionBytes,
    string? Pattern,
    int HitCount);

public sealed record DebugHitClusterRecord(
    string TraceId,
    string ClusterKey,
    string? ModuleRelativeRip,
    string? EffectiveAddress,
    int HitCount,
    IReadOnlyList<int> ThreadIds,
    IReadOnlyList<int> HitIndices,
    string? CallerFingerprint);

public sealed record DebugFollowUpSuggestionRecord(
    string TraceId,
    string Kind,
    string Address,
    int Length,
    string Reason,
    string? RelatedOffset,
    string? Confidence);

public sealed record DebugTraceInspectResult(
    int SchemaVersion,
    string Mode,
    string TraceDirectory,
    DebugTracePackageManifestDocument Package,
    DebugTraceResult? TraceManifest,
    IReadOnlyList<DebugTraceEventRecord> Events,
    IReadOnlyList<DebugTraceHitRecord> Hits,
    IReadOnlyList<DebugTraceMarkerRecord> Markers,
    IReadOnlyList<ProcessModuleInfo> Modules,
    IReadOnlyList<DebugInstructionFingerprintRecord> InstructionFingerprints,
    IReadOnlyList<DebugHitClusterRecord> HitClusters,
    IReadOnlyList<DebugFollowUpSuggestionRecord> FollowUpSuggestions,
    IReadOnlyList<string> Warnings);

public sealed record DebugExternalMarkerInputRecord(
    string? Kind,
    string? Label,
    string? Message,
    string? Source,
    IReadOnlyDictionary<string, string>? Metadata);
