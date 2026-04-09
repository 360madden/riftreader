using RiftReader.Reader.Models;

namespace RiftReader.Reader.Formatting;

public static class PlayerOwnerComponentRankTextFormatter
{
    public static string Format(PlayerOwnerComponentRankResult result)
    {
        var lines = new List<string>
        {
            $"Owner-component rank artifact: {result.ArtifactFile}",
            $"Artifact loaded (UTC):          {result.ArtifactLoadedAtUtc:O}",
            $"Artifact generated (UTC):       {result.ArtifactGeneratedAtUtc?.ToString("O") ?? "n/a"}",
            $"ReaderBridge snapshot:          {result.SnapshotFile}",
            $"Player:                         {FormatPlayer(result)}",
            $"Current focus fields:           {string.Join(", ", result.FocusFields)}",
            $"Owner:                          {result.OwnerAddress ?? "n/a"}",
            $"Container:                      {result.ContainerAddress ?? "n/a"}",
            $"Selected source:                {result.SelectedSourceAddress ?? "n/a"}",
            $"State record:                   {result.StateRecordAddress ?? "n/a"}",
            $"Entries ranked:                 {result.EntryCount}",
            $"Candidates:                     {result.Candidates.Count}"
        };

        if (result.Candidates.Count == 0)
        {
            lines.Add("Matches:                        none");
            return string.Join(Environment.NewLine, lines);
        }

        lines.Add("Ranked candidates:");

        for (var index = 0; index < result.Candidates.Count; index++)
        {
            var candidate = result.Candidates[index];
            lines.Add($"  {candidate.Rank,2}. index {candidate.Index,2}  score {candidate.Score,4}  {candidate.Kind}  {candidate.AddressHex}");

            if (candidate.Reasons.Count > 0)
            {
                lines.Add($"      why : {string.Join("; ", candidate.Reasons)}");
            }

            lines.Add($"      refs: owner {candidate.OwnerRefCount}, source {candidate.SourceRefCount}");
            lines.Add($"      q   : Q8={candidate.Q8 ?? "n/a"}  Q68={candidate.Q68 ?? "n/a"}  Q100={candidate.Q100 ?? "n/a"}");

            var roleHints = candidate.RoleHints.Count > 0 ? string.Join(", ", candidate.RoleHints) : "none";
            lines.Add($"      hint: {roleHints}");

            if (candidate.Coord48 is not null || candidate.Coord88 is not null || candidate.Orientation60 is not null || candidate.Orientation94 is not null)
            {
                lines.Add($"      c48 : {FormatCoord(candidate.Coord48)}");
                lines.Add($"      c88 : {FormatCoord(candidate.Coord88)}");
                lines.Add($"      o60 : {FormatCoord(candidate.Orientation60)}");
                lines.Add($"      o94 : {FormatCoord(candidate.Orientation94)}");
            }
        }

        return string.Join(Environment.NewLine, lines);
    }

    private static string FormatPlayer(PlayerOwnerComponentRankResult result)
    {
        var parts = new List<string>();

        if (!string.IsNullOrWhiteSpace(result.PlayerName))
        {
            parts.Add(result.PlayerName);
        }

        if (result.PlayerLevel.HasValue)
        {
            parts.Add($"Lv{result.PlayerLevel.Value}");
        }

        if (!string.IsNullOrWhiteSpace(result.PlayerRole))
        {
            parts.Add(result.PlayerRole);
        }

        if (!string.IsNullOrWhiteSpace(result.PlayerCalling))
        {
            parts.Add(result.PlayerCalling);
        }

        if (!string.IsNullOrWhiteSpace(result.PlayerGuild))
        {
            parts.Add($"Guild {result.PlayerGuild}");
        }

        if (!string.IsNullOrWhiteSpace(result.PlayerLocation))
        {
            parts.Add($"@ {result.PlayerLocation}");
        }

        if (result.PlayerHp.HasValue || result.PlayerHpMax.HasValue)
        {
            parts.Add($"HP {FormatPair(result.PlayerHp, result.PlayerHpMax)}");
        }

        if (!string.IsNullOrWhiteSpace(result.PlayerResourceKind) || result.PlayerResource.HasValue || result.PlayerResourceMax.HasValue)
        {
            parts.Add($"{(string.IsNullOrWhiteSpace(result.PlayerResourceKind) ? "Resource" : result.PlayerResourceKind)} {FormatPair(result.PlayerResource, result.PlayerResourceMax)}");
        }

        if (result.PlayerCombo.HasValue)
        {
            parts.Add($"Combo {result.PlayerCombo.Value}");
        }

        if (result.PlayerPlanar.HasValue || result.PlayerPlanarMax.HasValue)
        {
            parts.Add($"Planar {FormatPair(result.PlayerPlanar, result.PlayerPlanarMax)}");
        }

        if (result.PlayerVitality.HasValue)
        {
            parts.Add($"Vitality {result.PlayerVitality.Value}");
        }

        if (result.PlayerCoord is not null && result.PlayerCoord.X.HasValue && result.PlayerCoord.Y.HasValue && result.PlayerCoord.Z.HasValue)
        {
            parts.Add($"Coords {result.PlayerCoord.X:0.00}, {result.PlayerCoord.Y:0.00}, {result.PlayerCoord.Z:0.00}");
        }

        return parts.Count == 0 ? "n/a" : string.Join(" | ", parts);
    }

    private static string FormatPair(long? value, long? maxValue) =>
        value.HasValue || maxValue.HasValue
            ? $"{value?.ToString() ?? "?"}/{maxValue?.ToString() ?? "?"}"
            : "n/a";

    private static string FormatCoord(RiftReader.Reader.AddonSnapshots.ValidatorCoordinateSnapshot? coord)
    {
        if (coord is null || coord.X is null || coord.Y is null || coord.Z is null)
        {
            return "n/a";
        }

        return $"{coord.X:0.00000}, {coord.Y:0.00000}, {coord.Z:0.00000}";
    }
}
