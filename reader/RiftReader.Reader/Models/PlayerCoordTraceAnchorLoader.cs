using System.Text.Json;

namespace RiftReader.Reader.Models;

public static class PlayerCoordTraceAnchorLoader
{
    public static PlayerCoordTraceAnchorDocument? TryLoad(string? explicitPath, out string? error)
    {
        error = null;

        var sourceFile = ResolveSourceFile(explicitPath);
        if (string.IsNullOrWhiteSpace(sourceFile) || !File.Exists(sourceFile))
        {
            error = $"Unable to find the player coord trace file '{sourceFile ?? "<default>"}'.";
            return null;
        }

        try
        {
            var json = File.ReadAllText(sourceFile);
            var document = JsonSerializer.Deserialize<PlayerCoordTraceAnchorDocument>(
                json,
                new JsonSerializerOptions
                {
                    PropertyNameCaseInsensitive = true
                });

            if (document is null || document.Trace is null)
            {
                error = $"The player coord trace file '{sourceFile}' did not contain a trace payload.";
                return null;
            }

            return document with { SourceFile = sourceFile };
        }
        catch (Exception ex)
        {
            error = $"Unable to load the player coord trace file '{sourceFile}': {ex.Message}";
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
        return Path.Combine(repoRoot, "scripts", "captures", "player-coord-write-trace.json");
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
