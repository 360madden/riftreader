using System.Text.Json;

namespace RiftReader.Reader.Scanning;

public static class PlayerSignatureCeConfirmationLoader
{
    private static readonly JsonSerializerOptions JsonOptions = new()
    {
        PropertyNameCaseInsensitive = true
    };

    public static PlayerSignatureCeConfirmationDocument? TryLoad(string? filePath, out string? error)
    {
        error = null;

        var resolvedPath = ResolvePath(filePath);
        if (string.IsNullOrWhiteSpace(resolvedPath))
        {
            error = "No CE player-family confirmation file was found.";
            return null;
        }

        try
        {
            var json = File.ReadAllText(resolvedPath);
            var document = JsonSerializer.Deserialize<PlayerSignatureCeConfirmationDocument>(json, JsonOptions);
            if (document is null)
            {
                error = $"CE confirmation file '{resolvedPath}' did not contain a readable document.";
                return null;
            }

            return document with { ConfirmationFile = resolvedPath };
        }
        catch (Exception ex)
        {
            error = $"Unable to load CE confirmation file '{resolvedPath}': {ex.Message}";
            return null;
        }
    }

    private static string? ResolvePath(string? filePath)
    {
        if (!string.IsNullOrWhiteSpace(filePath))
        {
            var explicitPath = Path.GetFullPath(filePath);
            return File.Exists(explicitPath) ? explicitPath : null;
        }

        const string relativePath = @"scripts\captures\ce-smart-player-family.json";
        var current = new DirectoryInfo(Directory.GetCurrentDirectory());

        while (current is not null)
        {
            var candidate = Path.Combine(current.FullName, relativePath);
            if (File.Exists(candidate))
            {
                return candidate;
            }

            current = current.Parent;
        }

        return null;
    }
}
