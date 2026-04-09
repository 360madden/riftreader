using RiftReader.Reader.AddonSnapshots;

namespace RiftReader.Reader.Models;

public sealed record PlayerOwnerComponentRankResult(
    string Mode,
    string ArtifactFile,
    DateTimeOffset ArtifactLoadedAtUtc,
    DateTimeOffset? ArtifactGeneratedAtUtc,
    string SnapshotFile,
    string? PlayerName,
    int? PlayerLevel,
    string? PlayerCalling,
    string? PlayerGuild,
    string? PlayerRole,
    string? PlayerLocation,
    ValidatorCoordinateSnapshot? PlayerCoord,
    long? PlayerHp,
    long? PlayerHpMax,
    string? PlayerResourceKind,
    long? PlayerResource,
    long? PlayerResourceMax,
    long? PlayerCombo,
    long? PlayerPlanar,
    long? PlayerPlanarMax,
    long? PlayerVitality,
    string? OwnerAddress,
    string? ContainerAddress,
    string? SelectedSourceAddress,
    string? StateRecordAddress,
    int EntryCount,
    IReadOnlyList<string> FocusFields,
    IReadOnlyList<PlayerOwnerComponentRankCandidate> Candidates);
