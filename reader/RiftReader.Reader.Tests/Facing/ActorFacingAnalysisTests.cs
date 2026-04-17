using RiftReader.Reader.Facing;

namespace RiftReader.Reader.Tests.Facing;

public sealed class ActorFacingMathTests
{
    [Fact]
    public void ComputesYawAndPitchFromForwardVector()
    {
        var yaw = ActorFacingMath.ComputeYawRadians(0d, 1d);
        var pitch = ActorFacingMath.ComputePitchRadians(0d, 0d, 1d);

        Assert.InRange(ActorFacingMath.DegreesFromRadians(yaw), 89.999d, 90.001d);
        Assert.InRange(ActorFacingMath.DegreesFromRadians(pitch), -0.001d, 0.001d);
    }

    [Fact]
    public void ComputesSignedTurnErrorUsingNormalizedRadians()
    {
        var actorYaw = ActorFacingMath.RadiansFromDegrees(170d);
        var turnError = ActorFacingMath.ComputeSignedTurnErrorRadians(
            actorYawRadians: actorYaw,
            targetDeltaX: Math.Cos(ActorFacingMath.RadiansFromDegrees(-170d)),
            targetDeltaZ: Math.Sin(ActorFacingMath.RadiansFromDegrees(-170d)));

        Assert.InRange(ActorFacingMath.DegreesFromRadians(turnError), 19.9d, 20.1d);
    }

    [Fact]
    public void NormalizesPlanarVector()
    {
        var normalized = ActorFacingMath.TryNormalizePlanar(3d, 4d);

        Assert.NotNull(normalized);
        Assert.InRange(normalized.Value.X, 0.5999d, 0.6001d);
        Assert.InRange(normalized.Value.Z, 0.7999d, 0.8001d);
    }
}

public sealed class ActorFacingAnalyzerTests
{
    [Fact]
    public void EvaluateIntegrity_PassesForStrongBasis()
    {
        var result = ActorFacingAnalyzer.EvaluateIntegrity(new ActorFacingBasisMetrics(
            Determinant: 1.0d,
            ForwardMagnitude: 1.0d,
            UpMagnitude: 0.999d,
            RightMagnitude: 1.001d,
            ForwardDotUp: 0.0d,
            ForwardDotRight: 0.001d,
            UpDotRight: -0.001d,
            DuplicateBasisMaximumRowDelta: 0.01d));

        Assert.True(result.Pass);
        Assert.True(result.DeterminantPass);
        Assert.True(result.RowMagnitudesPass);
        Assert.True(result.CrossRowDotProductsPass);
        Assert.True(result.DuplicateBasisPass);
    }

    [Fact]
    public void EvaluateIntegrity_FailsForBadDeterminantAndDots()
    {
        var result = ActorFacingAnalyzer.EvaluateIntegrity(new ActorFacingBasisMetrics(
            Determinant: 0.8d,
            ForwardMagnitude: 1.0d,
            UpMagnitude: 1.0d,
            RightMagnitude: 1.0d,
            ForwardDotUp: 0.05d,
            ForwardDotRight: 0.0d,
            UpDotRight: 0.0d,
            DuplicateBasisMaximumRowDelta: 0.0d));

        Assert.False(result.Pass);
        Assert.False(result.DeterminantPass);
        Assert.False(result.CrossRowDotProductsPass);
    }

    [Fact]
    public void ClassifyFailureShape_RecognizesSignInversion()
    {
        var result = ActorFacingAnalyzer.ClassifyFailureShape(
            signedAngularErrorDegrees: 179d,
            movementDistance: 1.5d,
            integrityPass: true,
            turnResponsive: true);

        Assert.Equal(ActorFacingFailureShape.SignInverted, result);
    }

    [Fact]
    public void ClassifyFailureShape_RecognizesWrongAxis()
    {
        var result = ActorFacingAnalyzer.ClassifyFailureShape(
            signedAngularErrorDegrees: 92d,
            movementDistance: 1.2d,
            integrityPass: true,
            turnResponsive: true);

        Assert.Equal(ActorFacingFailureShape.WrongAxis, result);
    }

    [Fact]
    public void ClassifyFailureShape_RecognizesIntegrityInstability()
    {
        var result = ActorFacingAnalyzer.ClassifyFailureShape(
            signedAngularErrorDegrees: 20d,
            movementDistance: 1.2d,
            integrityPass: false,
            turnResponsive: true);

        Assert.Equal(ActorFacingFailureShape.IntegrityInstability, result);
    }

    [Fact]
    public void ClassifyFailureShape_RecognizesInsufficientMovement()
    {
        var result = ActorFacingAnalyzer.ClassifyFailureShape(
            signedAngularErrorDegrees: null,
            movementDistance: 0.1d,
            integrityPass: true,
            turnResponsive: true);

        Assert.Equal(ActorFacingFailureShape.InsufficientMovement, result);
    }

    [Fact]
    public void ClassifyFailureShape_RecognizesLocomotionMismatch()
    {
        var result = ActorFacingAnalyzer.ClassifyFailureShape(
            signedAngularErrorDegrees: 35d,
            movementDistance: 1.3d,
            integrityPass: true,
            turnResponsive: true);

        Assert.Equal(ActorFacingFailureShape.LocomotionMismatch, result);
    }
}
