using System.Text.Json;

namespace RiftReader.Reader.Sessions;

public static class SessionPackageLoader
{
    private static readonly JsonSerializerOptions JsonOptions = new()
    {
        PropertyNameCaseInsensitive = true
    };

    public static SessionPackageManifest? TryLoadManifest(string? inputPath, out string? error)
    {
        error = null;

        if (string.IsNullOrWhiteSpace(inputPath))
        {
            error = "A session package path is required.";
            return null;
        }

        var resolvedPath = Path.GetFullPath(inputPath);
        string manifestPath;

        if (Directory.Exists(resolvedPath))
        {
            manifestPath = Path.Combine(resolvedPath, "package-manifest.json");
        }
        else if (File.Exists(resolvedPath))
        {
            manifestPath = resolvedPath;
        }
        else
        {
            error = $"Session package path '{resolvedPath}' was not found.";
            return null;
        }

        if (!File.Exists(manifestPath))
        {
            error = $"Session package manifest '{manifestPath}' was not found.";
            return null;
        }

        try
        {
            var json = File.ReadAllText(manifestPath);
            var manifest = JsonSerializer.Deserialize<SessionPackageManifest>(json, JsonOptions);
            if (manifest is null)
            {
                error = $"Session package manifest '{manifestPath}' did not contain a valid document.";
                return null;
            }

            return manifest with
            {
                SessionDirectory = string.IsNullOrWhiteSpace(manifest.SessionDirectory)
                    ? Path.GetDirectoryName(manifestPath)
                    : manifest.SessionDirectory
            };
        }
        catch (JsonException ex)
        {
            error = $"Unable to parse session package manifest '{manifestPath}': {ex.Message}";
            return null;
        }
        catch (Exception ex)
        {
            error = $"Unable to read session package manifest '{manifestPath}': {ex.Message}";
            return null;
        }
    }

    public static SessionRecordResult? TryLoadRecordingManifest(string? filePath, out string? error)
    {
        error = null;

        if (string.IsNullOrWhiteSpace(filePath))
        {
            error = "A recording manifest path is required.";
            return null;
        }

        var resolvedPath = Path.GetFullPath(filePath);
        if (!File.Exists(resolvedPath))
        {
            error = $"Recording manifest '{resolvedPath}' was not found.";
            return null;
        }

        try
        {
            var json = File.ReadAllText(resolvedPath);
            var manifest = JsonSerializer.Deserialize<SessionRecordResult>(json, JsonOptions);
            if (manifest is null)
            {
                error = $"Recording manifest '{resolvedPath}' did not contain a valid document.";
                return null;
            }

            return manifest;
        }
        catch (JsonException ex)
        {
            error = $"Unable to parse recording manifest '{resolvedPath}': {ex.Message}";
            return null;
        }
        catch (Exception ex)
        {
            error = $"Unable to read recording manifest '{resolvedPath}': {ex.Message}";
            return null;
        }
    }

    public static IReadOnlyList<SessionSampleRecord>? TryLoadSamples(string? filePath, out string? error)
    {
        error = null;

        if (string.IsNullOrWhiteSpace(filePath))
        {
            error = "A samples.ndjson path is required.";
            return null;
        }

        var resolvedPath = Path.GetFullPath(filePath);
        if (!File.Exists(resolvedPath))
        {
            error = $"Samples file '{resolvedPath}' was not found.";
            return null;
        }

        try
        {
            var samples = new List<SessionSampleRecord>();
            var lineNumber = 0;

            foreach (var line in File.ReadLines(resolvedPath))
            {
                lineNumber++;
                if (string.IsNullOrWhiteSpace(line))
                {
                    continue;
                }

                var sample = JsonSerializer.Deserialize<SessionSampleRecord>(line, JsonOptions);
                if (sample is null)
                {
                    error = $"Samples file '{resolvedPath}' contained an invalid row at line {lineNumber}.";
                    return null;
                }

                samples.Add(sample);
            }

            return samples;
        }
        catch (JsonException ex)
        {
            error = $"Unable to parse samples file '{resolvedPath}': {ex.Message}";
            return null;
        }
        catch (Exception ex)
        {
            error = $"Unable to read samples file '{resolvedPath}': {ex.Message}";
            return null;
        }
    }

    public static IReadOnlyList<SessionMarkerRecord>? TryLoadMarkers(string? filePath, out string? error)
    {
        error = null;

        if (string.IsNullOrWhiteSpace(filePath))
        {
            return Array.Empty<SessionMarkerRecord>();
        }

        var resolvedPath = Path.GetFullPath(filePath);
        if (!File.Exists(resolvedPath))
        {
            error = $"Markers file '{resolvedPath}' was not found.";
            return null;
        }

        try
        {
            var markers = new List<SessionMarkerRecord>();
            var lineNumber = 0;

            foreach (var line in File.ReadLines(resolvedPath))
            {
                lineNumber++;
                if (string.IsNullOrWhiteSpace(line))
                {
                    continue;
                }

                var marker = JsonSerializer.Deserialize<SessionMarkerRecord>(line, JsonOptions);
                if (marker is null)
                {
                    error = $"Markers file '{resolvedPath}' contained an invalid row at line {lineNumber}.";
                    return null;
                }

                markers.Add(marker);
            }

            return markers;
        }
        catch (JsonException ex)
        {
            error = $"Unable to parse markers file '{resolvedPath}': {ex.Message}";
            return null;
        }
        catch (Exception ex)
        {
            error = $"Unable to read markers file '{resolvedPath}': {ex.Message}";
            return null;
        }
    }
}
