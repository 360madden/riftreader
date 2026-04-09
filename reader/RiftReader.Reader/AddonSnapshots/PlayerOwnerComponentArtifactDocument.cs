namespace RiftReader.Reader.AddonSnapshots;

public sealed record PlayerOwnerComponentArtifactDocument(
    string? Mode,
    DateTimeOffset? GeneratedAtUtc,
    string? SelectorTraceFile,
    PlayerOwnerComponentArtifactOwner? Owner,
    int? EntryCount,
    IReadOnlyList<PlayerOwnerComponentArtifactEntry>? Entries)
{
    public string SourceFile { get; init; } = string.Empty;

    public DateTimeOffset LoadedAtUtc { get; init; }
}

public sealed record PlayerOwnerComponentArtifactOwner(
    string? Address,
    string? ContainerAddress,
    string? SelectedSourceAddress,
    string? StateRecordAddress);

public sealed record PlayerOwnerComponentArtifactEntry(
    int Index,
    string? Address,
    IReadOnlyList<string>? RoleHints,
    string? Q8,
    string? Q68,
    string? Q100,
    int OwnerRefCount,
    int SourceRefCount,
    ValidatorCoordinateSnapshot? Coord48,
    ValidatorCoordinateSnapshot? Coord88,
    ValidatorCoordinateSnapshot? Orientation60,
    ValidatorCoordinateSnapshot? Orientation94);
