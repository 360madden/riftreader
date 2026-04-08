namespace RiftReader.Reader.Cli;

public sealed record ReaderOptions(
    int? ProcessId,
    string? ProcessName,
    nint? Address,
    int? Length,
    bool ReadAddonSnapshot,
    string? AddonSnapshotFile,
    bool JsonOutput);
