using System.Globalization;
using RiftReader.Reader.Models;

namespace RiftReader.Reader.Formatting;

public static class TargetCurrentReadTextFormatter
{
    public static string Format(TargetCurrentReadResult result)
    {
        if (!result.HasTarget)
        {
            return string.Join(Environment.NewLine, new[]
            {
                $"Process:              {result.ProcessName} ({result.ProcessId})",
                $"ReaderBridge source:  {result.ReaderBridgeSourceFile}",
                $"Target:               no target selected"
            });
        }

        var lines = new List<string>
        {
            $"Process:              {result.ProcessName} ({result.ProcessId})",
            $"ReaderBridge source:  {result.ReaderBridgeSourceFile}",
            $"Family:               {result.FamilyId}",
            $"Kind:                 {result.FamilyNotes}",
            $"Signature:            {result.Signature}",
            $"Selection source:     {result.SelectionSource}",
            $"Anchor provenance:    {result.AnchorProvenance}",
            $"Anchor cache file:    {result.AnchorCacheFile ?? "n/a"}",
            $"Anchor cache used:    {FormatBool(result.AnchorCacheUsed)}",
            $"Anchor cache updated: {FormatBool(result.AnchorCacheUpdated)}",
            $"Confirmation file:    {result.ConfirmationFile ?? "n/a"}",
            $"CE confirmed hits:    {result.CeConfirmedSampleCount}",
            $"Memory sample:        {result.Memory.AddressHex}",
            $"Memory name:          {result.Memory.Name ?? "n/a"}",
            $"Memory level:         {FormatInt(result.Memory.Level)}",
            $"Memory health:        {FormatInt(result.Memory.Health)}",
            $"Memory coords:        {FormatFloat(result.Memory.CoordX)}, {FormatFloat(result.Memory.CoordY)}, {FormatFloat(result.Memory.CoordZ)}",
            $"Memory distance:      {FormatFloat(result.Memory.Distance)}",
            $"Expected name:        {result.Expected.Name ?? "n/a"}",
            $"Expected level:       {FormatInt(result.Expected.Level)}",
            $"Expected health:      {FormatLong(result.Expected.Health)}/{FormatLong(result.Expected.HealthMax)}",
            $"Expected coords:      {FormatDouble(result.Expected.CoordX)}, {FormatDouble(result.Expected.CoordY)}, {FormatDouble(result.Expected.CoordZ)}",
            $"Expected distance:    {FormatDouble(result.Expected.Distance)}",
            $"Name matches:         {FormatBool(result.Match.NameMatches)}",
            $"Level matches:        {FormatBool(result.Match.LevelMatches)}",
            $"Health matches:       {FormatBool(result.Match.HealthMatches)}",
            $"Coords match:         {FormatBool(result.Match.CoordMatchesWithinTolerance)}",
            $"Distance match:       {FormatBool(result.Match.DistanceMatchesWithinTolerance)}",
            $"Coord deltas:         {FormatFloat(result.Match.DeltaX)}, {FormatFloat(result.Match.DeltaY)}, {FormatFloat(result.Match.DeltaZ)}",
            $"Distance delta:       {FormatFloat(result.Match.DeltaDistance)}"
        };

        return string.Join(Environment.NewLine, lines);
    }

    private static string FormatBool(bool value) => value ? "yes" : "no";

    private static string FormatInt(int? value) =>
        value?.ToString(CultureInfo.InvariantCulture) ?? "n/a";

    private static string FormatLong(long? value) =>
        value?.ToString(CultureInfo.InvariantCulture) ?? "n/a";

    private static string FormatFloat(float? value) =>
        value?.ToString("0.00000", CultureInfo.InvariantCulture) ?? "n/a";

    private static string FormatDouble(double? value) =>
        value?.ToString("0.00000", CultureInfo.InvariantCulture) ?? "n/a";
}
