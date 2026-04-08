namespace RiftReader.Reader.Models;

public sealed record PlayerCurrentReadResult(
    string Mode,
    int ProcessId,
    string ProcessName,
    string ReaderBridgeSourceFile,
    string FamilyId,
    string FamilyNotes,
    string Signature,
    string SelectionSource,
    string? ConfirmationFile,
    int CeConfirmedSampleCount,
    PlayerCurrentReadSample Memory,
    PlayerCurrentReadExpected Expected,
    PlayerCurrentReadMatch Match);
