using RiftReader.Reader.AddonSnapshots;

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

    private static bool NearlyEqual(double left, double right, double tolerance = 0.01d) =>
        Math.Abs(left - right) <= tolerance;

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
