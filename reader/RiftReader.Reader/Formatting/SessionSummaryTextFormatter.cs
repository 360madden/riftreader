using System.Text;
using RiftReader.Reader.Sessions;

namespace RiftReader.Reader.Formatting;

public static class SessionSummaryTextFormatter
{
    public static string Format(SessionPackageManifestDocument document)
    {
        var builder = new StringBuilder();
        AppendPackageSummary(builder, "Offline session package", document);
        return builder.ToString().TrimEnd();
    }

    public static string Format(SessionRecordResult result)
    {
        var builder = new StringBuilder();
        AppendRecordingSummary(builder, "Offline session recording", result);
        return builder.ToString().TrimEnd();
    }

    public static string Format(SessionInspectResult result)
    {
        var builder = new StringBuilder();
        builder.AppendLine("Offline session inspection");
        builder.AppendLine($"Schema version:      {result.SchemaVersion}");
        builder.AppendLine($"Mode:                {result.Mode}");
        builder.AppendLine($"Session directory:   {result.SessionDirectory}");

        builder.AppendLine();
        AppendPackageSummary(builder, "Package", result.Package, includeHeader: false);

        if (result.RecordingManifest is not null)
        {
            builder.AppendLine();
            AppendRecordingSummary(builder, "Recording", result.RecordingManifest, includeHeader: false);
        }

        if (result.ReaderBridgeSnapshot?.Current is not null)
        {
            builder.AppendLine();
            builder.AppendLine("ReaderBridge truth:");
            builder.AppendLine($"Snapshot file:       {result.ReaderBridgeSnapshot.SourceFile}");
            builder.AppendLine($"Player:              {result.ReaderBridgeSnapshot.Current.Player?.Name ?? "n/a"}");
            builder.AppendLine($"Player level:        {result.ReaderBridgeSnapshot.Current.Player?.Level?.ToString() ?? "n/a"}");
            builder.AppendLine($"Player zone:         {result.ReaderBridgeSnapshot.Current.Player?.Zone ?? "n/a"}");
            builder.AppendLine($"Player location:     {result.ReaderBridgeSnapshot.Current.Player?.LocationName ?? "n/a"}");
            builder.AppendLine($"Target:              {result.ReaderBridgeSnapshot.Current.Target?.Name ?? "n/a"}");
            builder.AppendLine($"Export reason:       {result.ReaderBridgeSnapshot.Current.ExportReason ?? result.ReaderBridgeSnapshot.LastReason ?? "n/a"}");
        }

        builder.AppendLine();
        builder.AppendLine("Inspection totals:");
        builder.AppendLine($"Loaded samples:      {result.LoadedSampleCount}");
        builder.AppendLine($"Loaded markers:      {result.LoadedMarkerCount}");
        builder.AppendLine($"Max timing drift:    {FormatDuration(result.MaxTimingDriftMilliseconds)}");
        builder.AppendLine($"Max capture duration:{FormatDuration(result.MaxCaptureDurationMilliseconds)}");
        builder.AppendLine($"Avg capture duration:{FormatDuration(result.AverageCaptureDurationMilliseconds)}");

        if (result.MarkerKinds is { Count: > 0 })
        {
            builder.AppendLine();
            builder.AppendLine("Marker kinds:");
            foreach (var markerKind in result.MarkerKinds)
            {
                builder.AppendLine($"- {markerKind.Kind}: {markerKind.Count}");
            }
        }

        if (result.Regions is { Count: > 0 })
        {
            builder.AppendLine();
            builder.AppendLine("Regions:");
            foreach (var region in result.Regions)
            {
                builder.AppendLine(
                    $"- {region.Name} [{region.Category}] @ {region.Address} len={region.Length} req={(region.Required ? "yes" : "no")} " +
                    $"samples={region.SampleCount} ok={region.SuccessfulReadCount} fail={region.FailedReadCount} bytes={region.TotalBytesRead} " +
                    $"changed={region.ChangedSampleCount}");

                if (!string.IsNullOrWhiteSpace(region.LastError))
                {
                    builder.AppendLine($"  last error: {region.LastError}");
                }
            }
        }

        if (result.Markers is { Count: > 0 })
        {
            builder.AppendLine();
            builder.AppendLine($"Recent markers (last {Math.Min(12, result.Markers.Count)}):");
            foreach (var marker in result.Markers.TakeLast(12))
            {
                builder.Append("- ");
                builder.Append(marker.Kind);

                if (marker.SampleIndex.HasValue)
                {
                    builder.Append($" [sample {marker.SampleIndex.Value}]");
                }

                if (!string.IsNullOrWhiteSpace(marker.Source))
                {
                    builder.Append($" <{marker.Source}>");
                }

                builder.Append($" @ {marker.RecordedAtUtc}");

                if (marker.ElapsedMilliseconds.HasValue)
                {
                    builder.Append($" (+{marker.ElapsedMilliseconds.Value} ms)");
                }

                builder.AppendLine();

                if (!string.IsNullOrWhiteSpace(marker.Label))
                {
                    builder.AppendLine($"  label: {marker.Label}");
                }

                if (!string.IsNullOrWhiteSpace(marker.Message))
                {
                    builder.AppendLine($"  message: {marker.Message}");
                }
            }
        }

        if (result.Warnings is { Count: > 0 })
        {
            builder.AppendLine();
            builder.AppendLine("Warnings:");
            foreach (var warning in result.Warnings)
            {
                builder.AppendLine($"- {warning}");
            }
        }

        return builder.ToString().TrimEnd();
    }

    private static void AppendPackageSummary(StringBuilder builder, string title, SessionPackageManifestDocument document, bool includeHeader = true)
    {
        if (includeHeader)
        {
            builder.AppendLine(title);
        }

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
    }

    private static void AppendRecordingSummary(StringBuilder builder, string title, SessionRecordResult result, bool includeHeader = true)
    {
        if (includeHeader)
        {
            builder.AppendLine(title);
        }

        builder.AppendLine($"Schema version:      {result.SchemaVersion}");
        builder.AppendLine($"Mode:                {result.Mode}");
        builder.AppendLine($"Session id:          {result.SessionId}");
        builder.AppendLine($"Output directory:    {result.OutputDirectory}");
        builder.AppendLine($"Process:             {FormatProcess(result.ProcessName, result.ProcessId)}");
        builder.AppendLine($"Module:              {result.ModuleName ?? "n/a"}");
        builder.AppendLine($"Window title:        {result.MainWindowTitle ?? "n/a"}");
        builder.AppendLine($"Watchset file:       {result.WatchsetFile}");
        builder.AppendLine($"Watchset regions:    {result.WatchsetRegionCount}");
        builder.AppendLine($"Requested samples:   {result.RequestedSampleCount}");
        builder.AppendLine($"Recorded samples:    {result.RecordedSampleCount}");
        builder.AppendLine($"Interval (ms):       {result.IntervalMilliseconds}");
        builder.AppendLine($"Started at (UTC):    {result.StartedAtUtc}");
        builder.AppendLine($"Completed at (UTC):  {result.CompletedAtUtc}");
        builder.AppendLine($"Interrupted:         {(result.Interrupted ? "yes" : "no")}");
        builder.AppendLine($"Marker count:        {result.MarkerCount}");
        builder.AppendLine($"Marker kinds:        {(result.MarkerKinds.Count == 0 ? "n/a" : string.Join(", ", result.MarkerKinds))}");
        builder.AppendLine($"Requested bytes:     {result.RequestedRegionByteCount}");
        builder.AppendLine($"Total bytes read:    {result.TotalBytesRead}");
        builder.AppendLine($"Region read failures:{result.TotalRegionReadFailures}");
        builder.AppendLine($"Integrity:           {result.IntegrityStatus}");

        if (result.MissingFiles is { Count: > 0 })
        {
            builder.AppendLine();
            builder.AppendLine("Missing files:");
            foreach (var path in result.MissingFiles)
            {
                builder.AppendLine($"- {path}");
            }
        }

        if (result.RegionSummaries is { Count: > 0 })
        {
            builder.AppendLine();
            builder.AppendLine("Region summaries:");
            foreach (var region in result.RegionSummaries)
            {
                builder.AppendLine(
                    $"- {region.Name} [{region.Category}] @ {region.Address} len={region.Length} req={(region.Required ? "yes" : "no")} " +
                    $"samples={region.SampleCount} ok={region.SuccessfulReadCount} fail={region.FailedReadCount} bytes={region.TotalBytesRead} " +
                    $"changed={region.ChangedSampleCount}");

                if (!string.IsNullOrWhiteSpace(region.LastError))
                {
                    builder.AppendLine($"  last error: {region.LastError}");
                }
            }
        }

        if (result.Modules is { Count: > 0 })
        {
            builder.AppendLine();
            builder.AppendLine("Modules:");
            foreach (var module in result.Modules)
            {
                builder.AppendLine($"- {module.FileName} [{module.ModuleName}] @ {module.BaseAddressHex} ({module.ModuleMemorySize} bytes)");
            }
        }

        if (result.WatchsetWarnings is { Count: > 0 })
        {
            builder.AppendLine();
            builder.AppendLine("Watchset warnings:");
            foreach (var warning in result.WatchsetWarnings)
            {
                builder.AppendLine($"- {warning}");
            }
        }

        if (result.Warnings is { Count: > 0 })
        {
            builder.AppendLine();
            builder.AppendLine("Warnings:");
            foreach (var warning in result.Warnings)
            {
                builder.AppendLine($"- {warning}");
            }
        }
    }

    private static string FormatDuration(long? milliseconds) =>
        milliseconds.HasValue ? $"{milliseconds.Value} ms" : "n/a";

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
