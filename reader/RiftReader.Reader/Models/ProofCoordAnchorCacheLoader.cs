using System.Text.Json;

namespace RiftReader.Reader.Models;

public static class ProofCoordAnchorCacheLoader
{
    public static ProofCoordAnchorCacheDocument? TryLoad(string? explicitPath, out string? error)
    {
        error = null;

        var sourceFile = ResolveSourceFile(explicitPath);
        if (string.IsNullOrWhiteSpace(sourceFile) || !File.Exists(sourceFile))
        {
            error = $"Unable to find the proof coord anchor cache file '{sourceFile ?? "<default>"}'.";
            return null;
        }

        try
        {
            var json = File.ReadAllText(sourceFile);
            var document = JsonSerializer.Deserialize<ProofCoordAnchorCacheDocument>(
                json,
                new JsonSerializerOptions
                {
                    PropertyNameCaseInsensitive = true
                });

            if (document is null)
            {
                error = $"The proof coord anchor cache file '{sourceFile}' was empty.";
                return null;
            }

            return document with { SourceFile = sourceFile };
        }
        catch (Exception ex)
        {
            error = $"Unable to load the proof coord anchor cache file '{sourceFile}': {ex.Message}";
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
        return Path.Combine(repoRoot, "scripts", "captures", "telemetry-proof-coord-anchor.json");
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

public sealed record ProofCoordAnchorCacheDocument(
    string? Mode,
    DateTimeOffset? GeneratedAtUtc,
    string? ProcessName,
    int? ProcessId,
    string? CanonicalCoordSourceKind,
    string? MatchSource,
    string? TraceSourceFile,
    string? VerificationMethod,
    bool? TraceMatchesProcess,
    string? CoordRegionAddress,
    int? CoordXRelativeOffset,
    int? CoordYRelativeOffset,
    int? CoordZRelativeOffset,
    ProofCoordAnchorCacheMatch? Match,
    string? SourceFile);

public sealed record ProofCoordAnchorCacheMatch(
    bool? CoordMatchesWithinTolerance,
    double? DeltaX,
    double? DeltaY,
    double? DeltaZ,
    string? ReferenceSource,
    string? ReferenceCapturedAtUtc,
    double? ReferenceAgeSeconds);
