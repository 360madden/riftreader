using System.Text.Json.Serialization;

namespace RiftReader.Reader.Navigation;

public sealed record NavigationWaypointFileDocument(
    int? SchemaVersion,
    NavigationMovementOptionsDocument? Movement,
    IReadOnlyList<NavigationWaypointDocument>? Waypoints);

public sealed record NavigationMovementOptionsDocument(
    string? ForwardKey,
    string? RunKey,
    string? WalkKey,
    string? DefaultPace,
    int? ForwardPulseMilliseconds,
    int? PostPulseSampleDelayMilliseconds,
    double? StartRadius,
    double? DefaultArrivalRadius,
    int? NoProgressWindowMilliseconds,
    double? MinimumProgressDistance,
    double? WrongWayToleranceDistance,
    int? MaxTravelSeconds);

public sealed record NavigationWaypointDocument(
    string? Id,
    string? Label,
    string? Zone,
    double? X,
    double? Y,
    double? Z,
    double? ArrivalRadius,
    string? Pace);

public sealed record WaypointNavigationConfiguration(
    string SourceFile,
    int SchemaVersion,
    WaypointMovementSettings Movement,
    IReadOnlyDictionary<string, WaypointDefinition> Waypoints);

public sealed record WaypointMovementSettings(
    string ForwardKey,
    string? RunKey,
    string? WalkKey,
    string DefaultPace,
    int ForwardPulseMilliseconds,
    int PostPulseSampleDelayMilliseconds,
    double StartRadius,
    double DefaultArrivalRadius,
    int NoProgressWindowMilliseconds,
    double MinimumProgressDistance,
    double WrongWayToleranceDistance,
    int MaxTravelSeconds);

public sealed record WaypointDefinition(
    string Id,
    string Label,
    string? Zone,
    double X,
    double Y,
    double Z,
    double? ArrivalRadius,
    string? Pace)
{
    [JsonIgnore]
    public NavigationCoordinate Coordinate => new(X, Y, Z);
}
