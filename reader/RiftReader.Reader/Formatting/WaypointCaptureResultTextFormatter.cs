using System.Globalization;
using RiftReader.Reader.Navigation;

namespace RiftReader.Reader.Formatting;

public static class WaypointCaptureResultTextFormatter
{
    public static string Format(WaypointCaptureResult result)
    {
        var lines = new List<string>
        {
            $"Process:              {result.ProcessName} ({result.ProcessId})",
            $"Waypoint file:        {result.WaypointFile}",
            $"Status:               {result.Status}",
            $"Waypoint id:          {result.WaypointId}",
            $"Waypoint label:       {result.WaypointLabel}",
            $"Waypoint zone:        {result.WaypointZone ?? "n/a"}",
            $"Waypoint pace:        {result.Pace ?? "inherit"}",
            $"Arrival radius:       {(result.ArrivalRadius.HasValue ? FormatDouble(result.ArrivalRadius.Value) : "inherit")}",
            $"Anchor source:        {result.AnchorSource}",
            $"Anchor address:       {result.AnchorAddress}",
            $"Captured coords:      {FormatCoord(result.Position)}"
        };

        return string.Join(Environment.NewLine, lines);
    }

    private static string FormatCoord(NavigationCoordinate coordinate) =>
        $"{FormatDouble(coordinate.X)}, {FormatDouble(coordinate.Y)}, {FormatDouble(coordinate.Z)}";

    private static string FormatDouble(double value) =>
        value.ToString("0.00000", CultureInfo.InvariantCulture);
}
