namespace RiftReader.Reader.AddonSnapshots;

public sealed record ReaderBridgeSnapshotDocument(
    string SourceFile,
    DateTimeOffset LoadedAtUtc,
    int? SchemaVersion,
    double? LastExportAt,
    string? LastReason,
    int? ExportCount,
    ReaderBridgeSnapshot? Current);
