namespace RiftReader.Reader.Facing;

public sealed record ActorFacingThresholds(
    double DeterminantMinimum,
    double DeterminantMaximum,
    double RowMagnitudeMinimum,
    double RowMagnitudeMaximum,
    double CrossRowDotProductMaximumAbsolute,
    double DuplicateBasisMaximumRowDelta,
    double IdleYawJitterDegrees,
    double IdlePlanarCoordDrift,
    double TurnYawDeltaDegrees,
    double TurnPlanarCoordDrift,
    double ForwardMovementDistance,
    double ForwardAngularErrorDegrees,
    double RepeatedForwardMedianAngularErrorDegrees,
    double RepeatedForwardSingleAngularErrorDegrees)
{
    public static ActorFacingThresholds Default { get; } = new(
        DeterminantMinimum: 0.98d,
        DeterminantMaximum: 1.02d,
        RowMagnitudeMinimum: 0.98d,
        RowMagnitudeMaximum: 1.02d,
        CrossRowDotProductMaximumAbsolute: 0.02d,
        DuplicateBasisMaximumRowDelta: 0.02d,
        IdleYawJitterDegrees: 3d,
        IdlePlanarCoordDrift: 0.15d,
        TurnYawDeltaDegrees: 15d,
        TurnPlanarCoordDrift: 0.25d,
        ForwardMovementDistance: 0.75d,
        ForwardAngularErrorDegrees: 12d,
        RepeatedForwardMedianAngularErrorDegrees: 8d,
        RepeatedForwardSingleAngularErrorDegrees: 15d);
}
