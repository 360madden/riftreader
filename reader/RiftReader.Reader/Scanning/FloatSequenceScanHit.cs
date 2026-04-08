namespace RiftReader.Reader.Scanning;

public sealed record FloatSequenceScanHit(
    long Address,
    string AddressHex,
    long RegionBase,
    string RegionBaseHex,
    long RegionSize,
    string ObservedValues,
    StringHitContext? Context);
