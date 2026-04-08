namespace RiftReader.Reader.Scanning;

public sealed record PlayerSignatureScanHit(
    long Address,
    string AddressHex,
    long RegionBase,
    string RegionBaseHex,
    long RegionSize,
    int Score,
    string FamilyId,
    int FamilyHitCount,
    IReadOnlyList<PlayerSignatureSignal> Signals,
    StringHitContext? Context);
