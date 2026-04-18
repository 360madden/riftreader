using System.Globalization;
using RiftReader.Reader.Lua;

namespace RiftReader.Reader.AddonSnapshots;

public static class ReaderBridgeSnapshotLoader
{
    private const string SavedVariablesFileName = "ReaderBridgeExport.lua";
    private const string RootVariableName = "ReaderBridgeExport_State";

    public static ReaderBridgeSnapshotDocument? TryLoad(string? explicitPath, out string? error)
    {
        var sourceFile = string.IsNullOrWhiteSpace(explicitPath)
            ? SavedVariablesFileLocator.TryFindLatest(SavedVariablesFileName, out error)
            : SavedVariablesFileLocator.ResolveExplicitPath(explicitPath!, out error);

        if (sourceFile is null)
        {
            return null;
        }

        string text;

        try
        {
            text = File.ReadAllText(sourceFile);
        }
        catch (Exception ex)
        {
            error = $"Unable to read ReaderBridge export file '{sourceFile}': {ex.Message}";
            return null;
        }

        if (!LuaAssignmentParser.TryParse(text, out var assignment, out error) || assignment is null)
        {
            return null;
        }

        if (!string.Equals(assignment.VariableName, RootVariableName, StringComparison.Ordinal))
        {
            error = $"Unexpected root variable '{assignment.VariableName}'. Expected '{RootVariableName}'.";
            return null;
        }

        if (assignment.Value is not LuaTable root)
        {
            error = $"Unexpected root value in '{sourceFile}'. Expected a Lua table.";
            return null;
        }

        var session = root.GetTable("session");
        var current = root.GetTable("current");

        error = null;
        return new ReaderBridgeSnapshotDocument(
            SourceFile: sourceFile,
            LoadedAtUtc: DateTimeOffset.UtcNow,
            SchemaVersion: root.GetInt32("schemaVersion"),
            LastExportAt: session?.GetDouble("lastExportAt"),
            LastReason: session?.GetString("lastReason"),
            ExportCount: session?.GetInt32("exportCount"),
            Current: current is null ? null : MapSnapshot(current));
    }

    private static ReaderBridgeSnapshot MapSnapshot(LuaTable table) =>
        new(
            SchemaVersion: table.GetInt32("schemaVersion"),
            Status: table.GetString("status"),
            ExportReason: table.GetString("exportReason"),
            ExportCount: table.GetInt32("exportCount"),
            GeneratedAtRealtime: table.GetDouble("generatedAtRealtime"),
            SourceMode: table.GetString("sourceMode"),
            SourceAddon: table.GetString("sourceAddon"),
            SourceVersion: table.GetString("sourceVersion"),
            ExportAddon: table.GetString("exportAddon"),
            ExportVersion: table.GetString("exportVersion"),
            PlayerId: table.GetString("playerId"),
            TargetId: table.GetString("targetId"),
            Hud: MapHud(table.GetTable("hud")),
            Player: MapUnit(table.GetTable("player")),
            Target: MapUnit(table.GetTable("target")),
            OrientationProbe: MapOrientationProbe(table.GetTable("orientationProbe")),
            PlayerStats: MapDoubleDictionary(table.GetTable("playerStats")),
            PlayerCoordDelta: MapCoordinateDelta(table.GetTable("playerCoordDelta")),
            NearbySummary: MapUnitCollectionSummary(table.GetTable("nearbySummary")),
            PartySummary: MapUnitCollectionSummary(table.GetTable("partySummary")),
            NearbyUnits: MapUnitList(table.GetTable("nearbyUnits")),
            PartyUnits: MapUnitList(table.GetTable("partyUnits")),
            PlayerBuffLines: MapStringList(table.GetTable("playerBuffLines")),
            PlayerDebuffLines: MapStringList(table.GetTable("playerDebuffLines")),
            TargetBuffLines: MapStringList(table.GetTable("targetBuffLines")),
            TargetDebuffLines: MapStringList(table.GetTable("targetDebuffLines")),
            PlayerBuffs: MapBuffList(table.GetTable("playerBuffs")),
            PlayerDebuffs: MapBuffList(table.GetTable("playerDebuffs")),
            TargetBuffs: MapBuffList(table.GetTable("targetBuffs")),
            TargetDebuffs: MapBuffList(table.GetTable("targetDebuffs")));

    private static ReaderBridgeHudSnapshot? MapHud(LuaTable? table)
    {
        if (table is null)
        {
            return null;
        }

        return new ReaderBridgeHudSnapshot(
            Visible: table.GetBoolean("visible"),
            Locked: table.GetBoolean("locked"),
            ShowBuffPanel: table.GetBoolean("showBuffPanel"));
    }

    private static ReaderBridgeUnitSnapshot? MapUnit(LuaTable? table)
    {
        if (table is null)
        {
            return null;
        }

        return new ReaderBridgeUnitSnapshot(
            Id: table.GetString("id"),
            Name: table.GetString("name"),
            Level: table.GetInt32("level"),
            Calling: table.GetString("calling"),
            Guild: table.GetString("guild"),
            Relation: table.GetString("relation"),
            Role: table.GetString("role"),
            Player: table.GetBoolean("player"),
            Combat: table.GetBoolean("combat"),
            Aggro: table.GetBoolean("aggro"),
            Blocked: table.GetBoolean("blocked"),
            Tagged: table.GetBoolean("tagged"),
            Mounted: GetBooleanAny(table, "mounted", "mount"),
            Pvp: table.GetBoolean("pvp"),
            Hp: table.GetInt64("hp"),
            HpMax: table.GetInt64("hpMax"),
            HpCap: table.GetInt64("hpCap"),
            HpPct: table.GetInt64("hpPct"),
            Absorb: table.GetInt64("absorb"),
            Vitality: table.GetInt64("vitality"),
            ResourceKind: table.GetString("resourceKind"),
            Resource: table.GetInt64("resource"),
            ResourceMax: table.GetInt64("resourceMax"),
            ResourcePct: table.GetInt64("resourcePct"),
            Mana: table.GetInt64("mana"),
            ManaMax: table.GetInt64("manaMax"),
            Energy: table.GetInt64("energy"),
            EnergyMax: table.GetInt64("energyMax"),
            Power: table.GetInt64("power"),
            Charge: table.GetInt64("charge"),
            ChargeMax: table.GetInt64("chargeMax"),
            ChargePct: table.GetInt64("chargePct"),
            Planar: table.GetInt64("planar"),
            PlanarMax: table.GetInt64("planarMax"),
            PlanarPct: table.GetInt64("planarPct"),
            Combo: table.GetInt64("combo"),
            ComboUnit: table.GetString("comboUnit"),
            Mark: GetValueTextAny(table, "mark", "marked"),
            Zone: table.GetString("zone"),
            LocationName: table.GetString("locationName"),
            Coord: MapCoordinate(table.GetTable("coord")),
            Distance: table.GetDouble("distance"),
            Ttd: table.GetDouble("ttd"),
            TtdText: table.GetString("ttdText"),
            Cast: MapCast(table.GetTable("cast")));
    }

    private static IReadOnlyList<ReaderBridgeUnitSnapshot> MapUnitList(LuaTable? table)
    {
        if (table is null || table.Items.Count == 0)
        {
            return Array.Empty<ReaderBridgeUnitSnapshot>();
        }

        var values = new List<ReaderBridgeUnitSnapshot>(table.Items.Count);

        foreach (var item in table.Items)
        {
            if (item is not LuaTable entry)
            {
                continue;
            }

            var mapped = MapUnit(entry);
            if (mapped is not null)
            {
                values.Add(mapped);
            }
        }

        return values;
    }

    private static ReaderBridgeCastSnapshot? MapCast(LuaTable? table)
    {
        if (table is null)
        {
            return null;
        }

        return new ReaderBridgeCastSnapshot(
            Active: table.GetBoolean("active"),
            AbilityName: table.GetString("abilityName"),
            Duration: table.GetDouble("duration"),
            Remaining: table.GetDouble("remaining"),
            Channeled: table.GetBoolean("channeled"),
            Uninterruptible: table.GetBoolean("uninterruptible"),
            ProgressPct: table.GetDouble("progressPct"),
            Text: table.GetString("text"));
    }

    private static ReaderBridgeOrientationProbeSnapshot? MapOrientationProbe(LuaTable? table)
    {
        if (table is null)
        {
            return null;
        }

        return new ReaderBridgeOrientationProbeSnapshot(
            Player: MapOrientationProbeUnit(table.GetTable("player")),
            Target: MapOrientationProbeUnit(table.GetTable("target")),
            StatCandidates: MapOrientationProbeFields(GetTableAny(table, "statCandidates", "sharedStatCandidates", "stats")));
    }

    private static ReaderBridgeOrientationProbeUnitSnapshot? MapOrientationProbeUnit(LuaTable? table)
    {
        if (table is null)
        {
            return null;
        }

        return new ReaderBridgeOrientationProbeUnitSnapshot(
            Source: GetStringAny(table, "source", "label"),
            UnitId: GetStringAny(table, "unitId", "id"),
            UnitAvailable: GetBooleanAny(table, "unitAvailable"),
            DirectHeadingApiAvailable: GetBooleanAny(table, "directHeadingApiAvailable"),
            DirectPitchApiAvailable: GetBooleanAny(table, "directPitchApiAvailable"),
            DirectHeading: GetDoubleAny(table, "directHeading", "heading"),
            DirectPitch: GetDoubleAny(table, "directPitch", "pitch"),
            Yaw: GetDoubleAny(table, "yaw", "directYaw"),
            Facing: GetStringAny(table, "facing", "directFacing"),
            DetailCandidates: MapOrientationProbeFields(GetTableAny(table, "detailCandidates", "detailFields", "detail", "candidates")),
            StateCandidates: MapOrientationProbeFields(GetTableAny(table, "stateCandidates", "stateFields", "state")));
    }

    private static IReadOnlyList<ReaderBridgeOrientationProbeFieldSnapshot> MapOrientationProbeFields(LuaTable? table)
    {
        if (table is null || table.Items.Count == 0)
        {
            return Array.Empty<ReaderBridgeOrientationProbeFieldSnapshot>();
        }

        var values = new List<ReaderBridgeOrientationProbeFieldSnapshot>(table.Items.Count);

        foreach (var item in table.Items)
        {
            if (item is LuaTable candidateTable)
            {
                values.Add(new ReaderBridgeOrientationProbeFieldSnapshot(
                    Key: GetStringAny(candidateTable, "key", "name", "field", "label"),
                    Value: GetValueTextAny(candidateTable, "value", "text", "result"),
                    Kind: GetStringAny(candidateTable, "kind", "source", "type", "valueType")));
                continue;
            }

            if (item is null)
            {
                continue;
            }

            values.Add(new ReaderBridgeOrientationProbeFieldSnapshot(
                Key: null,
                Value: item.ToString(),
                Kind: null));
        }

        return values;
    }

    private static ReaderBridgeCoordinateDeltaSnapshot? MapCoordinateDelta(LuaTable? table)
    {
        if (table is null)
        {
            return null;
        }

        var dx = table.GetDouble("dx");
        var dy = table.GetDouble("dy");
        var dz = table.GetDouble("dz");
        var distance = table.GetDouble("distance");
        var dt = table.GetDouble("dt");
        var speed = table.GetDouble("speed");

        if (dx is null && dy is null && dz is null && distance is null && dt is null && speed is null)
        {
            return null;
        }

        return new ReaderBridgeCoordinateDeltaSnapshot(
            Dx: dx,
            Dy: dy,
            Dz: dz,
            Distance: distance,
            Dt: dt,
            Speed: speed);
    }

    private static IReadOnlyDictionary<string, double> MapDoubleDictionary(LuaTable? table)
    {
        if (table is null || table.Fields.Count == 0)
        {
            return new Dictionary<string, double>(StringComparer.Ordinal);
        }

        var result = new Dictionary<string, double>(StringComparer.Ordinal);
        foreach (var (key, value) in table.Fields)
        {
            var numeric = LuaScalarConversions.ToDouble(value);
            if (numeric.HasValue)
            {
                result[key] = numeric.Value;
            }
        }

        return result;
    }

    private static IReadOnlyDictionary<string, int> MapIntDictionary(LuaTable? table)
    {
        if (table is null || table.Fields.Count == 0)
        {
            return new Dictionary<string, int>(StringComparer.Ordinal);
        }

        var result = new Dictionary<string, int>(StringComparer.Ordinal);
        foreach (var (key, value) in table.Fields)
        {
            var numeric = LuaScalarConversions.ToInt64(value);
            if (numeric.HasValue && numeric.Value is >= int.MinValue and <= int.MaxValue)
            {
                result[key] = (int)numeric.Value;
            }
        }

        return result;
    }

    private static ReaderBridgeUnitCollectionSummarySnapshot? MapUnitCollectionSummary(LuaTable? table)
    {
        if (table is null)
        {
            return null;
        }

        return new ReaderBridgeUnitCollectionSummarySnapshot(
            ScannedCount: table.GetInt32("scannedCount"),
            ExportedCount: table.GetInt32("exportedCount"),
            PlayerCount: table.GetInt32("playerCount"),
            CombatCount: table.GetInt32("combatCount"),
            PvpCount: table.GetInt32("pvpCount"),
            NearestDistance: table.GetDouble("nearestDistance"),
            NearestName: table.GetString("nearestName"),
            FarthestDistance: table.GetDouble("farthestDistance"),
            FarthestName: table.GetString("farthestName"),
            RelationCounts: MapIntDictionary(table.GetTable("relationCounts")));
    }

    private static IReadOnlyList<ReaderBridgeBuffSnapshot> MapBuffList(LuaTable? table)
    {
        if (table is null || table.Items.Count == 0)
        {
            return Array.Empty<ReaderBridgeBuffSnapshot>();
        }

        var values = new List<ReaderBridgeBuffSnapshot>(table.Items.Count);

        foreach (var item in table.Items)
        {
            if (item is not LuaTable entry)
            {
                continue;
            }

            values.Add(new ReaderBridgeBuffSnapshot(
                Id: GetValueTextAny(entry, "id"),
                Name: entry.GetString("name"),
                Remaining: entry.GetDouble("remaining"),
                Duration: entry.GetDouble("duration"),
                Stack: entry.GetInt64("stack"),
                Debuff: entry.GetBoolean("debuff"),
                Curse: entry.GetBoolean("curse"),
                Disease: entry.GetBoolean("disease"),
                Poison: entry.GetBoolean("poison"),
                Caster: entry.GetString("caster"),
                Text: entry.GetString("text"),
                Flags: MapStringList(entry.GetTable("flags"))));
        }

        return values;
    }

    private static ValidatorCoordinateSnapshot? MapCoordinate(LuaTable? table)
    {
        if (table is null)
        {
            return null;
        }

        var x = table.GetDouble("x");
        var y = table.GetDouble("y");
        var z = table.GetDouble("z");

        if (x is null && y is null && z is null)
        {
            return null;
        }

        return new ValidatorCoordinateSnapshot(x, y, z);
    }

    private static IReadOnlyList<string> MapStringList(LuaTable? table)
    {
        if (table is null || table.Items.Count == 0)
        {
            return Array.Empty<string>();
        }

        var values = new List<string>(table.Items.Count);

        foreach (var item in table.Items)
        {
            if (item is null)
            {
                continue;
            }

            values.Add(item.ToString() ?? string.Empty);
        }

        return values;
    }

    private static LuaTable? GetTableAny(LuaTable table, params string[] keys)
    {
        foreach (var key in keys)
        {
            var value = table.GetTable(key);
            if (value is not null)
            {
                return value;
            }
        }

        return null;
    }

    private static double? GetDoubleAny(LuaTable table, params string[] keys)
    {
        foreach (var key in keys)
        {
            var value = table.GetDouble(key);
            if (value.HasValue)
            {
                return value;
            }
        }

        return null;
    }

    private static string? GetStringAny(LuaTable table, params string[] keys)
    {
        foreach (var key in keys)
        {
            var value = table.GetString(key);
            if (!string.IsNullOrWhiteSpace(value))
            {
                return value;
            }
        }

        return null;
    }

    private static bool? GetBooleanAny(LuaTable table, params string[] keys)
    {
        foreach (var key in keys)
        {
            var value = table.GetBoolean(key);
            if (value.HasValue)
            {
                return value.Value;
            }
        }

        return null;
    }

    private static string? GetValueTextAny(LuaTable table, params string[] keys)
    {
        foreach (var key in keys)
        {
            if (!table.Fields.TryGetValue(key, out var value) || value is null)
            {
                continue;
            }

            return value switch
            {
                string text => text,
                bool boolean => boolean ? "true" : "false",
                long number => number.ToString(CultureInfo.InvariantCulture),
                int number => number.ToString(CultureInfo.InvariantCulture),
                double number => number.ToString(CultureInfo.InvariantCulture),
                _ => value.ToString()
            };
        }

        return null;
    }
}
