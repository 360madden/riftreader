namespace RiftReader.Reader.Models;

public sealed record TargetCurrentReadResult(
    string Mode,
    int ProcessId,
    string ProcessName,
    string ReaderBridgeSourceFile,
    string FamilyId,
    string FamilyNotes,
    string Signature,
    string SelectionSource,
    string AnchorProvenance,
    string? AnchorCacheFile,
    bool AnchorCacheUsed,
    bool AnchorCacheUpdated,
    string? ConfirmationFile,
    int CeConfirmedSampleCount,
    TargetCurrentReadSample Memory,
    TargetCurrentReadExpected Expected,
    TargetCurrentReadMatch Match,
    bool HasTarget);
