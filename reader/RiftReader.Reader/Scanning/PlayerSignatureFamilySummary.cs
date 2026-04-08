namespace RiftReader.Reader.Scanning;

public sealed record PlayerSignatureFamilySummary(
    string FamilyId,
    string Signature,
    int HitCount,
    int BestScore,
    string Notes,
    string RepresentativeAddressHex,
    IReadOnlyList<string> SampleAddresses);
