using RiftReader.Reader.AddonSnapshots;
using RiftReader.Reader.Memory;
using RiftReader.Reader.Scanning;

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

    public static PlayerOrientationCandidateSearchResult Find(
        ProcessMemoryReader reader,
        int processId,
        string processName,
        ReaderBridgeSnapshotDocument snapshotDocument,
        int maxHits)
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
                if (!reader.TryReadBytes(new nint(baseAddress), SearchWindowLength, out var bytes, out _))
                {
                    continue;
                }

                var primaryCoord = ReadTriplet(bytes, assumedOffset);
                var primaryCoordMatch = MatchesCoord(primaryCoord, coord, CoordTolerance);
                var secondaryCoordMatch = FindBestSecondaryCoordMatch(bytes, assumedOffset, coord);

                PlayerOrientationCandidate? bestForBase = null;

                foreach (var forwardOffset in EnumeratePrimaryForwardOffsets(assumedOffset, bytes.Length))
                {
                    foreach (var duplicateForwardOffset in EnumerateDuplicateForwardOffsets(forwardOffset, bytes.Length))
                    {
                        var basis = TryBuildCandidate(
                            bytes,
                            baseAddress,
                            hit.AddressHex,
                            assumedOffset,
                            primaryCoord,
                            secondaryCoordMatch.Coord,
                            primaryCoordMatch,
                            secondaryCoordMatch.Matches,
                            secondaryCoordMatch.Offset,
                            forwardOffset,
                            duplicateForwardOffset);

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

                if (bestForBase is not null && (!dedup.TryGetValue(baseAddress, out var existing) || bestForBase.Score > existing.Score))
                {
                    dedup[baseAddress] = bestForBase;
                }
            }
        }

        var ranked = dedup.Values
            .OrderByDescending(static c => c.Score)
            .ThenBy(static c => c.BasisDuplicateAgreement?.MaxRowDeltaMagnitude ?? double.MaxValue)
            .ToArray();

        return new PlayerOrientationCandidateSearchResult(
            Mode: "player-orientation-candidate-search",
            ProcessId: processId,
            ProcessName: processName,
            PlayerName: player.Name,
            PlayerCoord: coord,
            CandidateCount: ranked.Length,
            BestCandidate: ranked.FirstOrDefault(),
            Candidates: ranked.Take(maxHits).ToArray(),
            Notes: new[]
            {
                "Read-only single-process search over live player coord hits.",
                "Candidates scored by coord agreement, transform-like basis quality, and basis-duplicate agreement.",
                "The search now performs a bounded local sweep around coord hits instead of relying only on the original fixed offsets."
            });
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
        int duplicateForwardOffset)
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
            Score: score,
            Coord48MatchesPlayer: primaryCoordMatch,
            Coord88MatchesPlayer: secondaryCoordMatch,
            Coord48: primaryCoord,
            Coord88: secondaryCoord,
            Basis60: basisPrimary,
            Basis94: basisDuplicate,
            BasisDuplicateAgreement: duplicateAgreement,
            PreferredEstimate: preferredEstimate,
            DuplicateEstimate: duplicateEstimate);
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
    PlayerOrientationVectorEstimate DuplicateEstimate);

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
