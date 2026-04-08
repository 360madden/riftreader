using RiftReader.Reader.Memory;

namespace RiftReader.Reader.Scanning;

public static class ProcessPointerScanner
{
    private const int ChunkSize = 1024 * 1024;

    public static PointerScanResult Scan(
        ProcessMemoryReader reader,
        int processId,
        string processName,
        nint pointerTarget,
        int pointerWidth,
        int contextBytes,
        int maxHits)
    {
        ArgumentNullException.ThrowIfNull(reader);

        if (pointerTarget == 0)
        {
            throw new ArgumentOutOfRangeException(nameof(pointerTarget), "Pointer target must be non-zero.");
        }

        if (pointerWidth is not 4 and not 8)
        {
            throw new ArgumentOutOfRangeException(nameof(pointerWidth), "Pointer width must be 4 or 8 bytes.");
        }

        if (contextBytes < 0)
        {
            throw new ArgumentOutOfRangeException(nameof(contextBytes), "Context bytes must be zero or greater.");
        }

        if (maxHits <= 0)
        {
            throw new ArgumentOutOfRangeException(nameof(maxHits), "Max hits must be greater than zero.");
        }

        var pattern = BuildPointerPattern(pointerTarget, pointerWidth);
        var hits = new List<PointerScanHit>(Math.Min(maxHits, 64));

        foreach (var region in reader.EnumerateMemoryRegions())
        {
            if (!region.IsCommitted || !region.IsReadable || region.RegionSize <= 0)
            {
                continue;
            }

            ScanRegion(reader, region, pattern, hits, maxHits);

            if (hits.Count >= maxHits)
            {
                break;
            }
        }

        return new PointerScanResult(
            Mode: "pointer-scan",
            ProcessId: processId,
            ProcessName: processName,
            PointerTarget: $"0x{pointerTarget.ToInt64():X}",
            PointerWidth: pointerWidth,
            ContextBytes: contextBytes,
            MaxHits: maxHits,
            HitCount: hits.Count,
            Hits: contextBytes > 0
                ? EnrichHitsWithContext(reader, hits, contextBytes, pointerWidth)
                : hits);
    }

    private static byte[] BuildPointerPattern(nint pointerTarget, int pointerWidth)
    {
        var bytes = BitConverter.GetBytes(pointerTarget.ToInt64());
        return pointerWidth == 8 ? bytes : bytes[..4];
    }

    private static void ScanRegion(
        ProcessMemoryReader reader,
        ProcessMemoryRegion region,
        byte[] pattern,
        List<PointerScanHit> hits,
        int maxHits)
    {
        var overlapLength = Math.Max(0, pattern.Length - 1);
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
                    hits.Add(new PointerScanHit(
                        Address: absoluteAddress,
                        AddressHex: $"0x{absoluteAddress:X}",
                        RegionBase: region.BaseAddress.ToInt64(),
                        RegionBaseHex: $"0x{region.BaseAddress.ToInt64():X}",
                        RegionSize: region.RegionSize,
                        Context: null));
                }

                searchStart = hitIndex + 1;
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

    private static IReadOnlyList<PointerScanHit> EnrichHitsWithContext(
        ProcessMemoryReader reader,
        IReadOnlyList<PointerScanHit> hits,
        int contextBytes,
        int pointerWidth)
    {
        var enriched = new List<PointerScanHit>(hits.Count);

        foreach (var hit in hits)
        {
            var windowStart = Math.Max(0, hit.Address - contextBytes);
            var windowLength = checked(pointerWidth + (contextBytes * 2));
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
}
