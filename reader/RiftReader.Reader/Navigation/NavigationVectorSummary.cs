namespace RiftReader.Reader.Navigation;

public sealed record NavigationVectorSummary(
    string Mode,
    int ProcessId,
    string ProcessName,
    string WaypointFile,
    string DestinationWaypointId,
    string DestinationWaypointLabel,
    string AnchorSource,
    string CurrentAddressHex,
    NavigationCoordinate CurrentPosition,
    NavigationCoordinate DestinationPosition,
    double DeltaX,
    double DeltaY,
    double DeltaZ,
    double PlanarDistance,
    double HeightDelta,
    double WorldBearingRadians,
    double WorldBearingDegrees,
    double ArrivalRadius,
    bool WithinArrivalRadius,
    NavigationFacingSummary? Facing);
