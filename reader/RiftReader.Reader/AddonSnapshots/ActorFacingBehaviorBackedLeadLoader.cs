using System.Text.Json;

namespace RiftReader.Reader.AddonSnapshots;

public static class ActorFacingBehaviorBackedLeadLoader
{
    private const string RelativePath = @"scripts\actor-facing-behavior-backed-lead.json";

    private static readonly JsonSerializerOptions JsonOptions = new()
    {
        PropertyNameCaseInsensitive = true
    };

    public static ActorFacingBehaviorBackedLeadDocument? TryLoad(string? explicitPath, out string? error)
    {
        error = null;

        var sourceFile = ResolveSourceFile(explicitPath);
        if (string.IsNullOrWhiteSpace(sourceFile) || !File.Exists(sourceFile))
        {
            error = $"Unable to find the actor-facing behavior-backed lead '{sourceFile ?? "<default>"}'.";
            return null;
        }

        try
        {
            var json = File.ReadAllText(sourceFile);
            var document = JsonSerializer.Deserialize<ActorFacingBehaviorBackedLeadDocument>(json, JsonOptions);

            if (document is null)
            {
                error = $"The actor-facing behavior-backed lead '{sourceFile}' did not contain a readable document.";
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
            error = $"Unable to load the actor-facing behavior-backed lead '{sourceFile}': {ex.Message}";
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

public sealed record ActorFacingBehaviorBackedLeadDocument(
    string? Mode,
    DateTimeOffset? GeneratedAtUtc,
    DateTimeOffset? ValidatedAtUtc,
    string? ProcessName,
    string? SourceAddress,
    string? BasisForwardOffset,
    string? BasisDuplicateForwardOffset,
    string? Status,
    string? OperationalStatus,
    bool? PreferredLead,
    bool? SolvedActorFacing,
    bool? CanonicalActorYaw,
    IReadOnlyList<string>? Notes)
{
    public string SourceFile { get; init; } = string.Empty;

    public DateTimeOffset LoadedAtUtc { get; init; }
}

public static class ActorFacingBehaviorBackedLeadValidator
{
    public static ActorFacingBehaviorBackedLeadValidationResult Validate(
        ActorFacingBehaviorBackedLeadDocument leadDocument,
        string processName,
        int processId,
        DateTimeOffset processStartTimeUtc)
    {
        ArgumentNullException.ThrowIfNull(leadDocument);

        if (!string.IsNullOrWhiteSpace(leadDocument.ProcessName) &&
            !string.Equals(leadDocument.ProcessName, processName, StringComparison.OrdinalIgnoreCase))
        {
            return new ActorFacingBehaviorBackedLeadValidationResult(
                IsValid: false,
                Error: $"Behavior-backed lead targets process '{leadDocument.ProcessName}', but the live process is '{processName}'.");
        }

        var leadTimestamp = leadDocument.ValidatedAtUtc ?? leadDocument.GeneratedAtUtc;
        if (leadTimestamp.HasValue && leadTimestamp.Value < processStartTimeUtc.AddSeconds(-1))
        {
            return new ActorFacingBehaviorBackedLeadValidationResult(
                IsValid: false,
                Error: $"Behavior-backed lead '{leadDocument.SourceFile}' is stale for live PID {processId}: lead timestamp {leadTimestamp.Value:O} predates process start {processStartTimeUtc:O}.");
        }

        return new ActorFacingBehaviorBackedLeadValidationResult(IsValid: true, Error: null);
    }
}

public sealed record ActorFacingBehaviorBackedLeadValidationResult(
    bool IsValid,
    string? Error);
