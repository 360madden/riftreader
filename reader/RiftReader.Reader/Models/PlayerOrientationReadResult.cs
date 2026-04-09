using RiftReader.Reader.AddonSnapshots;

namespace RiftReader.Reader.Models;

public sealed record PlayerOrientationReadResult(
    string Mode,
    string ArtifactFile,
    DateTimeOffset ArtifactLoadedAtUtc,
    DateTimeOffset? ArtifactGeneratedAtUtc,
    string? SnapshotFile,
    DateTimeOffset? SnapshotLoadedAtUtc,
    string? PlayerName,
    int? PlayerLevel,
    string? PlayerGuild,
    string? PlayerLocation,
    ValidatorCoordinateSnapshot? PlayerCoord,
    string? SelectedSourceAddress,
    string? SelectedEntryAddress,
    int? SelectedEntryIndex,
    bool SelectedEntryMatchesSelectedSource,
    IReadOnlyList<string> SelectedEntryRoleHints,
    PlayerOrientationVectorEstimate? PreferredEstimate,
    IReadOnlyList<PlayerOrientationVectorEstimate> Estimates,
    IReadOnlyList<string> Notes);
