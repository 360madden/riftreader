using System.Globalization;
using RiftReader.Reader.Models;

namespace RiftReader.Reader.Formatting;

public static class PlayerActorTruthReadTextFormatter
{
    public static string Format(PlayerActorTruthReadResult result)
    {
        var lines = new List<string>
        {
            $"Process:                 {result.ProcessName} ({result.ProcessId})",
            $"ReaderBridge source:     {result.ReaderBridgeSourceFile}",
            $"Trace source:            {result.TraceSourceFile ?? "n/a"}",
            $"Trace available:         {FormatBool(result.TraceAvailable)}",
            $"Trace matches process:   {FormatBool(result.TraceMatchesProcess)}",
            $"Coord bootstrap:         {result.CoordBootstrapSource}",
            $"Orientation source:      {result.OrientationResolutionSource}",
            $"Coord object:            {result.Coordinates.ObjectBaseAddress ?? "n/a"} @ {FormatOffset(result.Coordinates.CoordBaseRelativeOffset)}",
            $"Coords:                  {FormatFloat(result.Coordinates.Memory.CoordX)}, {FormatFloat(result.Coordinates.Memory.CoordY)}, {FormatFloat(result.Coordinates.Memory.CoordZ)}",
            $"Coord match:             {FormatBool(result.Coordinates.Match.CoordMatchesWithinTolerance)}",
            $"Orientation object:      {result.Orientation.SelectedAddress}",
            $"Forward basis:           {result.Orientation.BasisPrimaryForwardOffset}",
            $"Yaw / pitch (deg):       {FormatDouble(result.Orientation.PreferredEstimate.YawDegrees)} / {FormatDouble(result.Orientation.PreferredEstimate.PitchDegrees)}",
            $"Basis orthonormal:       {FormatBool(result.Orientation.Basis.IsOrthonormal)}"
        };

        if (result.BestContainerChain is not null)
        {
            lines.Add($"Best chain parent/root:  {result.BestContainerChain.ParentAddress ?? "n/a"} -> {result.BestContainerChain.RootAddress ?? "n/a"} ({result.BestContainerChain.RootObservationCount}/{result.BestContainerChain.StabilitySampleCount} root obs)");
        }

        if (result.BestRootFamily is not null)
        {
            lines.Add($"Best root family:        {result.BestRootFamily.RegionBase} ({result.BestRootFamily.ObservationCount}/{result.BestRootFamily.StabilitySampleCount}, distinct={result.BestRootFamily.DistinctAddressCount})");
        }

        if (result.RootFamilySummary is not null)
        {
            lines.Add($"Canonical root instance: {result.RootFamilySummary.CanonicalInstanceAddress}");
            lines.Add($"Root family summary:     rep={result.RootFamilySummary.RepresentativeAddress} canonicalObs={result.RootFamilySummary.CanonicalInstanceObservationCount}/{result.RootFamilySummary.StabilitySampleCount}");
        }

        lines.Add($"Notes:                   {FormatNotes(result.Notes)}");

        return string.Join(Environment.NewLine, lines);
    }

    private static string FormatBool(bool value) => value ? "yes" : "no";

    private static string FormatOffset(int? value) =>
        value.HasValue ? $"0x{value.Value:X}" : "n/a";

    private static string FormatFloat(float? value) =>
        value?.ToString("0.00000", CultureInfo.InvariantCulture) ?? "n/a";

    private static string FormatDouble(double? value) =>
        value?.ToString("0.000", CultureInfo.InvariantCulture) ?? "n/a";

    private static string FormatNotes(IReadOnlyList<string> notes) =>
        notes.Count == 0 ? "none" : string.Join("; ", notes);
}
