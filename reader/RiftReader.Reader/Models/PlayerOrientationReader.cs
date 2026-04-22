using RiftReader.Reader.AddonSnapshots;
using RiftReader.Reader.Memory;
using RiftReader.Reader.Processes;

namespace RiftReader.Reader.Models;

public static class PlayerOrientationReader
{
    public static PlayerOrientationReadResult Read(
        PlayerOwnerComponentArtifactDocument artifactDocument,
        ReaderBridgeSnapshotDocument? snapshotDocument)
    {
        var player = snapshotDocument?.Current?.Player;
        var entries = artifactDocument.Entries ?? Array.Empty<PlayerOwnerComponentArtifactEntry>();
        var selectedEntry = SelectEntry(entries, artifactDocument.Owner?.SelectedSourceAddress, out var selectedSourceMatch);
        var estimates = new List<PlayerOrientationVectorEstimate>(capacity: 2);

        if (selectedEntry?.Orientation60 is not null)
        {
            estimates.Add(Estimate("Orientation60", selectedEntry.Orientation60));
        }

        if (selectedEntry?.Orientation94 is not null)
        {
            estimates.Add(Estimate("Orientation94", selectedEntry.Orientation94));
        }

        var preferredEstimate = estimates.FirstOrDefault(candidate => string.Equals(candidate.Name, "Orientation60", StringComparison.OrdinalIgnoreCase))
            ?? estimates.FirstOrDefault();
        var basisPrimaryEstimate = estimates.FirstOrDefault(candidate => string.Equals(candidate.Name, "Orientation60", StringComparison.OrdinalIgnoreCase));
        var basisDuplicateEstimate = estimates.FirstOrDefault(candidate => string.Equals(candidate.Name, "Orientation94", StringComparison.OrdinalIgnoreCase));
        var basisDuplicateDeltaMagnitude = GetVectorDeltaMagnitude(basisPrimaryEstimate?.Vector, basisDuplicateEstimate?.Vector);
        bool? basisDuplicateAgreementStrong = null;

        if (basisDuplicateDeltaMagnitude.HasValue)
        {
            basisDuplicateAgreementStrong = basisDuplicateDeltaMagnitude.Value <= 0.0001d;
        }

        var notes = new List<string>();

        notes.Add("LEGACY artifact-only mode: this path reads historical owner/source artifacts and must not be treated as current live truth without a matching live process selector.");

        if (selectedEntry is null)
        {
            notes.Add("No owner-component entry with orientation vectors could be selected.");
        }
        else
        {
            notes.Add(selectedSourceMatch
                ? "Selected entry matched the owner-selected source address."
                : "Selected entry was chosen by orientation-bearing fallback, not an exact selected-source match.");

            if (selectedEntry.RoleHints is { Count: > 0 })
            {
                notes.Add($"Selected entry role hints: {string.Join(", ", selectedEntry.RoleHints)}");
            }

            if (player?.Coord is not null)
            {
                if (MatchesCoord(selectedEntry.Coord48, player.Coord) || MatchesCoord(selectedEntry.Coord88, player.Coord))
                {
                    notes.Add("Selected entry coord snapshot matches the ReaderBridge player coords.");
                }
            }
        }

        if (snapshotDocument is null)
        {
            notes.Add("ReaderBridge snapshot unavailable; player context omitted.");
        }
        else if (player is null)
        {
            notes.Add("ReaderBridge snapshot loaded, but no player snapshot was available.");
        }

        return new PlayerOrientationReadResult(
            Mode: "player-orientation",
            ArtifactFile: artifactDocument.SourceFile,
            ArtifactLoadedAtUtc: artifactDocument.LoadedAtUtc,
            ArtifactGeneratedAtUtc: artifactDocument.GeneratedAtUtc,
            SnapshotFile: snapshotDocument?.SourceFile,
            SnapshotLoadedAtUtc: snapshotDocument?.LoadedAtUtc,
            PlayerName: player?.Name,
            PlayerLevel: player?.Level,
            PlayerGuild: player?.Guild,
            PlayerLocation: player?.LocationName ?? player?.Zone,
            PlayerCoord: player?.Coord,
            SelectedSourceAddress: artifactDocument.Owner?.SelectedSourceAddress,
            SelectedEntryAddress: selectedEntry?.Address,
            SelectedEntryIndex: selectedEntry?.Index,
            SelectedEntryMatchesSelectedSource: selectedSourceMatch,
            SelectedEntryRoleHints: selectedEntry?.RoleHints ?? Array.Empty<string>(),
            ResolutionMode: "artifact-owner-components",
            BasisPrimaryForwardOffset: basisPrimaryEstimate is not null ? "0x60" : null,
            BasisDuplicateForwardOffset: basisDuplicateEstimate is not null ? "0x94" : null,
            PreferredEstimate: preferredEstimate,
            BasisPrimaryEstimate: basisPrimaryEstimate,
            BasisDuplicateEstimate: basisDuplicateEstimate,
            BasisDuplicateDeltaMagnitude: basisDuplicateDeltaMagnitude,
            BasisDuplicateAgreementStrong: basisDuplicateAgreementStrong,
            Estimates: estimates,
            Notes: notes);
    }

    public static PlayerOrientationReadResult ReadLive(
        ProcessMemoryReader reader,
        ProcessTarget target,
        ReaderBridgeSnapshotDocument? snapshotDocument,
        ActorFacingBehaviorBackedLeadDocument leadDocument)
    {
        ArgumentNullException.ThrowIfNull(reader);
        ArgumentNullException.ThrowIfNull(target);
        ArgumentNullException.ThrowIfNull(leadDocument);

        var player = snapshotDocument?.Current?.Player;
        var selectedSourceAddress = ParseRequiredAddress(leadDocument.SourceAddress, nameof(leadDocument.SourceAddress));
        var basisPrimaryOffset = ParseRequiredOffset(leadDocument.BasisForwardOffset, nameof(leadDocument.BasisForwardOffset));
        var basisDuplicateOffset = ParseOptionalOffset(leadDocument.BasisDuplicateForwardOffset);
        var readLength = GetRequiredReadLength(basisPrimaryOffset, basisDuplicateOffset);

        if (!reader.TryReadBytes(new IntPtr(checked((long)selectedSourceAddress)), readLength, out var bytes, out var readError))
        {
            throw new InvalidOperationException(readError ?? $"Unable to read source bytes at 0x{selectedSourceAddress:X}.");
        }

        var basisPrimary = ReadBasis(bytes, basisPrimaryOffset, $"Basis@0x{basisPrimaryOffset:X}");
        var basisDuplicate = basisDuplicateOffset.HasValue
            ? ReadBasis(bytes, basisDuplicateOffset.Value, $"Basis@0x{basisDuplicateOffset.Value:X}")
            : null;

        var basisPrimaryEstimate = Estimate($"{basisPrimary.Name}.Forward", basisPrimary.Forward);
        var basisDuplicateEstimate = basisDuplicate is not null
            ? Estimate($"{basisDuplicate.Name}.Forward", basisDuplicate.Forward)
            : null;
        var basisDuplicateDeltaMagnitude = GetVectorDeltaMagnitude(basisPrimary.Forward, basisDuplicate?.Forward);
        bool? basisDuplicateAgreementStrong = basisDuplicateDeltaMagnitude.HasValue
            ? basisDuplicateDeltaMagnitude.Value <= 0.0001d
            : null;

        var preferredEstimate = IsMeaningfulBasisCandidate(basisPrimary, basisPrimaryEstimate)
            ? basisPrimaryEstimate
            : basisDuplicate is not null && basisDuplicateEstimate is not null && IsMeaningfulBasisCandidate(basisDuplicate, basisDuplicateEstimate)
                ? basisDuplicateEstimate
                : null;

        if (preferredEstimate is null)
        {
            throw new InvalidOperationException(
                $"Behavior-backed lead '{leadDocument.SourceFile}' did not resolve a meaningful live basis at 0x{selectedSourceAddress:X} ({leadDocument.BasisForwardOffset}).");
        }

        var estimates = new List<PlayerOrientationVectorEstimate>(capacity: basisDuplicateEstimate is null ? 1 : 2)
        {
            basisPrimaryEstimate
        };

        if (basisDuplicateEstimate is not null)
        {
            estimates.Add(basisDuplicateEstimate);
        }

        var notes = new List<string>
        {
            $"Resolved live source via behavior-backed lead file '{leadDocument.SourceFile}': 0x{selectedSourceAddress:X} (basis 0x{basisPrimaryOffset:X})."
        };

        if (!string.IsNullOrWhiteSpace(leadDocument.Status))
        {
            notes.Add($"Behavior-backed lead status: {leadDocument.Status}.");
        }

        if (leadDocument.Notes is { Count: > 0 })
        {
            foreach (var note in leadDocument.Notes)
            {
                if (!string.IsNullOrWhiteSpace(note))
                {
                    notes.Add(note);
                }
            }
        }

        if (!ReferenceEquals(preferredEstimate, basisPrimaryEstimate) && basisDuplicateEstimate is not null)
        {
            notes.Add($"Primary basis 0x{basisPrimaryOffset:X} was not meaningful; using duplicate basis 0x{basisDuplicateOffset:X} from the same live source.");
        }

        notes.Add($"Preferred estimate was recomputed from a fresh live memory read of PID {target.ProcessId} ({target.ProcessName}).");

        if (snapshotDocument is null)
        {
            notes.Add("ReaderBridge snapshot unavailable; player context omitted.");
        }
        else if (player is null)
        {
            notes.Add("ReaderBridge snapshot loaded, but no player snapshot was available.");
        }

        return new PlayerOrientationReadResult(
            Mode: "player-orientation-live",
            ArtifactFile: leadDocument.SourceFile,
            ArtifactLoadedAtUtc: leadDocument.LoadedAtUtc,
            ArtifactGeneratedAtUtc: leadDocument.ValidatedAtUtc ?? leadDocument.GeneratedAtUtc,
            SnapshotFile: snapshotDocument?.SourceFile,
            SnapshotLoadedAtUtc: snapshotDocument?.LoadedAtUtc,
            PlayerName: player?.Name,
            PlayerLevel: player?.Level,
            PlayerGuild: player?.Guild,
            PlayerLocation: player?.LocationName ?? player?.Zone,
            PlayerCoord: player?.Coord,
            SelectedSourceAddress: $"0x{selectedSourceAddress:X}",
            SelectedEntryAddress: null,
            SelectedEntryIndex: null,
            SelectedEntryMatchesSelectedSource: false,
            SelectedEntryRoleHints: Array.Empty<string>(),
            ResolutionMode: "live-behavior-backed-lead",
            BasisPrimaryForwardOffset: $"0x{basisPrimaryOffset:X}",
            BasisDuplicateForwardOffset: basisDuplicateOffset.HasValue ? $"0x{basisDuplicateOffset.Value:X}" : null,
            PreferredEstimate: preferredEstimate,
            BasisPrimaryEstimate: basisPrimaryEstimate,
            BasisDuplicateEstimate: basisDuplicateEstimate,
            BasisDuplicateDeltaMagnitude: basisDuplicateDeltaMagnitude,
            BasisDuplicateAgreementStrong: basisDuplicateAgreementStrong,
            Estimates: estimates,
            Notes: notes);
    }

    private static PlayerOwnerComponentArtifactEntry? SelectEntry(
        IReadOnlyList<PlayerOwnerComponentArtifactEntry> entries,
        string? selectedSourceAddress,
        out bool selectedSourceMatch)
    {
        selectedSourceMatch = false;

        if (entries.Count == 0)
        {
            return null;
        }

        var selectedSourceValue = TryParseAddress(selectedSourceAddress);
        PlayerOwnerComponentArtifactEntry? bestEntry = null;
        var bestScore = int.MinValue;

        foreach (var entry in entries)
        {
            var score = ScoreEntry(entry, selectedSourceValue, selectedSourceAddress);
            if (score > bestScore)
            {
                bestScore = score;
                bestEntry = entry;
            }
        }

        if (bestEntry is not null && selectedSourceValue.HasValue)
        {
            selectedSourceMatch = AddressesMatch(bestEntry.Address, selectedSourceValue.Value);
        }

        return bestEntry;
    }

    private static int ScoreEntry(
        PlayerOwnerComponentArtifactEntry entry,
        ulong? selectedSourceValue,
        string? selectedSourceAddress)
    {
        var score = 0;

        if (selectedSourceValue.HasValue && AddressesMatch(entry.Address, selectedSourceValue.Value))
        {
            score += 10_000;
        }

        if (entry.RoleHints is { Count: > 0 })
        {
            foreach (var roleHint in entry.RoleHints)
            {
                if (string.Equals(roleHint, "selected-source", StringComparison.OrdinalIgnoreCase))
                {
                    score += 750;
                }
                else if (string.Equals(roleHint, "orientation", StringComparison.OrdinalIgnoreCase))
                {
                    score += 250;
                }
                else if (roleHint.Contains("coord", StringComparison.OrdinalIgnoreCase))
                {
                    score += 150;
                }
            }
        }

        if (entry.Orientation60 is not null)
        {
            score += 100;
        }

        if (entry.Orientation94 is not null)
        {
            score += 100;
        }

        if (entry.Coord48 is not null || entry.Coord88 is not null)
        {
            score += 50;
        }

        score += entry.SourceRefCount * 2;
        score += entry.OwnerRefCount;

        if (!string.IsNullOrWhiteSpace(selectedSourceAddress) && string.Equals(entry.Address, selectedSourceAddress, StringComparison.OrdinalIgnoreCase))
        {
            score += 500;
        }

        return score;
    }

    private static bool MatchesCoord(
        ValidatorCoordinateSnapshot? candidate,
        ValidatorCoordinateSnapshot expected)
    {
        if (candidate is null || candidate.X is null || candidate.Y is null || candidate.Z is null)
        {
            return false;
        }

        if (expected.X is null || expected.Y is null || expected.Z is null)
        {
            return false;
        }

        return NearlyEqual(candidate.X.Value, expected.X.Value) &&
            NearlyEqual(candidate.Y.Value, expected.Y.Value) &&
            NearlyEqual(candidate.Z.Value, expected.Z.Value);
    }

    private static PlayerOrientationVectorEstimate Estimate(string name, ValidatorCoordinateSnapshot? vector)
    {
        if (vector is null || vector.X is null || vector.Y is null || vector.Z is null)
        {
            return new PlayerOrientationVectorEstimate(
                Name: name,
                Vector: vector,
                YawRadians: null,
                YawDegrees: null,
                PitchRadians: null,
                PitchDegrees: null,
                Magnitude: null);
        }

        var x = vector.X.Value;
        var y = vector.Y.Value;
        var z = vector.Z.Value;
        var magnitude = Math.Sqrt((x * x) + (y * y) + (z * z));

        if (magnitude <= double.Epsilon)
        {
            return new PlayerOrientationVectorEstimate(
                Name: name,
                Vector: vector,
                YawRadians: null,
                YawDegrees: null,
                PitchRadians: null,
                PitchDegrees: null,
                Magnitude: magnitude);
        }

        var yawRadians = Math.Atan2(z, x);
        var pitchRadians = Math.Atan2(y, Math.Sqrt((x * x) + (z * z)));

        return new PlayerOrientationVectorEstimate(
            Name: name,
            Vector: vector,
            YawRadians: yawRadians,
            YawDegrees: yawRadians * 180d / Math.PI,
            PitchRadians: pitchRadians,
            PitchDegrees: pitchRadians * 180d / Math.PI,
            Magnitude: magnitude);
    }

    private static PlayerOrientationBasisCandidate ReadBasis(byte[] bytes, int forwardOffset, string name)
    {
        var forward = ReadTriplet(bytes, forwardOffset);
        var up = ReadTriplet(bytes, forwardOffset + 0x0C);
        var right = ReadTriplet(bytes, forwardOffset + 0x18);
        var forwardEstimate = Estimate(name + ".Forward", forward);
        var upEstimate = Estimate(name + ".Up", up);
        var rightEstimate = Estimate(name + ".Right", right);
        var forwardDotUp = Dot(forward, up);
        var forwardDotRight = Dot(forward, right);
        var upDotRight = Dot(up, right);
        var determinant = Dot(Cross(forward, up), right);
        var isOrthonormal = IsOrthonormal(
            forwardEstimate.Magnitude,
            upEstimate.Magnitude,
            rightEstimate.Magnitude,
            forwardDotUp,
            forwardDotRight,
            upDotRight,
            determinant);

        return new PlayerOrientationBasisCandidate(
            Name: name,
            Forward: forward,
            Up: up,
            Right: right,
            Determinant: determinant,
            IsOrthonormal: isOrthonormal,
            ForwardDotUp: forwardDotUp,
            ForwardDotRight: forwardDotRight,
            UpDotRight: upDotRight);
    }

    private static bool AddressesMatch(string? address, ulong expected)
    {
        var parsed = TryParseAddress(address);
        return parsed.HasValue && parsed.Value == expected;
    }

    private static ulong? TryParseAddress(string? value)
    {
        if (string.IsNullOrWhiteSpace(value))
        {
            return null;
        }

        var trimmed = value.Trim();

        if (trimmed.StartsWith("0x", StringComparison.OrdinalIgnoreCase))
        {
            if (ulong.TryParse(trimmed[2..], System.Globalization.NumberStyles.HexNumber, System.Globalization.CultureInfo.InvariantCulture, out var hexValue))
            {
                return hexValue;
            }
        }
        else if (ulong.TryParse(trimmed, System.Globalization.NumberStyles.Integer, System.Globalization.CultureInfo.InvariantCulture, out var decimalValue))
        {
            return decimalValue;
        }

        return null;
    }

    private static ulong ParseRequiredAddress(string? value, string fieldName) =>
        TryParseAddress(value) ?? throw new InvalidOperationException($"Behavior-backed lead does not expose a valid {fieldName}.");

    private static int ParseRequiredOffset(string? value, string fieldName)
    {
        if (TryParseOffset(value) is int parsed)
        {
            return parsed;
        }

        throw new InvalidOperationException($"Behavior-backed lead does not expose a valid {fieldName}.");
    }

    private static int? ParseOptionalOffset(string? value) => TryParseOffset(value);

    private static int? TryParseOffset(string? value)
    {
        if (string.IsNullOrWhiteSpace(value))
        {
            return null;
        }

        var trimmed = value.Trim();

        if (trimmed.StartsWith("0x", StringComparison.OrdinalIgnoreCase))
        {
            if (int.TryParse(trimmed[2..], System.Globalization.NumberStyles.HexNumber, System.Globalization.CultureInfo.InvariantCulture, out var hexValue))
            {
                return hexValue;
            }

            return null;
        }

        return int.TryParse(trimmed, System.Globalization.NumberStyles.Integer, System.Globalization.CultureInfo.InvariantCulture, out var valueInt)
            ? valueInt
            : null;
    }

    private static bool NearlyEqual(double left, double right, double tolerance = 0.01d) =>
        Math.Abs(left - right) <= tolerance;

    private static ValidatorCoordinateSnapshot ReadTriplet(byte[] bytes, int offset) =>
        new(ReadSingle(bytes, offset), ReadSingle(bytes, offset + 4), ReadSingle(bytes, offset + 8));

    private static double? ReadSingle(byte[] bytes, int offset)
    {
        if (offset < 0 || offset + 4 > bytes.Length)
        {
            return null;
        }

        var value = (double)BitConverter.ToSingle(bytes, offset);
        if (double.IsNaN(value) || double.IsInfinity(value) || Math.Abs(value) > 1_000_000d)
        {
            return null;
        }

        return value;
    }

    private static ValidatorCoordinateSnapshot? Cross(ValidatorCoordinateSnapshot? left, ValidatorCoordinateSnapshot? right)
    {
        if (left?.X is not double lx || left.Y is not double ly || left.Z is not double lz ||
            right?.X is not double rx || right.Y is not double ry || right.Z is not double rz)
        {
            return null;
        }

        return new ValidatorCoordinateSnapshot(
            X: (ly * rz) - (lz * ry),
            Y: (lz * rx) - (lx * rz),
            Z: (lx * ry) - (ly * rx));
    }

    private static double? Dot(ValidatorCoordinateSnapshot? left, ValidatorCoordinateSnapshot? right)
    {
        if (left?.X is not double lx || left.Y is not double ly || left.Z is not double lz ||
            right?.X is not double rx || right.Y is not double ry || right.Z is not double rz)
        {
            return null;
        }

        return (lx * rx) + (ly * ry) + (lz * rz);
    }

    private static bool IsMeaningfulBasisCandidate(PlayerOrientationBasisCandidate basis, PlayerOrientationVectorEstimate estimate) =>
        basis.IsOrthonormal &&
        estimate.Magnitude is >= 0.85d and <= 1.15d;

    private static bool IsOrthonormal(double? a, double? b, double? c, double? ab, double? ac, double? bc, double? det) =>
        a.HasValue && b.HasValue && c.HasValue && ab.HasValue && ac.HasValue && bc.HasValue && det.HasValue &&
        Math.Abs(a.Value - 1d) <= 0.02d &&
        Math.Abs(b.Value - 1d) <= 0.02d &&
        Math.Abs(c.Value - 1d) <= 0.02d &&
        Math.Abs(ab.Value) <= 0.02d &&
        Math.Abs(ac.Value) <= 0.02d &&
        Math.Abs(bc.Value) <= 0.02d &&
        Math.Abs(Math.Abs(det.Value) - 1d) <= 0.02d;

    private static int GetRequiredReadLength(int primaryOffset, int? duplicateOffset)
    {
        var maxForwardOffset = duplicateOffset.HasValue
            ? Math.Max(primaryOffset, duplicateOffset.Value)
            : primaryOffset;
        var requiredLength = maxForwardOffset + 0x18 + 12;
        return Math.Max(requiredLength, 256);
    }

    private static double? GetVectorDeltaMagnitude(
        ValidatorCoordinateSnapshot? left,
        ValidatorCoordinateSnapshot? right)
    {
        if (left is null || right is null)
        {
            return null;
        }

        if (left.X is null || left.Y is null || left.Z is null)
        {
            return null;
        }

        if (right.X is null || right.Y is null || right.Z is null)
        {
            return null;
        }

        var dx = left.X.Value - right.X.Value;
        var dy = left.Y.Value - right.Y.Value;
        var dz = left.Z.Value - right.Z.Value;
        return Math.Sqrt((dx * dx) + (dy * dy) + (dz * dz));
    }
}
