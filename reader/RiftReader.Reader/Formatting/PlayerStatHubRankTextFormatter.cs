using System.Text;
using RiftReader.Reader.Models;

namespace RiftReader.Reader.Formatting;

public static class PlayerStatHubRankTextFormatter
{
    public static string Format(PlayerStatHubRankResult result)
    {
        var sb = new StringBuilder();

        sb.AppendLine("Player Stat-Hub Graph");
        sb.AppendLine("--------------------------------------------------------------------------------");
        sb.AppendLine($"Snapshot:           {result.SnapshotFile ?? "n/a"}");
        sb.AppendLine($"Owner components:   {result.OwnerComponentsFile ?? "n/a"}");
        sb.AppendLine($"Generated:          {result.GeneratedAtUtc}");
        sb.AppendLine();
        sb.AppendLine($"Player UnitId:      {result.PlayerUnitId} ({result.PlayerUnitIdRawHex})");
        sb.AppendLine($"Player Level:       {result.PlayerLevel?.ToString() ?? "n/a"}");
        sb.AppendLine($"Player HP:          {result.PlayerHp?.ToString() ?? "n/a"} / {result.PlayerHpMax?.ToString() ?? "n/a"}");
        sb.AppendLine($"Player Resource:    {result.PlayerResource?.ToString() ?? "n/a"} / {result.PlayerResourceMax?.ToString() ?? "n/a"}");
        sb.AppendLine();
        sb.AppendLine($"Owner Address:      {result.OwnerAddress}");
        sb.AppendLine($"State Address:      {result.StateRecordAddress}");
        sb.AppendLine($"Source Address:     {result.SelectedSourceAddress}");
        sb.AppendLine();
        sb.AppendLine("Identity Components (UnitId Match)");
        sb.AppendLine("--------------------------------------------------------------------------------");

        if (result.IdentityComponents.Count == 0)
        {
            sb.AppendLine("  (none found)");
        }
        else
        {
            foreach (var identity in result.IdentityComponents)
            {
                var hints = identity.RoleHints.Count > 0 ? $" | hints={string.Join(",", identity.RoleHints)}" : string.Empty;
                sb.AppendLine($"  [{identity.Index:D3}] {identity.Address}{hints}");
                sb.AppendLine($"        unitId-offsets: {string.Join(", ", identity.UnitIdOffsets.Select(o => $"0x{o:X}"))}");
                if (identity.OwnerOffsets.Count > 0) sb.AppendLine($"        owner-offsets:  {string.Join(", ", identity.OwnerOffsets.Select(o => $"0x{o:X}"))}");
                sb.AppendLine($"        pointers out:   {identity.PointerTargets.Count}");
            }
        }

        sb.AppendLine();
        sb.AppendLine("Ranked Shared Hubs (Points -> Hub)");
        sb.AppendLine("--------------------------------------------------------------------------------");

        if (result.RankedSharedHubs.Count == 0)
        {
            sb.AppendLine("  (none found)");
        }
        else
        {
            for (var i = 0; i < result.RankedSharedHubs.Count; i++)
            {
                var hub = result.RankedSharedHubs[i];
                var rank = i + 1;
                sb.AppendLine($"  {rank:D2}. {hub.Address} | Score: {hub.Score}");

                foreach (var reason in hub.Reasons)
                {
                    sb.AppendLine($"      - {reason}");
                }

                var refCount = hub.ComponentRefs.Count;
                var refsToShow = hub.ComponentRefs.Take(5).ToList();
                var refText = string.Join(", ", refsToShow.Select(r => $"comp[{r.ComponentIndex}]+{r.OffsetHex}"));
                if (refCount > 5) refText += $", ... ({refCount - 5} more)";
                sb.AppendLine($"      - Referenced by: {refText}");
                sb.AppendLine();
            }
        }

        sb.AppendLine();
        sb.AppendLine("Identity Graph Links (Identity -> Hub)");
        sb.AppendLine("--------------------------------------------------------------------------------");

        if (result.IdentityGraphLinks.Count == 0)
        {
            sb.AppendLine("  (none found)");
        }
        else
        {
            foreach (var link in result.IdentityGraphLinks)
            {
                sb.AppendLine($"  [{link.IdentityComponentIndex:D3}] {link.IdentityComponentAddress} --({link.OffsetHex})--> {link.HubAddress} (hub score: {link.HubScore})");
            }
        }

        return sb.ToString();
    }
}
