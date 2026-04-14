using System.Text.Json;

namespace RiftReader.Reader.Sessions;

public static class SessionWatchsetLoader
{
    private const int SupportedSchemaVersion = 1;

    private static readonly JsonSerializerOptions JsonOptions = new()
    {
        PropertyNameCaseInsensitive = true
    };

    public static SessionWatchsetDocument? TryLoad(string? filePath, out string? error)
    {
        if (string.IsNullOrWhiteSpace(filePath))
        {
            error = "A session watchset file is required.";
            return null;
        }

        var fullPath = Path.GetFullPath(filePath);
        if (!File.Exists(fullPath))
        {
            error = $"Session watchset file '{fullPath}' was not found.";
            return null;
        }

        string json;
        try
        {
            json = File.ReadAllText(fullPath);
        }
        catch (Exception ex)
        {
            error = $"Unable to read session watchset file '{fullPath}': {ex.Message}";
            return null;
        }

        SessionWatchsetDocument? document;
        try
        {
            document = JsonSerializer.Deserialize<SessionWatchsetDocument>(json, JsonOptions);
        }
        catch (JsonException ex)
        {
            error = $"Unable to parse session watchset file '{fullPath}': {ex.Message}";
            return null;
        }

        if (document is null)
        {
            error = $"Session watchset file '{fullPath}' did not contain a valid document.";
            return null;
        }

        if (document.SchemaVersion.HasValue && document.SchemaVersion.Value != SupportedSchemaVersion)
        {
            error = $"Session watchset file '{fullPath}' uses unsupported schema version {document.SchemaVersion.Value}. Supported version: {SupportedSchemaVersion}.";
            return null;
        }

        var normalizedRegions = document.Regions?
            .Where(static region => region is not null)
            .Select(static region => region!)
            .ToArray()
            ?? Array.Empty<SessionWatchRegion>();

        if (normalizedRegions.Length == 0)
        {
            error = $"Session watchset file '{fullPath}' does not define any regions.";
            return null;
        }

        for (var index = 0; index < normalizedRegions.Length; index++)
        {
            var region = normalizedRegions[index];
            if (string.IsNullOrWhiteSpace(region.Name))
            {
                error = $"Session watchset region #{index + 1} in '{fullPath}' is missing a name.";
                return null;
            }

            if (string.IsNullOrWhiteSpace(region.Address))
            {
                error = $"Session watchset region '{region.Name}' in '{fullPath}' is missing an address.";
                return null;
            }

            if (region.Length <= 0)
            {
                error = $"Session watchset region '{region.Name}' in '{fullPath}' has an invalid length ({region.Length}).";
                return null;
            }
        }

        error = null;
        return new SessionWatchsetDocument(
            Mode: document.Mode,
            GeneratedAtUtc: document.GeneratedAtUtc,
            SchemaVersion: document.SchemaVersion ?? SupportedSchemaVersion,
            ProcessName: document.ProcessName,
            PreferredSourceAddress: document.PreferredSourceAddress,
            Artifacts: document.Artifacts?
                .Where(static artifact => artifact is not null)
                .Select(static artifact => artifact!)
                .ToArray(),
            Warnings: document.Warnings?
                .Where(static warning => !string.IsNullOrWhiteSpace(warning))
                .Select(static warning => warning!)
                .ToArray(),
            Regions: normalizedRegions);
    }
}
