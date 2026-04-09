using System.Text.Json;

namespace RiftReader.Reader.AddonSnapshots;

public static class PlayerOwnerComponentArtifactLoader
{
    private const string RelativePath = @"scripts\captures\player-owner-components.json";

    private static readonly JsonSerializerOptions JsonOptions = new()
    {
        PropertyNameCaseInsensitive = true
    };

    public static PlayerOwnerComponentArtifactDocument? TryLoad(string? explicitPath, out string? error)
    {
        error = null;

        var sourceFile = ResolveSourceFile(explicitPath);
        if (string.IsNullOrWhiteSpace(sourceFile) || !File.Exists(sourceFile))
        {
            error = $"Unable to find the player owner-component artifact '{sourceFile ?? "<default>"}'.";
            return null;
        }

        try
        {
            var json = File.ReadAllText(sourceFile);
            var document = JsonSerializer.Deserialize<PlayerOwnerComponentArtifactDocument>(json, JsonOptions);

            if (document is null)
            {
                error = $"The player owner-component artifact '{sourceFile}' did not contain a readable document.";
                return null;
            }

            return document with
            {
                SourceFile = sourceFile,
                LoadedAtUtc = DateTimeOffset.UtcNow
            };
        }
        catch (Exception ex)
        {
            error = $"Unable to load the player owner-component artifact '{sourceFile}': {ex.Message}";
            return null;
        }
    }

    private static string ResolveSourceFile(string? explicitPath)
    {
        if (!string.IsNullOrWhiteSpace(explicitPath))
        {
            return Path.GetFullPath(explicitPath);
        }

        var repoRoot = TryFindRepoRoot(Directory.GetCurrentDirectory()) ?? Directory.GetCurrentDirectory();
        return Path.Combine(repoRoot, RelativePath);
    }

    private static string? TryFindRepoRoot(string startDirectory)
    {
        if (string.IsNullOrWhiteSpace(startDirectory))
        {
            return null;
        }

        var current = new DirectoryInfo(startDirectory);

        while (current is not null)
        {
            if (File.Exists(Path.Combine(current.FullName, "RiftReader.slnx")))
            {
                return current.FullName;
            }

            current = current.Parent;
        }

        return null;
    }
}
