using RiftReader.Reader.Models;

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

    public static double NormalizeDegrees(double degrees)
    {
        var normalized = degrees;
        while (normalized > 180d)
        {
            normalized -= 360d;
        }

        while (normalized <= -180d)
        {
            normalized += 360d;
        }

        return normalized;
    }

    public static NavigationFacingSummary BuildUnavailableFacingSummary(string status, string? message) =>
        new(
            Status: status,
            SourceKind: "behavior-backed-memory-facing",
            ResolutionMode: null,
            SelectedSourceAddress: null,
            BasisPrimaryForwardOffset: null,
            BasisDuplicateForwardOffset: null,
            YawRadians: null,
            YawDegrees: null,
            PitchRadians: null,
            PitchDegrees: null,
            SignedBearingDeltaDegrees: null,
            AbsoluteBearingDeltaDegrees: null,
            SuggestedTurnDirection: null,
            Reason: string.IsNullOrWhiteSpace(message) ? null : message);

    public static NavigationTurnPlan BuildUnavailableTurnPlan(
        double destinationBearingDegrees,
        double alignmentThresholdDegrees,
        string? reason) =>
        new(
            Status: "unavailable",
            SourceKind: "behavior-backed-memory-facing",
            ResolutionMode: null,
            SelectedSourceAddress: null,
            BasisPrimaryForwardOffset: null,
            DestinationBearingDegrees: destinationBearingDegrees,
            CurrentYawDegrees: null,
            SignedBearingDeltaDegrees: null,
            AbsoluteBearingDeltaDegrees: null,
            SuggestedTurnDirection: null,
            AlignmentThresholdDegrees: alignmentThresholdDegrees,
            WithinAlignmentThreshold: false,
            Reason: string.IsNullOrWhiteSpace(reason) ? null : reason);

    public static NavigationFacingSummary BuildFacingSummary(
        PlayerOrientationReadResult orientation,
        double destinationBearingDegrees)
    {
        ArgumentNullException.ThrowIfNull(orientation);

        var yawDegrees = orientation.PreferredEstimate?.YawDegrees;
        var pitchDegrees = orientation.PreferredEstimate?.PitchDegrees;
        if (!yawDegrees.HasValue)
        {
            return BuildUnavailableFacingSummary(
                status: "estimate-unavailable",
                message: "Actor-facing read did not return a usable yaw estimate for navigation alignment.");
        }

        var signedDelta = NormalizeDegrees(destinationBearingDegrees - yawDegrees.Value);
        var absoluteDelta = Math.Abs(signedDelta);
        var direction = absoluteDelta <= 0.0001d
            ? "aligned"
            : signedDelta > 0d
                ? "left"
                : "right";

        return new NavigationFacingSummary(
            Status: "available",
            SourceKind: "behavior-backed-memory-facing",
            ResolutionMode: orientation.ResolutionMode,
            SelectedSourceAddress: orientation.SelectedSourceAddress,
            BasisPrimaryForwardOffset: orientation.BasisPrimaryForwardOffset,
            BasisDuplicateForwardOffset: orientation.BasisDuplicateForwardOffset,
            YawRadians: orientation.PreferredEstimate?.YawRadians,
            YawDegrees: yawDegrees,
            PitchRadians: orientation.PreferredEstimate?.PitchRadians,
            PitchDegrees: pitchDegrees,
            SignedBearingDeltaDegrees: signedDelta,
            AbsoluteBearingDeltaDegrees: absoluteDelta,
            SuggestedTurnDirection: direction,
            Reason: null);
    }

    public static NavigationTurnPlan BuildTurnPlan(
        NavigationFacingSummary? facing,
        double destinationBearingDegrees,
        double alignmentThresholdDegrees)
    {
        if (alignmentThresholdDegrees < 0d)
        {
            throw new ArgumentOutOfRangeException(nameof(alignmentThresholdDegrees), "Alignment threshold cannot be negative.");
        }

        if (facing is null)
        {
            return BuildUnavailableTurnPlan(
                destinationBearingDegrees,
                alignmentThresholdDegrees,
                "Actor-facing truth was unavailable for navigation turn planning.");
        }

        if (!string.Equals(facing.Status, "available", StringComparison.OrdinalIgnoreCase) ||
            !facing.YawDegrees.HasValue ||
            !facing.SignedBearingDeltaDegrees.HasValue ||
            !facing.AbsoluteBearingDeltaDegrees.HasValue)
        {
            return new NavigationTurnPlan(
                Status: "unavailable",
                SourceKind: facing.SourceKind,
                ResolutionMode: facing.ResolutionMode,
                SelectedSourceAddress: facing.SelectedSourceAddress,
                BasisPrimaryForwardOffset: facing.BasisPrimaryForwardOffset,
                DestinationBearingDegrees: destinationBearingDegrees,
                CurrentYawDegrees: facing.YawDegrees,
                SignedBearingDeltaDegrees: facing.SignedBearingDeltaDegrees,
                AbsoluteBearingDeltaDegrees: facing.AbsoluteBearingDeltaDegrees,
                SuggestedTurnDirection: null,
                AlignmentThresholdDegrees: alignmentThresholdDegrees,
                WithinAlignmentThreshold: false,
                Reason: facing.Reason ?? "Actor-facing truth did not provide enough data to build a turn plan.");
        }

        var withinAlignmentThreshold =
            facing.AbsoluteBearingDeltaDegrees.Value <= alignmentThresholdDegrees ||
            string.Equals(facing.SuggestedTurnDirection, "aligned", StringComparison.OrdinalIgnoreCase);
        var suggestedTurnDirection = withinAlignmentThreshold
            ? "aligned"
            : facing.SuggestedTurnDirection;

        return new NavigationTurnPlan(
            Status: withinAlignmentThreshold ? "aligned" : "available",
            SourceKind: facing.SourceKind,
            ResolutionMode: facing.ResolutionMode,
            SelectedSourceAddress: facing.SelectedSourceAddress,
            BasisPrimaryForwardOffset: facing.BasisPrimaryForwardOffset,
            DestinationBearingDegrees: destinationBearingDegrees,
            CurrentYawDegrees: facing.YawDegrees,
            SignedBearingDeltaDegrees: facing.SignedBearingDeltaDegrees,
            AbsoluteBearingDeltaDegrees: facing.AbsoluteBearingDeltaDegrees,
            SuggestedTurnDirection: suggestedTurnDirection,
            AlignmentThresholdDegrees: alignmentThresholdDegrees,
            WithinAlignmentThreshold: withinAlignmentThreshold,
            Reason: facing.Reason);
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
}
