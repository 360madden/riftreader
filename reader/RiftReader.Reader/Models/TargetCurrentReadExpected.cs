namespace RiftReader.Reader.Models;

public sealed record TargetCurrentReadExpected(
    string? Name,
    int? Level,
    long? Health,
    long? HealthMax,
    double? CoordX,
    double? CoordY,
    double? CoordZ,
    double? Distance);
