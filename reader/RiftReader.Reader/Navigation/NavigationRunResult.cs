namespace RiftReader.Reader.Navigation;

public sealed record NavigationRunResult(
    string Mode,
    int ProcessId,
    string ProcessName,
    string WaypointFile,
    string Status,
    string StartWaypointId,
    string DestinationWaypointId,
    string Pace,
    string AnchorSource,
    double StartRadius,
    double ArrivalRadius,
    double InitialPlanarDistance,
    double FinalPlanarDistance,
    int PulseCount,
    string StopReason,
    NavigationCoordinate InitialPosition,
    NavigationCoordinate FinalPosition,
    NavigationCoordinate DestinationPosition,
    long ElapsedMilliseconds,
    NavigationTurnResult? TurnResult = null);
