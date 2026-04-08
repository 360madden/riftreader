using System.Text;
using RiftReader.Reader.Memory;

namespace RiftReader.Reader.Scanning;

public static class ProcessStringScanner
{
    private const int ChunkSize = 1024 * 1024;

    public static StringScanResult Scan(
        ProcessMemoryReader reader,
        int processId,
        string processName,
        string searchText,
        string searchSource,
        StringScanEncoding encoding,
        int contextBytes,
        int maxHits)
    {
        ArgumentNullException.ThrowIfNull(reader);
        ArgumentException.ThrowIfNullOrWhiteSpace(searchText);

        if (contextBytes < 0)
        {
            throw new ArgumentOutOfRangeException(nameof(contextBytes), "Context bytes must be zero or greater.");
        }

        if (maxHits <= 0)
        {
            throw new ArgumentOutOfRangeException(nameof(maxHits), "Max hits must be greater than zero.");
        }

        var patterns = BuildPatterns(searchText, encoding);
        var hits = new List<StringScanHit>(Math.Min(maxHits, 64));

        foreach (var region in reader.EnumerateMemoryRegions())
        {
            if (!region.IsCommitted || !region.IsReadable || region.RegionSize <= 0)
            {
                continue;
            }

            ScanRegion(reader, region, patterns, hits, maxHits);

            if (hits.Count >= maxHits)
            {
                break;
            }
        }

        return new StringScanResult(
            Mode: "string-scan",
            ProcessId: processId,
            ProcessName: processName,
            SearchText: searchText,
            SearchSource: searchSource,
            Encoding: encoding.ToString().ToLowerInvariant(),
            ContextBytes: contextBytes,
            MaxHits: maxHits,
            HitCount: hits.Count,
            Hits: contextBytes > 0
                ? EnrichHitsWithContext(reader, hits, contextBytes)
                : hits);
    }

    private static IReadOnlyList<SearchPattern> BuildPatterns(string searchText, StringScanEncoding encoding)
    {
        var patterns = new List<SearchPattern>(2);

        if (encoding is StringScanEncoding.Ascii or StringScanEncoding.Both)
        {
            patterns.Add(new SearchPattern("ascii", Encoding.ASCII.GetBytes(searchText)));
        }

        if (encoding is StringScanEncoding.Utf16 or StringScanEncoding.Both)
        {
            patterns.Add(new SearchPattern("utf16", Encoding.Unicode.GetBytes(searchText)));
        }

        return patterns;
    }

    private static void ScanRegion(
        ProcessMemoryReader reader,
        ProcessMemoryRegion region,
        IReadOnlyList<SearchPattern> patterns,
        List<StringScanHit> hits,
        int maxHits)
    {
        var maxPatternLength = patterns.Max(pattern => pattern.Bytes.Length);
        var overlapLength = Math.Max(0, maxPatternLength - 1);
        byte[] overlap = [];

        long regionOffset = 0;

        while (regionOffset < region.RegionSize && hits.Count < maxHits)
        {
            var bytesToRead = (int)Math.Min(ChunkSize, region.RegionSize - regionOffset);
            var address = new nint(region.BaseAddress.ToInt64() + regionOffset);

            if (!reader.TryReadBytes(address, bytesToRead, out var buffer, out _))
            {
                break;
            }

            var combined = Combine(overlap, buffer);

            foreach (var pattern in patterns)
            {
                FindPatternHits(combined, overlap.Length, pattern, region, address, hits, maxHits);

                if (hits.Count >= maxHits)
                {
                    break;
                }
            }

            if (overlapLength > 0)
            {
                var copyLength = Math.Min(overlapLength, combined.Length);
                overlap = combined[^copyLength..];
            }
            else
            {
                overlap = [];
            }

            regionOffset += buffer.Length;
        }
    }

    private static void FindPatternHits(
        byte[] combined,
        int overlapLength,
        SearchPattern pattern,
        ProcessMemoryRegion region,
        nint chunkAddress,
        List<StringScanHit> hits,
        int maxHits)
    {
        var searchStart = 0;
        var combinedSpan = combined.AsSpan();

        while (searchStart <= combined.Length - pattern.Bytes.Length && hits.Count < maxHits)
        {
            var foundIndex = combinedSpan[searchStart..].IndexOf(pattern.Bytes);
            if (foundIndex < 0)
            {
                break;
            }

            var hitIndex = searchStart + foundIndex;
            var hitEnd = hitIndex + pattern.Bytes.Length;
            var startsInOverlap = hitIndex < overlapLength;
            var crossesBoundary = hitEnd > overlapLength;

            if (!startsInOverlap || crossesBoundary)
            {
                var absoluteAddress = chunkAddress.ToInt64() - overlapLength + hitIndex;
                hits.Add(new StringScanHit(
                    Address: absoluteAddress,
                    AddressHex: $"0x{absoluteAddress:X}",
                    Encoding: pattern.Label,
                    RegionBase: region.BaseAddress.ToInt64(),
                    RegionBaseHex: $"0x{region.BaseAddress.ToInt64():X}",
                    RegionSize: region.RegionSize,
                    MatchLength: pattern.Bytes.Length,
                    Classification: null,
                    Context: null));
            }

            searchStart = hitIndex + 1;
        }
    }

    private static byte[] Combine(byte[] overlap, byte[] buffer)
    {
        if (overlap.Length == 0)
        {
            return buffer;
        }

        var combined = GC.AllocateUninitializedArray<byte>(overlap.Length + buffer.Length);
        Buffer.BlockCopy(overlap, 0, combined, 0, overlap.Length);
        Buffer.BlockCopy(buffer, 0, combined, overlap.Length, buffer.Length);
        return combined;
    }

    private static IReadOnlyList<StringScanHit> EnrichHitsWithContext(
        ProcessMemoryReader reader,
        IReadOnlyList<StringScanHit> hits,
        int contextBytes)
    {
        var enriched = new List<StringScanHit>(hits.Count);

        foreach (var hit in hits)
        {
            var windowStart = Math.Max(0, hit.Address - contextBytes);
            var windowLength = checked(hit.MatchLength + (contextBytes * 2));
            var address = new nint(windowStart);

            if (!reader.TryReadBytes(address, windowLength, out var bytes, out _))
            {
                enriched.Add(hit);
                continue;
            }

            enriched.Add(hit with
            {
                Classification = ClassifyHit(hit, bytes),
                Context = new StringHitContext(
                    WindowStart: $"0x{windowStart:X}",
                    WindowLength: bytes.Length,
                    BytesHex: FormatHex(bytes),
                    AsciiPreview: BuildAsciiPreview(bytes),
                    Utf16Preview: BuildUtf16Preview(bytes))
            });
        }

        return enriched;
    }

    private static string FormatHex(byte[] bytes) =>
        string.Join(" ", bytes.Select(static value => value.ToString("X2")));

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

    private static string ClassifyHit(StringScanHit hit, byte[] bytes)
    {
        var ascii = BuildAsciiPreview(bytes);
        var utf16 = BuildUtf16Preview(bytes);
        var joined = (ascii + " " + utf16).ToLowerInvariant();

        if (joined.Contains("name = \"") || joined.Contains("playerunit = \"") || joined.Contains("readerbridgeexport_state"))
        {
            return "serialized text copy";
        }

        if (joined.Contains("reason=") || joined.Contains("health=") || joined.Contains("level="))
        {
            return "debug or log text";
        }

        if (joined.Contains("\\savedvariab") || joined.Contains(".lua") || joined.Contains("\\deepwood\\"))
        {
            return "path or file cache";
        }

        if (joined.Contains("buffs)") || joined.Contains("if no") || joined.Contains("function"))
        {
            return "script or source text";
        }

        if (joined.Contains("player:") || joined.Contains("target:") || joined.Contains("(lv"))
        {
            return "ui or display text";
        }

        if (hit.Encoding == "ascii" && ascii.Contains('@'))
        {
            return "clustered identity record";
        }

        if (hit.Encoding == "utf16" && utf16.Length > 0 && ascii.Replace(".", string.Empty).Length <= utf16.Length * 2)
        {
            return "isolated wide string";
        }

        return "unclassified";
    }

    private sealed record SearchPattern(string Label, byte[] Bytes);
}
