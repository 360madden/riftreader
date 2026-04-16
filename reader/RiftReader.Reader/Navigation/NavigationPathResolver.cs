namespace RiftReader.Reader.Navigation;

public static class NavigationPathResolver
{
    private const string WaypointRelativePath = @"scripts\navigation\waypoints.json";
    private const string MovementScriptRelativePath = @"scripts\post-rift-key.ps1";

    public static string ResolveWaypointFile(string? explicitPath)
    {
        if (!string.IsNullOrWhiteSpace(explicitPath))
        {
            return Path.GetFullPath(explicitPath);
        }

        var repoRoot = TryFindRepoRoot(Directory.GetCurrentDirectory()) ?? Directory.GetCurrentDirectory();
        return Path.Combine(repoRoot, WaypointRelativePath);
    }

    public static string ResolveMovementScriptFile(string? explicitPath = null)
    {
        if (!string.IsNullOrWhiteSpace(explicitPath))
        {
            return Path.GetFullPath(explicitPath);
        }

        var repoRoot = TryFindRepoRoot(Directory.GetCurrentDirectory()) ?? Directory.GetCurrentDirectory();
        return Path.Combine(repoRoot, MovementScriptRelativePath);
    }

    public static string? TryFindRepoRoot(string startDirectory)
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
