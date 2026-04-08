namespace RiftReader.Reader.Scanning;

public sealed record PlayerSignatureCeConfirmedFamily(
    string FamilyId,
    string? Signature,
    string? Notes,
    int BestScore,
    int HitCount,
    string? RepresentativeAddressHex,
    IReadOnlyList<string>? SampleAddresses,
    int CeConfirmedSampleCount,
    IReadOnlyList<string>? CeConfirmedSampleAddresses);
