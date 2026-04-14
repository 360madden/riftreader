using System.Text.Json;

namespace RiftReader.Reader.Sessions;

public static class SessionRecordManifestLoader
{
    private const int SupportedSchemaVersion = 1;

    private static readonly JsonSerializerOptions JsonOptions = new()
    {
        PropertyNameCaseInsensitive = true
    };

    public static SessionRecordResult? TryLoad(string? filePath, out string? error)
    {
        if (string.IsNullOrWhiteSpace(filePath))
        {
            error = "A session recording manifest file is required.";
            return null;
        }

        var fullPath = Path.GetFullPath(filePath);
        if (!File.Exists(fullPath))
        {
            error = $"Session recording manifest '{fullPath}' was not found.";
            return null;
        }

        string json;
        try
        {
            json = File.ReadAllText(fullPath);
        }
        catch (Exception ex)
        {
            error = $"Unable to read session recording manifest '{fullPath}': {ex.Message}";
            return null;
        }

        SessionRecordResult? document;
        try
        {
            document = JsonSerializer.Deserialize<SessionRecordResult>(json, JsonOptions);
        }
        catch (JsonException ex)
        {
            error = $"Unable to parse session recording manifest '{fullPath}': {ex.Message}";
            return null;
        }

        if (document is null)
        {
            error = $"Session recording manifest '{fullPath}' did not contain a valid document.";
            return null;
        }

        if (document.SchemaVersion != SupportedSchemaVersion)
        {
            error = $"Session recording manifest '{fullPath}' uses unsupported schema version {document.SchemaVersion}. Supported version: {SupportedSchemaVersion}.";
            return null;
        }

        error = null;
        return document;
    }
}
