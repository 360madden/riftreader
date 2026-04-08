namespace RiftReader.Reader.Scanning;

public sealed record NumericScanHit(
    long Address,
    string AddressHex,
    long RegionBase,
    string RegionBaseHex,
    long RegionSize,
    string ValueType,
    string ObservedValue,
    string? Delta,
    StringHitContext? Context);
