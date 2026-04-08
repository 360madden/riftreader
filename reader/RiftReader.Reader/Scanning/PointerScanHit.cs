namespace RiftReader.Reader.Scanning;

public sealed record PointerScanHit(
    long Address,
    string AddressHex,
    long RegionBase,
    string RegionBaseHex,
    long RegionSize,
    StringHitContext? Context);
