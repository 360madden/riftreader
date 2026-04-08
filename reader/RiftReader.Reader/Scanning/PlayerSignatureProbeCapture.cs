namespace RiftReader.Reader.Scanning;

public sealed record PlayerSignatureProbeCapture(
    string Mode,
    int ProcessId,
    string ProcessName,
    string SearchLabel,
    string FamilyId,
    string FamilyNotes,
    string Signature,
    string? Label,
    string? OutputFile,
    int HitCount,
    IReadOnlyList<PlayerSignatureProbeSample> Samples);
