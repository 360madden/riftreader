namespace RiftReader.Reader.Models;

public sealed record PlayerCoordAnchorSourceMatch(
    bool CoordMatchesWithinTolerance,
    float? DeltaX,
    float? DeltaY,
    float? DeltaZ);
