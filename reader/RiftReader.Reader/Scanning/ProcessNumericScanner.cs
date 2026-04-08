using System.Buffers.Binary;
using System.Globalization;
using RiftReader.Reader.Memory;

namespace RiftReader.Reader.Scanning;

public static class ProcessNumericScanner
{
    private const int ChunkSize = 1024 * 1024;

    public static NumericScanResult ScanInt32(
        ProcessMemoryReader reader,
        int processId,
        string processName,
        int searchValue,
        int contextBytes,
        int maxHits)
    {
        return Scan(
            reader,
            processId,
            processName,
            valueType: "int32",
            searchValue.ToString(CultureInfo.InvariantCulture),
            tolerance: null,
            width: sizeof(int),
            contextBytes,
            maxHits,
            match: span =>
            {
                var value = BinaryPrimitives.ReadInt32LittleEndian(span);
                return value == searchValue
                    ? CreateHitValue("int32", value.ToString(CultureInfo.InvariantCulture), null)
                    : null;
            });
    }

    public static NumericScanResult ScanFloat(
        ProcessMemoryReader reader,
        int processId,
        string processName,
        float searchValue,
        double tolerance,
        int contextBytes,
        int maxHits)
    {
        return Scan(
            reader,
            processId,
            processName,
            valueType: "float",
            searchValue.ToString("G9", CultureInfo.InvariantCulture),
            tolerance: tolerance > 0d ? tolerance.ToString("G9", CultureInfo.InvariantCulture) : null,
            width: sizeof(float),
            contextBytes,
            maxHits,
            match: span =>
            {
                var bits = BinaryPrimitives.ReadInt32LittleEndian(span);
                var value = BitConverter.Int32BitsToSingle(bits);
                if (!float.IsFinite(value))
                {
                    return null;
                }

                var delta = Math.Abs(value - searchValue);
                return delta <= tolerance
                    ? CreateHitValue("float", value.ToString("G9", CultureInfo.InvariantCulture), delta > 0d ? delta.ToString("G9", CultureInfo.InvariantCulture) : null)
                    : null;
            });
    }

    public static NumericScanResult ScanDouble(
        ProcessMemoryReader reader,
        int processId,
        string processName,
        double searchValue,
        double tolerance,
        int contextBytes,
        int maxHits)
    {
        return Scan(
            reader,
            processId,
            processName,
            valueType: "double",
            searchValue.ToString("G17", CultureInfo.InvariantCulture),
            tolerance: tolerance > 0d ? tolerance.ToString("G17", CultureInfo.InvariantCulture) : null,
            width: sizeof(double),
            contextBytes,
            maxHits,
            match: span =>
            {
                var bits = BinaryPrimitives.ReadInt64LittleEndian(span);
                var value = BitConverter.Int64BitsToDouble(bits);
                if (!double.IsFinite(value))
                {
                    return null;
                }

                var delta = Math.Abs(value - searchValue);
                return delta <= tolerance
                    ? CreateHitValue("double", value.ToString("G17", CultureInfo.InvariantCulture), delta > 0d ? delta.ToString("G17", CultureInfo.InvariantCulture) : null)
                    : null;
            });
    }

    private static NumericScanResult Scan(
        ProcessMemoryReader reader,
        int processId,
        string processName,
        string valueType,
        string searchValue,
        string? tolerance,
        int width,
        int contextBytes,
        int maxHits,
        Func<ReadOnlySpan<byte>, MatchedValue?> match)
    {
        ArgumentNullException.ThrowIfNull(reader);

        if (contextBytes < 0)
        {
            throw new ArgumentOutOfRangeException(nameof(contextBytes), "Context bytes must be zero or greater.");
        }

        if (maxHits <= 0)
        {
            throw new ArgumentOutOfRangeException(nameof(maxHits), "Max hits must be greater than zero.");
        }

        var hits = new List<NumericScanHit>(Math.Min(maxHits, 64));

        foreach (var region in reader.EnumerateMemoryRegions())
        {
            if (!region.IsCommitted || !region.IsReadable || region.RegionSize <= 0)
            {
                continue;
            }

            ScanRegion(reader, region, width, match, hits, maxHits);

            if (hits.Count >= maxHits)
            {
                break;
            }
        }

        return new NumericScanResult(
            Mode: "numeric-scan",
            ProcessId: processId,
            ProcessName: processName,
            ValueType: valueType,
            SearchValue: searchValue,
            Tolerance: tolerance,
            ContextBytes: contextBytes,
            MaxHits: maxHits,
            HitCount: hits.Count,
            Hits: contextBytes > 0
                ? EnrichHitsWithContext(reader, hits, contextBytes, width)
                : hits);
    }

    private static void ScanRegion(
        ProcessMemoryReader reader,
        ProcessMemoryRegion region,
        int width,
        Func<ReadOnlySpan<byte>, MatchedValue?> match,
        List<NumericScanHit> hits,
        int maxHits)
    {
        var overlapLength = width - 1;
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

            var overlapBytes = overlap.Length;
            var combined = Combine(overlap, buffer);

            for (var hitIndex = 0; hitIndex <= combined.Length - width && hits.Count < maxHits; hitIndex++)
            {
                var hitEnd = hitIndex + width;
                var startsInOverlap = hitIndex < overlapLength;
                var crossesBoundary = hitEnd > overlapLength;

                if (startsInOverlap && !crossesBoundary)
                {
                    continue;
                }

                var matchedValue = match(combined.AsSpan(hitIndex, width));
                if (matchedValue is null)
                {
                    continue;
                }

                var absoluteAddress = address.ToInt64() - overlapBytes + hitIndex;
                hits.Add(new NumericScanHit(
                    Address: absoluteAddress,
                    AddressHex: $"0x{absoluteAddress:X}",
                    RegionBase: region.BaseAddress.ToInt64(),
                    RegionBaseHex: $"0x{region.BaseAddress.ToInt64():X}",
                    RegionSize: region.RegionSize,
                    ValueType: matchedValue.ValueType,
                    ObservedValue: matchedValue.ObservedValue,
                    Delta: matchedValue.Delta,
                    Context: null));
            }

            var copyLength = Math.Min(overlapLength, combined.Length);
            overlap = copyLength > 0 ? combined[^copyLength..] : [];
            regionOffset += buffer.Length;
        }
    }

    private static IReadOnlyList<NumericScanHit> EnrichHitsWithContext(
        ProcessMemoryReader reader,
        IReadOnlyList<NumericScanHit> hits,
        int contextBytes,
        int width)
    {
        var enriched = new List<NumericScanHit>(hits.Count);

        foreach (var hit in hits)
        {
            var windowStart = Math.Max(0, hit.Address - contextBytes);
            var windowLength = checked(width + (contextBytes * 2));
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

    private static MatchedValue CreateHitValue(string valueType, string observedValue, string? delta) =>
        new(valueType, observedValue, delta);

    private sealed record MatchedValue(string ValueType, string ObservedValue, string? Delta);
}
