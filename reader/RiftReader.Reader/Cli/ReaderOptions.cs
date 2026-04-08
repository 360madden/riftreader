using RiftReader.Reader.Scanning;

namespace RiftReader.Reader.Cli;

public sealed record ReaderOptions(
    int? ProcessId,
    string? ProcessName,
    nint? Address,
    int? Length,
    string? ScanString,
    nint? ScanPointer,
    int? ScanInt32,
    float? ScanFloat,
    double? ScanDouble,
    double ScanTolerance,
    int PointerWidth,
    StringScanEncoding ScanEncoding,
    int ScanContextBytes,
    int MaxHits,
    bool ScanReaderBridgePlayerName,
    bool ScanReaderBridgePlayerCoords,
    bool ScanReaderBridgePlayerSignature,
    bool ScanReaderBridgeIdentity,
    bool ReadAddonSnapshot,
    string? AddonSnapshotFile,
    bool ReadReaderBridgeSnapshot,
    string? ReaderBridgeSnapshotFile,
    bool JsonOutput);
