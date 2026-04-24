using System.Globalization;
using RiftReader.Reader.Navigation;

namespace RiftReader.Reader.Formatting;

public static class NavigationRoutePlanTextFormatter
{
    public static string Format(NavigationRoutePlanResult result)
    {
        var lines = new List<string>
        {
            $"Process:              {result.ProcessName} ({result.ProcessId})",
            $"Waypoint file:        {result.WaypointFile}",
            $"Status:               {result.Status}",
            $"Start waypoint:       {result.StartWaypointId}",
            $"Destination waypoint: {result.DestinationWaypointId}",
            $"Route:                {string.Join(" -> ", result.WaypointIds)}",
            $"Segment count:        {result.SegmentCount}",
            $"Total planar dist:    {FormatDouble(result.TotalPlanarDistance)}"
        };

        if (result.Issues.Count > 0)
        {
            lines.Add("Issues:");
            foreach (var issue in result.Issues)
            {
                lines.Add($"  - {issue}");
            }
        }

        if (result.Segments.Count > 0)
        {
            lines.Add("Segments:");
            foreach (var segment in result.Segments)
            {
                lines.Add(
                    $"  {segment.SegmentIndex}. {segment.StartWaypointId} -> {segment.DestinationWaypointId} " +
                    $"dist={FormatDouble(segment.PlanarDistance)} bearing={FormatDouble(segment.BearingDegrees)}° " +
                    $"arrival={FormatDouble(segment.ArrivalRadius)} pace={segment.Pace}");
            }
        }

        return string.Join(Environment.NewLine, lines);
    }

    private static string FormatDouble(double value) =>
        value.ToString("0.00000", CultureInfo.InvariantCulture);
}

