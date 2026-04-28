namespace RiftReader.Reader.Navigation;

public sealed record NavigationRoutePlanResult(
    string Mode,
    int ProcessId,
    string ProcessName,
    string WaypointFile,
    string Status,
    string StartWaypointId,
    string DestinationWaypointId,
    IReadOnlyList<string> WaypointIds,
    int SegmentCount,
    double TotalPlanarDistance,
    IReadOnlyList<NavigationRouteSegmentPlan> Segments,
    IReadOnlyList<string> Issues);

public sealed record NavigationRouteSegmentPlan(
    int SegmentIndex,
    string StartWaypointId,
    string DestinationWaypointId,
    string Pace,
    double ArrivalRadius,
    NavigationCoordinate StartPosition,
    NavigationCoordinate DestinationPosition,
    double PlanarDistance,
    double HeightDelta,
    double BearingRadians,
    double BearingDegrees);

