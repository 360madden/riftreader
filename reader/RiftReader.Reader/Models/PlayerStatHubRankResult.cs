using RiftReader.Reader.AddonSnapshots;

namespace RiftReader.Reader.Models;

public record PlayerStatHubRankResult(
    string Mode,
    string GeneratedAtUtc,
    string? OwnerComponentsFile,
    string? SnapshotFile,
    string OwnerAddress,
    string StateRecordAddress,
    string SelectedSourceAddress,
    string PlayerUnitId,
    string PlayerUnitIdRawHex,
    int? PlayerLevel,
    int? PlayerHp,
    int? PlayerHpMax,
    int? PlayerResource,
    int? PlayerResourceMax,
    int? PlayerCombo,
    int? PlayerPlanarMax,
    IReadOnlyList<PlayerStatHubIdentityComponentDetail> IdentityComponents,
    IReadOnlyList<PlayerStatHubCandidate> RankedSharedHubs,
    IReadOnlyList<PlayerStatHubGraphLink> IdentityGraphLinks
);

public record PlayerStatHubIdentityComponentDetail(
    int Index,
    string Address,
    IReadOnlyList<string> RoleHints,
    IReadOnlyList<PlayerStatHubPointerTarget> PointerTargets,
    IReadOnlyList<int> UnitIdOffsets,
    IReadOnlyList<int> OwnerOffsets,
    IReadOnlyList<int> StateOffsets,
    IReadOnlyList<int> SourceOffsets,
    IReadOnlyList<int> LevelOffsets,
    IReadOnlyList<int> HpOffsets,
    IReadOnlyList<int> HpMaxOffsets,
    IReadOnlyList<int> ResourceOffsets,
    IReadOnlyList<int> ResourceMaxOffsets,
    IReadOnlyList<int> ComboOffsets,
    IReadOnlyList<int> PlanarMaxOffsets
);

public record PlayerStatHubPointerTarget(
    int Offset,
    string OffsetHex,
    string Address,
    ulong Value
);

public record PlayerStatHubGraphLink(
    int IdentityComponentIndex,
    string IdentityComponentAddress,
    string OffsetHex,
    string HubAddress,
    int HubScore
);
