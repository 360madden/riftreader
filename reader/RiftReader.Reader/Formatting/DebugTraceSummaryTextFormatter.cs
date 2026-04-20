using System.Text;
using RiftReader.Reader.Debugging;

namespace RiftReader.Reader.Formatting;

public static class DebugTraceSummaryTextFormatter
{
    public static string Format(DebugTraceInspectResult inspection)
    {
        var builder = new StringBuilder();
        builder.AppendLine("Offline debug trace inspection");
        builder.AppendLine($"Schema version:      {inspection.SchemaVersion}");
        builder.AppendLine($"Trace directory:     {inspection.TraceDirectory}");
        builder.AppendLine($"Status:              {inspection.Package.Status ?? "n/a"}");
        builder.AppendLine($"Integrity:           {inspection.Package.IntegrityStatus ?? "n/a"}");
        builder.AppendLine($"Trace id:            {inspection.Package.TraceId ?? inspection.TraceManifest?.TraceId ?? "n/a"}");
        builder.AppendLine($"Label:               {inspection.Package.Label ?? inspection.TraceManifest?.Label ?? "n/a"}");
        builder.AppendLine($"Process:             {FormatProcess(inspection.Package.ProcessName ?? inspection.TraceManifest?.ProcessName, inspection.Package.ProcessId ?? inspection.TraceManifest?.ProcessId)}");
        builder.AppendLine($"Events:              {inspection.Events.Count}");
        builder.AppendLine($"Hits:                {inspection.Hits.Count}");
        builder.AppendLine($"Markers:             {inspection.Markers.Count}");
        builder.AppendLine($"Modules:             {inspection.Modules.Count}");

        if (inspection.TraceManifest is not null)
        {
            builder.AppendLine();
            builder.AppendLine("Trace manifest:");
            builder.AppendLine($"Mode:                {inspection.TraceManifest.Mode}");
            builder.AppendLine($"Breakpoint kind:     {inspection.TraceManifest.BreakpointKind}");
            builder.AppendLine($"Breakpoint address:  {inspection.TraceManifest.BreakpointAddress ?? "n/a"}");
            builder.AppendLine($"Module/offset:       {FormatModuleOffset(inspection.TraceManifest.BreakpointModuleName, inspection.TraceManifest.BreakpointModuleOffset)}");
            builder.AppendLine($"Attach outcome:      {inspection.TraceManifest.AttachOutcome}");
            builder.AppendLine($"Detach outcome:      {inspection.TraceManifest.DetachOutcome}");
            builder.AppendLine($"Cleanup outcome:     {inspection.TraceManifest.CleanupOutcome}");
            builder.AppendLine($"Architecture:        {inspection.TraceManifest.TargetArchitecture}");
            builder.AppendLine($"Capabilities:        {FormatCapabilities(inspection.TraceManifest.Capabilities)}");
            builder.AppendLine($"Started at (UTC):    {inspection.TraceManifest.StartedAtUtc}");
            builder.AppendLine($"Completed at (UTC):  {inspection.TraceManifest.CompletedAtUtc}");
            builder.AppendLine($"Elapsed (ms):        {inspection.TraceManifest.ElapsedMilliseconds}");
            builder.AppendLine($"Requested hits:      {inspection.TraceManifest.RequestedHitCount}");
            builder.AppendLine($"Recorded hits:       {inspection.TraceManifest.RecordedHitCount}");
            builder.AppendLine($"Event count:         {inspection.TraceManifest.EventCount}");
        }

        if (inspection.InstructionFingerprints.Count > 0)
        {
            builder.AppendLine();
            builder.AppendLine("Instruction fingerprints:");
            foreach (var fingerprint in inspection.InstructionFingerprints.Take(8))
            {
                builder.AppendLine($"- {fingerprint.ModuleRelativeRip} hits={fingerprint.HitCount} pattern={fingerprint.Pattern ?? fingerprint.InstructionBytes ?? "n/a"}");
            }
        }

        if (inspection.HitClusters.Count > 0)
        {
            builder.AppendLine();
            builder.AppendLine("Hit clusters:");
            foreach (var cluster in inspection.HitClusters.Take(8))
            {
                builder.AppendLine($"- {cluster.ClusterKey}: hits={cluster.HitCount} eff={cluster.EffectiveAddress ?? "n/a"} threads={string.Join(", ", cluster.ThreadIds)}");
            }
        }

        if (inspection.FollowUpSuggestions.Count > 0)
        {
            builder.AppendLine();
            builder.AppendLine("Follow-up suggestions:");
            foreach (var suggestion in inspection.FollowUpSuggestions.Take(8))
            {
                builder.AppendLine($"- {suggestion.Kind} @ {suggestion.Address} len={suggestion.Length}: {suggestion.Reason}");
            }
        }

        if (inspection.Markers.Count > 0)
        {
            builder.AppendLine();
            builder.AppendLine($"Recent markers (last {Math.Min(8, inspection.Markers.Count)}):");
            foreach (var marker in inspection.Markers.TakeLast(8))
            {
                builder.Append("- ");
                builder.Append(marker.Kind);
                builder.Append($" @ {marker.RecordedAtUtc}");
                if (marker.ElapsedMilliseconds.HasValue)
                {
                    builder.Append($" (+{marker.ElapsedMilliseconds.Value} ms)");
                }

                builder.AppendLine();
                if (!string.IsNullOrWhiteSpace(marker.Message))
                {
                    builder.AppendLine($"  message: {marker.Message}");
                }
            }
        }

        if (inspection.Warnings.Count > 0)
        {
            builder.AppendLine();
            builder.AppendLine("Warnings:");
            foreach (var warning in inspection.Warnings)
            {
                builder.AppendLine($"- {warning}");
            }
        }

        return builder.ToString().TrimEnd();
    }

    private static string FormatProcess(string? processName, int? processId)
    {
        if (string.IsNullOrWhiteSpace(processName) && !processId.HasValue)
        {
            return "n/a";
        }

        return string.IsNullOrWhiteSpace(processName)
            ? $"pid {processId!.Value}"
            : processId.HasValue ? $"{processName} (PID {processId.Value})" : processName;
    }

    private static string FormatModuleOffset(string? moduleName, string? offset)
    {
        if (string.IsNullOrWhiteSpace(moduleName) && string.IsNullOrWhiteSpace(offset))
        {
            return "n/a";
        }

        if (string.IsNullOrWhiteSpace(moduleName))
        {
            return offset!;
        }

        if (string.IsNullOrWhiteSpace(offset))
        {
            return moduleName;
        }

        return $"{moduleName}+{offset}";
    }

    private static string FormatCapabilities(DebugTraceCapabilities capabilities)
    {
        var enabled = new List<string>();
        if (capabilities.RegisterCapture) enabled.Add("registers");
        if (capabilities.StackCapture) enabled.Add("stack");
        if (capabilities.MemoryWindows) enabled.Add("memory-windows");
        if (capabilities.InstructionDecode) enabled.Add("decode");
        if (capabilities.InstructionFingerprint) enabled.Add("fingerprint");
        if (capabilities.HitClustering) enabled.Add("clusters");
        if (capabilities.FollowUpSuggestions) enabled.Add("follow-up");

        return enabled.Count == 0 ? "minimal" : string.Join(", ", enabled);
    }
}
