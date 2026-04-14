using System.Text.Json;

namespace RiftReader.Reader.Sessions;

public static class SessionPackageManifestLoader
{
    private const int SupportedSchemaVersion = 1;

    private static readonly JsonSerializerOptions JsonOptions = new()
    {
        PropertyNameCaseInsensitive = true
    };

    public static SessionPackageManifestDocument? TryLoad(string? sessionDirectory, out string? error)
    {
        if (string.IsNullOrWhiteSpace(sessionDirectory))
        {
            error = "A session directory is required.";
            return null;
        }

        var fullDirectory = Path.GetFullPath(sessionDirectory);
        if (!Directory.Exists(fullDirectory))
        {
            error = $"Session directory '{fullDirectory}' was not found.";
            return null;
        }

        var manifestPath = Path.Combine(fullDirectory, "package-manifest.json");
        if (!File.Exists(manifestPath))
        {
            error = $"Session package manifest '{manifestPath}' was not found.";
            return null;
        }

        string json;
        try
        {
            json = File.ReadAllText(manifestPath);
        }
        catch (Exception ex)
        {
            error = $"Unable to read session package manifest '{manifestPath}': {ex.Message}";
            return null;
        }

        SessionPackageManifestDocument? document;
        try
        {
            document = JsonSerializer.Deserialize<SessionPackageManifestDocument>(json, JsonOptions);
        }
        catch (JsonException ex)
        {
            error = $"Unable to parse session package manifest '{manifestPath}': {ex.Message}";
            return null;
        }

        if (document is null)
        {
            error = $"Session package manifest '{manifestPath}' did not contain a valid document.";
            return null;
        }

        if (document.SchemaVersion.HasValue && document.SchemaVersion.Value != SupportedSchemaVersion)
        {
            error = $"Session package manifest '{manifestPath}' uses unsupported schema version {document.SchemaVersion.Value}. Supported version: {SupportedSchemaVersion}.";
            return null;
        }

        error = null;
        return new SessionPackageManifestDocument(
            SchemaVersion: document.SchemaVersion ?? SupportedSchemaVersion,
            Mode: document.Mode,
            Status: document.Status,
            IntegrityStatus: document.IntegrityStatus,
            GeneratedAtUtc: document.GeneratedAtUtc,
            SessionId: document.SessionId,
            Label: document.Label,
            SessionDirectory: string.IsNullOrWhiteSpace(document.SessionDirectory) ? fullDirectory : document.SessionDirectory,
            WatchsetFile: document.WatchsetFile,
            CaptureConsistencyFile: document.CaptureConsistencyFile,
            ReaderBridgeSnapshotFile: document.ReaderBridgeSnapshotFile,
            ArtifactDirectory: document.ArtifactDirectory,
            RecordingManifestFile: document.RecordingManifestFile,
            SamplesFile: document.SamplesFile,
            MarkersFile: document.MarkersFile,
            ModulesFile: document.ModulesFile,
            Interrupted: document.Interrupted,
            SessionMarkerInputFile: document.SessionMarkerInputFile,
            MarkerCount: document.MarkerCount,
            MarkerKinds: document.MarkerKinds?
                .Where(static kind => !string.IsNullOrWhiteSpace(kind))
                .Select(static kind => kind!)
                .ToArray(),
            RequestedRegionByteCount: document.RequestedRegionByteCount,
            TotalBytesRead: document.TotalBytesRead,
            TotalRegionReadFailures: document.TotalRegionReadFailures,
            ProcessId: document.ProcessId,
            ProcessName: document.ProcessName,
            WatchsetRegionCount: document.WatchsetRegionCount,
            SampleCount: document.SampleCount,
            IntervalMilliseconds: document.IntervalMilliseconds,
            MissingFiles: document.MissingFiles?
                .Where(static path => !string.IsNullOrWhiteSpace(path))
                .Select(static path => path!)
                .ToArray(),
            FailureMessage: document.FailureMessage,
            CopiedArtifacts: document.CopiedArtifacts?
                .Where(static artifact => artifact is not null)
                .Select(static artifact => artifact!)
                .ToArray(),
            Warnings: document.Warnings?
                .Where(static warning => !string.IsNullOrWhiteSpace(warning))
                .Select(static warning => warning!)
                .ToArray());
    }
}
