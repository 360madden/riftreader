using RiftReader.Reader.AddonSnapshots;

namespace RiftReader.Reader.Formatting;

public static class ValidatorSnapshotTextFormatter
{
    public static string Format(ValidatorSnapshotDocument document)
    {
        var snapshot = document.Current;

        var lines = new List<string>
        {
            $"Addon snapshot file: {document.SourceFile}",
            $"Loaded at (UTC):    {document.LoadedAtUtc:O}",
            $"Sample count:       {document.SampleCount}",
            $"Last reason:        {document.LastReason ?? "n/a"}"
        };

        if (snapshot is null)
        {
            lines.Add("Current snapshot:   none");
            return string.Join(Environment.NewLine, lines);
        }

        lines.Add($"Sequence:           {snapshot.Sequence?.ToString() ?? "n/a"}");
        lines.Add($"Player:             {snapshot.Name ?? "n/a"} (Lv{snapshot.Level?.ToString() ?? "?"})");
        lines.Add($"Role:               {snapshot.Role ?? "n/a"}");
        lines.Add($"Location:           {snapshot.LocationName ?? snapshot.Zone ?? "n/a"}");
        lines.Add($"Health:             {FormatPair(snapshot.Health, snapshot.HealthMax)}");
        lines.Add($"Resource:           {FormatResource(snapshot)}");
        lines.Add($"Reason:             {snapshot.Reason ?? "n/a"}");

        var coordText = FormatCoord(snapshot.Coord);

        if (!string.IsNullOrWhiteSpace(coordText))
        {
            lines.Add($"Coords:             {coordText}");
        }

        return string.Join(Environment.NewLine, lines);
    }

    private static string FormatPair(long? value, long? maxValue) =>
        value.HasValue || maxValue.HasValue
            ? $"{value?.ToString() ?? "?"}/{maxValue?.ToString() ?? "?"}"
            : "n/a";

    private static string FormatResource(ValidatorSnapshot snapshot)
    {
        if (snapshot.Mana.HasValue || snapshot.ManaMax.HasValue)
        {
            return $"Mana {FormatPair(snapshot.Mana, snapshot.ManaMax)}";
        }

        if (snapshot.Energy.HasValue || snapshot.EnergyMax.HasValue)
        {
            return $"Energy {FormatPair(snapshot.Energy, snapshot.EnergyMax)}";
        }

        if (snapshot.Power.HasValue)
        {
            return $"Power {snapshot.Power.Value}";
        }

        if (snapshot.Combo.HasValue)
        {
            return $"Combo {snapshot.Combo.Value}";
        }

        return "n/a";
    }

    private static string? FormatCoord(ValidatorCoordinateSnapshot? coord)
    {
        if (coord is null || coord.X is null || coord.Y is null || coord.Z is null)
        {
            return null;
        }

        return $"{coord.X:0.0}, {coord.Y:0.0}, {coord.Z:0.0}";
    }
}
