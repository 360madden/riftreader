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
                LoadError: null);
        }

        var fullPath = Path.GetFullPath(filePath);
        if (!File.Exists(fullPath))
        {
            return new OrientationCandidateLedger(
                FilePath: fullPath,
                Entries: Array.Empty<OrientationCandidateLedgerEntry>(),
                EvidenceByCandidate: new Dictionary<string, OrientationCandidateLedgerEvidence>(StringComparer.OrdinalIgnoreCase),
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
                    LoadError: $"Unable to parse orientation candidate ledger '{fullPath}' at line {index + 1}: {ex.Message}");
            }

            if (entry is not null)
            {
                entries.Add(entry);
            }
        }

        var evidenceByCandidate = BuildEvidenceIndex(entries);
        return new OrientationCandidateLedger(
            FilePath: fullPath,
            Entries: entries,
            EvidenceByCandidate: evidenceByCandidate,
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

    private static IReadOnlyDictionary<string, OrientationCandidateLedgerEvidence> BuildEvidenceIndex(
        IReadOnlyList<OrientationCandidateLedgerEntry> entries)
    {
        var accumulators = new Dictionary<string, OrientationCandidateLedgerEvidenceAccumulator>(StringComparer.OrdinalIgnoreCase);

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

                accumulator = new OrientationCandidateLedgerEvidenceAccumulator(normalizedSourceAddress, normalizedBasisOffset);
                accumulators[key] = accumulator;
            }

            accumulator.Record(entry);
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

    private static bool IsPenalizedRejectedReason(string? rejectedReason) =>
        string.Equals(rejectedReason, "stable_but_nonresponsive", StringComparison.OrdinalIgnoreCase) ||
        string.Equals(rejectedReason, "idle_drift", StringComparison.OrdinalIgnoreCase) ||
        string.Equals(rejectedReason, "inter_preflight_idle_drift", StringComparison.OrdinalIgnoreCase);

    private sealed class OrientationCandidateLedgerEvidenceAccumulator(string sourceAddress, string basisForwardOffset)
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

        public OrientationCandidateLedgerEvidence ToEvidence()
        {
            var shouldPenalize =
                IsPenalizedRejectedReason(LatestCandidateRejectedReason) &&
                (!LatestCandidateResponsive || !string.Equals(LatestCandidateRejectedReason, "stable_but_nonresponsive", StringComparison.OrdinalIgnoreCase));
            var penalty = shouldPenalize
                ? Math.Min(400, 180 + Math.Max(0, StableNonresponsiveCount - 1) * 60)
                : 0;

            return new OrientationCandidateLedgerEvidence(
                SourceAddress: sourceAddress,
                BasisForwardOffset: basisForwardOffset,
                StableNonresponsiveCount: StableNonresponsiveCount,
                ResponsiveCount: ResponsiveCount,
                LatestCandidateRejectedReason: LatestCandidateRejectedReason,
                LatestGeneratedAtUtc: LatestGeneratedAtUtc,
                LatestCandidateResponsive: LatestCandidateResponsive,
                ScorePenalty: penalty);
        }

        private static DateTimeOffset? ParseDate(string? value) =>
            DateTimeOffset.TryParse(value, CultureInfo.InvariantCulture, DateTimeStyles.AssumeUniversal, out var parsed)
                ? parsed
                : null;
    }
}

public sealed record OrientationCandidateLedger(
    string? FilePath,
    IReadOnlyList<OrientationCandidateLedgerEntry> Entries,
    IReadOnlyDictionary<string, OrientationCandidateLedgerEvidence> EvidenceByCandidate,
    string? LoadError);

public sealed record OrientationCandidateLedgerEntry(
    string? GeneratedAtUtc,
    string? ProcessName,
    string? SourceAddress,
    string? BasisForwardOffset,
    string? ResolutionMode,
    string? DiscoveryMode,
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
