namespace RiftReader.Reader.Navigation;

public sealed record WaypointCaptureResult(
    string Mode,
    int ProcessId,
    string ProcessName,
    string WaypointFile,
    string Status,
    string WaypointId,
    string WaypointLabel,
    string? WaypointZone,
    string? Pace,
    double? ArrivalRadius,
    string AnchorSource,
    string AnchorAddress,
    NavigationCoordinate Position);
