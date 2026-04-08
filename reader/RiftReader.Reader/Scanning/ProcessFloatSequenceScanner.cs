using System.Globalization;
using RiftReader.Reader.Memory;

namespace RiftReader.Reader.Scanning;

public static class ProcessFloatSequenceScanner
{
    private const int ChunkSize = 1024 * 1024;

    public static FloatSequenceScanResult ScanFloatTriplet(
        ProcessMemoryReader reader,
        int processId,
        string processName,
        string searchLabel,
        float first,
        float second,
        float third,
        int contextBytes,
        int maxHits)
    {
        ArgumentNullException.ThrowIfNull(reader);

        if (!float.IsFinite(first) || !float.IsFinite(second) || !float.IsFinite(third))
        {
            throw new ArgumentOutOfRangeException(nameof(first), "Float triplet values must be finite.");
        }

        if (contextBytes < 0)
        {
            throw new ArgumentOutOfRangeException(nameof(contextBytes), "Context bytes must be zero or greater.");
        }

        if (maxHits <= 0)
        {
            throw new ArgumentOutOfRangeException(nameof(maxHits), "Max hits must be greater than zero.");
        }

        var pattern = BuildPattern(first, second, third);
        var hits = new List<FloatSequenceScanHit>(Math.Min(maxHits, 64));

        foreach (var region in reader.EnumerateMemoryRegions())
        {
            if (!region.IsCommitted || !region.IsReadable || region.RegionSize <= 0)
            {
                continue;
            }

            ScanRegion(reader, region, pattern, first, second, third, hits, maxHits);

            if (hits.Count >= maxHits)
            {
                break;
            }
        }

        return new FloatSequenceScanResult(
            Mode: "float-sequence-scan",
            ProcessId: processId,
            ProcessName: processName,
            SearchLabel: searchLabel,
            SearchValues: FormatValues(first, second, third),
            ContextBytes: contextBytes,
            MaxHits: maxHits,
            HitCount: hits.Count,
            Hits: contextBytes > 0
                ? EnrichHitsWithContext(reader, hits, contextBytes, pattern.Length)
                : hits);
    }

    private static byte[] BuildPattern(float first, float second, float third)
    {
        var bytes = GC.AllocateUninitializedArray<byte>(sizeof(float) * 3);
        BitConverter.GetBytes(first).CopyTo(bytes, 0);
        BitConverter.GetBytes(second).CopyTo(bytes, sizeof(float));
        BitConverter.GetBytes(third).CopyTo(bytes, sizeof(float) * 2);
        return bytes;
    }

    private static void ScanRegion(
        ProcessMemoryReader reader,
        ProcessMemoryRegion region,
        byte[] pattern,
        float first,
        float second,
        float third,
        List<FloatSequenceScanHit> hits,
        int maxHits)
    {
        var overlapLength = pattern.Length - 1;
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
            var searchStart = 0;
            var span = combined.AsSpan();

            while (searchStart <= combined.Length - pattern.Length && hits.Count < maxHits)
            {
                var foundIndex = span[searchStart..].IndexOf(pattern);
                if (foundIndex < 0)
                {
                    break;
                }

                var hitIndex = searchStart + foundIndex;
                var hitEnd = hitIndex + pattern.Length;
                var startsInOverlap = hitIndex < overlapLength;
                var crossesBoundary = hitEnd > overlapLength;

                if (!startsInOverlap || crossesBoundary)
                {
                    var absoluteAddress = address.ToInt64() - overlapLength + hitIndex;
                    hits.Add(new FloatSequenceScanHit(
                        Address: absoluteAddress,
                        AddressHex: $"0x{absoluteAddress:X}",
                        RegionBase: region.BaseAddress.ToInt64(),
                        RegionBaseHex: $"0x{region.BaseAddress.ToInt64():X}",
                        RegionSize: region.RegionSize,
                        ObservedValues: FormatValues(first, second, third),
                        Context: null));
                }

                searchStart = hitIndex + 1;
            }

            var copyLength = Math.Min(overlapLength, combined.Length);
            overlap = copyLength > 0 ? combined[^copyLength..] : [];
            regionOffset += buffer.Length;
        }
    }

    private static IReadOnlyList<FloatSequenceScanHit> EnrichHitsWithContext(
        ProcessMemoryReader reader,
        IReadOnlyList<FloatSequenceScanHit> hits,
        int contextBytes,
        int patternLength)
    {
        var enriched = new List<FloatSequenceScanHit>(hits.Count);

        foreach (var hit in hits)
        {
            var windowStart = Math.Max(0, hit.Address - contextBytes);
            var windowLength = checked(patternLength + (contextBytes * 2));
            var address = new nint(windowStart);

            if (!reader.TryReadBytes(address, windowLength, out var bytes, out _))
            {
                enriched.Add(hit);
                continue;
            }

            enriched.Add(hit with
            {
                Context = new StringHitContext(
                    WindowStart: $"0x{windowStart:X}",
                    WindowLength: bytes.Length,
                    BytesHex: string.Join(" ", bytes.Select(static value => value.ToString("X2"))),
                    AsciiPreview: BuildAsciiPreview(bytes),
                    Utf16Preview: BuildUtf16Preview(bytes))
            });
        }

        return enriched;
    }

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

        var text = System.Text.Encoding.Unicode.GetString(bytes, 0, evenLength);
        var chars = text
            .Select(static value => !char.IsControl(value) ? value : '.')
            .ToArray();

        return new string(chars).Trim('.');
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

    private static string FormatValues(float first, float second, float third) =>
        string.Create(
            CultureInfo.InvariantCulture,
            $"{first:G9}, {second:G9}, {third:G9}");
}
