using RiftReader.Reader.Sessions;

namespace RiftReader.Reader.Formatting;

public static class SessionInspectTextFormatter
{
    public static string Format(SessionInspectResult result)
    {
        var lines = new List<string>
        {
            $"Session id:                    {result.SessionId}",
            $"Session directory:             {result.SessionDirectory}",
            $"Label:                         {result.Label ?? "n/a"}",
            $"Process:                       {result.ProcessName ?? "n/a"} ({result.ProcessId?.ToString() ?? "n/a"})",
            $"Watchset regions:              {result.WatchsetRegionCount}",
            $"Declared/recorded samples:     {result.DeclaredSampleCount}/{result.RecordedSampleCount}",
            $"Markers:                       {result.MarkerCount}",
            $"Required regions:              {result.RequiredRegionCount}",
            $"Optional regions:              {result.OptionalRegionCount}",
            $"Required always readable:      {result.RequiredRegionsAlwaysReadable}",
            $"Required ever readable:        {result.RequiredRegionsEverReadable}",
            $"Optional ever readable:        {result.OptionalRegionsEverReadable}",
            $"Package warnings:              {result.PackageWarningCount}",
            $"Manifest warnings:             {result.ManifestWarningCount}"
        };

        if (result.TopRequiredFailureRegions.Count > 0)
        {
            lines.Add(string.Empty);
            lines.Add("Top required failure regions:");
            foreach (var region in result.TopRequiredFailureRegions)
            {
                lines.Add($"- {region.Name} [{region.Category}] failures={region.FailureCount} successes={region.SuccessCount} last-error={region.LastError ?? "n/a"}");
            }
        }

        if (result.TopReadableRegionsByChange.Count > 0)
        {
            lines.Add(string.Empty);
            lines.Add("Top readable changing regions:");
            foreach (var region in result.TopReadableRegionsByChange)
            {
                lines.Add($"- {region.Name} [{region.Category}] distinct-values={region.DistinctValueCount} successes={region.SuccessCount} failures={region.FailureCount}");
            }
        }

        if (result.Markers.Count > 0)
        {
            lines.Add(string.Empty);
            lines.Add("Markers:");
            foreach (var marker in result.Markers)
            {
                lines.Add($"- {marker.Kind} @ {marker.ElapsedMilliseconds?.ToString() ?? "n/a"} ms label={marker.Label ?? "n/a"}");
            }
        }

        return string.Join(Environment.NewLine, lines);
    }
}
