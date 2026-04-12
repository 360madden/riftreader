using System.Globalization;
using System.Text;
using RiftReader.Reader.AddonSnapshots;
using RiftReader.Reader.Memory;

namespace RiftReader.Reader.Scanning;

public static class TargetSignatureProbeCaptureBuilder
{
    public static TargetSignatureProbeCapture CaptureBestFamily(
        ProcessMemoryReader reader,
        int processId,
        string processName,
        ReaderBridgeSnapshotDocument snapshotDocument,
        int inspectionRadius,
        int maxHits,
        string? label,
        string? outputFile,
        bool preferCeConfirmation = true)
    {
        ArgumentNullException.ThrowIfNull(reader);
        ArgumentNullException.ThrowIfNull(snapshotDocument);

        var target = snapshotDocument.Current?.Target
            ?? throw new InvalidOperationException("ReaderBridge export did not contain a target snapshot.");

        var coord = target.Coord
            ?? throw new InvalidOperationException("ReaderBridge export did not contain target coordinates.");

        if (coord.X is not double coordX || coord.Y is not double coordY || coord.Z is not double coordZ)
        {
            throw new InvalidOperationException("ReaderBridge export did not contain a complete target coordinate triplet.");
        }

        var scanResult = ProcessTargetSignatureScanner.ScanReaderBridgeTargetSignature(
            reader,
            processId,
            processName,
            $"readerbridge-target-signature ({snapshotDocument.SourceFile})",
            (float)coordX,
            (float)coordY,
            (float)coordZ,
            target.Level,
            target.Hp,
            target.HpMax,
            target.Name,
            target.Distance,
            inspectionRadius,
            maxHits);

        if (scanResult.Families.Count == 0 || scanResult.Hits.Count == 0)
        {
            throw new InvalidOperationException("No grouped target-signature families were found.");
        }

        var ceConfirmation = preferCeConfirmation
            ? PlayerSignatureCeConfirmationLoader.TryLoad(null, out _)
            : null;
        var selected = SelectPreferredFamily(
            reader,
            scanResult,
            ceConfirmation,
            target.Level,
            TryNarrow(target.Hp),
            (float)coordX,
            (float)coordY,
            (float)coordZ);

        if (selected.Family is null || selected.RepresentativeHit is null)
        {
            throw new InvalidOperationException("Unable to resolve a representative target-signature family.");
        }

        var family = selected.Family;
        var representativeHit = selected.RepresentativeHit;
        var levelSignal = selected.LevelSignal;
        var healthSignal = selected.HealthSignal;
        var nameSignal = selected.NameSignal;
        var orderedSampleAddresses = selected.SelectionSource == "ce-confirmed" && selected.CeConfirmedSampleCount > 0
            ? selected.OrderedSampleAddresses.Take(selected.CeConfirmedSampleCount).ToArray()
            : family.SampleAddresses.Take(3).ToArray();

        var samples = new List<TargetSignatureProbeSample>(orderedSampleAddresses.Length);

        for (var index = 0; index < orderedSampleAddresses.Length; index++)
        {
            var sampleAddress = ParseHexAddress(orderedSampleAddresses[index]);
            samples.Add(new TargetSignatureProbeSample(
                SampleIndex: index + 1,
                Address: sampleAddress,
                AddressHex: $"0x{sampleAddress:X}",
                Level: levelSignal is null ? null : TryReadInt32(reader, sampleAddress + levelSignal.RelativeOffset),
                Health: healthSignal is null ? null : TryReadInt32(reader, sampleAddress + healthSignal.RelativeOffset),
                Name: nameSignal is null ? null : TryReadAscii(reader, sampleAddress + nameSignal.RelativeOffset, nameSignal.Value),
                CoordX: TryReadFloat(reader, sampleAddress + 0),
                CoordY: TryReadFloat(reader, sampleAddress + 4),
                CoordZ: TryReadFloat(reader, sampleAddress + 8),
                Distance: null));
        }

        string? resolvedOutputFile = null;

        if (!string.IsNullOrWhiteSpace(outputFile))
        {
            resolvedOutputFile = Path.GetFullPath(outputFile);
            AppendCaptureFile(resolvedOutputFile, label, family, samples);
        }

        return new TargetSignatureProbeCapture(
            Mode: "target-signature-probe-capture",
            ProcessId: processId,
            ProcessName: processName,
            SearchLabel: scanResult.SearchLabel,
            FamilyId: family.FamilyId,
            FamilyNotes: family.Notes,
            Signature: family.Signature,
            SelectionSource: selected.SelectionSource,
            ConfirmationFile: selected.ConfirmationFile,
            CeConfirmedSampleCount: selected.CeConfirmedSampleCount,
            Label: label,
            OutputFile: resolvedOutputFile,
            HitCount: samples.Count,
            Samples: samples);
    }

    private static (TargetSignatureFamilySummary? Family, TargetSignatureScanHit? RepresentativeHit, TargetSignatureSignal? LevelSignal, TargetSignatureSignal? HealthSignal, TargetSignatureSignal? NameSignal, string SelectionSource, string? ConfirmationFile, int CeConfirmedSampleCount, IReadOnlyList<string> OrderedSampleAddresses) SelectPreferredFamily(
        ProcessMemoryReader reader,
        TargetSignatureScanResult scanResult,
        PlayerSignatureCeConfirmationDocument? ceConfirmation,
        int? expectedLevel,
        int? expectedHealth,
        float expectedCoordX,
        float expectedCoordY,
        float expectedCoordZ)
    {
        var ceSelected = TrySelectCeConfirmedFamily(scanResult, ceConfirmation);
        if (ceSelected.Family is not null && ceSelected.RepresentativeHit is not null)
        {
            return ceSelected;
        }

        var verified = SelectBestVerifiedFamily(reader, scanResult, expectedLevel, expectedHealth, expectedCoordX, expectedCoordY, expectedCoordZ);
        return (
            verified.Family,
            verified.RepresentativeHit,
            verified.LevelSignal,
            verified.HealthSignal,
            verified.NameSignal,
            "heuristic",
            ceConfirmation?.ConfirmationFile,
            0,
            verified.Family?.SampleAddresses ?? Array.Empty<string>());
    }

    private static (TargetSignatureFamilySummary? Family, TargetSignatureScanHit? RepresentativeHit, TargetSignatureSignal? LevelSignal, TargetSignatureSignal? HealthSignal, TargetSignatureSignal? NameSignal, string SelectionSource, string? ConfirmationFile, int CeConfirmedSampleCount, IReadOnlyList<string> OrderedSampleAddresses) TrySelectCeConfirmedFamily(
        TargetSignatureScanResult scanResult,
        PlayerSignatureCeConfirmationDocument? ceConfirmation)
    {
        if (ceConfirmation?.WinnerFamilyId is not string winnerFamilyId || string.IsNullOrWhiteSpace(winnerFamilyId))
        {
            return default;
        }

        var family = scanResult.Families.FirstOrDefault(candidate =>
            string.Equals(candidate.FamilyId, winnerFamilyId, StringComparison.Ordinal));

        if (family is null)
        {
            return default;
        }

        var representativeHit = scanResult.Hits.FirstOrDefault(hit =>
            string.Equals(hit.FamilyId, winnerFamilyId, StringComparison.Ordinal));

        if (representativeHit is null)
        {
            return default;
        }

        return (
            family,
            representativeHit,
            FindSignal(representativeHit, "level"),
            FindSignal(representativeHit, "health"),
            FindSignal(representativeHit, "name"),
            "ce-guided-family",
            ceConfirmation.ConfirmationFile,
            0,
            family.SampleAddresses);
    }

    private static (TargetSignatureFamilySummary? Family, TargetSignatureScanHit? RepresentativeHit, TargetSignatureSignal? LevelSignal, TargetSignatureSignal? HealthSignal, TargetSignatureSignal? NameSignal) SelectBestVerifiedFamily(
        ProcessMemoryReader reader,
        TargetSignatureScanResult scanResult,
        int? expectedLevel,
        int? expectedHealth,
        float expectedCoordX,
        float expectedCoordY,
        float expectedCoordZ)
    {
        var ranked = new List<(int VerificationScore, TargetSignatureFamilySummary Family, TargetSignatureScanHit RepresentativeHit, TargetSignatureSignal? LevelSignal, TargetSignatureSignal? HealthSignal, TargetSignatureSignal? NameSignal)>();

        foreach (var family in scanResult.Families)
        {
            var representativeHit = scanResult.Hits.FirstOrDefault(hit => string.Equals(hit.FamilyId, family.FamilyId, StringComparison.Ordinal));
            if (representativeHit is null)
            {
                continue;
            }

            var levelSignal = FindSignal(representativeHit, "level");
            var healthSignal = FindSignal(representativeHit, "health");
            var nameSignal = FindSignal(representativeHit, "name");
            var verificationScore = 0;

            foreach (var sampleAddressText in family.SampleAddresses)
            {
                var sampleAddress = ParseHexAddress(sampleAddressText);
                var sampleCoordX = TryReadFloat(reader, sampleAddress + 0);
                var sampleCoordY = TryReadFloat(reader, sampleAddress + 4);
                var sampleCoordZ = TryReadFloat(reader, sampleAddress + 8);

                if (sampleCoordX.HasValue && sampleCoordY.HasValue && sampleCoordZ.HasValue &&
                    NearlyEquals(sampleCoordX.Value, expectedCoordX, 0.25f) &&
                    NearlyEquals(sampleCoordY.Value, expectedCoordY, 0.25f) &&
                    NearlyEquals(sampleCoordZ.Value, expectedCoordZ, 0.25f))
                {
                    verificationScore += 4;
                }

                if (expectedLevel.HasValue && levelSignal is not null)
                {
                    var level = TryReadInt32(reader, sampleAddress + levelSignal.RelativeOffset);
                    if (level == expectedLevel)
                    {
                        verificationScore += 1;
                    }
                }

                if (expectedHealth.HasValue && healthSignal is not null)
                {
                    var health = TryReadInt32(reader, sampleAddress + healthSignal.RelativeOffset);
                    if (health == expectedHealth)
                    {
                        verificationScore += 1;
                    }
                }
            }

            ranked.Add((verificationScore, family, representativeHit, levelSignal, healthSignal, nameSignal));
        }

        if (ranked.Count == 0)
        {
            return default;
        }

        var best = ranked
            .OrderByDescending(static entry => entry.VerificationScore)
            .ThenByDescending(static entry => entry.Family.BestScore)
            .ThenByDescending(static entry => entry.Family.HitCount)
            .ThenBy(static entry => entry.RepresentativeHit.Address)
            .First();

        return (best.Family, best.RepresentativeHit, best.LevelSignal, best.HealthSignal, best.NameSignal);
    }

    private static TargetSignatureSignal? FindSignal(TargetSignatureScanHit hit, string prefix) =>
        hit.Signals.FirstOrDefault(signal => signal.Name.StartsWith(prefix, StringComparison.Ordinal));

    private static bool NearlyEquals(float actual, float expected, float tolerance) =>
        float.IsFinite(actual) &&
        float.IsFinite(expected) &&
        MathF.Abs(actual - expected) <= tolerance;

    private static int? TryNarrow(long? value) =>
        value.HasValue && value.Value is >= int.MinValue and <= int.MaxValue
            ? (int)value.Value
            : null;

    private static long ParseHexAddress(string value)
    {
        var normalized = value.StartsWith("0x", StringComparison.OrdinalIgnoreCase)
            ? value[2..]
            : value;

        return long.Parse(normalized, NumberStyles.HexNumber, CultureInfo.InvariantCulture);
    }

    private static int? TryReadInt32(ProcessMemoryReader reader, long address)
    {
        if (!reader.TryReadBytes(new nint(address), sizeof(int), out var bytes, out _) || bytes.Length != sizeof(int))
        {
            return null;
        }

        return BitConverter.ToInt32(bytes, 0);
    }

    private static float? TryReadFloat(ProcessMemoryReader reader, long address)
    {
        if (!reader.TryReadBytes(new nint(address), sizeof(float), out var bytes, out _) || bytes.Length != sizeof(float))
        {
            return null;
        }

        return BitConverter.ToSingle(bytes, 0);
    }

    private static string? TryReadAscii(ProcessMemoryReader reader, long address, string? expectedValue)
    {
        var length = Math.Max((expectedValue?.Length ?? 0) + 16, 32);
        if (!reader.TryReadBytes(new nint(address), length, out var bytes, out _))
        {
            return null;
        }

        var terminatorIndex = Array.IndexOf(bytes, (byte)0);
        var textLength = terminatorIndex >= 0 ? terminatorIndex : bytes.Length;
        if (textLength <= 0)
        {
            return null;
        }

        var value = Encoding.ASCII.GetString(bytes, 0, textLength).Trim();
        return string.IsNullOrWhiteSpace(value) ? null : value;
    }

    private static void AppendCaptureFile(
        string outputFile,
        string? label,
        TargetSignatureFamilySummary family,
        IReadOnlyList<TargetSignatureProbeSample> samples)
    {
        var directory = Path.GetDirectoryName(outputFile);
        if (!string.IsNullOrWhiteSpace(directory))
        {
            Directory.CreateDirectory(directory);
        }

        using var writer = new StreamWriter(outputFile, append: true, new UTF8Encoding(encoderShouldEmitUTF8Identifier: false));

        foreach (var sample in samples)
        {
            writer.Write(DateTimeOffset.UtcNow.ToString("O", CultureInfo.InvariantCulture));
            writer.Write('\t');
            writer.Write(label ?? string.Empty);
            writer.Write('\t');
            writer.Write(family.FamilyId);
            writer.Write('\t');
            writer.Write(sample.SampleIndex.ToString(CultureInfo.InvariantCulture));
            writer.Write('\t');
            writer.Write(sample.AddressHex);
            writer.Write('\t');
            writer.Write(sample.Level?.ToString(CultureInfo.InvariantCulture) ?? string.Empty);
            writer.Write('\t');
            writer.Write(sample.Health?.ToString(CultureInfo.InvariantCulture) ?? string.Empty);
            writer.Write('\t');
            writer.Write(sample.CoordX?.ToString("0.00000", CultureInfo.InvariantCulture) ?? string.Empty);
            writer.Write('\t');
            writer.Write(sample.CoordY?.ToString("0.00000", CultureInfo.InvariantCulture) ?? string.Empty);
            writer.Write('\t');
            writer.Write(sample.CoordZ?.ToString("0.00000", CultureInfo.InvariantCulture) ?? string.Empty);
            writer.Write('\t');
            writer.Write((sample.Name ?? string.Empty).Replace('\t', ' ').Replace('\r', ' ').Replace('\n', ' '));
            writer.WriteLine();
        }
    }
}
