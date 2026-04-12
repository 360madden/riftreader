using System.Globalization;
using RiftReader.Reader.AddonSnapshots;
using RiftReader.Reader.Memory;

namespace RiftReader.Reader.Models;

public static class PlayerStatHubRanker
{
    private const int ComponentReadLength = 0x180;
    private const int HubReadLength = 0x340;
    private const int MaxPointersPerComponent = 20;
    private const ulong PointerMin = 0x10000;
    private const ulong PointerMax = 0x00007FFFFFFFFFFF;

    public static PlayerStatHubRankResult Rank(
        ProcessMemoryReader reader,
        ReaderBridgeSnapshotDocument snapshotDocument,
        PlayerOwnerComponentArtifactDocument artifactDocument)
    {
        ArgumentNullException.ThrowIfNull(reader);
        ArgumentNullException.ThrowIfNull(snapshotDocument);
        ArgumentNullException.ThrowIfNull(artifactDocument);

        var player = snapshotDocument.Current?.Player ?? throw new InvalidOperationException("ReaderBridge export did not contain a player snapshot.");
        var playerUnitIdHex = player.Id?.TrimStart('u', 'U') ?? throw new InvalidOperationException("Player UnitId is missing.");
        var playerUnitIdValue = ulong.Parse(playerUnitIdHex, NumberStyles.HexNumber, CultureInfo.InvariantCulture);

        var ownerAddress = ParseAddress(artifactDocument.Owner?.Address);
        var stateRecordAddress = ParseAddress(artifactDocument.Owner?.StateRecordAddress);
        var selectedSourceAddress = ParseAddress(artifactDocument.Owner?.SelectedSourceAddress);

        var components = artifactDocument.Entries ?? Array.Empty<PlayerOwnerComponentArtifactEntry>();
        var componentDetails = new List<PlayerStatHubIdentityComponentDetail>();
        var hubReferenceMap = new Dictionary<string, List<PlayerStatHubComponentReference>>();

        foreach (var component in components)
        {
            if (!TryParseAddress(component.Address, out var componentAddress)) continue;

            if (!reader.TryReadBytes(new nint((long)componentAddress), ComponentReadLength, out var bytes, out _)) continue;

            var pointers = GetHeapPointerEntries(bytes, MaxPointersPerComponent);
            var unitIdOffsets = FindUInt64Offsets(bytes, playerUnitIdValue);
            var ownerOffsets = ownerAddress != 0 ? FindUInt64Offsets(bytes, ownerAddress) : Array.Empty<int>();
            var stateOffsets = stateRecordAddress != 0 ? FindUInt64Offsets(bytes, stateRecordAddress) : Array.Empty<int>();
            var sourceOffsets = selectedSourceAddress != 0 ? FindUInt64Offsets(bytes, selectedSourceAddress) : Array.Empty<int>();

            var levelOffsets = player.Level.HasValue ? FindInt32Offsets(bytes, player.Level.Value) : Array.Empty<int>();
            var hpOffsets = player.Hp.HasValue ? FindInt32Offsets(bytes, (int)player.Hp.Value) : Array.Empty<int>();
            var hpMaxOffsets = player.HpMax.HasValue ? FindInt32Offsets(bytes, (int)player.HpMax.Value) : Array.Empty<int>();
            var resourceOffsets = player.Resource.HasValue ? FindInt32Offsets(bytes, (int)player.Resource.Value) : Array.Empty<int>();
            var resourceMaxOffsets = player.ResourceMax.HasValue ? FindInt32Offsets(bytes, (int)player.ResourceMax.Value) : Array.Empty<int>();
            var comboOffsets = player.Combo.HasValue ? FindInt32Offsets(bytes, (int)player.Combo.Value) : Array.Empty<int>();
            var planarMaxOffsets = player.PlanarMax.HasValue ? FindInt32Offsets(bytes, (int)player.PlanarMax.Value) : Array.Empty<int>();

            foreach (var pointer in pointers)
            {
                if (!hubReferenceMap.TryGetValue(pointer.Address, out var refs))
                {
                    refs = new List<PlayerStatHubComponentReference>();
                    hubReferenceMap[pointer.Address] = refs;
                }

                refs.Add(new PlayerStatHubComponentReference(
                    ComponentIndex: component.Index,
                    ComponentAddress: component.Address ?? "0x0",
                    Offset: pointer.Offset,
                    OffsetHex: pointer.OffsetHex
                ));
            }

            componentDetails.Add(new PlayerStatHubIdentityComponentDetail(
                Index: component.Index,
                Address: component.Address ?? "0x0",
                RoleHints: component.RoleHints ?? Array.Empty<string>(),
                PointerTargets: pointers.Select(p => new PlayerStatHubPointerTarget(p.Offset, p.OffsetHex, p.Address, p.Value)).ToList(),
                UnitIdOffsets: unitIdOffsets,
                OwnerOffsets: ownerOffsets,
                StateOffsets: stateOffsets,
                SourceOffsets: sourceOffsets,
                LevelOffsets: levelOffsets,
                HpOffsets: hpOffsets,
                HpMaxOffsets: hpMaxOffsets,
                ResourceOffsets: resourceOffsets,
                ResourceMaxOffsets: resourceMaxOffsets,
                ComboOffsets: comboOffsets,
                PlanarMaxOffsets: planarMaxOffsets
            ));
        }

        var identityComponents = componentDetails
            .Where(c => c.UnitIdOffsets.Count > 0)
            .OrderByDescending(c => c.OwnerOffsets.Count)
            .ThenByDescending(c => c.PointerTargets.Count)
            .ThenBy(c => c.Index)
            .ToList();

        var hubCandidates = new List<PlayerStatHubCandidate>();
        foreach (var hubEntry in hubReferenceMap)
        {
            var hubAddressText = hubEntry.Key;
            var references = hubEntry.Value;
            if (references.Count < 2) continue;

            if (!TryParseAddress(hubAddressText, out var hubAddress) || hubAddress == ownerAddress) continue;

            if (!reader.TryReadBytes(new nint((long)hubAddress), HubReadLength, out var hubBytes, out _)) continue;

            var levelOffsets = player.Level.HasValue ? FindInt32Offsets(hubBytes, player.Level.Value) : Array.Empty<int>();
            var hpOffsets = player.Hp.HasValue ? FindInt32Offsets(hubBytes, (int)player.Hp.Value) : Array.Empty<int>();
            var hpMaxOffsets = player.HpMax.HasValue ? FindInt32Offsets(hubBytes, (int)player.HpMax.Value) : Array.Empty<int>();
            var resourceOffsets = player.Resource.HasValue ? FindInt32Offsets(hubBytes, (int)player.Resource.Value) : Array.Empty<int>();
            var resourceMaxOffsets = player.ResourceMax.HasValue ? FindInt32Offsets(hubBytes, (int)player.ResourceMax.Value) : Array.Empty<int>();
            var comboOffsets = player.Combo.HasValue ? FindInt32Offsets(hubBytes, (int)player.Combo.Value) : Array.Empty<int>();
            var planarMaxOffsets = player.PlanarMax.HasValue ? FindInt32Offsets(hubBytes, (int)player.PlanarMax.Value) : Array.Empty<int>();
            var hubOwnerOffsets = ownerAddress != 0 ? FindUInt64Offsets(hubBytes, ownerAddress) : Array.Empty<int>();
            var hubStateOffsets = stateRecordAddress != 0 ? FindUInt64Offsets(hubBytes, stateRecordAddress) : Array.Empty<int>();
            var hubSourceOffsets = selectedSourceAddress != 0 ? FindUInt64Offsets(hubBytes, selectedSourceAddress) : Array.Empty<int>();

            var score = 0;
            var reasons = new List<string>();

            if (references.Count > 1)
            {
                score += (references.Count * 15);
                reasons.Add($"shared by {references.Count} components");
            }
            if (levelOffsets.Length > 0)
            {
                score += 40;
                reasons.Add($"contains level match at {string.Join(", ", levelOffsets.Select(o => $"0x{o:X}"))}");
            }
            if (hpOffsets.Length > 0 || hpMaxOffsets.Length > 0)
            {
                score += 70;
                reasons.Add("contains hp or hpMax match");
            }
            if (resourceOffsets.Length > 0 && resourceMaxOffsets.Length > 0)
            {
                score += 18;
                reasons.Add("contains resource/resourceMax pair");
            }
            if (comboOffsets.Length > 0 && planarMaxOffsets.Length > 0)
            {
                score += 8;
                reasons.Add("contains combo/planarMax pair");
            }
            if (hubOwnerOffsets.Length > 0)
            {
                score += 24;
                reasons.Add($"contains owner backref at {string.Join(", ", hubOwnerOffsets.Select(o => $"0x{o:X}"))}");
            }
            if (hubStateOffsets.Length > 0)
            {
                score += 12;
                reasons.Add("contains state-record backref");
            }
            if (hubSourceOffsets.Length > 0)
            {
                score += 12;
                reasons.Add("contains selected-source backref");
            }

            hubCandidates.Add(new PlayerStatHubCandidate(
                Address: hubAddressText,
                Score: score,
                ComponentRefs: references.OrderBy(r => r.ComponentIndex).ThenBy(r => r.Offset).ToList(),
                LevelOffsets: levelOffsets.Select(o => $"0x{o:X}").ToList(),
                HpOffsets: hpOffsets.Select(o => $"0x{o:X}").ToList(),
                HpMaxOffsets: hpMaxOffsets.Select(o => $"0x{o:X}").ToList(),
                ResourceOffsets: resourceOffsets.Select(o => $"0x{o:X}").ToList(),
                ResourceMaxOffsets: resourceMaxOffsets.Select(o => $"0x{o:X}").ToList(),
                ComboOffsets: comboOffsets.Select(o => $"0x{o:X}").ToList(),
                PlanarMaxOffsets: planarMaxOffsets.Select(o => $"0x{o:X}").ToList(),
                OwnerOffsets: hubOwnerOffsets.Select(o => $"0x{o:X}").ToList(),
                StateOffsets: hubStateOffsets.Select(o => $"0x{o:X}").ToList(),
                SourceOffsets: hubSourceOffsets.Select(o => $"0x{o:X}").ToList(),
                Reasons: reasons
            ));
        }

        var rankedHubs = hubCandidates
            .OrderByDescending(h => h.Score)
            .ThenBy(h => h.Address)
            .ToList();

        var identityGraphLinks = new List<PlayerStatHubGraphLink>();
        foreach (var identity in identityComponents)
        {
            foreach (var pointerTarget in identity.PointerTargets)
            {
                var matchingHub = rankedHubs.FirstOrDefault(h => h.Address == pointerTarget.Address);
                if (matchingHub != null)
                {
                    identityGraphLinks.Add(new PlayerStatHubGraphLink(
                        IdentityComponentIndex: identity.Index,
                        IdentityComponentAddress: identity.Address,
                        OffsetHex: pointerTarget.OffsetHex,
                        HubAddress: matchingHub.Address,
                        HubScore: matchingHub.Score
                    ));
                }
            }
        }

        return new PlayerStatHubRankResult(
            Mode: "player-stat-hub-graph",
            GeneratedAtUtc: DateTimeOffset.UtcNow.ToString("O"),
            OwnerComponentsFile: artifactDocument.SourceFile,
            SnapshotFile: snapshotDocument.SourceFile,
            OwnerAddress: $"0x{ownerAddress:X}",
            StateRecordAddress: $"0x{stateRecordAddress:X}",
            SelectedSourceAddress: $"0x{selectedSourceAddress:X}",
            PlayerUnitId: player.Id ?? "n/a",
            PlayerUnitIdRawHex: $"0x{playerUnitIdValue:X16}",
            PlayerLevel: player.Level,
            PlayerHp: (int?)player.Hp,
            PlayerHpMax: (int?)player.HpMax,
            PlayerResource: (int?)player.Resource,
            PlayerResourceMax: (int?)player.ResourceMax,
            PlayerCombo: (int?)player.Combo,
            PlayerPlanarMax: (int?)player.PlanarMax,
            IdentityComponents: identityComponents,
            RankedSharedHubs: rankedHubs,
            IdentityGraphLinks: identityGraphLinks
        );
    }

    private static ulong ParseAddress(string? address)
    {
        if (TryParseAddress(address, out var value)) return value;
        return 0;
    }

    private static bool TryParseAddress(string? address, out ulong value)
    {
        value = 0;
        if (string.IsNullOrWhiteSpace(address)) return false;

        var normalized = address.StartsWith("0x", StringComparison.OrdinalIgnoreCase) ? address[2..] : address;
        return ulong.TryParse(normalized, NumberStyles.HexNumber, CultureInfo.InvariantCulture, out value);
    }

    private static int[] FindInt32Offsets(byte[] bytes, int value)
    {
        var offsets = new List<int>();
        for (var i = 0; i <= bytes.Length - 4; i += 4)
        {
            if (BitConverter.ToInt32(bytes, i) == value) offsets.Add(i);
        }
        return offsets.ToArray();
    }

    private static int[] FindUInt64Offsets(byte[] bytes, ulong value)
    {
        var offsets = new List<int>();
        for (var i = 0; i <= bytes.Length - 8; i += 8)
        {
            if (BitConverter.ToUInt64(bytes, i) == value) offsets.Add(i);
        }
        return offsets.ToArray();
    }

    private sealed record TempPointer(int Offset, string OffsetHex, string Address, ulong Value);

    private static List<TempPointer> GetHeapPointerEntries(byte[] bytes, int limit)
    {
        var entries = new List<TempPointer>();
        var seen = new HashSet<ulong>();
        for (var i = 0; i <= bytes.Length - 8; i += 8)
        {
            var val = BitConverter.ToUInt64(bytes, i);
            if (val < PointerMin || val > PointerMax) continue;
            if (!seen.Add(val)) continue;

            entries.Add(new TempPointer(i, $"0x{i:X}", $"0x{val:X}", val));
            if (entries.Count >= limit) break;
        }
        return entries;
    }
}
