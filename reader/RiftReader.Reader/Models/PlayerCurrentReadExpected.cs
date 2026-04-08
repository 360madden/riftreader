namespace RiftReader.Reader.Models;

public sealed record PlayerCurrentReadExpected(
    string? Name,
    string? Location,
    int? Level,
    long? Health,
    long? HealthMax,
    double? CoordX,
    double? CoordY,
    double? CoordZ);
