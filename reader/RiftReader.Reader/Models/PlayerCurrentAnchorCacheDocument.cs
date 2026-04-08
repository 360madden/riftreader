namespace RiftReader.Reader.Models;

public sealed record PlayerCurrentAnchorCacheDocument(
    string ProcessName,
    string AddressHex,
    string FamilyId,
    string FamilyNotes,
    string Signature,
    string SelectionSource,
    string? ConfirmationFile,
    int CeConfirmedSampleCount,
    int LevelOffset,
    int HealthOffset,
    int CoordXOffset,
    int CoordYOffset,
    int CoordZOffset,
    DateTimeOffset SavedAtUtc);
