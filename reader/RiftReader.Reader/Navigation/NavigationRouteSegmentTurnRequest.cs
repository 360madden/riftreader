namespace RiftReader.Reader.Navigation;

public sealed record NavigationRouteSegmentTurnRequest(
    int SegmentIndex,
    WaypointDefinition StartWaypoint,
    WaypointDefinition DestinationWaypoint,
    NavigationPoseSample CurrentSample);
