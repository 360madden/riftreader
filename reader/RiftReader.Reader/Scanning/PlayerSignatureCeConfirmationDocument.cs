namespace RiftReader.Reader.Scanning;

public sealed record PlayerSignatureCeConfirmationDocument(
    string? Mode,
    string? GeneratedAtUtc,
    string? ProcessName,
    string? MovementKey,
    int MovementHoldMilliseconds,
    string? PreCeTopFamilyId,
    string? WinnerFamilyId,
    int CandidateFamilyCount,
    int CeConfirmedFamilyCount,
    PlayerSignatureCeConfirmedFamily? Winner,
    IReadOnlyList<PlayerSignatureCeConfirmedFamily>? Families,
    string? ConfirmationFile);
