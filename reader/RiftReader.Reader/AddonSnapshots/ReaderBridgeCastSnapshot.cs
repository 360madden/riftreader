namespace RiftReader.Reader.AddonSnapshots;

public sealed record ReaderBridgeCastSnapshot(
    bool? Active,
    string? AbilityName,
    double? Duration,
    double? Remaining,
    bool? Channeled,
    bool? Uninterruptible,
    double? ProgressPct,
    string? Text);
