using System.Globalization;
using RiftReader.Reader.Navigation;

namespace RiftReader.Reader.Formatting;

public static class NavigationVectorSummaryTextFormatter
{
    public static string Format(NavigationVectorSummary result)
    {
        var lines = new List<string>
        {
            $"Process:              {result.ProcessName} ({result.ProcessId})",
            $"Waypoint file:        {result.WaypointFile}",
            $"Destination waypoint: {result.DestinationWaypointId} ({result.DestinationWaypointLabel})",
            $"Anchor source:        {result.AnchorSource}",
            $"Current sample:       {result.CurrentAddressHex}",
            $"Current coords:       {FormatDouble(result.CurrentPosition.X)}, {FormatDouble(result.CurrentPosition.Y)}, {FormatDouble(result.CurrentPosition.Z)}",
            $"Destination coords:   {FormatDouble(result.DestinationPosition.X)}, {FormatDouble(result.DestinationPosition.Y)}, {FormatDouble(result.DestinationPosition.Z)}",
            $"Deltas:               {FormatDouble(result.DeltaX)}, {FormatDouble(result.DeltaY)}, {FormatDouble(result.DeltaZ)}",
            $"Planar distance:      {FormatDouble(result.PlanarDistance)}",
            $"Height delta:         {FormatDouble(result.HeightDelta)}",
            $"Bearing (rad/deg):    {FormatDouble(result.WorldBearingRadians)} / {FormatDouble(result.WorldBearingDegrees)}",
            $"Arrival radius:       {FormatDouble(result.ArrivalRadius)}",
            $"Within arrival:       {FormatBool(result.WithinArrivalRadius)}"
        };

        return string.Join(Environment.NewLine, lines);
    }

    private static string FormatBool(bool value) => value ? "yes" : "no";

    private static string FormatDouble(double value) =>
        value.ToString("0.00000", CultureInfo.InvariantCulture);
}
