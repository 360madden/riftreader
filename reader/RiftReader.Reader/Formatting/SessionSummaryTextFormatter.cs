using System.Text;
using RiftReader.Reader.Sessions;

namespace RiftReader.Reader.Formatting;

public static class SessionSummaryTextFormatter
{
    public static string Format(SessionPackageManifestDocument document)
    {
        var builder = new StringBuilder();
        builder.AppendLine("Offline session package");
        builder.AppendLine($"Session id:          {document.SessionId ?? "n/a"}");
        builder.AppendLine($"Label:               {document.Label ?? "n/a"}");
        builder.AppendLine($"Status:              {document.Status ?? "n/a"}");
        builder.AppendLine($"Integrity:           {document.IntegrityStatus ?? "n/a"}");
        builder.AppendLine($"Generated at:        {document.GeneratedAtUtc ?? "n/a"}");
        builder.AppendLine($"Session directory:   {document.SessionDirectory ?? "n/a"}");
        builder.AppendLine($"Process:             {FormatProcess(document.ProcessName, document.ProcessId)}");
        builder.AppendLine($"Watchset regions:    {document.WatchsetRegionCount?.ToString() ?? "n/a"}");
        builder.AppendLine($"Recorded samples:    {document.SampleCount?.ToString() ?? "n/a"}");
        builder.AppendLine($"Interval (ms):       {document.IntervalMilliseconds?.ToString() ?? "n/a"}");
        builder.AppendLine($"Artifacts copied:    {document.CopiedArtifacts?.Count.ToString() ?? "0"}");

        if (!string.IsNullOrWhiteSpace(document.WatchsetFile))
        {
            builder.AppendLine($"Watchset:            {document.WatchsetFile}");
        }

        if (!string.IsNullOrWhiteSpace(document.RecordingManifestFile))
        {
            builder.AppendLine($"Recording manifest:  {document.RecordingManifestFile}");
        }

        if (!string.IsNullOrWhiteSpace(document.SamplesFile))
        {
            builder.AppendLine($"Samples file:        {document.SamplesFile}");
        }

        if (!string.IsNullOrWhiteSpace(document.MarkersFile))
        {
            builder.AppendLine($"Markers file:        {document.MarkersFile}");
        }

        if (!string.IsNullOrWhiteSpace(document.ModulesFile))
        {
            builder.AppendLine($"Modules file:        {document.ModulesFile}");
        }

        if (document.MissingFiles is { Count: > 0 })
        {
            builder.AppendLine();
            builder.AppendLine("Missing files:");
            foreach (var path in document.MissingFiles)
            {
                builder.AppendLine($"- {path}");
            }
        }

        if (!string.IsNullOrWhiteSpace(document.FailureMessage))
        {
            builder.AppendLine();
            builder.AppendLine($"Failure: {document.FailureMessage}");
        }

        if (document.Warnings is { Count: > 0 })
        {
            builder.AppendLine();
            builder.AppendLine("Warnings:");
            foreach (var warning in document.Warnings)
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

        if (string.IsNullOrWhiteSpace(processName))
        {
            return $"pid {processId!.Value}";
        }

        return processId.HasValue
            ? $"{processName} (PID {processId.Value})"
            : processName;
    }
}
