using System.Globalization;
using RiftReader.Reader.Navigation;

namespace RiftReader.Reader.Formatting;

public static class NavigationRunResultTextFormatter
{
    public static string Format(NavigationRunResult result)
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
            $"Turn pulse count:     {result.TurnPulseCount}",
            $"Elapsed ms:           {result.ElapsedMilliseconds}",
            $"Initial coords:       {FormatCoord(result.InitialPosition)}",
            $"Final coords:         {FormatCoord(result.FinalPosition)}",
            $"Destination coords:   {FormatCoord(result.DestinationPosition)}"
        };

        if (result.InitialFacing is not null)
        {
            lines.Add($"Initial facing:       {FormatFacing(result.InitialFacing)}");
        }

        if (result.FinalFacing is not null)
        {
            lines.Add($"Final facing:         {FormatFacing(result.FinalFacing)}");
        }

        return string.Join(Environment.NewLine, lines);
    }

    private static string FormatFacing(NavigationFacingSummary facing) =>
        $"{facing.SourceAddressHex} @ {facing.BasisForwardOffset} | yaw {FormatDouble(facing.ActorYawDegrees)} deg | turn {FormatDouble(facing.SignedTurnErrorDegrees)} deg | integrity {FormatBool(facing.IntegrityPass)} | coord {FormatNullableBool(facing.CoordValidated)}";

    private static string FormatCoord(NavigationCoordinate coordinate) =>
        $"{FormatDouble(coordinate.X)}, {FormatDouble(coordinate.Y)}, {FormatDouble(coordinate.Z)}";

    private static string FormatBool(bool value) => value ? "yes" : "no";

    private static string FormatNullableBool(bool? value) =>
        value.HasValue ? FormatBool(value.Value) : "n/a";

    private static string FormatDouble(double value) =>
        value.ToString("0.00000", CultureInfo.InvariantCulture);
}
