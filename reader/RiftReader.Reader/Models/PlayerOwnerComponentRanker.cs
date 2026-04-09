using System.Globalization;
using RiftReader.Reader.AddonSnapshots;

namespace RiftReader.Reader.Models;

public static class PlayerOwnerComponentRanker
{
    private const float CoordTolerance = 0.25f;
    private const ulong PointerMin = 0x10000;
    private const ulong PointerMax = 0x00007FFFFFFFFFFF;

    public static PlayerOwnerComponentRankResult Rank(
        ReaderBridgeSnapshotDocument snapshotDocument,
        PlayerOwnerComponentArtifactDocument artifactDocument)
    {
        ArgumentNullException.ThrowIfNull(snapshotDocument);
        ArgumentNullException.ThrowIfNull(artifactDocument);

        var player = snapshotDocument.Current?.Player ?? throw new InvalidOperationException("ReaderBridge export did not contain a player snapshot.");
        var components = artifactDocument.Entries ?? Array.Empty<PlayerOwnerComponentArtifactEntry>();
        var focusFields = BuildFocusFields(player);

        var ranked = new List<PlayerOwnerComponentRankCandidate>(components.Count);

        foreach (var entry in components)
        {
            ranked.Add(ScoreEntry(entry, artifactDocument, player, focusFields));
        }

        ranked = ranked
            .OrderByDescending(candidate => candidate.Score)
            .ThenBy(candidate => candidate.Index)
            .ToList();

        for (var index = 0; index < ranked.Count; index++)
        {
            ranked[index] = ranked[index] with { Rank = index + 1 };
        }

        return new PlayerOwnerComponentRankResult(
            Mode: "player-owner-component-rank",
            ArtifactFile: artifactDocument.SourceFile,
            ArtifactLoadedAtUtc: artifactDocument.LoadedAtUtc,
            ArtifactGeneratedAtUtc: artifactDocument.GeneratedAtUtc,
            SnapshotFile: snapshotDocument.SourceFile,
            PlayerName: player.Name,
            PlayerLevel: player.Level,
            PlayerCalling: player.Calling,
            PlayerGuild: player.Guild,
            PlayerRole: player.Role,
            PlayerLocation: player.LocationName ?? player.Zone,
            PlayerCoord: player.Coord,
            PlayerHp: player.Hp,
            PlayerHpMax: player.HpMax,
            PlayerResourceKind: player.ResourceKind,
            PlayerResource: player.Resource,
            PlayerResourceMax: player.ResourceMax,
            PlayerCombo: player.Combo,
            PlayerPlanar: player.Planar,
            PlayerPlanarMax: player.PlanarMax,
            PlayerVitality: player.Vitality,
            OwnerAddress: artifactDocument.Owner?.Address,
            ContainerAddress: artifactDocument.Owner?.ContainerAddress,
            SelectedSourceAddress: artifactDocument.Owner?.SelectedSourceAddress,
            StateRecordAddress: artifactDocument.Owner?.StateRecordAddress,
            EntryCount: components.Count,
            FocusFields: focusFields,
            Candidates: ranked);
    }

    private static PlayerOwnerComponentRankCandidate ScoreEntry(
        PlayerOwnerComponentArtifactEntry entry,
        PlayerOwnerComponentArtifactDocument artifact,
        ReaderBridgeUnitSnapshot player,
        IReadOnlyList<string> focusFields)
    {
        var reasons = new List<string>();
        var score = 0;

        var roleHints = entry.RoleHints ?? Array.Empty<string>();
        var address = entry.Address ?? string.Empty;
        var isTransformLike = HasTransformRoleHint(roleHints);
        var coordMatch = MatchesPlayerCoords(entry, player, out var coordMatchReasons);
        var pointerLikeCount = 0;

        foreach (var reason in coordMatchReasons)
        {
            reasons.Add(reason);
        }

        if (isTransformLike || coordMatch)
        {
            score -= 120;
            reasons.Add("transform/source-shaped entry");
        }

        var q8Pointer = TryParsePointer(entry.Q8, out var q8Value);
        var q68Pointer = TryParsePointer(entry.Q68, out var q68Value);
        var q100Pointer = TryParsePointer(entry.Q100, out var q100Value);

        if (q8Pointer)
        {
            pointerLikeCount++;
            score += 20;
            reasons.Add($"Q8 looks like a pointer ({entry.Q8})");
        }

        if (q68Pointer)
        {
            pointerLikeCount++;
            score += 20;
            reasons.Add($"Q68 looks like a pointer ({entry.Q68})");
        }

        if (q100Pointer)
        {
            pointerLikeCount++;
            score += 20;
            reasons.Add($"Q100 looks like a pointer ({entry.Q100})");
        }

        if (pointerLikeCount >= 2)
        {
            score += 12;
            reasons.Add("pointer-rich component");
        }

        if (entry.OwnerRefCount > 1)
        {
            score += 8;
            reasons.Add($"shared by {entry.OwnerRefCount} owner refs");
        }
        else if (entry.OwnerRefCount == 1)
        {
            score += 2;
            reasons.Add("single-owner-linked");
        }

        if (entry.SourceRefCount > 0)
        {
            score += 4;
            reasons.Add($"source-linked ({entry.SourceRefCount})");
        }

        if (!isTransformLike && pointerLikeCount == 0)
        {
            score -= 6;
            reasons.Add("not pointer-rich enough to look stat-bearing yet");
        }

        if (MatchesKnownAnchor(entry.Address, artifact) || MatchesKnownAnchor(entry.Q8, artifact) || MatchesKnownAnchor(entry.Q68, artifact) || MatchesKnownAnchor(entry.Q100, artifact))
        {
            score += 15;
            reasons.Add("links to the known owner graph");
        }

        var kind = ClassifyKind(isTransformLike, pointerLikeCount, entry.OwnerRefCount, entry.SourceRefCount);
        if (kind == "state-like")
        {
            reasons.Add($"best candidate family for snapshot-backed fields: {string.Join(", ", focusFields)}");
        }

        return new PlayerOwnerComponentRankCandidate(
            Rank: 0,
            Index: entry.Index,
            AddressHex: NormalizeAddress(address),
            Score: score,
            Kind: kind,
            Reasons: reasons,
            RoleHints: roleHints,
            Q8: entry.Q8,
            Q68: entry.Q68,
            Q100: entry.Q100,
            OwnerRefCount: entry.OwnerRefCount,
            SourceRefCount: entry.SourceRefCount,
            Coord48: entry.Coord48,
            Coord88: entry.Coord88,
            Orientation60: entry.Orientation60,
            Orientation94: entry.Orientation94);
    }

    private static bool MatchesPlayerCoords(PlayerOwnerComponentArtifactEntry entry, ReaderBridgeUnitSnapshot player, out IReadOnlyList<string> reasons)
    {
        var output = new List<string>();

        if (player.Coord is null || player.Coord.X is not double expectedX || player.Coord.Y is not double expectedY || player.Coord.Z is not double expectedZ)
        {
            reasons = output;
            return false;
        }

        if (MatchesCoord(entry.Coord48, expectedX, expectedY, expectedZ))
        {
            output.Add("coord48 matches the live ReaderBridge player coords");
        }

        if (MatchesCoord(entry.Coord88, expectedX, expectedY, expectedZ))
        {
            output.Add("coord88 matches the live ReaderBridge player coords");
        }

        reasons = output;
        return output.Count > 0;
    }

    private static bool MatchesCoord(ValidatorCoordinateSnapshot? coord, double expectedX, double expectedY, double expectedZ)
    {
        if (coord is null || coord.X is null || coord.Y is null || coord.Z is null)
        {
            return false;
        }

        return NearlyEquals((float)coord.X.Value, (float)expectedX, CoordTolerance)
            && NearlyEquals((float)coord.Y.Value, (float)expectedY, CoordTolerance)
            && NearlyEquals((float)coord.Z.Value, (float)expectedZ, CoordTolerance);
    }

    private static bool HasTransformRoleHint(IEnumerable<string> roleHints) =>
        roleHints.Any(hint =>
            hint.Contains("selected-source", StringComparison.OrdinalIgnoreCase) ||
            hint.Contains("coord", StringComparison.OrdinalIgnoreCase) ||
            hint.Contains("orientation", StringComparison.OrdinalIgnoreCase));

    private static string ClassifyKind(bool isTransformLike, int pointerLikeCount, int ownerRefCount, int sourceRefCount)
    {
        if (isTransformLike)
        {
            return "transform/source";
        }

        if (pointerLikeCount >= 2)
        {
            return "state-like";
        }

        if (pointerLikeCount >= 1 || ownerRefCount > 1 || sourceRefCount > 0)
        {
            return "wrapper-like";
        }

        return "low-confidence";
    }

    private static IReadOnlyList<string> BuildFocusFields(ReaderBridgeUnitSnapshot player)
    {
        var fields = new List<string>();

        if (player.Level.HasValue)
        {
            fields.Add("Level");
        }

        if (player.Hp.HasValue || player.HpMax.HasValue)
        {
            fields.Add("Hp/HpMax");
        }

        if (!string.IsNullOrWhiteSpace(player.ResourceKind) || player.Resource.HasValue || player.ResourceMax.HasValue)
        {
            fields.Add(string.IsNullOrWhiteSpace(player.ResourceKind) ? "Resource" : $"{player.ResourceKind} resource");
        }

        if (player.Combo.HasValue)
        {
            fields.Add("Combo");
        }

        if (player.Planar.HasValue || player.PlanarMax.HasValue)
        {
            fields.Add("Planar/PlanarMax");
        }

        if (player.Vitality.HasValue)
        {
            fields.Add("Vitality");
        }

        if (!string.IsNullOrWhiteSpace(player.Calling))
        {
            fields.Add("Calling");
        }

        if (!string.IsNullOrWhiteSpace(player.Guild))
        {
            fields.Add("Guild");
        }

        if (!string.IsNullOrWhiteSpace(player.Role))
        {
            fields.Add("Role");
        }

        if (!string.IsNullOrWhiteSpace(player.LocationName ?? player.Zone))
        {
            fields.Add("Location");
        }

        if (player.Coord is not null && player.Coord.X.HasValue && player.Coord.Y.HasValue && player.Coord.Z.HasValue)
        {
            fields.Add("Coord");
        }

        return fields;
    }

    private static bool MatchesKnownAnchor(string? value, PlayerOwnerComponentArtifactDocument artifact)
    {
        if (!TryParsePointer(value, out var pointerValue))
        {
            return false;
        }

        return MatchesKnownAnchor(pointerValue, artifact);
    }

    private static bool MatchesKnownAnchor(ulong value, PlayerOwnerComponentArtifactDocument artifact)
    {
        var anchors = new[]
        {
            artifact.Owner?.Address,
            artifact.Owner?.ContainerAddress,
            artifact.Owner?.SelectedSourceAddress,
            artifact.Owner?.StateRecordAddress
        };

        foreach (var anchor in anchors)
        {
            if (TryParsePointer(anchor, out var anchorValue) && anchorValue == value)
            {
                return true;
            }
        }

        return false;
    }

    private static bool TryParsePointer(string? value, out ulong address)
    {
        address = 0;

        if (string.IsNullOrWhiteSpace(value))
        {
            return false;
        }

        var normalized = value.StartsWith("0x", StringComparison.OrdinalIgnoreCase)
            ? value[2..]
            : value;

        return ulong.TryParse(normalized, NumberStyles.HexNumber, CultureInfo.InvariantCulture, out address)
            && address >= PointerMin
            && address <= PointerMax;
    }

    private static bool NearlyEquals(float actual, float expected, float tolerance) =>
        float.IsFinite(actual) && float.IsFinite(expected) && MathF.Abs(actual - expected) <= tolerance;

    private static string NormalizeAddress(string? address) =>
        string.IsNullOrWhiteSpace(address)
            ? "n/a"
            : address.StartsWith("0x", StringComparison.OrdinalIgnoreCase)
                ? address
                : $"0x{address}";
}
