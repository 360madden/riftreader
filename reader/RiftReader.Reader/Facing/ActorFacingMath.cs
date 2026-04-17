namespace RiftReader.Reader.Facing;

public static class ActorFacingMath
{
    public static double ComputeYawRadians(double forwardX, double forwardZ) =>
        Math.Atan2(forwardZ, forwardX);

    public static double ComputePitchRadians(double forwardX, double forwardY, double forwardZ) =>
        Math.Atan2(forwardY, Math.Sqrt((forwardX * forwardX) + (forwardZ * forwardZ)));

    public static double ComputePlanarMagnitude(double valueX, double valueZ) =>
        Math.Sqrt((valueX * valueX) + (valueZ * valueZ));

    public static (double X, double Z)? TryNormalizePlanar(double valueX, double valueZ)
    {
        var magnitude = ComputePlanarMagnitude(valueX, valueZ);
        if (magnitude <= double.Epsilon)
        {
            return null;
        }

        return (valueX / magnitude, valueZ / magnitude);
    }

    public static double NormalizeRadians(double radians)
    {
        var normalized = radians;
        while (normalized > Math.PI)
        {
            normalized -= (2d * Math.PI);
        }

        while (normalized < -Math.PI)
        {
            normalized += (2d * Math.PI);
        }

        return normalized;
    }

    public static double NormalizeDegrees(double degrees)
    {
        var normalized = degrees;
        while (normalized > 180d)
        {
            normalized -= 360d;
        }

        while (normalized < -180d)
        {
            normalized += 360d;
        }

        return normalized;
    }

    public static double DegreesFromRadians(double radians) =>
        radians * 180d / Math.PI;

    public static double RadiansFromDegrees(double degrees) =>
        degrees * Math.PI / 180d;

    public static double ComputeObservedHeadingRadians(double deltaX, double deltaZ) =>
        Math.Atan2(deltaZ, deltaX);

    public static double ComputeSignedTurnErrorRadians(
        double actorYawRadians,
        double targetDeltaX,
        double targetDeltaZ) =>
        NormalizeRadians(Math.Atan2(targetDeltaZ, targetDeltaX) - actorYawRadians);
}
