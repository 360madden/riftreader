namespace RiftReader.Reader.Scanning;

public sealed record StringScanHit(
    long Address,
    string AddressHex,
    string Encoding,
    long RegionBase,
    string RegionBaseHex,
    long RegionSize,
    int MatchLength,
    string? Classification,
    StringHitContext? Context);
