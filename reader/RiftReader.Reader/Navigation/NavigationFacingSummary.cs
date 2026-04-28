namespace RiftReader.Reader.Navigation;

public sealed record NavigationFacingSummary(
    string Status,
    string SourceKind,
    string? ResolutionMode,
    string? SelectedSourceAddress,
    string? BasisPrimaryForwardOffset,
    string? BasisDuplicateForwardOffset,
    double? YawRadians,
    double? YawDegrees,
    double? PitchRadians,
    double? PitchDegrees,
    double? SignedBearingDeltaDegrees,
    double? AbsoluteBearingDeltaDegrees,
    string? SuggestedTurnDirection,
    string? Reason);
