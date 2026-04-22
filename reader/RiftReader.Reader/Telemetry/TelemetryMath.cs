namespace RiftReader.Reader.Telemetry;

public static class TelemetryMath
{
    public static double? ComputeTravelHeadingRadians(double? dx, double? dz)
    {
        if (!dx.HasValue || !dz.HasValue)
        {
            return null;
        }

        if (Math.Abs(dx.Value) < 0.000001d && Math.Abs(dz.Value) < 0.000001d)
        {
            return null;
        }

        return Math.Atan2(dz.Value, dx.Value);
    }

    public static double? ComputeTravelHeadingDegrees(double? dx, double? dz)
    {
        var radians = ComputeTravelHeadingRadians(dx, dz);
        return radians.HasValue ? radians.Value * 180d / Math.PI : null;
    }

    public static double NormalizeAngleDegrees(double deltaDegrees)
    {
        var normalized = deltaDegrees % 360d;

        if (normalized > 180d)
        {
            normalized -= 360d;
        }
        else if (normalized < -180d)
        {
            normalized += 360d;
        }

        return normalized;
    }

    public static double? ComputeYawRateDegreesPerSecond(double? previousYawDegrees, DateTimeOffset? previousAtUtc, double? currentYawDegrees, DateTimeOffset currentAtUtc)
    {
        if (!previousYawDegrees.HasValue || !previousAtUtc.HasValue || !currentYawDegrees.HasValue)
        {
            return null;
        }

        var dt = (currentAtUtc - previousAtUtc.Value).TotalSeconds;
        if (dt <= 0d)
        {
            return null;
        }

        var delta = NormalizeAngleDegrees(currentYawDegrees.Value - previousYawDegrees.Value);
        return delta / dt;
    }

    public static double? ComputeDistance(TelemetryVector3? previous, TelemetryVector3? current)
    {
        if (previous is null || current is null)
        {
            return null;
        }

        var dx = current.X - previous.X;
        var dy = current.Y - previous.Y;
        var dz = current.Z - previous.Z;
        return Math.Sqrt((dx * dx) + (dy * dy) + (dz * dz));
    }
}
