namespace RiftReader.Reader.AddonSnapshots;

public sealed record ReaderBridgeHudSnapshot(
    bool? Visible,
    bool? Locked,
    bool? ShowBuffPanel);
