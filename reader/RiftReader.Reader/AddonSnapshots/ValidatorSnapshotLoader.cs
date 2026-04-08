using System.Globalization;
using RiftReader.Reader.Lua;

namespace RiftReader.Reader.AddonSnapshots;

public static class ValidatorSnapshotLoader
{
    private const string SavedVariablesFileName = "RiftReaderValidator.lua";
    private const string RootVariableName = "RiftReaderValidator_State";

    public static ValidatorSnapshotDocument? TryLoad(string? explicitPath, out string? error)
    {
        var sourceFile = string.IsNullOrWhiteSpace(explicitPath)
            ? TryFindLatestSavedVariablesFile(out error)
            : ResolveExplicitPath(explicitPath!, out error);

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
            error = $"Unable to read addon snapshot file '{sourceFile}': {ex.Message}";
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

        var current = root.GetTable("current");
        var session = root.GetTable("session");
        var samples = root.GetTable("samples");

        error = null;
        return new ValidatorSnapshotDocument(
            SourceFile: sourceFile,
            LoadedAtUtc: DateTimeOffset.UtcNow,
            SampleCount: samples?.Items.Count ?? 0,
            LastCaptureAt: session?.GetDouble("lastCaptureAt"),
            LastReason: session?.GetString("lastReason"),
            Current: current is null ? null : MapSnapshot(current));
    }

    private static string? TryFindLatestSavedVariablesFile(out string? error)
    {
        var documentsPath = Environment.GetFolderPath(Environment.SpecialFolder.MyDocuments);

        if (string.IsNullOrWhiteSpace(documentsPath) || !Directory.Exists(documentsPath))
        {
            error = "Unable to locate the user's Documents folder for Rift saved variables.";
            return null;
        }

        var riftSavedRoot = Path.Combine(documentsPath, "RIFT", "Interface", "Saved");

        if (!Directory.Exists(riftSavedRoot))
        {
            error = $"Rift saved variables folder was not found: '{riftSavedRoot}'.";
            return null;
        }

        string[] matches;

        try
        {
            matches = Directory.GetFiles(riftSavedRoot, SavedVariablesFileName, SearchOption.AllDirectories);
        }
        catch (Exception ex)
        {
            error = $"Unable to search '{riftSavedRoot}' for '{SavedVariablesFileName}': {ex.Message}";
            return null;
        }

        if (matches.Length == 0)
        {
            error = $"No '{SavedVariablesFileName}' files were found under '{riftSavedRoot}'.";
            return null;
        }

        error = null;
        return matches
            .OrderByDescending(path => File.GetLastWriteTimeUtc(path))
            .First();
    }

    private static string? ResolveExplicitPath(string explicitPath, out string? error)
    {
        string resolvedPath;

        try
        {
            resolvedPath = Path.GetFullPath(explicitPath);
        }
        catch (Exception ex)
        {
            error = $"Invalid addon snapshot path '{explicitPath}': {ex.Message}";
            return null;
        }

        if (!File.Exists(resolvedPath))
        {
            error = $"Addon snapshot file was not found: '{resolvedPath}'.";
            return null;
        }

        error = null;
        return resolvedPath;
    }

    private static ValidatorSnapshot MapSnapshot(LuaTable table) =>
        new(
            Sequence: table.GetInt64("sequence"),
            Reason: table.GetString("reason"),
            CapturedAt: table.GetDouble("capturedAt"),
            PlayerUnit: table.GetString("playerUnit"),
            Name: table.GetString("name"),
            Level: table.GetInt32("level"),
            Health: table.GetInt64("health"),
            HealthMax: table.GetInt64("healthMax"),
            Mana: table.GetInt64("mana"),
            ManaMax: table.GetInt64("manaMax"),
            Energy: table.GetInt64("energy"),
            EnergyMax: table.GetInt64("energyMax"),
            Power: table.GetInt64("power"),
            Charge: table.GetInt64("charge"),
            ChargeMax: table.GetInt64("chargeMax"),
            Combo: table.GetInt64("combo"),
            Role: table.GetString("role"),
            Combat: table.GetBoolean("combat"),
            Zone: table.GetString("zone"),
            LocationName: table.GetString("locationName"),
            Coord: MapCoordinate(table.GetTable("coord")));

    private static ValidatorCoordinateSnapshot? MapCoordinate(LuaTable? table)
    {
        if (table is null)
        {
            return null;
        }

        var x = table.GetDouble("x") ?? table.GetDouble("coordX") ?? table.GetItemDouble(0);
        var y = table.GetDouble("y") ?? table.GetDouble("coordY") ?? table.GetItemDouble(1);
        var z = table.GetDouble("z") ?? table.GetDouble("coordZ") ?? table.GetItemDouble(2);

        if (x is null && y is null && z is null)
        {
            return null;
        }

        return new ValidatorCoordinateSnapshot(x, y, z);
    }
}
