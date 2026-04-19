using RiftReader.Reader.Facing;

namespace RiftReader.Reader.Navigation;

public static class NavigationMath
{
    public static double ComputePlanarDistance(double deltaX, double deltaZ) =>
        Math.Sqrt((deltaX * deltaX) + (deltaZ * deltaZ));

    public static (double Radians, double Degrees) ComputeBearing(double deltaX, double deltaZ)
    {
        var radians = Math.Atan2(deltaZ, deltaX);
        var degrees = radians * 180d / Math.PI;
        return (radians, degrees);
    }

    public static NavigationVectorSummary BuildSummary(
        int processId,
        string processName,
        string waypointFile,
        WaypointDefinition destinationWaypoint,
        NavigationPoseSample currentSample,
        string anchorSource,
        double arrivalRadius,
        NavigationFacingSummary? facing = null)
    {
        var deltaX = destinationWaypoint.X - currentSample.X;
        var deltaY = destinationWaypoint.Y - currentSample.Y;
        var deltaZ = destinationWaypoint.Z - currentSample.Z;
        var planarDistance = ComputePlanarDistance(deltaX, deltaZ);
        var (bearingRadians, bearingDegrees) = ComputeBearing(deltaX, deltaZ);

        return new NavigationVectorSummary(
            Mode: "navigation-current-read",
            ProcessId: processId,
            ProcessName: processName,
            WaypointFile: waypointFile,
            DestinationWaypointId: destinationWaypoint.Id,
            DestinationWaypointLabel: destinationWaypoint.Label,
            AnchorSource: anchorSource,
            CurrentAddressHex: currentSample.AddressHex,
            CurrentPosition: new NavigationCoordinate(currentSample.X, currentSample.Y, currentSample.Z),
            DestinationPosition: destinationWaypoint.Coordinate,
            DeltaX: deltaX,
            DeltaY: deltaY,
            DeltaZ: deltaZ,
            PlanarDistance: planarDistance,
            HeightDelta: deltaY,
            WorldBearingRadians: bearingRadians,
            WorldBearingDegrees: bearingDegrees,
            ArrivalRadius: arrivalRadius,
            WithinArrivalRadius: planarDistance <= arrivalRadius,
            Facing: facing);
    }

    public static NavigationFacingSummary BuildFacingSummary(
        NavigationFacingSample sample,
        double targetDeltaX,
        double targetDeltaZ)
    {
        ArgumentNullException.ThrowIfNull(sample);

        var signedTurnErrorRadians = ComputePlanarDistance(targetDeltaX, targetDeltaZ) <= double.Epsilon
            ? 0d
            : ActorFacingMath.ComputeSignedTurnErrorRadians(
                sample.YawRadians,
                targetDeltaX,
                targetDeltaZ);

        return new NavigationFacingSummary(
            SourceName: sample.SourceName,
            SourceAddressHex: sample.SourceAddressHex,
            BasisForwardOffset: sample.BasisForwardOffset,
            ActorYawRadians: sample.YawRadians,
            ActorYawDegrees: sample.YawDegrees,
            SignedTurnErrorRadians: signedTurnErrorRadians,
            SignedTurnErrorDegrees: ActorFacingMath.DegreesFromRadians(signedTurnErrorRadians),
            CoordValidated: sample.CoordValidated,
            IntegrityPass: sample.IntegrityPass,
            IntegrityNotes: sample.IntegrityNotes);
    }
}
