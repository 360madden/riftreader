namespace RiftReader.Reader.Models;

public sealed record PlayerCurrentReadSample(
    string AddressHex,
    int? Level,
    int? Health,
    string? Name,
    string? Location,
    float? CoordX,
    float? CoordY,
    float? CoordZ);
