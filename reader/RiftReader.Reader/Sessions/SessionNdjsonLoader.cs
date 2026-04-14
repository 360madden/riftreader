using System.Text.Json;

namespace RiftReader.Reader.Sessions;

public static class SessionNdjsonLoader
{
    private static readonly JsonSerializerOptions JsonOptions = new()
    {
        PropertyNameCaseInsensitive = true
    };

    public static IReadOnlyList<SessionSampleRecord>? TryLoadSamples(string? filePath, out string? error) =>
        TryLoadNdjson(filePath, "session samples", out error, static (line, options) => JsonSerializer.Deserialize<SessionSampleRecord>(line, options));

    public static IReadOnlyList<SessionMarkerRecord>? TryLoadMarkers(string? filePath, out string? error) =>
        TryLoadNdjson(filePath, "session markers", out error, static (line, options) => JsonSerializer.Deserialize<SessionMarkerRecord>(line, options));

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

            T? value;
            try
            {
                value = parseLine(line, JsonOptions);
            }
            catch (JsonException ex)
            {
                error = $"Unable to parse {description} file '{fullPath}' at line {index + 1}: {ex.Message}";
                return null;
            }

            if (value is not null)
            {
                results.Add(value);
            }
        }

        error = null;
        return results;
    }
}
