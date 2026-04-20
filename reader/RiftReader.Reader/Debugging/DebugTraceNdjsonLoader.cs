using System.Text.Json;
using RiftReader.Reader.Processes;

namespace RiftReader.Reader.Debugging;

public static class DebugTraceNdjsonLoader
{
    private static readonly JsonSerializerOptions JsonOptions = new()
    {
        PropertyNameCaseInsensitive = true
    };

    public static IReadOnlyList<DebugTraceEventRecord>? TryLoadEvents(string? filePath, out string? error) =>
        TryLoadNdjson(filePath, "debug trace events", out error, static (line, options) => JsonSerializer.Deserialize<DebugTraceEventRecord>(line, options));

    public static IReadOnlyList<DebugTraceHitRecord>? TryLoadHits(string? filePath, out string? error) =>
        TryLoadNdjson(filePath, "debug trace hits", out error, static (line, options) => JsonSerializer.Deserialize<DebugTraceHitRecord>(line, options));

    public static IReadOnlyList<DebugTraceMarkerRecord>? TryLoadMarkers(string? filePath, out string? error) =>
        TryLoadNdjson(filePath, "debug trace markers", out error, static (line, options) => JsonSerializer.Deserialize<DebugTraceMarkerRecord>(line, options));

    public static IReadOnlyList<T>? TryLoadJsonArray<T>(string? filePath, string description, out string? error)
    {
        if (string.IsNullOrWhiteSpace(filePath))
        {
            error = $"A file path is required for {description}.";
            return null;
        }

        var fullPath = Path.GetFullPath(filePath);
        if (!File.Exists(fullPath))
        {
            error = $"{description} file '{fullPath}' was not found.";
            return null;
        }

        try
        {
            var json = File.ReadAllText(fullPath);
            var values = JsonSerializer.Deserialize<T[]>(json, JsonOptions);
            error = null;
            return values ?? Array.Empty<T>();
        }
        catch (Exception ex)
        {
            error = $"Unable to load {description} file '{fullPath}': {ex.Message}";
            return null;
        }
    }

    private static IReadOnlyList<T>? TryLoadNdjson<T>(
        string? filePath,
        string description,
        out string? error,
        Func<string, JsonSerializerOptions, T?> parseLine)
    {
        if (string.IsNullOrWhiteSpace(filePath))
        {
            error = $"A file path is required for {description}.";
            return null;
        }

        var fullPath = Path.GetFullPath(filePath);
        if (!File.Exists(fullPath))
        {
            error = $"{description} file '{fullPath}' was not found.";
            return null;
        }

        var results = new List<T>();
        string[] lines;
        try
        {
            lines = File.ReadAllLines(fullPath);
        }
        catch (Exception ex)
        {
            error = $"Unable to read {description} file '{fullPath}': {ex.Message}";
            return null;
        }

        for (var index = 0; index < lines.Length; index++)
        {
            var line = lines[index];
            if (string.IsNullOrWhiteSpace(line))
            {
                continue;
            }

            try
            {
                var value = parseLine(line, JsonOptions);
                if (value is not null)
                {
                    results.Add(value);
                }
            }
            catch (JsonException ex)
            {
                error = $"Unable to parse {description} file '{fullPath}' at line {index + 1}: {ex.Message}";
                return null;
            }
        }

        error = null;
        return results;
    }
}
