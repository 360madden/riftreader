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
            Hud: MapHud(table.GetTable("hud")),
            Player: MapUnit(table.GetTable("player")),
            Target: MapUnit(table.GetTable("target")),
            OrientationProbe: MapOrientationProbe(table.GetTable("orientationProbe")),
            PlayerBuffLines: MapStringList(table.GetTable("playerBuffLines")),
            PlayerDebuffLines: MapStringList(table.GetTable("playerDebuffLines")),
            TargetBuffLines: MapStringList(table.GetTable("targetBuffLines")),
            TargetDebuffLines: MapStringList(table.GetTable("targetDebuffLines")));

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
            Pvp: table.GetBoolean("pvp"),
            Hp: table.GetInt64("hp"),
            HpMax: table.GetInt64("hpMax"),
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
            Zone: table.GetString("zone"),
            LocationName: table.GetString("locationName"),
            Coord: MapCoordinate(table.GetTable("coord")),
            Distance: table.GetDouble("distance"),
            Ttd: table.GetDouble("ttd"),
            TtdText: table.GetString("ttdText"),
            Cast: MapCast(table.GetTable("cast")));
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
