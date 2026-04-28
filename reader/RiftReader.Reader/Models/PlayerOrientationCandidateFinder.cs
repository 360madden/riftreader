using RiftReader.Reader.AddonSnapshots;
using RiftReader.Reader.Memory;
using RiftReader.Reader.Scanning;
using System.Globalization;

namespace RiftReader.Reader.Models;

public static class PlayerOrientationCandidateFinder
{
    private const int SearchWindowLength = 0x160;
    private const int CoordOffsetStart = 0x40;
    private const int CoordOffsetEnd = 0x90;
    private const int CoordStep = 0x04;
    private const double CoordTolerance = 0.25d;
    private const int BasisPrimaryLead = 0x10;
    private const int BasisPrimaryTrail = 0x50;
    private const int BasisDuplicateLead = 0x20;
    private const int BasisDuplicateTrail = 0x48;
    private const int PointerHopRootReadLength = 0x100;
    private const int PointerHopChildReadLength = 0x200;
    private const int PointerHopMaxBasisOffset = 0x160;
    private const int PointerHopMaxDepth = 2;
    private const int PointerHopMaxChildrenPerNode = 16;
    private const int PointerHopMaxQueuedNodes = 96;
    private const int PointerCarrierMinimumPointers = 2;
    private const int MinimumLocalWindowReadLength = 0x80;
    private const int MinimumPointerRootReadLength = 0x80;
    private const int MinimumPointerChildReadLength = 0x80;
    private const double PointerHopForwardComponentFloor = 0.05d;
    private const double PointerHopHorizontalMagnitudeFloor = 0.20d;

    public static PlayerOrientationCandidateSearchResult Find(
        ProcessMemoryReader reader,
        int processId,
        string processName,
        ReaderBridgeSnapshotDocument snapshotDocument,
        int maxHits,
        IReadOnlyList<PlayerOrientationProbeSeed>? probeSeeds = null,
        string? orientationCandidateLedgerFile = null)
    {
        var player = snapshotDocument.Current?.Player ?? throw new InvalidOperationException("ReaderBridge snapshot did not contain a current player.");
        var coord = player.Coord ?? throw new InvalidOperationException("ReaderBridge snapshot did not contain current player coordinates.");
        if (coord.X is null || coord.Y is null || coord.Z is null)
        {
            throw new InvalidOperationException("ReaderBridge player coordinates were incomplete.");
        }

        var scan = ProcessFloatSequenceScanner.ScanFloatTriplet(
            reader,
            processId,
            processName,
            "readerbridge-player-coords",
            (float)coord.X.Value,
            (float)coord.Y.Value,
            (float)coord.Z.Value,
            contextBytes: 0,
            maxHits: Math.Max(maxHits, 4));

        var normalizedProbeSeeds = NormalizeProbeSeeds(probeSeeds);
        var ledger = OrientationCandidateLedgerLoader.Load(orientationCandidateLedgerFile);
        var diagnostics = new OrientationProbeDiagnosticsAccumulator
        {
            CoordHitCount = scan.Hits.Count,
            SeedProbeCount = normalizedProbeSeeds.Count
        };

        var dedup = new Dictionary<long, PlayerOrientationCandidate>();

        foreach (var hit in scan.Hits)
        {
            foreach (var assumedOffset in EnumerateCoordOffsets())
            {
                if (hit.Address < assumedOffset)
                {
                    continue;
                }

                var baseAddress = hit.Address - assumedOffset;
                diagnostics.LocalWindowProbeCount++;
                if (!TryReadWindowWithFallback(reader, baseAddress, SearchWindowLength, MinimumLocalWindowReadLength, out var bytes))
                {
                    diagnostics.LocalWindowReadFailures++;
                    continue;
                }

                ProbeLocalCandidateWindow(
                    bytes,
                    baseAddress,
                    hit.AddressHex,
                    assumedOffset,
                    coord,
                    discoveryMode: "coord-hit-window",
                    probeSource: "readerbridge-player-coord-hit",
                    probeRootAddress: $"0x{baseAddress:X}",
                    scoreBonus: 0,
                    dedup,
                    diagnostics);
            }
        }

        ProbeSeededLocalCandidates(reader, coord, normalizedProbeSeeds, dedup, diagnostics);

        var ranked = dedup.Values
            .OrderByDescending(static c => c.Score)
            .ThenBy(static c => c.BasisDuplicateAgreement?.MaxRowDeltaMagnitude ?? double.MaxValue)
            .ToArray();

        var pointerHopCandidates = FindPointerHopCandidates(
                reader,
                processId,
                processName,
                snapshotDocument,
                normalizedProbeSeeds,
                diagnostics,
                ledger.EvidenceByCandidate,
                Math.Max(maxHits, 12))
            .Take(maxHits)
            .ToArray();

        var diagnosticsRecord = diagnostics.ToRecord();

        return new PlayerOrientationCandidateSearchResult(
            Mode: "player-orientation-candidate-search",
            ProcessId: processId,
            ProcessName: processName,
            PlayerName: player.Name,
            PlayerCoord: coord,
            CandidateCount: ranked.Length,
            BestCandidate: ranked.FirstOrDefault(),
            Candidates: ranked.Take(maxHits).ToArray(),
            PointerHopCandidateCount: pointerHopCandidates.Length,
            BestPointerHopCandidate: pointerHopCandidates.FirstOrDefault(),
            PointerHopCandidates: pointerHopCandidates,
            Diagnostics: diagnosticsRecord,
            Notes: BuildSearchNotes(normalizedProbeSeeds, diagnosticsRecord, ledger, pointerHopCandidates));
    }

    private static IReadOnlyList<string> BuildSearchNotes(
        IReadOnlyList<PlayerOrientationProbeSeed> probeSeeds,
        PlayerOrientationProbeDiagnostics diagnostics,
        OrientationCandidateLedger ledger,
        IReadOnlyList<PlayerOrientationPointerHopCandidate> pointerHopCandidates)
    {
        var notes = new List<string>
        {
            "Read-only single-process search over live player coord hits.",
            "Candidates scored by coord agreement, transform-like basis quality, and basis-duplicate agreement.",
            "The search now performs a bounded local sweep around coord hits instead of relying only on the original fixed offsets.",
            "When local coord-window candidates fail, the finder also follows first-hop and second-hop readable pointers from grouped player-signature family roots and explicit live probe seeds."
        };

        if (probeSeeds.Count > 0)
        {
            notes.Add($"Explicit probe seeds were used: {string.Join(", ", probeSeeds.Select(static seed => $"{seed.Source}@{seed.Address}"))}.");
        }

        notes.Add($"Pointer-hop diagnostics: roots={diagnostics.PointerRootCount}, children={diagnostics.UniqueChildPointerCount}, secondHopRoots={diagnostics.SecondHopRootCount}, childReadFailures={diagnostics.ChildReadFailures}.");

        if (diagnostics.RejectedNonOrthonormalBasisCount > 0 ||
            diagnostics.RejectedLowComponentDiversityCount > 0 ||
            diagnostics.RejectedLowHorizontalMagnitudeCount > 0)
        {
            notes.Add($"Rejected pointer-hop bases: nonOrthonormal={diagnostics.RejectedNonOrthonormalBasisCount}, lowComponentDiversity={diagnostics.RejectedLowComponentDiversityCount}, lowHorizontalMagnitude={diagnostics.RejectedLowHorizontalMagnitudeCount}.");
        }

        if (!string.IsNullOrWhiteSpace(ledger.LoadError))
        {
            notes.Add(ledger.LoadError);
        }
        else if (ledger.Entries.Count > 0)
        {
            var penalizedCount = pointerHopCandidates.Count(static candidate => candidate.LedgerPenalty > 0);
            notes.Add($"Orientation candidate ledger evidence loaded from '{ledger.FilePath}': entries={ledger.Entries.Count}, uniqueCandidates={ledger.EvidenceByCandidate.Count}, penalizedPointerHopCandidates={penalizedCount}.");
        }

        return notes;
    }

    private static IReadOnlyList<PlayerOrientationProbeSeed> NormalizeProbeSeeds(IReadOnlyList<PlayerOrientationProbeSeed>? probeSeeds)
    {
        if (probeSeeds is null || probeSeeds.Count == 0)
        {
            return Array.Empty<PlayerOrientationProbeSeed>();
        }

        var dedup = new Dictionary<long, PlayerOrientationProbeSeed>();
        foreach (var seed in probeSeeds)
        {
            if (!TryParseHexAddress(seed.Address, out var address))
            {
                continue;
            }

            var normalized = seed with { Address = $"0x{address:X}" };
            if (!dedup.TryGetValue(address, out var existing) || normalized.RootScore > existing.RootScore)
            {
                dedup[address] = normalized;
            }
        }

        return dedup.Values
            .OrderByDescending(static seed => seed.RootScore)
            .ThenBy(static seed => seed.Source, StringComparer.OrdinalIgnoreCase)
            .ToArray();
    }

    private static void ProbeSeededLocalCandidates(
        ProcessMemoryReader reader,
        ValidatorCoordinateSnapshot expectedCoord,
        IReadOnlyList<PlayerOrientationProbeSeed> probeSeeds,
        IDictionary<long, PlayerOrientationCandidate> dedup,
        OrientationProbeDiagnosticsAccumulator diagnostics)
    {
        foreach (var seed in probeSeeds)
        {
            if (!TryParseHexAddress(seed.Address, out var baseAddress))
            {
                continue;
            }

            diagnostics.LocalWindowProbeCount++;
            if (!TryReadWindowWithFallback(reader, baseAddress, SearchWindowLength, MinimumLocalWindowReadLength, out var bytes))
            {
                diagnostics.LocalWindowReadFailures++;
                diagnostics.SeedProbeReadFailures++;
                continue;
            }

            foreach (var assumedOffset in EnumerateSeedCoordOffsets(seed.PreferredCoordOffset, bytes.Length))
            {
                ProbeLocalCandidateWindow(
                    bytes,
                    baseAddress,
                    $"0x{baseAddress + assumedOffset:X}",
                    assumedOffset,
                    expectedCoord,
                    discoveryMode: "seeded-root-local",
                    probeSource: seed.Source,
                    probeRootAddress: $"0x{baseAddress:X}",
                    scoreBonus: Math.Max(0, seed.RootScore),
                    dedup,
                    diagnostics,
                    seedProbe: true);
            }
        }
    }

    private static IEnumerable<int> EnumerateSeedCoordOffsets(int? preferredCoordOffset, int byteLength)
    {
        if (preferredCoordOffset.HasValue &&
            preferredCoordOffset.Value >= 0 &&
            preferredCoordOffset.Value + 0x0C <= byteLength)
        {
            yield return preferredCoordOffset.Value;
        }

        foreach (var offset in EnumerateCoordOffsets())
        {
            if (preferredCoordOffset.HasValue && offset == preferredCoordOffset.Value)
            {
                continue;
            }

            if (offset + 0x0C <= byteLength)
            {
                yield return offset;
            }
        }
    }

    private static void ProbeLocalCandidateWindow(
        byte[] bytes,
        long baseAddress,
        string hitAddressHex,
        int assumedCoordOffset,
        ValidatorCoordinateSnapshot expectedCoord,
        string discoveryMode,
        string probeSource,
        string probeRootAddress,
        int scoreBonus,
        IDictionary<long, PlayerOrientationCandidate> dedup,
        OrientationProbeDiagnosticsAccumulator diagnostics,
        bool seedProbe = false)
    {
        var primaryCoord = ReadTriplet(bytes, assumedCoordOffset);
        var primaryCoordMatch = MatchesCoord(primaryCoord, expectedCoord, CoordTolerance);
        if (!primaryCoordMatch)
        {
            diagnostics.LocalCoordMismatchCount++;
            return;
        }

        if (seedProbe)
        {
            diagnostics.SeedCoordMatchCount++;
        }

        var secondaryCoordMatch = FindBestSecondaryCoordMatch(bytes, assumedCoordOffset, expectedCoord);
        PlayerOrientationCandidate? bestForBase = null;

        foreach (var forwardOffset in EnumeratePrimaryForwardOffsets(assumedCoordOffset, bytes.Length))
        {
            foreach (var duplicateForwardOffset in EnumerateDuplicateForwardOffsets(forwardOffset, bytes.Length))
            {
                var basis = TryBuildCandidate(
                    bytes,
                    baseAddress,
                    hitAddressHex,
                    assumedCoordOffset,
                    primaryCoord,
                    secondaryCoordMatch.Coord,
                    primaryCoordMatch,
                    secondaryCoordMatch.Matches,
                    secondaryCoordMatch.Offset,
                    forwardOffset,
                    duplicateForwardOffset,
                    discoveryMode,
                    probeSource,
                    probeRootAddress,
                    scoreBonus);

                if (basis is null)
                {
                    continue;
                }

                if (bestForBase is null || basis.Score > bestForBase.Score)
                {
                    bestForBase = basis;
                }
            }
        }

        if (bestForBase is not null &&
            (!dedup.TryGetValue(baseAddress, out var existing) || bestForBase.Score > existing.Score))
        {
            dedup[baseAddress] = bestForBase;
        }
    }

    private static PlayerOrientationCandidate? TryBuildCandidate(
        byte[] bytes,
        long baseAddress,
        string hitAddressHex,
        int assumedCoordOffset,
        ValidatorCoordinateSnapshot primaryCoord,
        ValidatorCoordinateSnapshot secondaryCoord,
        bool primaryCoordMatch,
        bool secondaryCoordMatch,
        int? secondaryCoordOffset,
        int forwardOffset,
        int duplicateForwardOffset,
        string discoveryMode,
        string probeSource,
        string probeRootAddress,
        int scoreBonus)
    {
        var basisPrimary = ReadBasis(
            bytes,
            forwardOffset,
            forwardOffset + 0x0C,
            forwardOffset + 0x18,
            $"Basis@0x{forwardOffset:X}");

        var basisDuplicate = ReadBasis(
            bytes,
            duplicateForwardOffset,
            duplicateForwardOffset + 0x0C,
            duplicateForwardOffset + 0x18,
            $"Basis@0x{duplicateForwardOffset:X}");

        var preferredEstimate = Estimate("Preferred", basisPrimary.Forward);
        var duplicateEstimate = Estimate("Duplicate", basisDuplicate.Forward);
        var duplicateAgreement = BuildDuplicateAgreement(basisPrimary, basisDuplicate);
        var score = Score(primaryCoordMatch, secondaryCoordMatch, basisPrimary, basisDuplicate, preferredEstimate, duplicateEstimate, duplicateAgreement);
        if (score <= 0)
        {
            return null;
        }

        return new PlayerOrientationCandidate(
            Address: $"0x{baseAddress:X}",
            HitAddress: hitAddressHex,
            AssumedCoordOffset: $"0x{assumedCoordOffset:X}",
            CoordPrimaryOffset: $"0x{assumedCoordOffset:X}",
            CoordDuplicateOffset: secondaryCoordOffset.HasValue ? $"0x{secondaryCoordOffset.Value:X}" : null,
            BasisPrimaryForwardOffset: $"0x{forwardOffset:X}",
            BasisDuplicateForwardOffset: $"0x{duplicateForwardOffset:X}",
            Score: score + Math.Max(0, scoreBonus),
            Coord48MatchesPlayer: primaryCoordMatch,
            Coord88MatchesPlayer: secondaryCoordMatch,
            Coord48: primaryCoord,
            Coord88: secondaryCoord,
            Basis60: basisPrimary,
            Basis94: basisDuplicate,
            BasisDuplicateAgreement: duplicateAgreement,
            PreferredEstimate: preferredEstimate,
            DuplicateEstimate: duplicateEstimate,
            DiscoveryMode: discoveryMode,
            ProbeSource: probeSource,
            ProbeRootAddress: probeRootAddress);
    }

    private static ValidatorCoordinateSnapshot ReadTriplet(byte[] bytes, int offset) =>
        new(ReadSingle(bytes, offset), ReadSingle(bytes, offset + 4), ReadSingle(bytes, offset + 8));

    private static double? ReadSingle(byte[] bytes, int offset)
    {
        if (offset + 4 > bytes.Length) return null;
        var value = (double)BitConverter.ToSingle(bytes, offset);
        if (double.IsNaN(value) || double.IsInfinity(value) || Math.Abs(value) > 1_000_000d) return null;
        return value;
    }

    private static PlayerOrientationBasisCandidate ReadBasis(byte[] bytes, int forwardOffset, int upOffset, int rightOffset, string name)
    {
        var forward = ReadTriplet(bytes, forwardOffset);
        var up = ReadTriplet(bytes, upOffset);
        var right = ReadTriplet(bytes, rightOffset);
        var forwardEstimate = Estimate(name + ".Forward", forward);
        var upEstimate = Estimate(name + ".Up", up);
        var rightEstimate = Estimate(name + ".Right", right);
        var fwdUp = Dot(forward, up);
        var fwdRight = Dot(forward, right);
        var upRight = Dot(up, right);
        var determinant = Dot(Cross(forward, up), right);
        var ortho = IsOrthonormal(forwardEstimate.Magnitude, upEstimate.Magnitude, rightEstimate.Magnitude, fwdUp, fwdRight, upRight, determinant);
        return new(name, forward, up, right, determinant, ortho, fwdUp, fwdRight, upRight);
    }

    private static bool IsOrthonormal(double? a, double? b, double? c, double? ab, double? ac, double? bc, double? det) =>
        a.HasValue && b.HasValue && c.HasValue && ab.HasValue && ac.HasValue && bc.HasValue && det.HasValue &&
        Math.Abs(a.Value - 1d) <= 0.02 && Math.Abs(b.Value - 1d) <= 0.02 && Math.Abs(c.Value - 1d) <= 0.02 &&
        Math.Abs(ab.Value) <= 0.02 && Math.Abs(ac.Value) <= 0.02 && Math.Abs(bc.Value) <= 0.02 && Math.Abs(Math.Abs(det.Value) - 1d) <= 0.02;

    private static PlayerOrientationBasisDuplicateAgreement? BuildDuplicateAgreement(PlayerOrientationBasisCandidate left, PlayerOrientationBasisCandidate right)
    {
        var fd = Delta(left.Forward, right.Forward);
        var ud = Delta(left.Up, right.Up);
        var rd = Delta(left.Right, right.Right);
        var vals = new[] { fd, ud, rd }.Where(static v => v.HasValue).Select(static v => v!.Value).ToArray();
        if (vals.Length == 0) return null;
        var max = vals.Max();
        return new(fd, ud, rd, max, max <= 0.0001d, max <= 0.01d);
    }

    private static int Score(
        bool coordPrimary,
        bool coordDuplicate,
        PlayerOrientationBasisCandidate basis60,
        PlayerOrientationBasisCandidate basis94,
        PlayerOrientationVectorEstimate preferredEstimate,
        PlayerOrientationVectorEstimate duplicateEstimate,
        PlayerOrientationBasisDuplicateAgreement? duplicate)
    {
        var score = 0;
        if (coordPrimary) score += 40;
        if (coordDuplicate) score += 140;
        if (!coordPrimary) return 0;
        if (!coordDuplicate && !basis60.IsOrthonormal && !basis94.IsOrthonormal) return 0;
        if (basis60.IsOrthonormal) score += 80;
        if (basis94.IsOrthonormal) score += 80;
        score += MagnitudeScore(preferredEstimate.Magnitude);
        score += MagnitudeScore(duplicateEstimate.Magnitude);
        score += DirectionalityScore(basis60);
        score += DirectionalityScore(basis94);
        if (!basis60.IsOrthonormal && !basis94.IsOrthonormal && (preferredEstimate.Magnitude is null || preferredEstimate.Magnitude < 0.3) && (duplicateEstimate.Magnitude is null || duplicateEstimate.Magnitude < 0.3))
        {
            return 0;
        }
        if (duplicate is not null)
        {
            if (duplicate.Strong) score += 80;
            else if (duplicate.Usable) score += 60;
            else if (duplicate.MaxRowDeltaMagnitude <= 0.05d) score += 40;
        }
        score += DeterminantBonus(basis60.Determinant);
        score += DeterminantBonus(basis94.Determinant);
        return score;
    }

    private static int MagnitudeScore(double? magnitude)
    {
        if (!magnitude.HasValue) return 0;
        var value = magnitude.Value;
        if (value is >= 0.85 and <= 1.15) return 60;
        if (value is >= 0.5 and <= 1.5) return 25;
        if (value < 0.05) return -120;
        if (value < 0.2) return -60;
        return 0;
    }

    private static int DirectionalityScore(PlayerOrientationBasisCandidate basis)
    {
        var score = 0;
        if (HasMeaningfulVector(basis.Forward)) score += 20;
        if (HasMeaningfulVector(basis.Up)) score += 10;
        if (HasMeaningfulVector(basis.Right)) score += 10;
        return score;
    }

    private static bool HasMeaningfulVector(ValidatorCoordinateSnapshot vector)
    {
        if (vector.X is null || vector.Y is null || vector.Z is null)
        {
            return false;
        }

        var magnitude = Math.Sqrt((vector.X.Value * vector.X.Value) + (vector.Y.Value * vector.Y.Value) + (vector.Z.Value * vector.Z.Value));
        return magnitude >= 0.2d;
    }

    private static int DeterminantBonus(double? determinant)
    {
        if (!determinant.HasValue) return 0;
        var delta = Math.Abs(Math.Abs(determinant.Value) - 1d);
        if (delta > 5d) return 0;
        return Math.Max(0, 20 - (int)(delta * 100));
    }

    private static bool MatchesCoord(ValidatorCoordinateSnapshot candidate, ValidatorCoordinateSnapshot expected, double tolerance) =>
        candidate.X.HasValue && candidate.Y.HasValue && candidate.Z.HasValue &&
        expected.X.HasValue && expected.Y.HasValue && expected.Z.HasValue &&
        Math.Abs(candidate.X.Value - expected.X.Value) <= tolerance &&
        Math.Abs(candidate.Y.Value - expected.Y.Value) <= tolerance &&
        Math.Abs(candidate.Z.Value - expected.Z.Value) <= tolerance;

    private static PlayerOrientationVectorEstimate Estimate(string name, ValidatorCoordinateSnapshot vector)
    {
        if (vector.X is null || vector.Y is null || vector.Z is null)
        {
            return new(name, vector, null, null, null, null, null);
        }
        var x = vector.X.Value; var y = vector.Y.Value; var z = vector.Z.Value;
        var mag = Math.Sqrt(x * x + y * y + z * z);
        if (mag <= double.Epsilon) return new(name, vector, null, null, null, null, mag);
        var yaw = Math.Atan2(z, x);
        var pitch = Math.Atan2(y, Math.Sqrt(x * x + z * z));
        return new(name, vector, yaw, yaw * 180d / Math.PI, pitch, pitch * 180d / Math.PI, mag);
    }

    private static double? Dot(ValidatorCoordinateSnapshot a, ValidatorCoordinateSnapshot b) =>
        a.X.HasValue && a.Y.HasValue && a.Z.HasValue && b.X.HasValue && b.Y.HasValue && b.Z.HasValue
            ? (a.X.Value * b.X.Value) + (a.Y.Value * b.Y.Value) + (a.Z.Value * b.Z.Value)
            : null;

    private static ValidatorCoordinateSnapshot Cross(ValidatorCoordinateSnapshot a, ValidatorCoordinateSnapshot b) =>
        a.X.HasValue && a.Y.HasValue && a.Z.HasValue && b.X.HasValue && b.Y.HasValue && b.Z.HasValue
            ? new(
                (a.Y.Value * b.Z.Value) - (a.Z.Value * b.Y.Value),
                (a.Z.Value * b.X.Value) - (a.X.Value * b.Z.Value),
                (a.X.Value * b.Y.Value) - (a.Y.Value * b.X.Value))
            : new(null, null, null);

    private static double? Delta(ValidatorCoordinateSnapshot a, ValidatorCoordinateSnapshot b) =>
        a.X.HasValue && a.Y.HasValue && a.Z.HasValue && b.X.HasValue && b.Y.HasValue && b.Z.HasValue
            ? Math.Sqrt(Math.Pow(a.X.Value - b.X.Value, 2) + Math.Pow(a.Y.Value - b.Y.Value, 2) + Math.Pow(a.Z.Value - b.Z.Value, 2))
            : null;

    private static IEnumerable<int> EnumerateCoordOffsets()
    {
        for (var offset = CoordOffsetStart; offset <= CoordOffsetEnd; offset += CoordStep)
        {
            yield return offset;
        }
    }

    private static IEnumerable<int> EnumeratePrimaryForwardOffsets(int assumedCoordOffset, int byteLength)
    {
        var start = Math.Max(0, assumedCoordOffset + BasisPrimaryLead);
        var end = Math.Min(byteLength - 0x1C, assumedCoordOffset + BasisPrimaryTrail);

        for (var offset = start; offset <= end; offset += CoordStep)
        {
            yield return offset;
        }
    }

    private static IEnumerable<int> EnumerateDuplicateForwardOffsets(int primaryForwardOffset, int byteLength)
    {
        var start = Math.Max(primaryForwardOffset + 0x0C, primaryForwardOffset + BasisDuplicateLead);
        var end = Math.Min(byteLength - 0x1C, primaryForwardOffset + BasisDuplicateTrail);

        for (var offset = start; offset <= end; offset += CoordStep)
        {
            yield return offset;
        }
    }

    private static (int? Offset, ValidatorCoordinateSnapshot Coord, bool Matches) FindBestSecondaryCoordMatch(
        byte[] bytes,
        int primaryCoordOffset,
        ValidatorCoordinateSnapshot expected)
    {
        int? bestOffset = null;
        var bestCoord = new ValidatorCoordinateSnapshot(null, null, null);
        var bestDistance = double.MaxValue;

        foreach (var offset in EnumerateCoordOffsets())
        {
            if (offset == primaryCoordOffset)
            {
                continue;
            }

            var coord = ReadTriplet(bytes, offset);
            if (!MatchesCoord(coord, expected, CoordTolerance))
            {
                continue;
            }

            var distance = Math.Abs(offset - primaryCoordOffset);
            if (distance < bestDistance)
            {
                bestDistance = distance;
                bestOffset = offset;
                bestCoord = coord;
            }
        }

        return (bestOffset, bestCoord, bestOffset.HasValue);
    }

    private static IReadOnlyList<PlayerOrientationPointerHopCandidate> FindPointerHopCandidates(
        ProcessMemoryReader reader,
        int processId,
        string processName,
        ReaderBridgeSnapshotDocument snapshotDocument,
        IReadOnlyList<PlayerOrientationProbeSeed> probeSeeds,
        OrientationProbeDiagnosticsAccumulator diagnostics,
        IReadOnlyDictionary<string, OrientationCandidateLedgerEvidence> ledgerEvidenceByCandidate,
        int maxHits)
    {
        var player = snapshotDocument.Current?.Player ?? throw new InvalidOperationException("ReaderBridge snapshot did not contain a current player.");
        var coord = player.Coord ?? throw new InvalidOperationException("ReaderBridge snapshot did not contain current player coordinates.");
        if (coord.X is null || coord.Y is null || coord.Z is null)
        {
            return Array.Empty<PlayerOrientationPointerHopCandidate>();
        }

        var scan = ProcessPlayerSignatureScanner.ScanReaderBridgePlayerSignature(
            reader,
            processId,
            processName,
            $"readerbridge-player-signature ({snapshotDocument.SourceFile})",
            (float)coord.X.Value,
            (float)coord.Y.Value,
            (float)coord.Z.Value,
            player.Level,
            player.Hp,
            player.HpMax,
            player.Name,
            player.LocationName,
            inspectionRadius: 96,
            maxHits: maxHits);

        var roots = BuildPointerProbeRoots(scan, probeSeeds);
        diagnostics.PointerRootCount = roots.Count;

        var bestByChildAddress = new Dictionary<long, PlayerOrientationPointerHopCandidate>();
        var queuedNodeKeys = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        var queue = new Queue<PointerProbeNode>();

        foreach (var root in roots)
        {
            if (queuedNodeKeys.Add(root.Key))
            {
                queue.Enqueue(root);
            }
        }

        var queuedNodeCount = queue.Count;
        while (queue.Count > 0 && queuedNodeCount <= PointerHopMaxQueuedNodes)
        {
            var node = queue.Dequeue();
            var readLength = node.Depth == 0 ? PointerHopRootReadLength : PointerHopChildReadLength;
            var minimumReadLength = node.Depth == 0 ? MinimumPointerRootReadLength : MinimumPointerChildReadLength;

            if (!TryReadWindowWithFallback(reader, node.CurrentAddress, readLength, minimumReadLength, out var rootBytes))
            {
                diagnostics.PointerRootReadFailures++;
                continue;
            }

            var seenChildAddresses = new HashSet<long>();
            var enqueuedChildren = 0;

            for (var offset = 0; offset + sizeof(ulong) <= rootBytes.Length; offset += sizeof(ulong))
            {
                diagnostics.PointerSlotCount++;

                var childAddressValue = BitConverter.ToUInt64(rootBytes, offset);
                if (!LooksLikeUserPointer(childAddressValue))
                {
                    continue;
                }

                var childAddress = checked((long)childAddressValue);
                if (!seenChildAddresses.Add(childAddress))
                {
                    continue;
                }

                diagnostics.UniqueChildPointerCount++;

                if (!TryReadWindowWithFallback(reader, childAddress, PointerHopChildReadLength, MinimumPointerChildReadLength, out var childBytes))
                {
                    diagnostics.ChildReadFailures++;
                    continue;
                }

                var bestForChild = FindBestPointerHopBasisForChild(
                    childBytes,
                    childAddress,
                    node.CurrentAddressHex,
                    node.RootAddressHex,
                    node.RootSource,
                    node.FamilyId,
                    node.RootScore,
                    node.Depth + 1,
                    offset,
                    diagnostics);

                if (bestForChild is not null &&
                    (!bestByChildAddress.TryGetValue(childAddress, out var existing) || bestForChild.Score > existing.Score))
                {
                    bestByChildAddress[childAddress] = bestForChild;
                }

                if (node.Depth + 1 >= PointerHopMaxDepth ||
                    enqueuedChildren >= PointerHopMaxChildrenPerNode ||
                    queuedNodeCount >= PointerHopMaxQueuedNodes ||
                    !LooksLikePointerCarrier(childBytes))
                {
                    continue;
                }

                var childNode = new PointerProbeNode(
                    RootAddress: node.RootAddress,
                    RootAddressHex: node.RootAddressHex,
                    RootSource: node.RootSource,
                    FamilyId: node.FamilyId,
                    RootScore: Math.Max(node.RootScore, bestForChild?.Score ?? node.RootScore),
                    CurrentAddress: childAddress,
                    CurrentAddressHex: $"0x{childAddress:X}",
                    Depth: node.Depth + 1);

                if (queuedNodeKeys.Add(childNode.Key))
                {
                    queue.Enqueue(childNode);
                    queuedNodeCount++;
                    enqueuedChildren++;
                    diagnostics.SecondHopRootCount++;
                }
            }
        }

        return bestByChildAddress.Values
            .Select(candidate => ApplyLedgerEvidence(candidate, ledgerEvidenceByCandidate))
            .OrderByDescending(static candidate => candidate.Score)
            .ThenBy(static candidate => candidate.HopDepth)
            .ThenBy(static candidate => Math.Abs(candidate.PreferredEstimate.YawDegrees ?? double.MaxValue))
            .ToArray();
    }

    private static PlayerOrientationPointerHopCandidate ApplyLedgerEvidence(
        PlayerOrientationPointerHopCandidate candidate,
        IReadOnlyDictionary<string, OrientationCandidateLedgerEvidence> ledgerEvidenceByCandidate)
    {
        var rawScore = candidate.Score;
        var key = OrientationCandidateLedgerLoader.BuildCandidateKey(candidate.Address, candidate.BasisPrimaryForwardOffset);
        if (string.IsNullOrWhiteSpace(key) ||
            !ledgerEvidenceByCandidate.TryGetValue(key, out var evidence))
        {
            return candidate with { RawScore = rawScore };
        }

        var penalty = evidence.ScorePenalty;
        return candidate with
        {
            Score = Math.Max(0, rawScore - penalty),
            RawScore = rawScore,
            LedgerPenalty = penalty,
            LedgerRejectionReason = evidence.LatestCandidateRejectedReason,
            LedgerStableNonresponsiveCount = evidence.StableNonresponsiveCount,
            LedgerResponsiveCount = evidence.ResponsiveCount,
            LedgerLatestGeneratedAtUtc = evidence.LatestGeneratedAtUtc
        };
    }

    private static IReadOnlyList<PointerProbeNode> BuildPointerProbeRoots(
        PlayerSignatureScanResult scan,
        IReadOnlyList<PlayerOrientationProbeSeed> probeSeeds)
    {
        var roots = new List<PointerProbeNode>();

        foreach (var family in scan.Families)
        {
            foreach (var sampleAddressText in family.SampleAddresses)
            {
                if (!TryParseHexAddress(sampleAddressText, out var sampleAddress))
                {
                    continue;
                }

                roots.Add(new PointerProbeNode(
                    RootAddress: sampleAddress,
                    RootAddressHex: $"0x{sampleAddress:X}",
                    RootSource: "player-signature-family",
                    FamilyId: family.FamilyId,
                    RootScore: family.BestScore,
                    CurrentAddress: sampleAddress,
                    CurrentAddressHex: $"0x{sampleAddress:X}",
                    Depth: 0));
            }
        }

        foreach (var seed in probeSeeds)
        {
            if (!TryParseHexAddress(seed.Address, out var seedAddress))
            {
                continue;
            }

            roots.Add(new PointerProbeNode(
                RootAddress: seedAddress,
                RootAddressHex: $"0x{seedAddress:X}",
                RootSource: seed.Source,
                FamilyId: null,
                RootScore: Math.Max(0, seed.RootScore),
                CurrentAddress: seedAddress,
                CurrentAddressHex: $"0x{seedAddress:X}",
                Depth: 0));
        }

        return roots;
    }

    private static PlayerOrientationPointerHopCandidate? FindBestPointerHopBasisForChild(
        byte[] childBytes,
        long childAddress,
        string parentAddressHex,
        string rootAddressHex,
        string rootSource,
        string? parentFamilyId,
        int parentScore,
        int hopDepth,
        int pointerOffset,
        OrientationProbeDiagnosticsAccumulator diagnostics)
    {
        PlayerOrientationPointerHopCandidate? best = null;
        var maxBasisOffset = Math.Min(PointerHopMaxBasisOffset, childBytes.Length - 0x1C);

        for (var basisOffset = 0; basisOffset <= maxBasisOffset; basisOffset += CoordStep)
        {
            var basis = ReadBasis(
                childBytes,
                basisOffset,
                basisOffset + 0x0C,
                basisOffset + 0x18,
                $"Basis@0x{basisOffset:X}");

            var rejectionReason = GetPointerHopBasisRejectionReason(basis);
            if (rejectionReason is not PointerHopBasisRejectionReason.None)
            {
                diagnostics.RecordPointerHopRejection(rejectionReason);
                continue;
            }

            var estimate = Estimate($"Basis@0x{basisOffset:X}", basis.Forward);
            var candidate = new PlayerOrientationPointerHopCandidate(
                Address: $"0x{childAddress:X}",
                ParentAddress: parentAddressHex,
                ParentFamilyId: parentFamilyId,
                ParentScore: parentScore,
                DiscoveryMode: hopDepth == 1 ? "pointer-hop" : "second-hop-pointer-hop",
                BasisPrimaryForwardOffset: $"0x{basisOffset:X}",
                Score: ScorePointerHopCandidate(basis, estimate, parentScore, hopDepth, rootSource),
                Basis: basis,
                PreferredEstimate: estimate,
                RootAddress: rootAddressHex,
                RootSource: rootSource,
                HopDepth: hopDepth,
                PointerOffset: $"0x{pointerOffset:X}");

            if (best is null || candidate.Score > best.Score)
            {
                best = candidate;
            }
        }

        return best;
    }

    private static bool LooksLikeUserPointer(ulong value) =>
        value >= 0x0000000000010000UL &&
        value <= 0x00007FFFFFFFFFFFUL &&
        (value % sizeof(ulong)) == 0;

    private static bool TryParseHexAddress(string value, out long address)
    {
        address = 0;
        if (string.IsNullOrWhiteSpace(value))
        {
            return false;
        }

        var normalized = value.StartsWith("0x", StringComparison.OrdinalIgnoreCase)
            ? value[2..]
            : value;

        return long.TryParse(normalized, NumberStyles.HexNumber, CultureInfo.InvariantCulture, out address) && address > 0;
    }

    private static PointerHopBasisRejectionReason GetPointerHopBasisRejectionReason(PlayerOrientationBasisCandidate basis)
    {
        if (!basis.IsOrthonormal)
        {
            return PointerHopBasisRejectionReason.NonOrthonormal;
        }

        if (basis.Forward.X is not double x || basis.Forward.Y is not double y || basis.Forward.Z is not double z)
        {
            return PointerHopBasisRejectionReason.NonOrthonormal;
        }

        var components = new[]
        {
            Math.Abs(x),
            Math.Abs(y),
            Math.Abs(z)
        };

        var nonTrivialComponents = components.Count(component => component >= PointerHopForwardComponentFloor);
        if (nonTrivialComponents < 2)
        {
            return PointerHopBasisRejectionReason.LowComponentDiversity;
        }

        var horizontalMagnitude = Math.Sqrt((x * x) + (z * z));
        return horizontalMagnitude < PointerHopHorizontalMagnitudeFloor
            ? PointerHopBasisRejectionReason.LowHorizontalMagnitude
            : PointerHopBasisRejectionReason.None;
    }

    private static bool LooksLikePointerCarrier(byte[] bytes)
    {
        var pointerCount = 0;
        for (var offset = 0; offset + sizeof(ulong) <= bytes.Length; offset += sizeof(ulong))
        {
            if (!LooksLikeUserPointer(BitConverter.ToUInt64(bytes, offset)))
            {
                continue;
            }

            pointerCount++;
            if (pointerCount >= PointerCarrierMinimumPointers)
            {
                return true;
            }
        }

        return false;
    }

    private static bool TryReadWindowWithFallback(
        ProcessMemoryReader reader,
        long address,
        int preferredLength,
        int minimumLength,
        out byte[] bytes)
    {
        var length = preferredLength;
        while (length >= minimumLength)
        {
            if (reader.TryReadBytes(new nint(address), length, out bytes, out _))
            {
                return true;
            }

            length -= 0x20;
        }

        bytes = Array.Empty<byte>();
        return false;
    }

    private static int ScorePointerHopCandidate(
        PlayerOrientationBasisCandidate basis,
        PlayerOrientationVectorEstimate estimate,
        int parentScore,
        int hopDepth,
        string rootSource)
    {
        var score = Math.Max(0, parentScore);

        if (basis.IsOrthonormal)
        {
            score += 80;
        }

        score += DeterminantBonus(basis.Determinant);

        if (estimate.Magnitude is >= 0.85d and <= 1.15d)
        {
            score += 40;
        }

        score += hopDepth == 1 ? 20 : 10;

        if (string.Equals(rootSource, "coord-anchor-source-object", StringComparison.OrdinalIgnoreCase))
        {
            score += 60;
        }
        else if (string.Equals(rootSource, "coord-anchor-object-base", StringComparison.OrdinalIgnoreCase))
        {
            score += 35;
        }

        return score;
    }

    private sealed record PointerProbeNode(
        long RootAddress,
        string RootAddressHex,
        string RootSource,
        string? FamilyId,
        int RootScore,
        long CurrentAddress,
        string CurrentAddressHex,
        int Depth)
    {
        public string Key => $"{RootAddressHex}:{CurrentAddressHex}:{Depth}";
    }

    private enum PointerHopBasisRejectionReason
    {
        None = 0,
        NonOrthonormal,
        LowComponentDiversity,
        LowHorizontalMagnitude
    }

    private sealed class OrientationProbeDiagnosticsAccumulator
    {
        public int CoordHitCount { get; set; }
        public int LocalWindowProbeCount { get; set; }
        public int LocalWindowReadFailures { get; set; }
        public int LocalCoordMismatchCount { get; set; }
        public int SeedProbeCount { get; set; }
        public int SeedProbeReadFailures { get; set; }
        public int SeedCoordMatchCount { get; set; }
        public int PointerRootCount { get; set; }
        public int PointerRootReadFailures { get; set; }
        public int PointerSlotCount { get; set; }
        public int UniqueChildPointerCount { get; set; }
        public int ChildReadFailures { get; set; }
        public int SecondHopRootCount { get; set; }
        public int RejectedNonOrthonormalBasisCount { get; set; }
        public int RejectedLowComponentDiversityCount { get; set; }
        public int RejectedLowHorizontalMagnitudeCount { get; set; }

        public void RecordPointerHopRejection(PointerHopBasisRejectionReason reason)
        {
            switch (reason)
            {
                case PointerHopBasisRejectionReason.NonOrthonormal:
                    RejectedNonOrthonormalBasisCount++;
                    break;
                case PointerHopBasisRejectionReason.LowComponentDiversity:
                    RejectedLowComponentDiversityCount++;
                    break;
                case PointerHopBasisRejectionReason.LowHorizontalMagnitude:
                    RejectedLowHorizontalMagnitudeCount++;
                    break;
            }
        }

        public PlayerOrientationProbeDiagnostics ToRecord() =>
            new(
                CoordHitCount,
                LocalWindowProbeCount,
                LocalWindowReadFailures,
                LocalCoordMismatchCount,
                SeedProbeCount,
                SeedProbeReadFailures,
                SeedCoordMatchCount,
                PointerRootCount,
                PointerRootReadFailures,
                PointerSlotCount,
                UniqueChildPointerCount,
                ChildReadFailures,
                SecondHopRootCount,
                RejectedNonOrthonormalBasisCount,
                RejectedLowComponentDiversityCount,
                RejectedLowHorizontalMagnitudeCount);
    }
}

public sealed record PlayerOrientationCandidateSearchResult(
    string Mode,
    int ProcessId,
    string ProcessName,
    string? PlayerName,
    ValidatorCoordinateSnapshot PlayerCoord,
    int CandidateCount,
    PlayerOrientationCandidate? BestCandidate,
    IReadOnlyList<PlayerOrientationCandidate> Candidates,
    int PointerHopCandidateCount,
    PlayerOrientationPointerHopCandidate? BestPointerHopCandidate,
    IReadOnlyList<PlayerOrientationPointerHopCandidate> PointerHopCandidates,
    PlayerOrientationProbeDiagnostics Diagnostics,
    IReadOnlyList<string> Notes);

public sealed record PlayerOrientationCandidate(
    string Address,
    string HitAddress,
    string AssumedCoordOffset,
    string CoordPrimaryOffset,
    string? CoordDuplicateOffset,
    string BasisPrimaryForwardOffset,
    string BasisDuplicateForwardOffset,
    int Score,
    bool Coord48MatchesPlayer,
    bool Coord88MatchesPlayer,
    ValidatorCoordinateSnapshot Coord48,
    ValidatorCoordinateSnapshot Coord88,
    PlayerOrientationBasisCandidate Basis60,
    PlayerOrientationBasisCandidate Basis94,
    PlayerOrientationBasisDuplicateAgreement? BasisDuplicateAgreement,
    PlayerOrientationVectorEstimate PreferredEstimate,
    PlayerOrientationVectorEstimate DuplicateEstimate,
    string DiscoveryMode,
    string ProbeSource,
    string ProbeRootAddress);

public sealed record PlayerOrientationBasisCandidate(
    string Name,
    ValidatorCoordinateSnapshot Forward,
    ValidatorCoordinateSnapshot Up,
    ValidatorCoordinateSnapshot Right,
    double? Determinant,
    bool IsOrthonormal,
    double? ForwardDotUp,
    double? ForwardDotRight,
    double? UpDotRight);

public sealed record PlayerOrientationBasisDuplicateAgreement(
    double? ForwardDeltaMagnitude,
    double? UpDeltaMagnitude,
    double? RightDeltaMagnitude,
    double MaxRowDeltaMagnitude,
    bool Strong,
    bool Usable);

public sealed record PlayerOrientationPointerHopCandidate(
    string Address,
    string ParentAddress,
    string? ParentFamilyId,
    int ParentScore,
    string DiscoveryMode,
    string BasisPrimaryForwardOffset,
    int Score,
    PlayerOrientationBasisCandidate Basis,
    PlayerOrientationVectorEstimate PreferredEstimate,
    string RootAddress,
    string RootSource,
    int HopDepth,
    string PointerOffset,
    int? RawScore = null,
    int LedgerPenalty = 0,
    string? LedgerRejectionReason = null,
    int LedgerStableNonresponsiveCount = 0,
    int LedgerResponsiveCount = 0,
    string? LedgerLatestGeneratedAtUtc = null);

public sealed record PlayerOrientationProbeSeed(
    string Address,
    string Source,
    int RootScore = 0,
    int? PreferredCoordOffset = null);

public sealed record PlayerOrientationProbeDiagnostics(
    int CoordHitCount,
    int LocalWindowProbeCount,
    int LocalWindowReadFailures,
    int LocalCoordMismatchCount,
    int SeedProbeCount,
    int SeedProbeReadFailures,
    int SeedCoordMatchCount,
    int PointerRootCount,
    int PointerRootReadFailures,
    int PointerSlotCount,
    int UniqueChildPointerCount,
    int ChildReadFailures,
    int SecondHopRootCount,
    int RejectedNonOrthonormalBasisCount,
    int RejectedLowComponentDiversityCount,
    int RejectedLowHorizontalMagnitudeCount);
