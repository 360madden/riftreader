namespace RiftReader.Reader.Facing;

public sealed record ActorFacingBasisMetrics(
    double? Determinant,
    double? ForwardMagnitude,
    double? UpMagnitude,
    double? RightMagnitude,
    double? ForwardDotUp,
    double? ForwardDotRight,
    double? UpDotRight,
    double? DuplicateBasisMaximumRowDelta);
