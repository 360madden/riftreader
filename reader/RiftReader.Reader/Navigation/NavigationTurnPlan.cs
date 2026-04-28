namespace RiftReader.Reader.Navigation;

public sealed record NavigationTurnPlan(
    string Status,
    string? SourceKind,
    string? ResolutionMode,
    string? SelectedSourceAddress,
    string? BasisPrimaryForwardOffset,
    double DestinationBearingDegrees,
    double? CurrentYawDegrees,
    double? SignedBearingDeltaDegrees,
    double? AbsoluteBearingDeltaDegrees,
    string? SuggestedTurnDirection,
    double AlignmentThresholdDegrees,
    bool WithinAlignmentThreshold,
    string? Reason);

public sealed record NavigationTurnSample(
    int PulseIndex,
    string Key,
    NavigationCoordinate Position,
    double? YawDegrees,
    double? SignedBearingDeltaDegrees,
    double? AbsoluteBearingDeltaDegrees,
    string? SuggestedTurnDirection,
    string? SelectedSourceAddress,
    string? BasisPrimaryForwardOffset);

public sealed record NavigationTurnResult(
    string Status,
    bool Succeeded,
    bool Attempted,
    string? TurnKey,
    string? TurnDirection,
    double ThresholdDegrees,
    int PulseCount,
    int WorseningPulseCount,
    int MaxWorseningPulses,
    NavigationTurnPlan InitialPlan,
    NavigationTurnPlan FinalPlan,
    NavigationCoordinate InitialPosition,
    NavigationCoordinate FinalPosition,
    IReadOnlyList<NavigationTurnSample> Samples,
    string? Reason,
    IReadOnlyList<NavigationEvent>? Events = null);

public sealed record NavigationAutoTurnOptions(
    bool Enabled,
    double WithinDegrees,
    string TurnLeftKey,
    string TurnRightKey,
    int TurnPulseMilliseconds,
    int PostTurnSampleDelayMilliseconds,
    int SettleDelayMilliseconds,
    int MaxTurnPulses,
    double WorseningToleranceDegrees,
    int MaxWorseningPulses);
