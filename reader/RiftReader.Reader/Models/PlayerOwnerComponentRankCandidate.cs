using RiftReader.Reader.AddonSnapshots;

namespace RiftReader.Reader.Models;

public sealed record PlayerOwnerComponentRankCandidate(
    int Rank,
    int Index,
    string AddressHex,
    int Score,
    string Kind,
    IReadOnlyList<string> Reasons,
    IReadOnlyList<string> RoleHints,
    string? Q8,
    string? Q68,
    string? Q100,
    int OwnerRefCount,
    int SourceRefCount,
    ValidatorCoordinateSnapshot? Coord48,
    ValidatorCoordinateSnapshot? Coord88,
    ValidatorCoordinateSnapshot? Orientation60,
    ValidatorCoordinateSnapshot? Orientation94);
