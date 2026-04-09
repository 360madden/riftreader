using System.Globalization;
using RiftReader.Reader.Models;

namespace RiftReader.Reader.Formatting;

public static class PlayerOrientationReadTextFormatter
{
    public static string Format(PlayerOrientationReadResult result)
    {
        var lines = new List<string>
        {
            $"Orientation artifact:          {result.ArtifactFile}",
            $"Artifact loaded (UTC):        {result.ArtifactLoadedAtUtc:O}",
            $"Artifact generated (UTC):     {result.ArtifactGeneratedAtUtc?.ToString("O") ?? "n/a"}",
            $"ReaderBridge snapshot:        {result.SnapshotFile ?? "n/a"}",
            $"Player:                       {FormatPlayer(result)}",
            $"Selected source address:      {result.SelectedSourceAddress ?? "n/a"}",
            $"Selected entry:               {FormatSelectedEntry(result)}",
            $"Preferred estimate:           {FormatEstimate(result.PreferredEstimate)}",
            $"Estimates:                    {result.Estimates.Count}",
            $"Notes:                        {FormatNotes(result.Notes)}"
        };

        if (result.Estimates.Count == 0)
        {
            lines.Add("Candidate vectors:             none");
            return string.Join(Environment.NewLine, lines);
        }

        lines.Add("Candidate vectors:");

        foreach (var estimate in result.Estimates)
        {
            lines.Add($"  - {estimate.Name}: {FormatEstimate(estimate)}");
        }

        return string.Join(Environment.NewLine, lines);
    }

    private static string FormatPlayer(PlayerOrientationReadResult result)
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

        if (!string.IsNullOrWhiteSpace(result.PlayerGuild))
        {
            parts.Add($"Guild {result.PlayerGuild}");
        }

        if (!string.IsNullOrWhiteSpace(result.PlayerLocation))
        {
            parts.Add($"@ {result.PlayerLocation}");
        }

        if (result.PlayerCoord is not null && result.PlayerCoord.X.HasValue && result.PlayerCoord.Y.HasValue && result.PlayerCoord.Z.HasValue)
        {
            parts.Add($"Coords {result.PlayerCoord.X:0.00}, {result.PlayerCoord.Y:0.00}, {result.PlayerCoord.Z:0.00}");
        }

        return parts.Count == 0 ? "n/a" : string.Join(" | ", parts);
    }

    private static string FormatSelectedEntry(PlayerOrientationReadResult result)
    {
        if (string.IsNullOrWhiteSpace(result.SelectedEntryAddress))
        {
            return "n/a";
        }

        var parts = new List<string>
        {
            $"index {result.SelectedEntryIndex?.ToString(CultureInfo.InvariantCulture) ?? "n/a"}",
            result.SelectedEntryAddress
        };

        parts.Add(result.SelectedEntryMatchesSelectedSource ? "exact selected-source match" : "fallback match");

        if (result.SelectedEntryRoleHints.Count > 0)
        {
            parts.Add($"hints {string.Join(", ", result.SelectedEntryRoleHints)}");
        }

        return string.Join(" | ", parts);
    }

    private static string FormatEstimate(PlayerOrientationVectorEstimate? estimate)
    {
        if (estimate is null)
        {
            return "n/a";
        }

        var parts = new List<string>
        {
            FormatVector(estimate.Vector)
        };

        if (estimate.YawRadians.HasValue || estimate.PitchRadians.HasValue)
        {
            parts.Add($"yaw {FormatAngle(estimate.YawRadians, estimate.YawDegrees)}");
            parts.Add($"pitch {FormatAngle(estimate.PitchRadians, estimate.PitchDegrees)}");
        }

        if (estimate.Magnitude.HasValue)
        {
            parts.Add($"mag {estimate.Magnitude.Value:0.00000}");
        }

        return string.Join(" | ", parts);
    }

    private static string FormatVector(RiftReader.Reader.AddonSnapshots.ValidatorCoordinateSnapshot? vector)
    {
        if (vector is null || !vector.X.HasValue || !vector.Y.HasValue || !vector.Z.HasValue)
        {
            return "vec n/a";
        }

        return $"vec {vector.X.Value:0.00000}, {vector.Y.Value:0.00000}, {vector.Z.Value:0.00000}";
    }

    private static string FormatAngle(double? radians, double? degrees)
    {
        if (!radians.HasValue || !degrees.HasValue)
        {
            return "n/a";
        }

        return $"{radians.Value:0.000000} rad ({degrees.Value:0.000} deg)";
    }

    private static string FormatNotes(IReadOnlyList<string> notes) =>
        notes.Count == 0 ? "none" : string.Join("; ", notes);
}
