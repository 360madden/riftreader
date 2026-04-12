namespace RiftReader.Reader.Models;

public sealed record TargetCurrentReadSample(
    string AddressHex,
    int? Level,
    int? Health,
    string? Name,
    float? CoordX,
    float? CoordY,
    float? CoordZ,
    float? Distance);
