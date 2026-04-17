namespace RiftReader.Reader.Facing;

public static class ActorFacingAnalyzer
{
    public static ActorFacingIntegrityResult EvaluateIntegrity(
        ActorFacingBasisMetrics metrics,
        ActorFacingThresholds? thresholds = null)
    {
        ArgumentNullException.ThrowIfNull(metrics);

        var activeThresholds = thresholds ?? ActorFacingThresholds.Default;
        var notes = new List<string>();

        var determinantPass =
            metrics.Determinant.HasValue &&
            metrics.Determinant.Value >= activeThresholds.DeterminantMinimum &&
            metrics.Determinant.Value <= activeThresholds.DeterminantMaximum;
        if (!determinantPass)
        {
            notes.Add("determinant-out-of-range");
        }

        var rowMagnitudesPass =
            IsRowMagnitudePass(metrics.ForwardMagnitude, activeThresholds) &&
            IsRowMagnitudePass(metrics.UpMagnitude, activeThresholds) &&
            IsRowMagnitudePass(metrics.RightMagnitude, activeThresholds);
        if (!rowMagnitudesPass)
        {
            notes.Add("row-magnitude-out-of-range");
        }

        var crossRowDotProductsPass =
            IsCrossDotPass(metrics.ForwardDotUp, activeThresholds) &&
            IsCrossDotPass(metrics.ForwardDotRight, activeThresholds) &&
            IsCrossDotPass(metrics.UpDotRight, activeThresholds);
        if (!crossRowDotProductsPass)
        {
            notes.Add("cross-row-dot-out-of-range");
        }

        var duplicateBasisPass =
            !metrics.DuplicateBasisMaximumRowDelta.HasValue ||
            metrics.DuplicateBasisMaximumRowDelta.Value <= activeThresholds.DuplicateBasisMaximumRowDelta;
        if (!duplicateBasisPass)
        {
            notes.Add("duplicate-basis-delta-too-large");
        }

        var pass = determinantPass &&
                   rowMagnitudesPass &&
                   crossRowDotProductsPass &&
                   duplicateBasisPass;

        if (pass)
        {
            notes.Add("integrity-pass");
        }

        return new ActorFacingIntegrityResult(
            DeterminantPass: determinantPass,
            RowMagnitudesPass: rowMagnitudesPass,
            CrossRowDotProductsPass: crossRowDotProductsPass,
            DuplicateBasisPass: duplicateBasisPass,
            Pass: pass,
            Notes: notes);
    }

    public static string ClassifyFailureShape(
        double? signedAngularErrorDegrees,
        double movementDistance,
        bool integrityPass,
        bool turnResponsive,
        ActorFacingThresholds? thresholds = null)
    {
        var activeThresholds = thresholds ?? ActorFacingThresholds.Default;

        if (!integrityPass)
        {
            return ActorFacingFailureShape.IntegrityInstability;
        }

        if (!signedAngularErrorDegrees.HasValue || movementDistance < activeThresholds.ForwardMovementDistance)
        {
            return ActorFacingFailureShape.InsufficientMovement;
        }

        var absoluteError = Math.Abs(ActorFacingMath.NormalizeDegrees(signedAngularErrorDegrees.Value));

        if (Math.Abs(absoluteError - 180d) <= 25d)
        {
            return ActorFacingFailureShape.SignInverted;
        }

        if (Math.Abs(absoluteError - 90d) <= 20d)
        {
            return ActorFacingFailureShape.WrongAxis;
        }

        if (turnResponsive && absoluteError > activeThresholds.ForwardAngularErrorDegrees)
        {
            return ActorFacingFailureShape.LocomotionMismatch;
        }

        return ActorFacingFailureShape.None;
    }

    private static bool IsRowMagnitudePass(double? value, ActorFacingThresholds thresholds) =>
        value.HasValue &&
        value.Value >= thresholds.RowMagnitudeMinimum &&
        value.Value <= thresholds.RowMagnitudeMaximum;

    private static bool IsCrossDotPass(double? value, ActorFacingThresholds thresholds) =>
        value.HasValue &&
        Math.Abs(value.Value) <= thresholds.CrossRowDotProductMaximumAbsolute;
}
