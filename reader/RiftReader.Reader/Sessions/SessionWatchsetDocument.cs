namespace RiftReader.Reader.Sessions;

public sealed record SessionWatchsetDocument(
    string? Mode,
    string? GeneratedAtUtc,
    string? ProcessName,
    string? PreferredSourceAddress,
    IReadOnlyList<SessionWatchsetArtifact>? Artifacts,
    IReadOnlyList<string>? Warnings,
    IReadOnlyList<SessionWatchRegion>? Regions);

public sealed record SessionWatchsetArtifact(
    string? Role,
    string? File,
    string? GeneratedAtUtc,
    string? SelectedSourceAddress);

public sealed record SessionWatchRegion(
    string? Name,
    string? Category,
    string? Address,
    int Length,
    bool Required,
    int? Priority,
    string? SourceArtifactFile,
    string? Notes);
