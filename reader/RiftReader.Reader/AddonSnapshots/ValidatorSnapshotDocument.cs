namespace RiftReader.Reader.AddonSnapshots;

public sealed record ValidatorSnapshotDocument(
    string SourceFile,
    DateTimeOffset LoadedAtUtc,
    int SampleCount,
    double? LastCaptureAt,
    string? LastReason,
    ValidatorSnapshot? Current);
