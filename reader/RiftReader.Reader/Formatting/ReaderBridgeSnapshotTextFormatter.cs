using RiftReader.Reader.AddonSnapshots;

namespace RiftReader.Reader.Formatting;

public static class ReaderBridgeSnapshotTextFormatter
{
    public static string Format(ReaderBridgeSnapshotDocument document)
    {
        var snapshot = document.Current;

        var lines = new List<string>
        {
            $"ReaderBridge export file: {document.SourceFile}",
            $"Loaded at (UTC):         {document.LoadedAtUtc:O}",
            $"Last reason:             {document.LastReason ?? "n/a"}",
            $"Export count:            {document.ExportCount?.ToString() ?? "n/a"}"
        };

        if (snapshot is null)
        {
            lines.Add("Current snapshot:        none");
            return string.Join(Environment.NewLine, lines);
        }

        lines.Add($"Status:                  {snapshot.Status ?? "n/a"}");
        lines.Add($"Source mode:             {snapshot.SourceMode ?? "n/a"}");
        lines.Add($"Source addon:            {snapshot.SourceAddon ?? "n/a"} v{snapshot.SourceVersion ?? "?"}");
        lines.Add($"Export addon:            {snapshot.ExportAddon ?? "n/a"} v{snapshot.ExportVersion ?? "?"}");
        lines.Add($"Reason:                  {snapshot.ExportReason ?? "n/a"}");

        if (snapshot.Player is not null)
        {
            lines.Add($"Player:                  {snapshot.Player.Name ?? "n/a"} (Lv{snapshot.Player.Level?.ToString() ?? "?"})");
            lines.Add($"Player health:           {FormatPair(snapshot.Player.Hp, snapshot.Player.HpMax)}");
            lines.Add($"Player resource:         {FormatResource(snapshot.Player)}");
            lines.Add($"Player flags:            {FormatPlayerFlags(snapshot.Player)}");

            var playerLocation = snapshot.Player.LocationName ?? snapshot.Player.Zone;
            if (!string.IsNullOrWhiteSpace(playerLocation))
            {
                lines.Add($"Player location:         {playerLocation}");
            }

            var coord = FormatCoord(snapshot.Player.Coord);
            if (!string.IsNullOrWhiteSpace(coord))
            {
                lines.Add($"Player coords:           {coord}");
            }
        }

        if (snapshot.PlayerCoordDelta is not null && snapshot.PlayerCoordDelta.Distance.HasValue)
        {
            lines.Add(
                $"Player motion:           {snapshot.PlayerCoordDelta.Distance.Value:0.000} over {snapshot.PlayerCoordDelta.Dt?.ToString("0.000") ?? "?"}s"
                + (snapshot.PlayerCoordDelta.Speed.HasValue ? $" ({snapshot.PlayerCoordDelta.Speed.Value:0.000}/s)" : string.Empty));
        }

        if (snapshot.Target is not null && !string.IsNullOrWhiteSpace(snapshot.Target.Name))
        {
            lines.Add($"Target:                  {snapshot.Target.Name} (Lv{snapshot.Target.Level?.ToString() ?? "?"})");
            lines.Add($"Target health:           {FormatPair(snapshot.Target.Hp, snapshot.Target.HpMax)}");
            lines.Add($"Target resource:         {FormatResource(snapshot.Target)}");

            var targetLocation = snapshot.Target.LocationName ?? snapshot.Target.Zone;
            if (!string.IsNullOrWhiteSpace(targetLocation))
            {
                lines.Add($"Target location:         {targetLocation}");
            }

            if (snapshot.Target.Distance.HasValue)
            {
                lines.Add($"Target distance:         {snapshot.Target.Distance.Value:0.00}");
            }

            if (!string.IsNullOrWhiteSpace(snapshot.Target.TtdText))
            {
                lines.Add($"Target TTD:              {snapshot.Target.TtdText}");
            }
        }

        if (snapshot.PlayerBuffLines.Count > 0)
        {
            lines.Add($"Player buffs:            {string.Join(" | ", snapshot.PlayerBuffLines)}");
        }

        if (snapshot.TargetBuffLines.Count > 0)
        {
            lines.Add($"Target buffs:            {string.Join(" | ", snapshot.TargetBuffLines)}");
        }

        if (snapshot.NearbySummary is not null)
        {
            lines.Add(
                $"Nearby units:            scanned {snapshot.NearbySummary.ScannedCount?.ToString() ?? "0"}, exported {snapshot.NearbySummary.ExportedCount?.ToString() ?? "0"}, players {snapshot.NearbySummary.PlayerCount?.ToString() ?? "0"}, combat {snapshot.NearbySummary.CombatCount?.ToString() ?? "0"}");
        }

        if (snapshot.PartySummary is not null)
        {
            lines.Add(
                $"Party units:             exported {snapshot.PartySummary.ExportedCount?.ToString() ?? "0"}, combat {snapshot.PartySummary.CombatCount?.ToString() ?? "0"}, pvp {snapshot.PartySummary.PvpCount?.ToString() ?? "0"}");
        }

        if (snapshot.PlayerBuffs.Count > 0 || snapshot.PlayerDebuffs.Count > 0)
        {
            lines.Add($"Player aura detail:      buffs {snapshot.PlayerBuffs.Count}, debuffs {snapshot.PlayerDebuffs.Count}");
        }

        if (snapshot.TargetBuffs.Count > 0 || snapshot.TargetDebuffs.Count > 0)
        {
            lines.Add($"Target aura detail:      buffs {snapshot.TargetBuffs.Count}, debuffs {snapshot.TargetDebuffs.Count}");
        }

        return string.Join(Environment.NewLine, lines);
    }

    private static string FormatPair(long? value, long? maxValue) =>
        value.HasValue || maxValue.HasValue
            ? $"{value?.ToString() ?? "?"}/{maxValue?.ToString() ?? "?"}"
            : "n/a";

    private static string FormatResource(ReaderBridgeUnitSnapshot snapshot)
    {
        if (!string.IsNullOrWhiteSpace(snapshot.ResourceKind))
        {
            return $"{snapshot.ResourceKind} {FormatPair(snapshot.Resource, snapshot.ResourceMax)}";
        }

        if (snapshot.Power.HasValue)
        {
            return $"Power {snapshot.Power.Value}";
        }

        return "n/a";
    }

    private static string FormatPlayerFlags(ReaderBridgeUnitSnapshot snapshot)
    {
        var flags = new List<string>();

        if (snapshot.Combat == true)
        {
            flags.Add("combat");
        }

        if (snapshot.Pvp == true)
        {
            flags.Add("pvp");
        }

        if (snapshot.Mounted == true)
        {
            flags.Add("mounted");
        }

        if (snapshot.Aggro == true)
        {
            flags.Add("aggro");
        }

        if (snapshot.Tagged == true)
        {
            flags.Add("tagged");
        }

        return flags.Count == 0 ? "none" : string.Join(", ", flags);
    }

    private static string? FormatCoord(ValidatorCoordinateSnapshot? coord)
    {
        if (coord is null || coord.X is null || coord.Y is null || coord.Z is null)
        {
            return null;
        }

        return $"{coord.X:0.00}, {coord.Y:0.00}, {coord.Z:0.00}";
    }
}
