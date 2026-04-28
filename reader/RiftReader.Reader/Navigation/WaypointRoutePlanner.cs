namespace RiftReader.Reader.Navigation;

public static class WaypointRoutePlanner
{
    public static NavigationRoutePlanResult BuildPlan(
        int processId,
        string processName,
        string waypointFile,
        WaypointMovementSettings movement,
        IReadOnlyList<WaypointDefinition> routeWaypoints)
    {
        ArgumentNullException.ThrowIfNull(movement);
        ArgumentNullException.ThrowIfNull(routeWaypoints);

        var issues = new List<string>();
        var segments = new List<NavigationRouteSegmentPlan>();
        var waypointIds = routeWaypoints
            .Where(static waypoint => waypoint is not null)
            .Select(static waypoint => waypoint.Id)
            .ToArray();

        if (routeWaypoints.Count < 2)
        {
            issues.Add("Navigation route planning requires at least a start and destination waypoint.");
        }

        for (var index = 0; index < routeWaypoints.Count - 1; index++)
        {
            var start = routeWaypoints[index];
            var destination = routeWaypoints[index + 1];
            var segmentIndex = index + 1;

            if (string.Equals(start.Id, destination.Id, StringComparison.OrdinalIgnoreCase))
            {
                issues.Add($"Route segment {segmentIndex} repeats waypoint '{start.Id}'.");
            }

            if (!string.IsNullOrWhiteSpace(start.Zone) &&
                !string.IsNullOrWhiteSpace(destination.Zone) &&
                !string.Equals(start.Zone, destination.Zone, StringComparison.OrdinalIgnoreCase))
            {
                issues.Add($"Route segment {segmentIndex} crosses zones from '{start.Zone}' to '{destination.Zone}'.");
            }

            var deltaX = destination.X - start.X;
            var deltaY = destination.Y - start.Y;
            var deltaZ = destination.Z - start.Z;
            var planarDistance = NavigationMath.ComputePlanarDistance(deltaX, deltaZ);
            if (planarDistance <= 0.0001d)
            {
                issues.Add($"Route segment {segmentIndex} has no planar distance.");
            }

            var (bearingRadians, bearingDegrees) = NavigationMath.ComputeBearing(deltaX, deltaZ);
            var pace = destination.Pace ?? movement.DefaultPace;
            var arrivalRadius = destination.ArrivalRadius ?? movement.DefaultArrivalRadius;
            segments.Add(new NavigationRouteSegmentPlan(
                SegmentIndex: segmentIndex,
                StartWaypointId: start.Id,
                DestinationWaypointId: destination.Id,
                Pace: pace,
                ArrivalRadius: arrivalRadius,
                StartPosition: start.Coordinate,
                DestinationPosition: destination.Coordinate,
                PlanarDistance: planarDistance,
                HeightDelta: deltaY,
                BearingRadians: bearingRadians,
                BearingDegrees: bearingDegrees));
        }

        var status = issues.Count == 0 ? "success" : "failure";
        return new NavigationRoutePlanResult(
            Mode: "navigation-route-plan",
            ProcessId: processId,
            ProcessName: processName,
            WaypointFile: waypointFile,
            Status: status,
            StartWaypointId: waypointIds.FirstOrDefault() ?? string.Empty,
            DestinationWaypointId: waypointIds.LastOrDefault() ?? string.Empty,
            WaypointIds: waypointIds,
            SegmentCount: segments.Count,
            TotalPlanarDistance: segments.Sum(static segment => segment.PlanarDistance),
            Segments: segments,
            Issues: issues);
    }
}

