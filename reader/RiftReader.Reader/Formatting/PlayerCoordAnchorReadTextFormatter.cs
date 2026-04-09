using RiftReader.Reader.Models;

namespace RiftReader.Reader.Formatting;

public static class PlayerCoordAnchorReadTextFormatter
{
    public static string Format(PlayerCoordAnchorReadResult result)
    {
        var lines = new List<string>
        {
            $"Process:                    {result.ProcessName} ({result.ProcessId})",
            $"Trace file:                 {result.SourceFile}",
            $"Trace process:              {(result.TraceProcessName is null ? "n/a" : $"{result.TraceProcessName} ({result.TraceProcessId?.ToString() ?? "n/a"})")}",
            $"Trace matches process:      {result.TraceMatchesProcess}",
            $"Verification:               {result.VerificationMethod ?? "n/a"}",
            $"Candidate:                  {result.CandidateAddress ?? "n/a"} [{result.CandidateSource ?? "n/a"}]",
            $"Target address:             {result.TargetAddress ?? "n/a"}",
            $"Effective address:          {result.EffectiveAddress ?? "n/a"}",
            $"Access operand:             {result.AccessOperand ?? "n/a"}",
            $"Access type:                {result.AccessType ?? "n/a"}",
            $"Matched offset:             {result.MatchedOffset?.ToString() ?? "n/a"}",
            $"Access displacement:        {result.AccessDisplacement?.ToString() ?? "n/a"}",
            $"Coord base rel. offset:     {FormatOffset(result.InferredCoordBaseRelativeOffset)}",
            $"Base register:              {result.BaseRegister ?? "n/a"}",
            $"Base register value:        {result.BaseRegisterValue ?? "n/a"}",
            $"Object base address:        {result.ObjectBaseAddress ?? "n/a"}",
            $"Level rel. offset:          {FormatOffset(result.LevelRelativeOffset)}",
            $"Health rel. offset:         {FormatOffset(result.HealthRelativeOffset)}",
            $"Coord X rel. offset:        {FormatOffset(result.CoordXRelativeOffset)}",
            $"Coord Y rel. offset:        {FormatOffset(result.CoordYRelativeOffset)}",
            $"Coord Z rel. offset:        {FormatOffset(result.CoordZRelativeOffset)}",
            $"Source object register:     {result.SourceObjectRegister ?? "n/a"}",
            $"Source object value:        {result.SourceObjectRegisterValue ?? "n/a"}",
            $"Source object address:      {result.SourceObjectAddress ?? "n/a"}",
            $"Source coord rel. offset:   {FormatOffset(result.SourceCoordRelativeOffset)}",
            $"ReaderBridge source:        {result.ReaderBridgeSourceFile ?? "n/a"}",
            $"Instruction address:        {result.InstructionAddress ?? "n/a"}",
            $"Instruction symbol:         {result.InstructionSymbol ?? "n/a"}",
            $"Instruction:                {result.Instruction ?? "n/a"}",
            $"Pattern:                    {result.Pattern ?? "n/a"}",
            $"Module:                     {result.ModuleName ?? "n/a"}",
            $"Module base:                {result.ModuleBase ?? "n/a"}",
            $"Module offset:              {result.ModuleOffset ?? "n/a"}"
        };

        if (result.MemorySample is not null)
        {
            lines.Add($"Trace sample address:       {result.MemorySample.AddressHex}");
            lines.Add($"Trace sample level:         {result.MemorySample.Level?.ToString() ?? "n/a"}");
            lines.Add($"Trace sample health:        {result.MemorySample.Health?.ToString() ?? "n/a"}");
            lines.Add(
                $"Trace sample coords:        {FormatFloat(result.MemorySample.CoordX)}, {FormatFloat(result.MemorySample.CoordY)}, {FormatFloat(result.MemorySample.CoordZ)}");
        }

        if (result.SourceObjectSample is not null)
        {
            lines.Add($"Source sample address:      {result.SourceObjectSample.AddressHex}");
            lines.Add(
                $"Source sample coords:       {FormatFloat(result.SourceObjectSample.CoordX)}, {FormatFloat(result.SourceObjectSample.CoordY)}, {FormatFloat(result.SourceObjectSample.CoordZ)}");
        }

        if (result.Expected is not null)
        {
            lines.Add($"Expected level:             {result.Expected.Level?.ToString() ?? "n/a"}");
            lines.Add($"Expected health:            {result.Expected.Health?.ToString() ?? "n/a"}");
            lines.Add(
                $"Expected coords:            {FormatDouble(result.Expected.CoordX)}, {FormatDouble(result.Expected.CoordY)}, {FormatDouble(result.Expected.CoordZ)}");
        }

        if (result.Match is not null)
        {
            lines.Add($"Trace level matches:        {result.Match.LevelMatches}");
            lines.Add($"Trace health matches:       {result.Match.HealthMatches}");
            lines.Add($"Trace coords match:         {result.Match.CoordMatchesWithinTolerance}");
            lines.Add(
                $"Trace deltas:               {FormatDelta(result.Match.DeltaX)}, {FormatDelta(result.Match.DeltaY)}, {FormatDelta(result.Match.DeltaZ)}");
        }

        if (result.SourceObjectMatch is not null)
        {
            lines.Add($"Source coords match:        {result.SourceObjectMatch.CoordMatchesWithinTolerance}");
            lines.Add(
                $"Source deltas:              {FormatDelta(result.SourceObjectMatch.DeltaX)}, {FormatDelta(result.SourceObjectMatch.DeltaY)}, {FormatDelta(result.SourceObjectMatch.DeltaZ)}");
        }

        if (result.ModulePattern is not null)
        {
            lines.Add($"Pattern found in module:     {result.ModulePattern.Found}");
            if (result.ModulePattern.Found)
            {
                lines.Add($"Pattern match address:       {result.ModulePattern.Address ?? "n/a"}");
                lines.Add($"Pattern rel. offset:         {result.ModulePattern.RelativeOffsetHex ?? "n/a"}");
            }
        }

        return string.Join(Environment.NewLine, lines);
    }

    private static string FormatOffset(int? value)
    {
        if (!value.HasValue)
        {
            return "n/a";
        }

        return $"{value.Value} (0x{value.Value:X})";
    }

    private static string FormatFloat(float? value) =>
        value.HasValue
            ? value.Value.ToString("0.###", System.Globalization.CultureInfo.InvariantCulture)
            : "n/a";

    private static string FormatDouble(double? value) =>
        value.HasValue
            ? value.Value.ToString("0.###", System.Globalization.CultureInfo.InvariantCulture)
            : "n/a";

    private static string FormatDelta(float? value) =>
        value.HasValue
            ? value.Value.ToString("0.###", System.Globalization.CultureInfo.InvariantCulture)
            : "n/a";
}
