using System.Globalization;
using System.Text.Json;

namespace RiftReader.Reader.Models;

public static class OrientationCandidateLedgerLoader
{
    private static readonly JsonSerializerOptions JsonOptions = new()
    {
        PropertyNameCaseInsensitive = true
    };

    public static OrientationCandidateLedger Load(string? filePath)
    {
        if (string.IsNullOrWhiteSpace(filePath))
        {
            return new OrientationCandidateLedger(
                FilePath: null,
                Entries: Array.Empty<OrientationCandidateLedgerEntry>(),
                EvidenceByCandidate: new Dictionary<string, OrientationCandidateLedgerEvidence>(StringComparer.OrdinalIgnoreCase),
                EvidenceByFamily: new Dictionary<string, OrientationCandidateLedgerFamilyEvidence>(StringComparer.OrdinalIgnoreCase),
                LoadError: null);
        }

        var fullPath = Path.GetFullPath(filePath);
        if (!File.Exists(fullPath))
        {
            return new OrientationCandidateLedger(
                FilePath: fullPath,
                Entries: Array.Empty<OrientationCandidateLedgerEntry>(),
                EvidenceByCandidate: new Dictionary<string, OrientationCandidateLedgerEvidence>(StringComparer.OrdinalIgnoreCase),
                EvidenceByFamily: new Dictionary<string, OrientationCandidateLedgerFamilyEvidence>(StringComparer.OrdinalIgnoreCase),
                LoadError: null);
        }

        string[] lines;
        try
        {
            lines = File.ReadAllLines(fullPath);
        }
        catch (Exception ex)
        {
            return new OrientationCandidateLedger(
                FilePath: fullPath,
                Entries: Array.Empty<OrientationCandidateLedgerEntry>(),
                EvidenceByCandidate: new Dictionary<string, OrientationCandidateLedgerEvidence>(StringComparer.OrdinalIgnoreCase),
                EvidenceByFamily: new Dictionary<string, OrientationCandidateLedgerFamilyEvidence>(StringComparer.OrdinalIgnoreCase),
                LoadError: $"Unable to read orientation candidate ledger '{fullPath}': {ex.Message}");
        }

        var entries = new List<OrientationCandidateLedgerEntry>();
        for (var index = 0; index < lines.Length; index++)
        {
            var line = lines[index];
            if (string.IsNullOrWhiteSpace(line))
            {
                continue;
            }

            OrientationCandidateLedgerEntry? entry;
            try
            {
                entry = JsonSerializer.Deserialize<OrientationCandidateLedgerEntry>(line, JsonOptions);
            }
            catch (JsonException ex)
            {
                return new OrientationCandidateLedger(
                    FilePath: fullPath,
                    Entries: entries,
                    EvidenceByCandidate: new Dictionary<string, OrientationCandidateLedgerEvidence>(StringComparer.OrdinalIgnoreCase),
                    EvidenceByFamily: new Dictionary<string, OrientationCandidateLedgerFamilyEvidence>(StringComparer.OrdinalIgnoreCase),
                    LoadError: $"Unable to parse orientation candidate ledger '{fullPath}' at line {index + 1}: {ex.Message}");
            }

            if (entry is not null)
            {
                entries.Add(entry);
            }
        }

        var evidenceByCandidate = BuildEvidenceIndex(entries);
        var evidenceByFamily = BuildFamilyEvidenceIndex(entries);
        return new OrientationCandidateLedger(
            FilePath: fullPath,
            Entries: entries,
            EvidenceByCandidate: evidenceByCandidate,
            EvidenceByFamily: evidenceByFamily,
            LoadError: null);
    }

    public static string? BuildCandidateKey(string? sourceAddress, string? basisForwardOffset)
    {
        if (!TryNormalizeHex(sourceAddress, out var normalizedSource))
        {
            return null;
        }

        if (!TryNormalizeHex(basisForwardOffset, out var normalizedBasisOffset))
        {
            normalizedBasisOffset = "0x0";
        }

        return $"{normalizedSource}|{normalizedBasisOffset}";
    }

    public static IReadOnlyList<string> BuildFamilyKeys(
        string? discoveryMode,
        string? basisForwardOffset,
        string? parentFamilyId,
        string? rootAddress,
        string? parentAddress)
    {
        if (!TryNormalizeHex(basisForwardOffset, out var normalizedBasisOffset))
        {
            normalizedBasisOffset = "0x0";
        }

        var normalizedDiscoveryMode = NormalizeDiscoveryMode(discoveryMode);
        var keys = new List<string>(capacity: 2);
        var seen = new HashSet<string>(StringComparer.OrdinalIgnoreCase);

        if (!string.IsNullOrWhiteSpace(parentFamilyId))
        {
            var familyIdKey = $"{normalizedDiscoveryMode}|{normalizedBasisOffset}|family:{parentFamilyId.Trim().ToUpperInvariant()}";
            if (seen.Add(familyIdKey))
            {
                keys.Add(familyIdKey);
            }
        }

        if (!TryNormalizeHex(rootAddress, out var normalizedRootAddress))
        {
            TryNormalizeHex(parentAddress, out normalizedRootAddress);
        }

        if (!string.IsNullOrWhiteSpace(normalizedRootAddress))
        {
            var rootKey = $"{normalizedDiscoveryMode}|{normalizedBasisOffset}|root:{normalizedRootAddress}";
            if (seen.Add(rootKey))
            {
                keys.Add(rootKey);
            }
        }

        return keys;
    }

    private static IReadOnlyDictionary<string, OrientationCandidateLedgerEvidence> BuildEvidenceIndex(
        IReadOnlyList<OrientationCandidateLedgerEntry> entries)
    {
        var accumulators = new Dictionary<string, CandidateEvidenceAccumulatorEntry>(StringComparer.OrdinalIgnoreCase);

        foreach (var entry in entries)
        {
            var key = BuildCandidateKey(entry.SourceAddress, entry.BasisForwardOffset);
            if (string.IsNullOrWhiteSpace(key))
            {
                continue;
            }

            if (!accumulators.TryGetValue(key, out var accumulator))
            {
                if (!TryNormalizeHex(entry.SourceAddress, out var normalizedSourceAddress))
                {
                    continue;
                }

                if (!TryNormalizeHex(entry.BasisForwardOffset, out var normalizedBasisOffset))
                {
                    normalizedBasisOffset = "0x0";
                }

                accumulator = new CandidateEvidenceAccumulatorEntry(normalizedSourceAddress, normalizedBasisOffset);
                accumulators[key] = accumulator;
            }

            accumulator.Stats.Record(entry);
        }

        return accumulators.ToDictionary(
            static pair => pair.Key,
            static pair => pair.Value.ToEvidence(),
            StringComparer.OrdinalIgnoreCase);
    }

    private static IReadOnlyDictionary<string, OrientationCandidateLedgerFamilyEvidence> BuildFamilyEvidenceIndex(
        IReadOnlyList<OrientationCandidateLedgerEntry> entries)
    {
        var accumulators = new Dictionary<string, FamilyEvidenceAccumulatorEntry>(StringComparer.OrdinalIgnoreCase);

        foreach (var entry in entries)
        {
            var familyKeys = BuildFamilyKeys(
                entry.DiscoveryMode,
                entry.BasisForwardOffset,
                entry.ParentFamilyId,
                entry.RootAddress,
                entry.ParentAddress);
            if (familyKeys.Count == 0)
            {
                continue;
            }

            if (!TryNormalizeHex(entry.BasisForwardOffset, out var normalizedBasisOffset))
            {
                normalizedBasisOffset = "0x0";
            }

            string? normalizedRootAddress = null;
            if (!TryNormalizeHex(entry.RootAddress, out normalizedRootAddress))
            {
                TryNormalizeHex(entry.ParentAddress, out normalizedRootAddress);
            }

            foreach (var familyKey in familyKeys)
            {
                if (!accumulators.TryGetValue(familyKey, out var accumulator))
                {
                    accumulator = new FamilyEvidenceAccumulatorEntry(
                        familyKey,
                        NormalizeDiscoveryMode(entry.DiscoveryMode),
                        normalizedBasisOffset,
                        string.IsNullOrWhiteSpace(entry.ParentFamilyId) ? null : entry.ParentFamilyId.Trim().ToUpperInvariant(),
                        normalizedRootAddress);
                    accumulators[familyKey] = accumulator;
                }

                accumulator.Stats.Record(entry);
            }
        }

        return accumulators.ToDictionary(
            static pair => pair.Key,
            static pair => pair.Value.ToEvidence(),
            StringComparer.OrdinalIgnoreCase);
    }

    private static bool TryNormalizeHex(string? value, out string normalized)
    {
        normalized = string.Empty;
        if (string.IsNullOrWhiteSpace(value))
        {
            return false;
        }

        var trimmed = value.Trim();
        if (trimmed.StartsWith("0x", StringComparison.OrdinalIgnoreCase))
        {
            trimmed = trimmed[2..];
            if (!ulong.TryParse(trimmed, NumberStyles.HexNumber, CultureInfo.InvariantCulture, out var hexValue))
            {
                return false;
            }

            normalized = $"0x{hexValue:X}";
            return true;
        }

        if (ulong.TryParse(trimmed, NumberStyles.Integer, CultureInfo.InvariantCulture, out var integerValue))
        {
            normalized = $"0x{integerValue:X}";
            return true;
        }

        if (ulong.TryParse(trimmed, NumberStyles.HexNumber, CultureInfo.InvariantCulture, out var implicitHexValue))
        {
            normalized = $"0x{implicitHexValue:X}";
            return true;
        }

        return false;
    }

    private static string NormalizeDiscoveryMode(string? value) =>
        string.IsNullOrWhiteSpace(value)
            ? "unknown"
            : value.Trim().ToLowerInvariant();

    private static bool IsPenalizedRejectedReason(string? rejectedReason) =>
        string.Equals(rejectedReason, "stable_but_nonresponsive", StringComparison.OrdinalIgnoreCase) ||
        string.Equals(rejectedReason, "idle_drift", StringComparison.OrdinalIgnoreCase) ||
        string.Equals(rejectedReason, "inter_preflight_idle_drift", StringComparison.OrdinalIgnoreCase);

    private sealed class LedgerEvidenceAccumulator
    {
        private DateTimeOffset? _latestGeneratedAtUtc;

        public int StableNonresponsiveCount { get; private set; }
        public int ResponsiveCount { get; private set; }
        public string? LatestCandidateRejectedReason { get; private set; }
        public string? LatestGeneratedAtUtc { get; private set; }
        public bool LatestCandidateResponsive { get; private set; }

        public void Record(OrientationCandidateLedgerEntry entry)
        {
            if (entry.CandidateResponsive == true)
            {
                ResponsiveCount++;
            }

            if (string.Equals(entry.CandidateRejectedReason, "stable_but_nonresponsive", StringComparison.OrdinalIgnoreCase))
            {
                StableNonresponsiveCount++;
            }

            var generatedAtUtc = ParseDate(entry.GeneratedAtUtc);
            if (!_latestGeneratedAtUtc.HasValue ||
                (generatedAtUtc.HasValue && generatedAtUtc.Value >= _latestGeneratedAtUtc.Value))
            {
                _latestGeneratedAtUtc = generatedAtUtc;
                LatestGeneratedAtUtc = entry.GeneratedAtUtc;
                LatestCandidateRejectedReason = entry.CandidateRejectedReason;
                LatestCandidateResponsive = entry.CandidateResponsive == true;
            }
        }

        private static DateTimeOffset? ParseDate(string? value) =>
            DateTimeOffset.TryParse(value, CultureInfo.InvariantCulture, DateTimeStyles.AssumeUniversal, out var parsed)
                ? parsed
                : null;

        public int GetCandidatePenalty()
        {
            var shouldPenalize =
                IsPenalizedRejectedReason(LatestCandidateRejectedReason) &&
                (!LatestCandidateResponsive || !string.Equals(LatestCandidateRejectedReason, "stable_but_nonresponsive", StringComparison.OrdinalIgnoreCase));
            return shouldPenalize
                ? Math.Min(400, 180 + Math.Max(0, StableNonresponsiveCount - 1) * 60)
                : 0;
        }

        public int GetFamilyPenalty()
        {
            if (ResponsiveCount > 0 || !IsPenalizedRejectedReason(LatestCandidateRejectedReason))
            {
                return 0;
            }

            return Math.Min(220, 80 + Math.Max(0, StableNonresponsiveCount - 1) * 35);
        }

        public int GetFamilyBonus()
        {
            if (ResponsiveCount <= 0)
            {
                return 0;
            }

            var bonus = 95 + Math.Max(0, ResponsiveCount - 1) * 30;
            if (LatestCandidateResponsive)
            {
                bonus += 25;
            }

            if (StableNonresponsiveCount == 0)
            {
                bonus += 20;
            }

            return Math.Min(220, bonus);
        }
    }

    private sealed class CandidateEvidenceAccumulatorEntry(string sourceAddress, string basisForwardOffset)
    {
        public LedgerEvidenceAccumulator Stats { get; } = new();

        public OrientationCandidateLedgerEvidence ToEvidence() =>
            new(
                SourceAddress: sourceAddress,
                BasisForwardOffset: basisForwardOffset,
                StableNonresponsiveCount: Stats.StableNonresponsiveCount,
                ResponsiveCount: Stats.ResponsiveCount,
                LatestCandidateRejectedReason: Stats.LatestCandidateRejectedReason,
                LatestGeneratedAtUtc: Stats.LatestGeneratedAtUtc,
                LatestCandidateResponsive: Stats.LatestCandidateResponsive,
                ScorePenalty: Stats.GetCandidatePenalty());
    }

    private sealed class FamilyEvidenceAccumulatorEntry(
        string familyKey,
        string discoveryMode,
        string basisForwardOffset,
        string? parentFamilyId,
        string? rootAddress)
    {
        public LedgerEvidenceAccumulator Stats { get; } = new();

        public OrientationCandidateLedgerFamilyEvidence ToEvidence() =>
            new(
                FamilyKey: familyKey,
                DiscoveryMode: discoveryMode,
                BasisForwardOffset: basisForwardOffset,
                ParentFamilyId: parentFamilyId,
                RootAddress: rootAddress,
                StableNonresponsiveCount: Stats.StableNonresponsiveCount,
                ResponsiveCount: Stats.ResponsiveCount,
                LatestCandidateRejectedReason: Stats.LatestCandidateRejectedReason,
                LatestGeneratedAtUtc: Stats.LatestGeneratedAtUtc,
                LatestCandidateResponsive: Stats.LatestCandidateResponsive,
                ScorePenalty: Stats.GetFamilyPenalty(),
                ScoreBonus: Stats.GetFamilyBonus());
    }
}

public sealed record OrientationCandidateLedger(
    string? FilePath,
    IReadOnlyList<OrientationCandidateLedgerEntry> Entries,
    IReadOnlyDictionary<string, OrientationCandidateLedgerEvidence> EvidenceByCandidate,
    IReadOnlyDictionary<string, OrientationCandidateLedgerFamilyEvidence> EvidenceByFamily,
    string? LoadError);

public sealed record OrientationCandidateLedgerEntry(
    string? GeneratedAtUtc,
    string? ProcessName,
    string? SourceAddress,
    string? BasisForwardOffset,
    string? ResolutionMode,
    string? DiscoveryMode,
    string? ParentFamilyId,
    string? ParentAddress,
    string? RootAddress,
    string? RootSource,
    int? HopDepth,
    string? EvaluationMode,
    string? StimulusKey,
    bool? SourceStable,
    double? CoordDriftMagnitude,
    double? YawDeltaDegrees,
    double? PitchDeltaDegrees,
    bool? CandidateResponsive,
    string? CandidateRejectedReason,
    IReadOnlyList<string>? Notes);

public sealed record OrientationCandidateLedgerEvidence(
    string SourceAddress,
    string BasisForwardOffset,
    int StableNonresponsiveCount,
    int ResponsiveCount,
    string? LatestCandidateRejectedReason,
    string? LatestGeneratedAtUtc,
    bool LatestCandidateResponsive,
    int ScorePenalty);

public sealed record OrientationCandidateLedgerFamilyEvidence(
    string FamilyKey,
    string DiscoveryMode,
    string BasisForwardOffset,
    string? ParentFamilyId,
    string? RootAddress,
    int StableNonresponsiveCount,
    int ResponsiveCount,
    string? LatestCandidateRejectedReason,
    string? LatestGeneratedAtUtc,
    bool LatestCandidateResponsive,
    int ScorePenalty,
    int ScoreBonus);
