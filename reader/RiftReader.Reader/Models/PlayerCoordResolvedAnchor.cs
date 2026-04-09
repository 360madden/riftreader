namespace RiftReader.Reader.Models;

public sealed record PlayerCoordResolvedAnchor(
    string BaseRegister,
    string BaseRegisterValue,
    long ObjectBaseAddress,
    int CoordBaseRelativeOffset,
    int CoordXOffset,
    int CoordYOffset,
    int CoordZOffset,
    int LevelOffset,
    int HealthOffset);
