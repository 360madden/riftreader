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

        var yaw = TryComputeNavigationBearing(orientation.PreferredEstimate);
        var pitchDegrees = orientation.PreferredEstimate?.PitchDegrees;
        if (!yaw.HasValue)
        {
            return BuildUnavailableFacingSummary(
                status: "estimate-unavailable",
                message: "Actor-facing read did not return a usable forward-key movement bearing estimate for navigation alignment.");
        }

        var signedDelta = NormalizeDegrees(destinationBearingDegrees - yaw.Value.Degrees);
        var absoluteDelta = Math.Abs(signedDelta);
        var direction = absoluteDelta <= 0.0001d
            ? "aligned"
            : signedDelta > 0d
                ? "right"
                : "left";

        return new NavigationFacingSummary(
            Status: "available",
            SourceKind: "behavior-backed-memory-facing",
            ResolutionMode: orientation.ResolutionMode,
            SelectedSourceAddress: orientation.SelectedSourceAddress,
            BasisPrimaryForwardOffset: orientation.BasisPrimaryForwardOffset,
            BasisDuplicateForwardOffset: orientation.BasisDuplicateForwardOffset,
            YawRadians: yaw.Value.Radians,
            YawDegrees: yaw.Value.Degrees,
            PitchRadians: orientation.PreferredEstimate?.PitchRadians,
            PitchDegrees: pitchDegrees,
            SignedBearingDeltaDegrees: signedDelta,
            AbsoluteBearingDeltaDegrees: absoluteDelta,
            SuggestedTurnDirection: direction,
            Reason: null);
    }

    public static NavigationFacingSummary BuildCandidateFacingSummary(
        PlayerOrientationReadResult orientation,
        double destinationBearingDegrees,
        string status,
        string sourceKind,
        string? reason)
    {
        ArgumentNullException.ThrowIfNull(orientation);

        if (string.IsNullOrWhiteSpace(status))
        {
            throw new ArgumentException("Candidate facing status cannot be blank.", nameof(status));
        }

        if (string.IsNullOrWhiteSpace(sourceKind))
        {
            throw new ArgumentException("Candidate facing source kind cannot be blank.", nameof(sourceKind));
        }

        var yaw = TryComputeNavigationBearing(orientation.PreferredEstimate);
        if (!yaw.HasValue)
        {
            const string unusableEstimateReason = "Owner-components artifact candidate did not return a usable forward-key movement bearing estimate.";
            return new NavigationFacingSummary(
                Status: status,
                SourceKind: sourceKind,
                ResolutionMode: orientation.ResolutionMode,
                SelectedSourceAddress: orientation.SelectedSourceAddress,
                BasisPrimaryForwardOffset: orientation.BasisPrimaryForwardOffset,
                BasisDuplicateForwardOffset: orientation.BasisDuplicateForwardOffset,
                YawRadians: null,
                YawDegrees: null,
                PitchRadians: orientation.PreferredEstimate?.PitchRadians,
                PitchDegrees: orientation.PreferredEstimate?.PitchDegrees,
                SignedBearingDeltaDegrees: null,
                AbsoluteBearingDeltaDegrees: null,
                SuggestedTurnDirection: null,
                Reason: string.IsNullOrWhiteSpace(reason)
                    ? unusableEstimateReason
                    : $"{reason} {unusableEstimateReason}");
        }

        var signedDelta = NormalizeDegrees(destinationBearingDegrees - yaw.Value.Degrees);
        var absoluteDelta = Math.Abs(signedDelta);
        var direction = absoluteDelta <= 0.0001d
            ? "aligned"
            : signedDelta > 0d
                ? "right"
                : "left";

        return new NavigationFacingSummary(
            Status: status,
            SourceKind: sourceKind,
            ResolutionMode: orientation.ResolutionMode,
            SelectedSourceAddress: orientation.SelectedSourceAddress,
            BasisPrimaryForwardOffset: orientation.BasisPrimaryForwardOffset,
            BasisDuplicateForwardOffset: orientation.BasisDuplicateForwardOffset,
            YawRadians: yaw.Value.Radians,
            YawDegrees: yaw.Value.Degrees,
            PitchRadians: orientation.PreferredEstimate?.PitchRadians,
            PitchDegrees: orientation.PreferredEstimate?.PitchDegrees,
            SignedBearingDeltaDegrees: signedDelta,
            AbsoluteBearingDeltaDegrees: absoluteDelta,
            SuggestedTurnDirection: direction,
            Reason: string.IsNullOrWhiteSpace(reason) ? null : reason);
    }

    private static (double Radians, double Degrees)? TryComputeNavigationBearing(PlayerOrientationVectorEstimate? estimate)
    {
        var vector = estimate?.Vector;
        if (vector?.X is double vectorX &&
            vector.Z is double vectorZ &&
            IsFinite(vectorX) &&
            IsFinite(vectorZ) &&
            Math.Sqrt((vectorX * vectorX) + (vectorZ * vectorZ)) > double.Epsilon)
        {
            // Live W-key validation maps the actor-facing basis projection to the
            // opposite forward-key movement bearing in Rift's X/Z plane.
            var radians = Math.Atan2(-vectorX, -vectorZ);
            return (radians, NormalizeDegrees(radians * 180d / Math.PI));
        }

        if (estimate?.YawRadians is { } yawRadians && IsFinite(yawRadians))
        {
            var radians = NormalizeRadians((Math.PI / 2d) - yawRadians + Math.PI);
            return (radians, NormalizeDegrees(radians * 180d / Math.PI));
        }

        if (estimate?.YawDegrees is { } yawDegrees && IsFinite(yawDegrees))
        {
            var degrees = NormalizeDegrees(270d - yawDegrees);
            return (degrees * Math.PI / 180d, degrees);
        }

        return null;
    }

    private static double NormalizeRadians(double radians)
    {
        var normalized = radians;
        while (normalized > Math.PI)
        {
            normalized -= 2d * Math.PI;
        }

        while (normalized <= -Math.PI)
        {
            normalized += 2d * Math.PI;
        }

        return normalized;
    }

    private static bool IsFinite(double value) =>
        !double.IsNaN(value) && !double.IsInfinity(value);

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
