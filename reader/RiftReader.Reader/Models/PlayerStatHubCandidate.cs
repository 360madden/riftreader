namespace RiftReader.Reader.Models;

public record PlayerStatHubCandidate(
    string Address,
    int Score,
    IReadOnlyList<PlayerStatHubComponentReference> ComponentRefs,
    IReadOnlyList<string> LevelOffsets,
    IReadOnlyList<string> HpOffsets,
    IReadOnlyList<string> HpMaxOffsets,
    IReadOnlyList<string> ResourceOffsets,
    IReadOnlyList<string> ResourceMaxOffsets,
    IReadOnlyList<string> ComboOffsets,
    IReadOnlyList<string> PlanarMaxOffsets,
    IReadOnlyList<string> OwnerOffsets,
    IReadOnlyList<string> StateOffsets,
    IReadOnlyList<string> SourceOffsets,
    IReadOnlyList<string> Reasons
);
