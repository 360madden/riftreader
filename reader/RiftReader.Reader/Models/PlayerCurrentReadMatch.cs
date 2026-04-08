namespace RiftReader.Reader.Models;

public sealed record PlayerCurrentReadMatch(
    bool LevelMatches,
    bool HealthMatches,
    bool CoordMatchesWithinTolerance,
    float? DeltaX,
    float? DeltaY,
    float? DeltaZ);
