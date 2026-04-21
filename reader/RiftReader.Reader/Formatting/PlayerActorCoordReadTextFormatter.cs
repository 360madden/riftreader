using System.Globalization;
using RiftReader.Reader.Models;

namespace RiftReader.Reader.Formatting;

public static class PlayerActorCoordReadTextFormatter
{
    public static string Format(PlayerActorCoordReadResult result)
    {
        var lines = new List<string>
        {
            $"Process:                 {result.ProcessName} ({result.ProcessId})",
            $"ReaderBridge source:     {result.ReaderBridgeSourceFile}",
            $"Trace source:            {result.TraceSourceFile ?? "n/a"}",
            $"Trace available:         {FormatBool(result.TraceAvailable)}",
            $"Trace matches process:   {FormatBool(result.TraceMatchesProcess)}",
            $"Resolution source:       {result.ResolutionSource}",
            $"Anchor provenance:       {result.AnchorProvenance}",
            $"Family:                  {result.FamilyId ?? "n/a"}",
            $"Kind:                    {result.FamilyNotes ?? "n/a"}",
            $"Signature:               {result.Signature ?? "n/a"}",
            $"Selection source:        {result.SelectionSource ?? "n/a"}",
            $"Confirmation file:       {result.ConfirmationFile ?? "n/a"}",
            $"CE confirmed hits:       {result.CeConfirmedSampleCount}",
            $"Base register:           {result.BaseRegister ?? "n/a"}",
            $"Base register value:     {result.BaseRegisterValue ?? "n/a"}",
            $"Object base address:     {result.ObjectBaseAddress ?? "n/a"}",
            $"Coord base rel. offset:  {FormatOffset(result.CoordBaseRelativeOffset)}",
            $"Coord X rel. offset:     {FormatOffset(result.CoordXRelativeOffset)}",
            $"Coord Y rel. offset:     {FormatOffset(result.CoordYRelativeOffset)}",
            $"Coord Z rel. offset:     {FormatOffset(result.CoordZRelativeOffset)}",
            $"Level rel. offset:       {FormatOffset(result.LevelRelativeOffset)}",
            $"Health rel. offset:      {FormatOffset(result.HealthRelativeOffset)}",
            $"Module:                  {result.ModuleName ?? "n/a"}",
            $"Module offset:           {result.ModuleOffset ?? "n/a"}",
            $"Instruction symbol:      {result.InstructionSymbol ?? "n/a"}",
            $"Instruction:             {result.Instruction ?? "n/a"}",
            $"Pattern:                 {result.Pattern ?? "n/a"}",
            $"Memory sample:           {result.Memory.AddressHex}",
            $"Memory level:            {FormatInt(result.Memory.Level)}",
            $"Memory health:           {FormatInt(result.Memory.Health)}",
            $"Memory coords:           {FormatFloat(result.Memory.CoordX)}, {FormatFloat(result.Memory.CoordY)}, {FormatFloat(result.Memory.CoordZ)}",
            $"Expected level:          {FormatInt(result.Expected.Level)}",
            $"Expected health:         {FormatLong(result.Expected.Health)}/{FormatLong(result.Expected.HealthMax)}",
            $"Expected coords:         {FormatDouble(result.Expected.CoordX)}, {FormatDouble(result.Expected.CoordY)}, {FormatDouble(result.Expected.CoordZ)}",
            $"Coords match:            {FormatBool(result.Match.CoordMatchesWithinTolerance)}",
            $"Coord deltas:            {FormatFloat(result.Match.DeltaX)}, {FormatFloat(result.Match.DeltaY)}, {FormatFloat(result.Match.DeltaZ)}"
        };

        if (result.ModulePattern is not null)
        {
            lines.Add($"Pattern found in module:   {FormatBool(result.ModulePattern.Found)}");
            if (result.ModulePattern.Found)
            {
                lines.Add($"Pattern match address:     {result.ModulePattern.Address ?? "n/a"}");
                lines.Add($"Pattern rel. offset:       {result.ModulePattern.RelativeOffsetHex ?? "n/a"}");
            }
        }

        if (result.BestContainerChain is not null)
        {
            lines.Add($"Best chain parent:       {result.BestContainerChain.ParentAddress ?? "n/a"}");
            lines.Add($"Best chain root:         {result.BestContainerChain.RootAddress ?? "n/a"}");
            lines.Add($"Chain observations:      {result.BestContainerChain.ParentObservationCount}/{result.BestContainerChain.StabilitySampleCount} parent, {result.BestContainerChain.RootObservationCount}/{result.BestContainerChain.StabilitySampleCount} root");
        }

        if (result.BestRootFamily is not null)
        {
            lines.Add($"Best root family:        {result.BestRootFamily.RegionBase}");
            lines.Add($"Root family evidence:    {result.BestRootFamily.ObservationCount}/{result.BestRootFamily.StabilitySampleCount} observations across {result.BestRootFamily.DistinctAddressCount} addresses");
            lines.Add($"Root family exemplar:    {result.BestRootFamily.RepresentativeAddress}");
        }

        if (result.RootFamilySummary is not null)
        {
            lines.Add($"Canonical root instance: {result.RootFamilySummary.CanonicalInstanceAddress}");
            lines.Add($"Root family summary:     {result.RootFamilySummary.RegionBase} canonicalObs={result.RootFamilySummary.CanonicalInstanceObservationCount}/{result.RootFamilySummary.StabilitySampleCount} rep={result.RootFamilySummary.RepresentativeAddress}");
        }

        if (result.Notes.Count > 0)
        {
            lines.Add("Notes:");
            foreach (var note in result.Notes)
            {
                lines.Add($"- {note}");
            }
        }

        return string.Join(Environment.NewLine, lines);
    }

    private static string FormatBool(bool value) => value ? "yes" : "no";

    private static string FormatOffset(int? value) =>
        value.HasValue ? $"{value.Value} (0x{value.Value:X})" : "n/a";

    private static string FormatInt(int? value) =>
        value?.ToString(CultureInfo.InvariantCulture) ?? "n/a";

    private static string FormatLong(long? value) =>
        value?.ToString(CultureInfo.InvariantCulture) ?? "n/a";

    private static string FormatFloat(float? value) =>
        value?.ToString("0.00000", CultureInfo.InvariantCulture) ?? "n/a";

    private static string FormatDouble(double? value) =>
        value?.ToString("0.00000", CultureInfo.InvariantCulture) ?? "n/a";
}
