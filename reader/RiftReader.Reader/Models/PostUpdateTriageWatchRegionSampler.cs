using System.Globalization;
using System.Text.Json;
using RiftReader.Reader.Memory;
using RiftReader.Reader.Processes;

namespace RiftReader.Reader.Models;

public static class PostUpdateTriageWatchRegionSampler
{
    public static PostUpdateTriageWatchRegionSampleResult Sample(
        ProcessTarget target,
        ProcessMemoryReader reader,
        string bundleFile,
        int maxRegions)
    {
        ArgumentNullException.ThrowIfNull(target);
        ArgumentNullException.ThrowIfNull(reader);

        if (string.IsNullOrWhiteSpace(bundleFile))
        {
            throw new InvalidOperationException("A triage bundle path is required to sample watch regions.");
        }

        var resolvedBundleFile = Path.GetFullPath(bundleFile);
        if (!File.Exists(resolvedBundleFile))
        {
            throw new FileNotFoundException("The triage bundle file does not exist.", resolvedBundleFile);
        }

        var loadedBundle = LoadBundle(resolvedBundleFile);
        var selectedRegions = loadedBundle.SuggestedWatchRegions
            .Take(Math.Max(1, maxRegions))
            .ToArray();

        if (selectedRegions.Length == 0)
        {
            throw new InvalidOperationException("The triage bundle does not contain any suggested watch regions.");
        }

        var samples = new List<PostUpdateTriageWatchRegionSample>(selectedRegions.Length);

        foreach (var region in selectedRegions)
        {
            var normalizedCandidateAddress = NormalizeHexAddress(region.CandidateAddress) ?? region.CandidateAddress;
            loadedBundle.LineageSummariesByCandidate.TryGetValue(normalizedCandidateAddress, out var lineageSummary);

            if (region.Length <= 0)
            {
                samples.Add(new PostUpdateTriageWatchRegionSample(
                    Name: region.Name,
                    Address: region.Address,
                    Length: region.Length,
                    Purpose: region.Purpose,
                    CandidateAddress: normalizedCandidateAddress,
                    Kind: region.Kind,
                    StableAcrossBundles: region.StableAcrossBundles,
                    CandidateLineageSummary: lineageSummary?.Summary,
                    CandidatePreviousRank: lineageSummary?.PreviousRank,
                    ReadSucceeded: false,
                    BytesRead: 0,
                    BytesHex: null,
                    PreviewHex: null,
                    Error: "Watch region length must be greater than zero."));
                continue;
            }

            var addressValue = TryParseHexInt64(region.Address);
            if (!addressValue.HasValue)
            {
                samples.Add(new PostUpdateTriageWatchRegionSample(
                    Name: region.Name,
                    Address: region.Address,
                    Length: region.Length,
                    Purpose: region.Purpose,
                    CandidateAddress: normalizedCandidateAddress,
                    Kind: region.Kind,
                    StableAcrossBundles: region.StableAcrossBundles,
                    CandidateLineageSummary: lineageSummary?.Summary,
                    CandidatePreviousRank: lineageSummary?.PreviousRank,
                    ReadSucceeded: false,
                    BytesRead: 0,
                    BytesHex: null,
                    PreviewHex: null,
                    Error: $"Unable to parse watch region address '{region.Address}'."));
                continue;
            }

            if (!reader.TryReadBytes(new nint(addressValue.Value), region.Length, out var bytes, out var readError))
            {
                samples.Add(new PostUpdateTriageWatchRegionSample(
                    Name: region.Name,
                    Address: region.Address,
                    Length: region.Length,
                    Purpose: region.Purpose,
                    CandidateAddress: normalizedCandidateAddress,
                    Kind: region.Kind,
                    StableAcrossBundles: region.StableAcrossBundles,
                    CandidateLineageSummary: lineageSummary?.Summary,
                    CandidatePreviousRank: lineageSummary?.PreviousRank,
                    ReadSucceeded: false,
                    BytesRead: 0,
                    BytesHex: null,
                    PreviewHex: null,
                    Error: readError));
                continue;
            }

            var previewLength = Math.Min(bytes.Length, 32);
            var previewHex = previewLength > 0 ? Convert.ToHexString(bytes[..previewLength]) : string.Empty;

            samples.Add(new PostUpdateTriageWatchRegionSample(
                Name: region.Name,
                Address: region.Address,
                Length: region.Length,
                Purpose: region.Purpose,
                CandidateAddress: normalizedCandidateAddress,
                Kind: region.Kind,
                StableAcrossBundles: region.StableAcrossBundles,
                CandidateLineageSummary: lineageSummary?.Summary,
                CandidatePreviousRank: lineageSummary?.PreviousRank,
                ReadSucceeded: true,
                BytesRead: bytes.Length,
                BytesHex: Convert.ToHexString(bytes),
                PreviewHex: previewHex,
                Error: null));
        }

        var successfulRegionCount = samples.Count(static sample => sample.ReadSucceeded);
        var failedRegionCount = samples.Count - successfulRegionCount;
        var notes = new List<string>
        {
            $"Loaded {loadedBundle.SuggestedWatchRegions.Count} suggested watch region(s) from {resolvedBundleFile}.",
            $"Sampled {samples.Count} region(s) against PID {target.ProcessId} ({target.ProcessName})."
        };

        if (!string.IsNullOrWhiteSpace(loadedBundle.GeneratedAtUtc))
        {
            notes.Add($"Bundle generated at {loadedBundle.GeneratedAtUtc}.");
        }

        if (loadedBundle.LineageSummariesByCandidate.Count > 0)
        {
            notes.Add($"Matched lineage summaries for {loadedBundle.LineageSummariesByCandidate.Count} candidate(s).");
        }

        return new PostUpdateTriageWatchRegionSampleResult(
            Mode: "sample-triage-watch-regions",
            BundleFile: resolvedBundleFile,
            BundleGeneratedAtUtc: loadedBundle.GeneratedAtUtc,
            ProcessId: target.ProcessId,
            ProcessName: target.ProcessName,
            ModuleName: target.ModuleName,
            MainWindowTitle: target.MainWindowTitle,
            RequestedRegionCount: Math.Max(1, maxRegions),
            SampledRegionCount: samples.Count,
            SuccessfulRegionCount: successfulRegionCount,
            FailedRegionCount: failedRegionCount,
            Samples: samples,
            Notes: notes);
    }

    private static LoadedTriageBundle LoadBundle(string bundleFile)
    {
        using var document = JsonDocument.Parse(File.ReadAllText(bundleFile));
        var root = document.RootElement;

        var generatedAtUtc = TryGetString(root, "GeneratedAtUtc");
        var regions = new List<PostUpdateTriageSuggestedWatchRegion>();
        if (root.TryGetProperty("SuggestedWatchRegions", out var regionElement) && regionElement.ValueKind == JsonValueKind.Array)
        {
            foreach (var element in regionElement.EnumerateArray())
            {
                regions.Add(new PostUpdateTriageSuggestedWatchRegion(
                    Name: TryGetString(element, "Name") ?? $"region-{regions.Count + 1}",
                    Address: NormalizeHexAddress(TryGetString(element, "Address")) ?? (TryGetString(element, "Address") ?? "0x0"),
                    Length: TryGetInt32(element, "Length") ?? 0,
                    Purpose: TryGetString(element, "Purpose") ?? string.Empty,
                    CandidateAddress: NormalizeHexAddress(TryGetString(element, "CandidateAddress")) ?? (TryGetString(element, "CandidateAddress") ?? string.Empty),
                    Kind: TryGetString(element, "Kind") ?? "unknown",
                    StableAcrossBundles: TryGetBoolean(element, "StableAcrossBundles") ?? false));
            }
        }

        var lineageByCandidate = new Dictionary<string, PostUpdateTriageLineageSummary>(StringComparer.OrdinalIgnoreCase);
        if (root.TryGetProperty("LineageSummaries", out var lineageElement) && lineageElement.ValueKind == JsonValueKind.Array)
        {
            foreach (var element in lineageElement.EnumerateArray())
            {
                var candidateAddress = NormalizeHexAddress(TryGetString(element, "CandidateAddress"));
                if (string.IsNullOrWhiteSpace(candidateAddress))
                {
                    continue;
                }

                lineageByCandidate[candidateAddress] = new PostUpdateTriageLineageSummary(
                    Rank: TryGetInt32(element, "Rank") ?? 0,
                    CandidateAddress: candidateAddress,
                    Kind: TryGetString(element, "Kind") ?? "unknown",
                    RootAddress: NormalizeHexAddress(TryGetString(element, "RootAddress")),
                    ParentAddress: NormalizeHexAddress(TryGetString(element, "ParentAddress")),
                    RootSource: TryGetString(element, "RootSource"),
                    HopDepth: TryGetInt32(element, "HopDepth") ?? 0,
                    PointerOffset: TryGetString(element, "PointerOffset"),
                    BasisPrimaryForwardOffset: TryGetString(element, "BasisPrimaryForwardOffset"),
                    StableAcrossBundles: TryGetBoolean(element, "StableAcrossBundles") ?? false,
                    PreviousMatchKind: TryGetString(element, "PreviousMatchKind"),
                    PreviousRank: TryGetInt32(element, "PreviousRank"),
                    TotalScore: TryGetInt32(element, "TotalScore") ?? 0,
                    Summary: TryGetString(element, "Summary") ?? string.Empty);
            }
        }

        return new LoadedTriageBundle(
            GeneratedAtUtc: generatedAtUtc,
            SuggestedWatchRegions: regions,
            LineageSummariesByCandidate: lineageByCandidate);
    }

    private static string? TryGetString(JsonElement element, string propertyName) =>
        element.TryGetProperty(propertyName, out var property) && property.ValueKind == JsonValueKind.String
            ? property.GetString()
            : null;

    private static int? TryGetInt32(JsonElement element, string propertyName)
    {
        if (!element.TryGetProperty(propertyName, out var property))
        {
            return null;
        }

        if (property.ValueKind == JsonValueKind.Number && property.TryGetInt32(out var numericValue))
        {
            return numericValue;
        }

        if (property.ValueKind == JsonValueKind.String &&
            int.TryParse(property.GetString(), NumberStyles.Integer, CultureInfo.InvariantCulture, out var stringValue))
        {
            return stringValue;
        }

        return null;
    }

    private static bool? TryGetBoolean(JsonElement element, string propertyName)
    {
        if (!element.TryGetProperty(propertyName, out var property))
        {
            return null;
        }

        if (property.ValueKind == JsonValueKind.True)
        {
            return true;
        }

        if (property.ValueKind == JsonValueKind.False)
        {
            return false;
        }

        if (property.ValueKind == JsonValueKind.String &&
            bool.TryParse(property.GetString(), out var stringValue))
        {
            return stringValue;
        }

        return null;
    }

    private static string? NormalizeHexAddress(string? value)
    {
        var parsed = TryParseHexInt64(value);
        return parsed.HasValue ? $"0x{parsed.Value:X}" : null;
    }

    private static long? TryParseHexInt64(string? value)
    {
        if (string.IsNullOrWhiteSpace(value))
        {
            return null;
        }

        var trimmed = value.Trim();
        if (trimmed.StartsWith("0x", StringComparison.OrdinalIgnoreCase))
        {
            trimmed = trimmed[2..];
        }

        return long.TryParse(trimmed, NumberStyles.HexNumber, CultureInfo.InvariantCulture, out var hexValue)
            ? hexValue
            : null;
    }

    private sealed record LoadedTriageBundle(
        string? GeneratedAtUtc,
        IReadOnlyList<PostUpdateTriageSuggestedWatchRegion> SuggestedWatchRegions,
        IReadOnlyDictionary<string, PostUpdateTriageLineageSummary> LineageSummariesByCandidate);
}

public sealed record PostUpdateTriageWatchRegionSampleResult(
    string Mode,
    string BundleFile,
    string? BundleGeneratedAtUtc,
    int ProcessId,
    string ProcessName,
    string? ModuleName,
    string? MainWindowTitle,
    int RequestedRegionCount,
    int SampledRegionCount,
    int SuccessfulRegionCount,
    int FailedRegionCount,
    IReadOnlyList<PostUpdateTriageWatchRegionSample> Samples,
    IReadOnlyList<string> Notes);

public sealed record PostUpdateTriageWatchRegionSample(
    string Name,
    string Address,
    int Length,
    string Purpose,
    string CandidateAddress,
    string Kind,
    bool StableAcrossBundles,
    string? CandidateLineageSummary,
    int? CandidatePreviousRank,
    bool ReadSucceeded,
    int BytesRead,
    string? BytesHex,
    string? PreviewHex,
    string? Error);
