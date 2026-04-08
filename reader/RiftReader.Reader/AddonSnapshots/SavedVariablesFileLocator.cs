namespace RiftReader.Reader.AddonSnapshots;

internal static class SavedVariablesFileLocator
{
    public static string? TryFindLatest(string fileName, out string? error)
    {
        var documentsPath = Environment.GetFolderPath(Environment.SpecialFolder.MyDocuments);

        if (string.IsNullOrWhiteSpace(documentsPath) || !Directory.Exists(documentsPath))
        {
            error = "Unable to locate the user's Documents folder for Rift saved variables.";
            return null;
        }

        var riftSavedRoot = Path.Combine(documentsPath, "RIFT", "Interface", "Saved");

        if (!Directory.Exists(riftSavedRoot))
        {
            error = $"Rift saved variables folder was not found: '{riftSavedRoot}'.";
            return null;
        }

        string[] matches;

        try
        {
            matches = Directory.GetFiles(riftSavedRoot, fileName, SearchOption.AllDirectories);
        }
        catch (Exception ex)
        {
            error = $"Unable to search '{riftSavedRoot}' for '{fileName}': {ex.Message}";
            return null;
        }

        if (matches.Length == 0)
        {
            error = $"No '{fileName}' files were found under '{riftSavedRoot}'.";
            return null;
        }

        error = null;
        return matches
            .OrderByDescending(path => File.GetLastWriteTimeUtc(path))
            .First();
    }

    public static string? ResolveExplicitPath(string explicitPath, out string? error)
    {
        string resolvedPath;

        try
        {
            resolvedPath = Path.GetFullPath(explicitPath);
        }
        catch (Exception ex)
        {
            error = $"Invalid addon snapshot path '{explicitPath}': {ex.Message}";
            return null;
        }

        if (!File.Exists(resolvedPath))
        {
            error = $"Addon snapshot file was not found: '{resolvedPath}'.";
            return null;
        }

        error = null;
        return resolvedPath;
    }
}
