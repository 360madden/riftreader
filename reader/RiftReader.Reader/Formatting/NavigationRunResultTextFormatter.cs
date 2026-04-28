using System.Globalization;
using RiftReader.Reader.Navigation;

namespace RiftReader.Reader.Formatting;

public static class NavigationRunResultTextFormatter
{
    public static string Format(NavigationRunResult result, bool includeEventTimeline = false)
    {
        var lines = new List<string>
        {
            $"Process:              {result.ProcessName} ({result.ProcessId})",
            $"Waypoint file:        {result.WaypointFile}",
            $"Status:               {result.Status}",
            $"Stop reason:          {result.StopReason}",
            $"Start waypoint:       {result.StartWaypointId}",
            $"Destination waypoint: {result.DestinationWaypointId}",
            $"Pace:                 {result.Pace}",
            $"Anchor source:        {result.AnchorSource}",
            $"Start radius:         {FormatDouble(result.StartRadius)}",
            $"Arrival radius:       {FormatDouble(result.ArrivalRadius)}",
            $"Initial planar dist:  {FormatDouble(result.InitialPlanarDistance)}",
            $"Final planar dist:    {FormatDouble(result.FinalPlanarDistance)}",
            $"Pulse count:          {result.PulseCount}",
            $"Elapsed ms:           {result.ElapsedMilliseconds}",
            $"Initial coords:       {FormatCoord(result.InitialPosition)}",
            $"Final coords:         {FormatCoord(result.FinalPosition)}",
            $"Destination coords:   {FormatCoord(result.DestinationPosition)}"
        };

        if (result.TurnResult is not null)
        {
            lines.Add($"Turn status:          {result.TurnResult.Status}");
            lines.Add($"Turn attempted:       {result.TurnResult.Attempted}");
            lines.Add($"Turn pulses:          {result.TurnResult.PulseCount}");
            lines.Add($"Turn threshold:       {FormatDouble(result.TurnResult.ThresholdDegrees)}");

            if (result.TurnResult.InitialPlan.AbsoluteBearingDeltaDegrees.HasValue ||
                result.TurnResult.FinalPlan.AbsoluteBearingDeltaDegrees.HasValue)
            {
                lines.Add($"Turn delta (i/f):     {FormatNullableDouble(result.TurnResult.InitialPlan.AbsoluteBearingDeltaDegrees)} / {FormatNullableDouble(result.TurnResult.FinalPlan.AbsoluteBearingDeltaDegrees)}");
            }

            if (!string.IsNullOrWhiteSpace(result.TurnResult.TurnDirection) ||
                !string.IsNullOrWhiteSpace(result.TurnResult.TurnKey))
            {
                lines.Add($"Turn direction/key:   {result.TurnResult.TurnDirection ?? "n/a"} / {result.TurnResult.TurnKey ?? "n/a"}");
            }

            if (!string.IsNullOrWhiteSpace(result.TurnResult.Reason))
            {
                lines.Add($"Turn note:            {result.TurnResult.Reason}");
            }

            if (result.TurnResult.Events is { Count: > 0 } turnEvents)
            {
                lines.Add($"Turn event count:     {turnEvents.Count}");
                lines.Add($"Turn last event:      {FormatEvent(turnEvents[^1])}");

                if (includeEventTimeline)
                {
                    lines.Add("Turn events:");

                    foreach (var turnEvent in turnEvents)
                    {
                        lines.Add($"  - {FormatEvent(turnEvent)}");
                    }
                }
            }
        }

        if (result.Events is { Count: > 0 } events)
        {
            lines.Add($"Event count:          {events.Count}");
            lines.Add($"Last event:           {FormatEvent(events[^1])}");

            if (includeEventTimeline)
            {
                lines.Add("Events:");

                foreach (var navigationEvent in events)
                {
                    lines.Add($"  - {FormatEvent(navigationEvent)}");
                }
            }
        }

        return string.Join(Environment.NewLine, lines);
    }

    private static string FormatEvent(NavigationEvent navigationEvent)
    {
        var parts = new List<string>
        {
            $"t={navigationEvent.ElapsedMilliseconds}ms",
            $"{navigationEvent.Stage}/{navigationEvent.Type}"
        };

        if (!string.IsNullOrWhiteSpace(navigationEvent.Status))
        {
            parts.Add($"[{navigationEvent.Status}]");
        }

        if (navigationEvent.PulseIndex.HasValue)
        {
            parts.Add($"pulse={navigationEvent.PulseIndex.Value}");
        }

        if (!string.IsNullOrWhiteSpace(navigationEvent.Key))
        {
            parts.Add($"key={navigationEvent.Key}");
        }

        if (navigationEvent.PlanarDistance.HasValue)
        {
            parts.Add($"dist={FormatDouble(navigationEvent.PlanarDistance.Value)}");
        }

        if (navigationEvent.AbsoluteBearingDeltaDegrees.HasValue)
        {
            parts.Add($"delta={FormatDouble(navigationEvent.AbsoluteBearingDeltaDegrees.Value)}");
        }

        if (navigationEvent.Position is not null)
        {
            parts.Add($"pos={FormatCoord(navigationEvent.Position)}");
        }

        if (!string.IsNullOrWhiteSpace(navigationEvent.Detail))
        {
            parts.Add($"note={navigationEvent.Detail}");
        }

        return string.Join(" ", parts);
    }

    private static string FormatCoord(NavigationCoordinate coordinate) =>
        $"{FormatDouble(coordinate.X)}, {FormatDouble(coordinate.Y)}, {FormatDouble(coordinate.Z)}";

    private static string FormatDouble(double value) =>
        value.ToString("0.00000", CultureInfo.InvariantCulture);

    private static string FormatNullableDouble(double? value) =>
        value.HasValue
            ? value.Value.ToString("0.00000", CultureInfo.InvariantCulture)
            : "n/a";
}
