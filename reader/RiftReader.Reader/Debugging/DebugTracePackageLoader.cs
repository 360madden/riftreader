using System.Text.Json;
using RiftReader.Reader.Processes;

namespace RiftReader.Reader.Debugging;

public static class DebugTracePackageLoader
{
    private const int SupportedSchemaVersion = 1;

    private static readonly JsonSerializerOptions JsonOptions = new()
    {
        PropertyNameCaseInsensitive = true
    };

    public static DebugTracePackageManifestDocument? TryLoadPackage(string? traceDirectory, out string? error)
    {
        if (string.IsNullOrWhiteSpace(traceDirectory))
        {
            error = "A debug trace directory is required.";
            return null;
        }

        var fullDirectory = Path.GetFullPath(traceDirectory);
        if (!Directory.Exists(fullDirectory))
        {
            error = $"Debug trace directory '{fullDirectory}' was not found.";
            return null;
        }

        var manifestPath = Path.Combine(fullDirectory, "package-manifest.json");
        if (!File.Exists(manifestPath))
        {
            error = $"Debug trace package manifest '{manifestPath}' was not found.";
            return null;
        }

        try
        {
            var json = File.ReadAllText(manifestPath);
            var document = JsonSerializer.Deserialize<DebugTracePackageManifestDocument>(json, JsonOptions);
            if (document is null)
            {
                error = $"Debug trace package manifest '{manifestPath}' did not contain a valid document.";
                return null;
            }

            if (document.SchemaVersion.HasValue && document.SchemaVersion.Value != SupportedSchemaVersion)
            {
                error = $"Debug trace package manifest '{manifestPath}' uses unsupported schema version {document.SchemaVersion.Value}. Supported version: {SupportedSchemaVersion}.";
                return null;
            }

            error = null;
            return document with
            {
                SchemaVersion = document.SchemaVersion ?? SupportedSchemaVersion,
                TraceDirectory = string.IsNullOrWhiteSpace(document.TraceDirectory) ? fullDirectory : document.TraceDirectory
            };
        }
        catch (Exception ex)
        {
            error = $"Unable to load debug trace package manifest '{manifestPath}': {ex.Message}";
            return null;
        }
    }

    public static DebugTraceResult? TryLoadTraceManifest(string? filePath, out string? error)
    {
        if (string.IsNullOrWhiteSpace(filePath))
        {
            error = "A debug trace manifest file is required.";
            return null;
        }

        var fullPath = Path.GetFullPath(filePath);
        if (!File.Exists(fullPath))
        {
            error = $"Debug trace manifest '{fullPath}' was not found.";
            return null;
        }

        try
        {
            var json = File.ReadAllText(fullPath);
            var document = JsonSerializer.Deserialize<DebugTraceResult>(json, JsonOptions);
            if (document is null)
            {
                error = $"Debug trace manifest '{fullPath}' did not contain a valid document.";
                return null;
            }

            if (document.SchemaVersion != SupportedSchemaVersion)
            {
                error = $"Debug trace manifest '{fullPath}' uses unsupported schema version {document.SchemaVersion}. Supported version: {SupportedSchemaVersion}.";
                return null;
            }

            error = null;
            return document;
        }
        catch (Exception ex)
        {
            error = $"Unable to load debug trace manifest '{fullPath}': {ex.Message}";
            return null;
        }
    }

    public static DebugTraceInspectResult? TryInspect(string? traceDirectory, out string? error)
    {
        var package = TryLoadPackage(traceDirectory, out error);
        if (package is null)
        {
            return null;
        }

        var warnings = new List<string>();
        string? traceManifestError = null;
        var traceManifest = !string.IsNullOrWhiteSpace(package.RecordingManifestFile)
            ? TryLoadTraceManifest(package.RecordingManifestFile, out traceManifestError)
            : null;

        if (traceManifest is null && !string.IsNullOrWhiteSpace(package.RecordingManifestFile))
        {
            warnings.Add(traceManifestError ?? $"Unable to load debug trace manifest '{package.RecordingManifestFile}'.");
        }

        string? eventsError = null;
        var events = !string.IsNullOrWhiteSpace(package.EventsFile)
            ? DebugTraceNdjsonLoader.TryLoadEvents(package.EventsFile, out eventsError)
            : Array.Empty<DebugTraceEventRecord>();
        if (events is null)
        {
            warnings.Add(eventsError ?? $"Unable to load debug trace events '{package.EventsFile}'.");
            events = Array.Empty<DebugTraceEventRecord>();
        }

        string? hitsError = null;
        var hits = !string.IsNullOrWhiteSpace(package.HitsFile)
            ? DebugTraceNdjsonLoader.TryLoadHits(package.HitsFile, out hitsError)
            : Array.Empty<DebugTraceHitRecord>();
        if (hits is null)
        {
            warnings.Add(hitsError ?? $"Unable to load debug trace hits '{package.HitsFile}'.");
            hits = Array.Empty<DebugTraceHitRecord>();
        }

        string? markersError = null;
        var markers = !string.IsNullOrWhiteSpace(package.MarkersFile)
            ? DebugTraceNdjsonLoader.TryLoadMarkers(package.MarkersFile, out markersError)
            : Array.Empty<DebugTraceMarkerRecord>();
        if (markers is null)
        {
            warnings.Add(markersError ?? $"Unable to load debug trace markers '{package.MarkersFile}'.");
            markers = Array.Empty<DebugTraceMarkerRecord>();
        }

        string? modulesError = null;
        var modules = !string.IsNullOrWhiteSpace(package.ModulesFile)
            ? DebugTraceNdjsonLoader.TryLoadJsonArray<ProcessModuleInfo>(package.ModulesFile, "debug trace modules", out modulesError)
            : Array.Empty<ProcessModuleInfo>();
        if (modules is null)
        {
            warnings.Add(modulesError ?? $"Unable to load debug trace modules '{package.ModulesFile}'.");
            modules = Array.Empty<ProcessModuleInfo>();
        }

        string? fingerprintError = null;
        var fingerprints = !string.IsNullOrWhiteSpace(package.InstructionFingerprintsFile)
            ? DebugTraceNdjsonLoader.TryLoadJsonArray<DebugInstructionFingerprintRecord>(package.InstructionFingerprintsFile, "debug trace instruction fingerprints", out fingerprintError)
            : Array.Empty<DebugInstructionFingerprintRecord>();
        if (fingerprints is null)
        {
            warnings.Add(fingerprintError ?? $"Unable to load debug trace instruction fingerprints '{package.InstructionFingerprintsFile}'.");
            fingerprints = Array.Empty<DebugInstructionFingerprintRecord>();
        }

        string? clusterError = null;
        var hitClusters = !string.IsNullOrWhiteSpace(package.HitClustersFile)
            ? DebugTraceNdjsonLoader.TryLoadJsonArray<DebugHitClusterRecord>(package.HitClustersFile, "debug trace hit clusters", out clusterError)
            : Array.Empty<DebugHitClusterRecord>();
        if (hitClusters is null)
        {
            warnings.Add(clusterError ?? $"Unable to load debug trace hit clusters '{package.HitClustersFile}'.");
            hitClusters = Array.Empty<DebugHitClusterRecord>();
        }

        string? suggestionError = null;
        var suggestions = !string.IsNullOrWhiteSpace(package.FollowUpSuggestionsFile)
            ? DebugTraceNdjsonLoader.TryLoadJsonArray<DebugFollowUpSuggestionRecord>(package.FollowUpSuggestionsFile, "debug trace follow-up suggestions", out suggestionError)
            : Array.Empty<DebugFollowUpSuggestionRecord>();
        if (suggestions is null)
        {
            warnings.Add(suggestionError ?? $"Unable to load debug trace follow-up suggestions '{package.FollowUpSuggestionsFile}'.");
            suggestions = Array.Empty<DebugFollowUpSuggestionRecord>();
        }

        warnings.AddRange(package.Warnings?.Where(static warning => !string.IsNullOrWhiteSpace(warning)) ?? []);
        warnings = warnings
            .Where(static warning => !string.IsNullOrWhiteSpace(warning))
            .Distinct(StringComparer.OrdinalIgnoreCase)
            .ToList();

        error = null;
        return new DebugTraceInspectResult(
            SchemaVersion: package.SchemaVersion ?? SupportedSchemaVersion,
            Mode: "debug-trace-summary",
            TraceDirectory: package.TraceDirectory ?? Path.GetFullPath(traceDirectory!),
            Package: package,
            TraceManifest: traceManifest,
            Events: events,
            Hits: hits,
            Markers: markers,
            Modules: modules,
            InstructionFingerprints: fingerprints,
            HitClusters: hitClusters,
            FollowUpSuggestions: suggestions,
            Warnings: warnings);
    }
}
