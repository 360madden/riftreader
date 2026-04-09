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
            $"Verification:               {result.VerificationMethod ?? "n/a"}",
            $"Candidate:                  {result.CandidateAddress ?? "n/a"} [{result.CandidateSource ?? "n/a"}]",
            $"Target address:             {result.TargetAddress ?? "n/a"}",
            $"Effective address:          {result.EffectiveAddress ?? "n/a"}",
            $"Access operand:             {result.AccessOperand ?? "n/a"}",
            $"Access type:                {result.AccessType ?? "n/a"}",
            $"Matched offset:             {result.MatchedOffset?.ToString() ?? "n/a"}",
            $"Access displacement:        {result.AccessDisplacement?.ToString() ?? "n/a"}",
            $"Coord base rel. offset:     {FormatOffset(result.InferredCoordBaseRelativeOffset)}",
            $"Instruction address:        {result.InstructionAddress ?? "n/a"}",
            $"Instruction symbol:         {result.InstructionSymbol ?? "n/a"}",
            $"Instruction:                {result.Instruction ?? "n/a"}",
            $"Pattern:                    {result.Pattern ?? "n/a"}",
            $"Module:                     {result.ModuleName ?? "n/a"}",
            $"Module base:                {result.ModuleBase ?? "n/a"}",
            $"Module offset:              {result.ModuleOffset ?? "n/a"}"
        };

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
}
