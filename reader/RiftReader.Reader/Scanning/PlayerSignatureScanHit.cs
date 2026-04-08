namespace RiftReader.Reader.Scanning;

public sealed record PlayerSignatureScanHit(
    long Address,
    string AddressHex,
    long RegionBase,
    string RegionBaseHex,
    long RegionSize,
    int Score,
    IReadOnlyList<PlayerSignatureSignal> Signals,
    StringHitContext? Context);
