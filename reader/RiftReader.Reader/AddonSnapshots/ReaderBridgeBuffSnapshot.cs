namespace RiftReader.Reader.AddonSnapshots;

public sealed record ReaderBridgeBuffSnapshot(
    string? Id,
    string? Name,
    double? Remaining,
    double? Duration,
    long? Stack,
    bool? Debuff,
    bool? Curse,
    bool? Disease,
    bool? Poison,
    string? Caster,
    string? Text,
    IReadOnlyList<string> Flags);
