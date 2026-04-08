using System.Globalization;
using System.Text.Json;

namespace RiftReader.Reader.Models;

public static class PlayerCurrentAnchorCacheStore
{
    private static readonly JsonSerializerOptions JsonOptions = new()
    {
        PropertyNameCaseInsensitive = true,
        WriteIndented = true
    };

    public static IReadOnlyList<PlayerCurrentAnchorCacheEntry> LoadCandidates(string? filePath, out string? primaryPath, out string? error)
    {
        error = null;
        primaryPath = ResolvePrimaryPath(filePath);

        if (string.IsNullOrWhiteSpace(primaryPath))
        {
            return [];
        }

        var entries = new List<PlayerCurrentAnchorCacheEntry>(2);

        TryLoadInto(entries, primaryPath, ref error);

        var backupPath = GetBackupPath(primaryPath);
        if (!string.Equals(primaryPath, backupPath, StringComparison.OrdinalIgnoreCase))
        {
            TryLoadInto(entries, backupPath, ref error);
        }

        return entries;
    }

    public static string Save(PlayerCurrentAnchorCacheDocument document, string? filePath)
    {
        ArgumentNullException.ThrowIfNull(document);

        var primaryPath = ResolvePrimaryPath(filePath);
        if (string.IsNullOrWhiteSpace(primaryPath))
        {
            throw new InvalidOperationException("Unable to resolve the player anchor cache path.");
        }

        var directory = Path.GetDirectoryName(primaryPath);
        if (!string.IsNullOrWhiteSpace(directory))
        {
            Directory.CreateDirectory(directory);
        }

        if (File.Exists(primaryPath))
        {
            File.Copy(primaryPath, GetBackupPath(primaryPath), overwrite: true);
        }

        var json = JsonSerializer.Serialize(document, JsonOptions);
        File.WriteAllText(primaryPath, json);
        return primaryPath;
    }

    public static bool TryParseAddress(string addressHex, out long address)
    {
        address = 0;
        if (string.IsNullOrWhiteSpace(addressHex))
        {
            return false;
        }

        var normalized = addressHex.StartsWith("0x", StringComparison.OrdinalIgnoreCase)
            ? addressHex[2..]
            : addressHex;

        return long.TryParse(normalized, NumberStyles.HexNumber, CultureInfo.InvariantCulture, out address) && address > 0;
    }

    private static void TryLoadInto(List<PlayerCurrentAnchorCacheEntry> entries, string path, ref string? error)
    {
        if (!File.Exists(path))
        {
            return;
        }

        try
        {
            var json = File.ReadAllText(path);
            var document = JsonSerializer.Deserialize<PlayerCurrentAnchorCacheDocument>(json, JsonOptions);
            if (document is null)
            {
                error ??= $"Player anchor cache file '{path}' did not contain a readable document.";
                return;
            }

            entries.Add(new PlayerCurrentAnchorCacheEntry(path, document));
        }
        catch (Exception ex)
        {
            error ??= $"Unable to load player anchor cache '{path}': {ex.Message}";
        }
    }

    private static string? ResolvePrimaryPath(string? filePath)
    {
        if (!string.IsNullOrWhiteSpace(filePath))
        {
            return Path.GetFullPath(filePath);
        }

        const string relativePath = @"scripts\captures\player-current-anchor.json";
        var current = new DirectoryInfo(Directory.GetCurrentDirectory());

        while (current is not null)
        {
            var markerFile = Path.Combine(current.FullName, "RiftReader.slnx");
            if (File.Exists(markerFile))
            {
                return Path.Combine(current.FullName, relativePath);
            }

            current = current.Parent;
        }

        return null;
    }

    private static string GetBackupPath(string primaryPath)
    {
        var directory = Path.GetDirectoryName(primaryPath) ?? string.Empty;
        var fileNameWithoutExtension = Path.GetFileNameWithoutExtension(primaryPath);
        var extension = Path.GetExtension(primaryPath);
        return Path.Combine(directory, $"{fileNameWithoutExtension}.previous{extension}");
    }
}

public sealed record PlayerCurrentAnchorCacheEntry(
    string Path,
    PlayerCurrentAnchorCacheDocument Document);
