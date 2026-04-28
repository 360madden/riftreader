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

        if (result.Facing is not null)
        {
            lines.Add($"Facing status:        {result.Facing.Status}");

            if (!string.IsNullOrWhiteSpace(result.Facing.SourceKind))
            {
                lines.Add($"Facing source kind:   {result.Facing.SourceKind}");
            }

            if (!string.IsNullOrWhiteSpace(result.Facing.ResolutionMode))
            {
                lines.Add($"Facing mode:          {result.Facing.ResolutionMode}");
            }

            if (!string.IsNullOrWhiteSpace(result.Facing.SelectedSourceAddress) ||
                !string.IsNullOrWhiteSpace(result.Facing.BasisPrimaryForwardOffset))
            {
                lines.Add($"Facing source/basis:  {result.Facing.SelectedSourceAddress ?? "n/a"} / {result.Facing.BasisPrimaryForwardOffset ?? "n/a"}");
            }

            if (result.Facing.YawDegrees.HasValue || result.Facing.PitchDegrees.HasValue)
            {
                lines.Add($"Facing yaw/pitch:     {FormatNullableDouble(result.Facing.YawDegrees)} / {FormatNullableDouble(result.Facing.PitchDegrees)}");
            }

            if (result.Facing.SignedBearingDeltaDegrees.HasValue || result.Facing.AbsoluteBearingDeltaDegrees.HasValue)
            {
                lines.Add($"Heading delta:        {FormatNullableDouble(result.Facing.SignedBearingDeltaDegrees)} signed / {FormatNullableDouble(result.Facing.AbsoluteBearingDeltaDegrees)} abs ({result.Facing.SuggestedTurnDirection ?? "n/a"})");
            }

            if (!string.IsNullOrWhiteSpace(result.Facing.Reason))
            {
                lines.Add($"Facing note:          {result.Facing.Reason}");
            }
        }

        return string.Join(Environment.NewLine, lines);
    }

    private static string FormatBool(bool value) => value ? "yes" : "no";

    private static string FormatNullableDouble(double? value) =>
        value.HasValue
            ? FormatDouble(value.Value)
            : "n/a";

    private static string FormatDouble(double value) =>
        value.ToString("0.00000", CultureInfo.InvariantCulture);
}
