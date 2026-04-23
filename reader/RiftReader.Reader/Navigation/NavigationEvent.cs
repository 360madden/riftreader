namespace RiftReader.Reader.Navigation;

public sealed record NavigationEvent(
    string Stage,
    string Type,
    long ElapsedMilliseconds,
    string? Status = null,
    int? PulseIndex = null,
    string? Key = null,
    NavigationCoordinate? Position = null,
    double? PlanarDistance = null,
    double? SignedBearingDeltaDegrees = null,
    double? AbsoluteBearingDeltaDegrees = null,
    string? Detail = null);
