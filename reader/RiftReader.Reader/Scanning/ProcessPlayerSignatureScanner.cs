using System.Globalization;
using System.Text;
using RiftReader.Reader.Memory;

namespace RiftReader.Reader.Scanning;

public static class ProcessPlayerSignatureScanner
{
    public static PlayerSignatureScanResult ScanReaderBridgePlayerSignature(
        ProcessMemoryReader reader,
        int processId,
        string processName,
        string sourceLabel,
        float coordX,
        float coordY,
        float coordZ,
        int? level,
        long? health,
        long? healthMax,
        string? playerName,
        string? locationName,
        int inspectionRadius,
        int maxHits)
    {
        ArgumentNullException.ThrowIfNull(reader);
        ArgumentException.ThrowIfNullOrWhiteSpace(sourceLabel);

        if (inspectionRadius < 0)
        {
            throw new ArgumentOutOfRangeException(nameof(inspectionRadius), "Inspection radius must be zero or greater.");
        }

        if (maxHits <= 0)
        {
            throw new ArgumentOutOfRangeException(nameof(maxHits), "Max hits must be greater than zero.");
        }

        var candidateLimit = Math.Max(maxHits * 4, 32);
        var coordinateCandidates = ProcessFloatSequenceScanner.ScanFloatTriplet(
            reader,
            processId,
            processName,
            sourceLabel,
            coordX,
            coordY,
            coordZ,
            contextBytes: 0,
            maxHits: candidateLimit);

        var hits = new List<PlayerSignatureScanHit>(coordinateCandidates.Hits.Count);
        var effectiveRadius = Math.Max(inspectionRadius, 96);

        foreach (var candidate in coordinateCandidates.Hits)
        {
            var windowStart = Math.Max(0, candidate.Address - effectiveRadius);
            var windowLength = checked((effectiveRadius * 2) + (sizeof(float) * 3));
            if (!reader.TryReadBytes(new nint(windowStart), windowLength, out var bytes, out _))
            {
                continue;
            }

            var signals = new List<PlayerSignatureSignal>(8)
            {
                new("coords", FormatFloatTriplet(coordX, coordY, coordZ), 0)
            };

            var score = 1;

            AddIntSignals(bytes, windowStart, candidate.Address, "level", level, ref score, 2, signals, maxOccurrences: 2);
            AddIntSignals(bytes, windowStart, candidate.Address, "health", TryNarrow(health), ref score, 3, signals, maxOccurrences: 4);

            var narrowedHealthMax = TryNarrow(healthMax);
            if (narrowedHealthMax.HasValue && narrowedHealthMax != TryNarrow(health))
            {
                AddIntSignals(bytes, windowStart, candidate.Address, "healthMax", narrowedHealthMax, ref score, 2, signals, maxOccurrences: 2);
            }

            AddAsciiSignal(bytes, windowStart, candidate.Address, "name", playerName, ref score, 3, signals);
            AddAsciiSignal(bytes, windowStart, candidate.Address, "location", locationName, ref score, 2, signals);

            var context = new StringHitContext(
                WindowStart: $"0x{windowStart:X}",
                WindowLength: bytes.Length,
                BytesHex: string.Join(" ", bytes.Select(static value => value.ToString("X2"))),
                AsciiPreview: BuildAsciiPreview(bytes),
                Utf16Preview: BuildUtf16Preview(bytes));

            hits.Add(new PlayerSignatureScanHit(
                Address: candidate.Address,
                AddressHex: candidate.AddressHex,
                RegionBase: candidate.RegionBase,
                RegionBaseHex: candidate.RegionBaseHex,
                RegionSize: candidate.RegionSize,
                Score: score,
                FamilyId: string.Empty,
                FamilyHitCount: 0,
                Signals: signals,
                Context: context));
        }

        var families = hits
            .GroupBy(BuildFamilySignature)
            .Select(group =>
            {
                var representative = group
                    .OrderByDescending(static hit => hit.Score)
                    .ThenByDescending(static hit => hit.Signals.Count)
                    .ThenBy(static hit => hit.Address)
                    .First();

                var familyId = BuildFamilyId(group.Key);
                var familyHitCount = group.Count();

                return new
                {
                    FamilyId = familyId,
                    Signature = group.Key,
                    HitCount = familyHitCount,
                    BestScore = representative.Score,
                    Notes = ClassifyFamily(representative),
                    Representative = representative with
                    {
                        FamilyId = familyId,
                        FamilyHitCount = familyHitCount
                    },
                    SampleAddresses = group
                        .OrderBy(static hit => hit.Address)
                        .Take(3)
                        .Select(static hit => hit.AddressHex)
                        .ToArray()
                };
            })
            .OrderByDescending(static family => family.BestScore)
            .ThenByDescending(static family => family.HitCount)
            .ThenBy(static family => family.Representative.Address)
            .ToArray();

        var rankedHits = families
            .Select(static family => family.Representative)
            .Take(maxHits)
            .ToArray();

        var familySummaries = families
            .Take(maxHits)
            .Select(static family => new PlayerSignatureFamilySummary(
                FamilyId: family.FamilyId,
                Signature: family.Signature,
                HitCount: family.HitCount,
                BestScore: family.BestScore,
                Notes: family.Notes,
                RepresentativeAddressHex: family.Representative.AddressHex,
                SampleAddresses: family.SampleAddresses))
            .ToArray();

        return new PlayerSignatureScanResult(
            Mode: "player-signature-scan",
            ProcessId: processId,
            ProcessName: processName,
            SearchLabel: sourceLabel,
            InspectionRadius: effectiveRadius,
            CandidateCount: coordinateCandidates.Hits.Count,
            RawHitCount: hits.Count,
            FamilyCount: families.Length,
            MaxHits: maxHits,
            HitCount: rankedHits.Length,
            Families: familySummaries,
            Hits: rankedHits);
    }

    private static void AddIntSignals(
        byte[] bytes,
        long windowStart,
        long anchorAddress,
        string name,
        int? value,
        ref int score,
        int weight,
        List<PlayerSignatureSignal> signals,
        int maxOccurrences)
    {
        if (!value.HasValue)
        {
            return;
        }

        var pattern = BitConverter.GetBytes(value.Value);
        var matchIndices = FindAllPatternIndices(bytes, pattern, maxOccurrences);
        if (matchIndices.Count == 0)
        {
            return;
        }

        for (var index = 0; index < matchIndices.Count; index++)
        {
            var absoluteAddress = windowStart + matchIndices[index];
            var signalName = matchIndices.Count == 1 ? name : $"{name}[{index + 1}]";
            signals.Add(new PlayerSignatureSignal(
                Name: signalName,
                Value: value.Value.ToString(CultureInfo.InvariantCulture),
                RelativeOffset: (int)(absoluteAddress - anchorAddress)));
        }

        score += weight;
    }

    private static void AddAsciiSignal(
        byte[] bytes,
        long windowStart,
        long anchorAddress,
        string name,
        string? value,
        ref int score,
        int weight,
        List<PlayerSignatureSignal> signals)
    {
        if (string.IsNullOrWhiteSpace(value))
        {
            return;
        }

        var pattern = Encoding.ASCII.GetBytes(value);
        var index = bytes.AsSpan().IndexOf(pattern);
        if (index < 0)
        {
            return;
        }

        var absoluteAddress = windowStart + index;
        signals.Add(new PlayerSignatureSignal(
            Name: name,
            Value: value,
            RelativeOffset: (int)(absoluteAddress - anchorAddress)));
        score += weight;
    }

    private static int? TryNarrow(long? value) =>
        value.HasValue && value.Value is >= int.MinValue and <= int.MaxValue
            ? (int)value.Value
            : null;

    private static string BuildFamilySignature(PlayerSignatureScanHit hit)
    {
        return string.Join(
            "|",
            hit.Signals
                .OrderBy(static signal => signal.RelativeOffset)
                .ThenBy(static signal => signal.Name, StringComparer.Ordinal)
                .Select(static signal => $"{signal.Name}@{signal.RelativeOffset}"));
    }

    private static string BuildFamilyId(string signature)
    {
        unchecked
        {
            const uint offset = 2166136261;
            const uint prime = 16777619;
            uint hash = offset;

            foreach (var character in signature)
            {
                hash ^= character;
                hash *= prime;
            }

            return $"fam-{hash:X8}";
        }
    }

    private static string ClassifyFamily(PlayerSignatureScanHit representative)
    {
        var text = ((representative.Context?.AsciiPreview ?? string.Empty) + " " + (representative.Context?.Utf16Preview ?? string.Empty))
            .ToLowerInvariant();

        if (text.Contains("<font") || text.Contains("reason=ui") || text.Contains("captured sample"))
        {
            return "ui/log text";
        }

        if (text.Contains(".lua") || text.Contains("lib/"))
        {
            return "script/cache text";
        }

        if (text.Contains(".nif") || text.Contains("mount_") || text.Contains("_idle") || text.Contains("elements/"))
        {
            return "asset/cache text";
        }

        if (text.Contains("tavril plaza") || text.Contains("sanctum"))
        {
            return "location/cache blob";
        }

        return "unclassified blob";
    }

    private static IReadOnlyList<int> FindAllPatternIndices(byte[] bytes, byte[] pattern, int maxOccurrences)
    {
        var indices = new List<int>(Math.Min(maxOccurrences, 8));
        var searchStart = 0;
        var span = bytes.AsSpan();

        while (searchStart <= bytes.Length - pattern.Length && indices.Count < maxOccurrences)
        {
            var foundIndex = span[searchStart..].IndexOf(pattern);
            if (foundIndex < 0)
            {
                break;
            }

            var absoluteIndex = searchStart + foundIndex;
            indices.Add(absoluteIndex);
            searchStart = absoluteIndex + 1;
        }

        return indices;
    }

    private static string FormatFloatTriplet(float x, float y, float z) =>
        string.Create(CultureInfo.InvariantCulture, $"{x:G9}, {y:G9}, {z:G9}");

    private static string BuildAsciiPreview(byte[] bytes)
    {
        var chars = bytes
            .Select(static value => value is >= 32 and <= 126 ? (char)value : '.')
            .ToArray();

        return new string(chars).Trim('.');
    }

    private static string BuildUtf16Preview(byte[] bytes)
    {
        var evenLength = bytes.Length - (bytes.Length % 2);
        if (evenLength <= 0)
        {
            return string.Empty;
        }

        var text = Encoding.Unicode.GetString(bytes, 0, evenLength);
        var chars = text
            .Select(static value => !char.IsControl(value) ? value : '.')
            .ToArray();

        return new string(chars).Trim('.');
    }
}
