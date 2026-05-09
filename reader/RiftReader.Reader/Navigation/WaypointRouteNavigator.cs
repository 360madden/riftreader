namespace RiftReader.Reader.Navigation;

public static class WaypointRouteNavigator
{
    public static NavigationRouteRunResult Run(
        int processId,
        string processName,
        string waypointFile,
        WaypointMovementSettings movement,
        IReadOnlyList<WaypointDefinition> routeWaypoints,
        INavigationPoseSource poseSource,
        IMovementBackend movementBackend,
        Func<NavigationRouteSegmentTurnRequest, NavigationTurnResult>? turnBeforeSegment = null)
    {
        ArgumentNullException.ThrowIfNull(movement);
        ArgumentNullException.ThrowIfNull(routeWaypoints);
        ArgumentNullException.ThrowIfNull(poseSource);
        ArgumentNullException.ThrowIfNull(movementBackend);

        var plan = WaypointRoutePlanner.BuildPlan(
            processId,
            processName,
            waypointFile,
            movement,
            routeWaypoints);

        if (!string.Equals(plan.Status, "success", StringComparison.OrdinalIgnoreCase))
        {
            return BuildResult(
                plan,
                routeWaypoints,
                poseSource.AnchorSource,
                status: "failure",
                stopReason: "route-plan-invalid",
                failedSegmentIndex: null,
                segmentResults: Array.Empty<NavigationRunResult>(),
                issues: plan.Issues);
        }

        var segmentResults = new List<NavigationRunResult>(plan.SegmentCount);
        var issues = new List<string>();

        for (var index = 0; index < routeWaypoints.Count - 1; index++)
        {
            var startWaypoint = routeWaypoints[index];
            var destinationWaypoint = routeWaypoints[index + 1];
            var segmentIndex = index + 1;
            var segmentMovement = index == 0
                ? movement
                : movement with
                {
                    StartRadius = Math.Max(
                        movement.StartRadius,
                        startWaypoint.ArrivalRadius ?? movement.DefaultArrivalRadius)
                };
            var pace = destinationWaypoint.Pace ?? movement.DefaultPace;
            var arrivalRadius = destinationWaypoint.ArrivalRadius ?? movement.DefaultArrivalRadius;
            NavigationTurnResult? turnResult = null;

            if (turnBeforeSegment is not null)
            {
                if (!poseSource.TryReadCurrent(out var turnSample, out var turnPoseError))
                {
                    var telemetryFailure = BuildSegmentFailure(
                        processId,
                        processName,
                        waypointFile,
                        segmentMovement,
                        startWaypoint,
                        destinationWaypoint,
                        pace,
                        arrivalRadius,
                        poseSource.AnchorSource,
                        stopReason: "telemetry-lost",
                        position: startWaypoint.Coordinate,
                        detail: turnPoseError ?? "Navigation pose sample was unavailable before route segment auto-turn.",
                        turnResult: null);
                    segmentResults.Add(telemetryFailure);
                    issues.Add($"Route segment {segmentIndex} failed with stop reason '{telemetryFailure.StopReason}'.");
                    return BuildResult(
                        plan,
                        routeWaypoints,
                        poseSource.AnchorSource,
                        status: "failure",
                        stopReason: telemetryFailure.StopReason,
                        failedSegmentIndex: segmentIndex,
                        segmentResults: segmentResults,
                        issues: issues);
                }

                turnResult = turnBeforeSegment(new NavigationRouteSegmentTurnRequest(
                    SegmentIndex: segmentIndex,
                    StartWaypoint: startWaypoint,
                    DestinationWaypoint: destinationWaypoint,
                    CurrentSample: turnSample));

                if (!turnResult.Succeeded)
                {
                    var turnFailure = BuildSegmentFailure(
                        processId,
                        processName,
                        waypointFile,
                        segmentMovement,
                        startWaypoint,
                        destinationWaypoint,
                        pace,
                        arrivalRadius,
                        poseSource.AnchorSource,
                        stopReason: $"auto-turn-{turnResult.Status}",
                        position: turnResult.FinalPosition,
                        detail: turnResult.Reason ?? "Auto-turn failed before route segment movement could start.",
                        turnResult: turnResult,
                        movementBackend: movementBackend.BackendKind,
                        initialSample: turnSample);
                    segmentResults.Add(turnFailure);
                    issues.Add($"Route segment {segmentIndex} failed with stop reason '{turnFailure.StopReason}'.");
                    return BuildResult(
                        plan,
                        routeWaypoints,
                        poseSource.AnchorSource,
                        status: "failure",
                        stopReason: turnFailure.StopReason,
                        failedSegmentIndex: segmentIndex,
                        segmentResults: segmentResults,
                        issues: issues);
                }
            }

            var segmentResult = WaypointNavigator.Run(
                processId,
                processName,
                waypointFile,
                segmentMovement,
                startWaypoint,
                destinationWaypoint,
                poseSource,
                movementBackend,
                pace,
                arrivalRadius,
                movement.MaxTravelSeconds);
            if (turnResult is not null)
            {
                segmentResult = segmentResult with { TurnResult = turnResult };
            }

            segmentResults.Add(segmentResult);

            if (!string.Equals(segmentResult.Status, "success", StringComparison.OrdinalIgnoreCase))
            {
                issues.Add($"Route segment {segmentIndex} failed with stop reason '{segmentResult.StopReason}'.");
                return BuildResult(
                    plan,
                    routeWaypoints,
                    poseSource.AnchorSource,
                    status: "failure",
                    stopReason: segmentResult.StopReason,
                    failedSegmentIndex: segmentIndex,
                    segmentResults: segmentResults,
                    issues: issues);
            }
        }

        return BuildResult(
            plan,
            routeWaypoints,
            poseSource.AnchorSource,
            status: "success",
            stopReason: "arrived",
            failedSegmentIndex: null,
            segmentResults: segmentResults,
            issues: issues);
    }

    private static NavigationRouteRunResult BuildResult(
        NavigationRoutePlanResult plan,
        IReadOnlyList<WaypointDefinition> routeWaypoints,
        string anchorSource,
        string status,
        string stopReason,
        int? failedSegmentIndex,
        IReadOnlyList<NavigationRunResult> segmentResults,
        IReadOnlyList<string> issues)
    {
        var firstSegment = segmentResults.FirstOrDefault();
        var lastSegment = segmentResults.LastOrDefault();
        var completedSegmentCount = segmentResults.Count(static segment =>
            string.Equals(segment.Status, "success", StringComparison.OrdinalIgnoreCase));
        var finalDestination = routeWaypoints.Count > 0
            ? routeWaypoints[^1].Coordinate
            : (NavigationCoordinate?)null;

        return new NavigationRouteRunResult(
            Mode: "navigate-waypoint-route",
            ProcessId: plan.ProcessId,
            ProcessName: plan.ProcessName,
            WaypointFile: plan.WaypointFile,
            Status: status,
            StartWaypointId: plan.StartWaypointId,
            DestinationWaypointId: plan.DestinationWaypointId,
            WaypointIds: plan.WaypointIds,
            SegmentCount: plan.SegmentCount,
            CompletedSegmentCount: completedSegmentCount,
            FailedSegmentIndex: failedSegmentIndex,
            StopReason: stopReason,
            AnchorSource: anchorSource,
            TotalPlanarDistance: plan.TotalPlanarDistance,
            FinalPlanarDistance: ComputeFinalPlanarDistance(lastSegment?.FinalPosition, finalDestination),
            TotalPulseCount: segmentResults.Sum(static segment => segment.PulseCount),
            InitialPosition: firstSegment?.InitialPosition,
            FinalPosition: lastSegment?.FinalPosition,
            DestinationPosition: finalDestination,
            ElapsedMilliseconds: segmentResults.Sum(static segment => segment.ElapsedMilliseconds),
            SegmentResults: segmentResults.ToArray(),
            Issues: issues.ToArray(),
            MovementBackend: firstSegment?.MovementBackend ?? MovementBackendKinds.NotCreated);
    }

    private static double ComputeFinalPlanarDistance(
        NavigationCoordinate? finalPosition,
        NavigationCoordinate? finalDestination)
    {
        if (finalPosition is null || finalDestination is null)
        {
            return 0d;
        }

        return NavigationMath.ComputePlanarDistance(
            finalDestination.X - finalPosition.X,
            finalDestination.Z - finalPosition.Z);
    }

    private static NavigationRunResult BuildSegmentFailure(
        int processId,
        string processName,
        string waypointFile,
        WaypointMovementSettings movement,
        WaypointDefinition startWaypoint,
        WaypointDefinition destinationWaypoint,
        string pace,
        double arrivalRadius,
        string anchorSource,
        string stopReason,
        NavigationCoordinate position,
        string detail,
        NavigationTurnResult? turnResult,
        string movementBackend = MovementBackendKinds.NotCreated,
        NavigationPoseSample? initialSample = null)
    {
        var initialPosition = initialSample is null
            ? position
            : new NavigationCoordinate(initialSample.X, initialSample.Y, initialSample.Z);
        var initialPlanarDistance = ComputePlanarDistance(initialPosition, destinationWaypoint);
        var finalPlanarDistance = ComputePlanarDistance(position, destinationWaypoint);
        var events = new[]
        {
            new NavigationEvent(
                Stage: "navigation",
                Type: "stop",
                ElapsedMilliseconds: 0,
                Status: stopReason,
                PulseIndex: turnResult?.PulseCount,
                Position: position,
                PlanarDistance: finalPlanarDistance,
                Detail: detail)
        };

        return new NavigationRunResult(
            Mode: "navigate-waypoints",
            ProcessId: processId,
            ProcessName: processName,
            WaypointFile: waypointFile,
            Status: "failure",
            StartWaypointId: startWaypoint.Id,
            DestinationWaypointId: destinationWaypoint.Id,
            Pace: pace,
            AnchorSource: anchorSource,
            StartRadius: movement.StartRadius,
            ArrivalRadius: arrivalRadius,
            InitialPlanarDistance: initialPlanarDistance,
            FinalPlanarDistance: finalPlanarDistance,
            PulseCount: 0,
            StopReason: stopReason,
            InitialPosition: initialPosition,
            FinalPosition: position,
            DestinationPosition: destinationWaypoint.Coordinate,
            ElapsedMilliseconds: 0,
            MovementBackend: movementBackend,
            TurnResult: turnResult,
            Events: events);
    }

    private static double ComputePlanarDistance(
        NavigationCoordinate currentPosition,
        WaypointDefinition destinationWaypoint) =>
        NavigationMath.ComputePlanarDistance(
            destinationWaypoint.X - currentPosition.X,
            destinationWaypoint.Z - currentPosition.Z);
}
