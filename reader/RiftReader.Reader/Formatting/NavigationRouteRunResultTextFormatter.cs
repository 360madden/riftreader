using System.Globalization;
using RiftReader.Reader.Navigation;

namespace RiftReader.Reader.Formatting;

public static class NavigationRouteRunResultTextFormatter
{
    public static string Format(NavigationRouteRunResult result)
    {
        var lines = new List<string>
        {
            $"Process:              {result.ProcessName} ({result.ProcessId})",
            $"Waypoint file:        {result.WaypointFile}",
            $"Status:               {result.Status}",
            $"Stop reason:          {result.StopReason}",
            $"Start waypoint:       {result.StartWaypointId}",
            $"Destination waypoint: {result.DestinationWaypointId}",
            $"Route:                {string.Join(" -> ", result.WaypointIds)}",
            $"Anchor source:        {result.AnchorSource}",
            $"Segment count:        {result.SegmentCount}",
            $"Completed segments:   {result.CompletedSegmentCount}",
            $"Failed segment:       {FormatNullableInt(result.FailedSegmentIndex)}",
            $"Total planned dist:   {FormatDouble(result.TotalPlanarDistance)}",
            $"Final planar dist:    {FormatDouble(result.FinalPlanarDistance)}",
            $"Total pulses:         {result.TotalPulseCount}",
            $"Elapsed ms:           {result.ElapsedMilliseconds}",
            $"Initial coords:       {FormatCoord(result.InitialPosition)}",
            $"Final coords:         {FormatCoord(result.FinalPosition)}",
            $"Destination coords:   {FormatCoord(result.DestinationPosition)}"
        };

        if (result.Issues.Count > 0)
        {
            lines.Add("Issues:");
            foreach (var issue in result.Issues)
            {
                lines.Add($"  - {issue}");
            }
        }

        if (result.SegmentResults.Count > 0)
        {
            lines.Add("Segments:");
            for (var index = 0; index < result.SegmentResults.Count; index++)
            {
                var segment = result.SegmentResults[index];
                var turnStatus = segment.TurnResult is null
                    ? "n/a"
                    : segment.TurnResult.Status;
                lines.Add(
                    $"  {index + 1}. {segment.StartWaypointId} -> {segment.DestinationWaypointId} " +
                    $"status={segment.Status} reason={segment.StopReason} pace={segment.Pace} " +
                    $"turn={turnStatus} pulses={segment.PulseCount} finalDist={FormatDouble(segment.FinalPlanarDistance)}");
            }
        }

        return string.Join(Environment.NewLine, lines);
    }

    private static string FormatCoord(NavigationCoordinate? coordinate) =>
        coordinate is null
            ? "n/a"
            : $"{FormatDouble(coordinate.X)}, {FormatDouble(coordinate.Y)}, {FormatDouble(coordinate.Z)}";

    private static string FormatDouble(double value) =>
        value.ToString("0.00000", CultureInfo.InvariantCulture);

    private static string FormatNullableInt(int? value) =>
        value.HasValue
            ? value.Value.ToString(CultureInfo.InvariantCulture)
            : "n/a";
}
