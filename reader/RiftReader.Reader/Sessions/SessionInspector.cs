namespace RiftReader.Reader.Sessions;

public static class SessionInspector
{
    public static SessionInspectResult? TryInspect(string? sessionPath, out string? error)
    {
        error = null;

        var packageManifest = SessionPackageLoader.TryLoadManifest(sessionPath, out error);
        if (packageManifest is null)
        {
            return null;
        }

        var recordingManifest = SessionPackageLoader.TryLoadRecordingManifest(packageManifest.RecordingManifestFile, out error);
        if (recordingManifest is null)
        {
            return null;
        }

        var samples = SessionPackageLoader.TryLoadSamples(recordingManifest.SamplesFile, out error);
        if (samples is null)
        {
            return null;
        }

        var markers = SessionPackageLoader.TryLoadMarkers(recordingManifest.MarkersFile, out error);
        if (markers is null)
        {
            return null;
        }

        var statsByRegion = new Dictionary<string, RegionStats>(StringComparer.OrdinalIgnoreCase);
        foreach (var sample in samples)
        {
            foreach (var region in sample.Regions)
            {
                if (!statsByRegion.TryGetValue(region.Name, out var stats))
                {
                    stats = new RegionStats(region.Name, region.Category, region.Required, region.Address, region.Length);
                    statsByRegion.Add(region.Name, stats);
                }

                stats.Observe(region);
            }
        }

        var orderedRegionStats = statsByRegion.Values
            .OrderByDescending(static region => region.Required)
            .ThenByDescending(static region => region.DistinctValueCount)
            .ThenBy(static region => region.Name, StringComparer.OrdinalIgnoreCase)
            .ToArray();

        var topReadableRegionsByChange = orderedRegionStats
            .Where(static region => region.SuccessCount > 0)
            .OrderByDescending(static region => region.DistinctValueCount)
            .ThenByDescending(static region => region.SuccessCount)
            .ThenBy(static region => region.Name, StringComparer.OrdinalIgnoreCase)
            .Take(12)
            .Select(static region => region.ToResult())
            .ToArray();

        var topRequiredFailureRegions = orderedRegionStats
            .Where(static region => region.Required && region.FailureCount > 0)
            .OrderByDescending(static region => region.FailureCount)
            .ThenBy(static region => region.Name, StringComparer.OrdinalIgnoreCase)
            .Take(12)
            .Select(static region => region.ToResult())
            .ToArray();

        return new SessionInspectResult(
            Mode: "inspect-session",
            SessionId: recordingManifest.SessionId,
            SessionDirectory: packageManifest.SessionDirectory ?? recordingManifest.OutputDirectory,
            Label: packageManifest.Label ?? recordingManifest.Label,
            ProcessName: recordingManifest.ProcessName,
            ProcessId: recordingManifest.ProcessId,
            WatchsetRegionCount: recordingManifest.WatchsetRegionCount,
            DeclaredSampleCount: recordingManifest.RequestedSampleCount,
            RecordedSampleCount: recordingManifest.RecordedSampleCount,
            MarkerCount: markers.Count,
            PackageWarningCount: packageManifest.Warnings?.Count ?? 0,
            ManifestWarningCount: recordingManifest.Warnings.Count,
            RequiredRegionCount: orderedRegionStats.Count(static region => region.Required),
            OptionalRegionCount: orderedRegionStats.Count(static region => !region.Required),
            RequiredRegionsAlwaysReadable: orderedRegionStats.Count(region => region.Required && region.FailureCount == 0 && region.SuccessCount == samples.Count),
            RequiredRegionsEverReadable: orderedRegionStats.Count(static region => region.Required && region.SuccessCount > 0),
            OptionalRegionsEverReadable: orderedRegionStats.Count(static region => !region.Required && region.SuccessCount > 0),
            PackageWarnings: packageManifest.Warnings?
                .Where(static warning => !string.IsNullOrWhiteSpace(warning))
                .Select(static warning => warning!)
                .ToArray()
                ?? Array.Empty<string>(),
            ManifestWarnings: recordingManifest.Warnings
                .Where(static warning => !string.IsNullOrWhiteSpace(warning))
                .ToArray(),
            TopReadableRegionsByChange: topReadableRegionsByChange,
            TopRequiredFailureRegions: topRequiredFailureRegions,
            Markers: markers
                .Select(static marker => new SessionMarkerSummary(
                    Kind: marker.Kind,
                    RecordedAtUtc: marker.RecordedAtUtc,
                    ElapsedMilliseconds: marker.ElapsedMilliseconds,
                    Label: marker.Label,
                    Message: marker.Message))
                .ToArray());
    }

    private sealed class RegionStats
    {
        private readonly HashSet<string> _distinctValues = new(StringComparer.Ordinal);

        public RegionStats(string name, string category, bool required, string? firstAddress, int? length)
        {
            Name = name;
            Category = category;
            Required = required;
            FirstAddress = firstAddress;
            Length = length;
        }

        public string Name { get; }
        public string Category { get; }
        public bool Required { get; }
        public string? FirstAddress { get; }
        public int? Length { get; }
        public int SuccessCount { get; private set; }
        public int FailureCount { get; private set; }
        public int DistinctValueCount => _distinctValues.Count;
        public string? LastError { get; private set; }

        public void Observe(SessionRegionSampleRecord region)
        {
            if (region.ReadSucceeded)
            {
                SuccessCount++;
                if (!string.IsNullOrWhiteSpace(region.BytesHex))
                {
                    _distinctValues.Add(region.BytesHex);
                }
            }
            else
            {
                FailureCount++;
                LastError = region.Error;
            }
        }

        public SessionRegionInspectResult ToResult() =>
            new(
                Name: Name,
                Category: Category,
                Required: Required,
                SuccessCount: SuccessCount,
                FailureCount: FailureCount,
                DistinctValueCount: DistinctValueCount,
                FirstAddress: FirstAddress,
                Length: Length,
                LastError: LastError);
    }
}
