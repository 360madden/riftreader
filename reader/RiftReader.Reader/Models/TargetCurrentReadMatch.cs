namespace RiftReader.Reader.Models;

public sealed record TargetCurrentReadMatch(
    bool NameMatches,
    bool LevelMatches,
    bool HealthMatches,
    bool CoordMatchesWithinTolerance,
    bool DistanceMatchesWithinTolerance,
    float? DeltaX,
    float? DeltaY,
    float? DeltaZ,
    float? DeltaDistance);
