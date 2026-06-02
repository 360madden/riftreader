namespace RiftReader.Reader.AddonSnapshots;

public sealed record ReaderBridgeHudSnapshot(
    bool? Visible,
    bool? Locked,
    bool? ShowBuffPanel,
    string? CompactStatus,
    string? CompactStatusReason,
    string? CompactTarget,
    string? CompactSafety);
