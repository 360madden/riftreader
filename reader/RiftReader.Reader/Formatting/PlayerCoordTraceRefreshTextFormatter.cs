using System.Text;
using RiftReader.Reader.Models;

namespace RiftReader.Reader.Formatting;

public static class PlayerCoordTraceRefreshTextFormatter
{
    public static string Format(PlayerCoordTraceRefreshResult result)
    {
        ArgumentNullException.ThrowIfNull(result);

        var anchor = result.Anchor;
        var builder = new StringBuilder();
        builder.AppendLine("Player coord trace refresh");
        builder.AppendLine($"Process:                    {result.ProcessName} [{result.ProcessId}]");
        builder.AppendLine($"Trace file:                 {result.TraceSourceFile}");
        builder.AppendLine($"Refresh performed:          {result.RefreshPerformed}");
        builder.AppendLine($"Trace matches process:      {anchor.TraceMatchesProcess}");
        builder.AppendLine($"Verification:               {anchor.VerificationMethod ?? "n/a"}");
        builder.AppendLine($"Instruction:                {anchor.InstructionSymbol ?? anchor.Instruction ?? "n/a"}");
        builder.AppendLine($"Object base:                {anchor.ObjectBaseAddress ?? "n/a"} ({anchor.BaseRegister ?? "n/a"})");
        builder.AppendLine($"Source object:              {anchor.SourceObjectAddress ?? "n/a"} ({anchor.SourceObjectRegister ?? "n/a"})");
        builder.AppendLine($"Coord offsets:              X={anchor.CoordXRelativeOffset?.ToString() ?? "n/a"}, Y={anchor.CoordYRelativeOffset?.ToString() ?? "n/a"}, Z={anchor.CoordZRelativeOffset?.ToString() ?? "n/a"}");
        builder.AppendLine($"Source coord offset:        {anchor.SourceCoordRelativeOffset?.ToString() ?? "n/a"}");
        builder.AppendLine($"Primary coord match:        {anchor.Match?.CoordMatchesWithinTolerance.ToString() ?? "n/a"}");
        builder.AppendLine($"Source coord match:         {anchor.SourceObjectMatch?.CoordMatchesWithinTolerance.ToString() ?? "n/a"}");
        return builder.ToString().TrimEnd();
    }
}
