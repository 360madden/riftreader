using System.Globalization;
using System.Text;
using System.Text.Json;
using System.Text.Json.Serialization;

namespace RiftReader.Reader.Navigation;

public sealed record TomTomWaypointImportOptions(
    string SourceFile,
    string DestinationFile,
    IReadOnlyList<string> ListNames,
    string? Zone,
    double DefaultY,
    string IdPrefix,
    double? ArrivalRadius,
    string? Pace);

public sealed record TomTomWaypointImportResult(
    string Mode,
    string SourceFile,
    string DestinationFile,
    int ImportedWaypointCount,
    int PreservedWaypointCount,
    int UpdatedWaypointCount,
    IReadOnlyList<TomTomWaypointImportListSummary> Lists,
    IReadOnlyList<TomTomImportedWaypointSummary> Waypoints,
    IReadOnlyList<string> Warnings);

public sealed record TomTomWaypointImportListSummary(
    string Name,
    int ImportedWaypointCount,
    int SkippedWaypointCount);

public sealed record TomTomImportedWaypointSummary(
    string Id,
    string ListName,
    string? Zone,
    double X,
    double Y,
    double Z,
    string Label);

public static class TomTomWaypointImporter
{
    private const int SupportedSchemaVersion = 1;

    private static readonly JsonSerializerOptions ReadOptions = new()
    {
        PropertyNameCaseInsensitive = true
    };

    private static readonly JsonSerializerOptions WriteOptions = new()
    {
        WriteIndented = true,
        PropertyNamingPolicy = JsonNamingPolicy.CamelCase,
        DefaultIgnoreCondition = JsonIgnoreCondition.WhenWritingNull
    };

    public static TomTomWaypointImportResult? TryImport(
        TomTomWaypointImportOptions options,
        out string? error)
    {
        error = null;

        if (string.IsNullOrWhiteSpace(options.SourceFile))
        {
            error = "TomTom saved variables file must not be blank.";
            return null;
        }

        if (!File.Exists(options.SourceFile))
        {
            error = $"TomTom saved variables file was not found: '{options.SourceFile}'.";
            return null;
        }

        if (string.IsNullOrWhiteSpace(options.DestinationFile))
        {
            error = "Navigation waypoint output file must not be blank.";
            return null;
        }

        if (!double.IsFinite(options.DefaultY))
        {
            error = "TomTom default Y must be finite.";
            return null;
        }

        if (options.ArrivalRadius.HasValue && (!double.IsFinite(options.ArrivalRadius.Value) || options.ArrivalRadius.Value <= 0d))
        {
            error = "TomTom arrival radius must be positive when provided.";
            return null;
        }

        string? normalizedPace = null;
        if (!string.IsNullOrWhiteSpace(options.Pace) &&
            !NavigationPace.TryNormalize(options.Pace, out normalizedPace))
        {
            error = $"Unsupported TomTom import pace '{options.Pace}'. Use run, walk, or keep.";
            return null;
        }

        var idPrefix = string.IsNullOrWhiteSpace(options.IdPrefix)
            ? "tomtom"
            : SanitizeIdPart(options.IdPrefix);
        if (string.IsNullOrWhiteSpace(idPrefix))
        {
            idPrefix = "tomtom";
        }

        Dictionary<string, LuaValue> assignments;
        try
        {
            var lua = File.ReadAllText(options.SourceFile);
            assignments = new LuaSavedVariablesParser(lua).ParseAssignments();
        }
        catch (Exception ex)
        {
            error = $"Unable to parse TomTom saved variables '{options.SourceFile}': {ex.Message}";
            return null;
        }

        if (!TryResolvePickupLocations(assignments, out var pickupLocations, out error))
        {
            return null;
        }

        var includeLists = new HashSet<string>(
            (options.ListNames ?? Array.Empty<string>()).Where(static value => !string.IsNullOrWhiteSpace(value)).Select(static value => value.Trim()),
            StringComparer.OrdinalIgnoreCase);
        var zoneFilter = string.IsNullOrWhiteSpace(options.Zone) ? null : options.Zone.Trim();
        var warnings = new List<string>();
        var imported = new List<NavigationWaypointDocument>();
        var summaries = new List<TomTomImportedWaypointSummary>();
        var listSummaries = new List<TomTomWaypointImportListSummary>();
        var usedIds = new HashSet<string>(StringComparer.OrdinalIgnoreCase);

        foreach (var (listName, listValue) in pickupLocations.Fields.OrderBy(static pair => pair.Key, StringComparer.OrdinalIgnoreCase))
        {
            if (includeLists.Count > 0 && !includeLists.Contains(listName))
            {
                continue;
            }

            if (listValue is not LuaTable listTable)
            {
                warnings.Add($"Skipped TomTom list '{listName}' because it was not a table.");
                listSummaries.Add(new TomTomWaypointImportListSummary(listName, ImportedWaypointCount: 0, SkippedWaypointCount: 1));
                continue;
            }

            var importedForList = 0;
            var skippedForList = 0;
            var listIdPart = SanitizeIdPart(listName);
            if (string.IsNullOrWhiteSpace(listIdPart))
            {
                listIdPart = "list";
            }

            for (var index = 0; index < listTable.ArrayItems.Count; index++)
            {
                var entryNumber = index + 1;
                if (!TryReadTomTomEntry(listTable.ArrayItems[index], out var zone, out var x, out var z, out var comment, out var entryError))
                {
                    skippedForList++;
                    warnings.Add($"Skipped TomTom list '{listName}' entry #{entryNumber}: {entryError}");
                    continue;
                }

                if (!string.IsNullOrWhiteSpace(zoneFilter) &&
                    !string.Equals(zone, zoneFilter, StringComparison.OrdinalIgnoreCase))
                {
                    skippedForList++;
                    continue;
                }

                var baseId = $"{idPrefix}_{listIdPart}_{entryNumber:000}";
                var id = baseId;
                var duplicateIndex = 2;
                while (!usedIds.Add(id))
                {
                    id = $"{baseId}_{duplicateIndex}";
                    duplicateIndex++;
                }

                var label = string.IsNullOrWhiteSpace(comment)
                    ? $"{listName} #{entryNumber}"
                    : $"{listName}: {comment.Trim()}";

                var waypoint = new NavigationWaypointDocument(
                    Id: id,
                    Label: label,
                    Zone: zone,
                    X: x,
                    Y: options.DefaultY,
                    Z: z,
                    ArrivalRadius: options.ArrivalRadius,
                    Pace: normalizedPace);

                imported.Add(waypoint);
                summaries.Add(new TomTomImportedWaypointSummary(
                    Id: id,
                    ListName: listName,
                    Zone: zone,
                    X: x,
                    Y: options.DefaultY,
                    Z: z,
                    Label: label));
                importedForList++;
            }

            listSummaries.Add(new TomTomWaypointImportListSummary(listName, importedForList, skippedForList));
        }

        if (includeLists.Count > 0)
        {
            foreach (var missingList in includeLists.Where(listName => !pickupLocations.Fields.ContainsKey(listName)))
            {
                warnings.Add($"Requested TomTom list '{missingList}' was not found.");
            }
        }

        if (imported.Count == 0)
        {
            error = warnings.Count > 0
                ? "No TomTom waypoints were imported. " + string.Join(" ", warnings)
                : "No TomTom waypoints were imported.";
            return null;
        }

        if (!TryLoadExistingDocument(options.DestinationFile, out var existingDocument, out error))
        {
            return null;
        }

        var importedIds = new HashSet<string>(imported.Select(static waypoint => waypoint.Id!), StringComparer.OrdinalIgnoreCase);
        var existingWaypoints = existingDocument.Waypoints?.Where(static waypoint => waypoint is not null).ToList() ?? [];
        var updatedCount = existingWaypoints.Count(waypoint => !string.IsNullOrWhiteSpace(waypoint!.Id) && importedIds.Contains(waypoint.Id.Trim()));
        var preservedWaypoints = existingWaypoints
            .Where(waypoint => string.IsNullOrWhiteSpace(waypoint!.Id) || !importedIds.Contains(waypoint.Id.Trim()))
            .ToList();
        preservedWaypoints.AddRange(imported);

        var document = new NavigationWaypointFileDocument(
            SchemaVersion: existingDocument.SchemaVersion ?? SupportedSchemaVersion,
            Provenance: existingDocument.Provenance,
            Movement: existingDocument.Movement ?? CreateDefaultMovement(),
            Waypoints: preservedWaypoints);

        try
        {
            var directory = Path.GetDirectoryName(options.DestinationFile);
            if (!string.IsNullOrWhiteSpace(directory))
            {
                Directory.CreateDirectory(directory);
            }

            var json = JsonSerializer.Serialize(document, WriteOptions);
            File.WriteAllText(options.DestinationFile, json, new UTF8Encoding(encoderShouldEmitUTF8Identifier: false));
        }
        catch (Exception ex)
        {
            error = $"Unable to write navigation waypoint file '{options.DestinationFile}': {ex.Message}";
            return null;
        }

        if (WaypointNavigationConfigurationLoader.TryLoad(options.DestinationFile, out var loadError) is null)
        {
            error = loadError ?? $"Imported waypoint file '{options.DestinationFile}' could not be reloaded.";
            return null;
        }

        return new TomTomWaypointImportResult(
            Mode: "tomtom-waypoint-import",
            SourceFile: options.SourceFile,
            DestinationFile: options.DestinationFile,
            ImportedWaypointCount: imported.Count,
            PreservedWaypointCount: preservedWaypoints.Count - imported.Count,
            UpdatedWaypointCount: updatedCount,
            Lists: listSummaries,
            Waypoints: summaries,
            Warnings: warnings);
    }

    private static bool TryResolvePickupLocations(
        IReadOnlyDictionary<string, LuaValue> assignments,
        out LuaTable pickupLocations,
        out string? error)
    {
        pickupLocations = default!;
        error = null;

        if (assignments.TryGetValue("TomTomGlobal", out var globalValue) &&
            globalValue is LuaTable globalTable &&
            globalTable.Fields.TryGetValue("PickupLocations", out var pickupValue) &&
            pickupValue is LuaTable pickupTable)
        {
            pickupLocations = pickupTable;
            return true;
        }

        if (assignments.TryGetValue("PickupLocations", out var directPickupValue) &&
            directPickupValue is LuaTable directPickupTable)
        {
            pickupLocations = directPickupTable;
            return true;
        }

        error = "TomTom saved variables did not contain TomTomGlobal.PickupLocations.";
        return false;
    }

    private static bool TryReadTomTomEntry(
        LuaValue value,
        out string zone,
        out double x,
        out double z,
        out string? comment,
        out string error)
    {
        zone = string.Empty;
        x = 0d;
        z = 0d;
        comment = null;
        error = string.Empty;

        if (value is not LuaTable table)
        {
            error = "entry was not a table";
            return false;
        }

        if (table.ArrayItems.Count < 3)
        {
            error = "entry did not contain zone, x, and z values";
            return false;
        }

        if (table.ArrayItems[0] is not LuaString zoneValue || string.IsNullOrWhiteSpace(zoneValue.Value))
        {
            error = "entry zone was missing or not a string";
            return false;
        }

        if (table.ArrayItems[1] is not LuaNumber xValue || !double.IsFinite(xValue.Value))
        {
            error = "entry x coordinate was missing or not numeric";
            return false;
        }

        if (table.ArrayItems[2] is not LuaNumber zValue || !double.IsFinite(zValue.Value))
        {
            error = "entry z coordinate was missing or not numeric";
            return false;
        }

        zone = zoneValue.Value.Trim();
        x = xValue.Value;
        z = zValue.Value;
        comment = TryGetArrayString(table, 4) ?? TryGetArrayString(table, 3);

        return true;
    }

    private static string? TryGetArrayString(LuaTable table, int index) =>
        table.ArrayItems.Count > index && table.ArrayItems[index] is LuaString value
            ? value.Value
            : null;

    private static bool TryLoadExistingDocument(
        string destinationFile,
        out NavigationWaypointFileDocument document,
        out string? error)
    {
        if (!File.Exists(destinationFile))
        {
            document = new NavigationWaypointFileDocument(
                SchemaVersion: SupportedSchemaVersion,
                Provenance: null,
                Movement: CreateDefaultMovement(),
                Waypoints: []);
            error = null;
            return true;
        }

        try
        {
            var json = File.ReadAllText(destinationFile);
            var parsed = JsonSerializer.Deserialize<NavigationWaypointFileDocument>(json, ReadOptions);
            if (parsed is null)
            {
                document = default!;
                error = $"Navigation waypoint file '{destinationFile}' did not contain a readable document.";
                return false;
            }

            document = parsed;
            error = null;
            return true;
        }
        catch (Exception ex)
        {
            document = default!;
            error = $"Unable to load navigation waypoint file '{destinationFile}': {ex.Message}";
            return false;
        }
    }

    private static NavigationMovementOptionsDocument CreateDefaultMovement() =>
        new(
            ForwardKey: "w",
            RunKey: null,
            WalkKey: null,
            DefaultPace: NavigationPace.Keep,
            ForwardPulseMilliseconds: 250,
            PostPulseSampleDelayMilliseconds: 150,
            StartRadius: 2.0d,
            DefaultArrivalRadius: 1.5d,
            NoProgressWindowMilliseconds: 1500,
            MinimumProgressDistance: 0.35d,
            WrongWayToleranceDistance: 0.75d,
            MaxTravelSeconds: 30);

    private static string SanitizeIdPart(string value)
    {
        var builder = new StringBuilder();
        var previousSeparator = false;
        foreach (var ch in value.Trim().ToLowerInvariant())
        {
            if (char.IsLetterOrDigit(ch))
            {
                builder.Append(ch);
                previousSeparator = false;
            }
            else if ((ch == '_' || ch == '-') && builder.Length > 0 && !previousSeparator)
            {
                builder.Append(ch);
                previousSeparator = true;
            }
            else if (builder.Length > 0 && !previousSeparator)
            {
                builder.Append('_');
                previousSeparator = true;
            }
        }

        return builder.ToString().Trim('_', '-');
    }

    private abstract record LuaValue;

    private sealed record LuaNil : LuaValue
    {
        public static readonly LuaNil Instance = new();
    }

    private sealed record LuaString(string Value) : LuaValue;

    private sealed record LuaNumber(double Value) : LuaValue;

    private sealed record LuaBoolean(bool Value) : LuaValue;

    private sealed record LuaTable : LuaValue
    {
        public List<LuaValue> ArrayItems { get; } = [];
        public Dictionary<string, LuaValue> Fields { get; } = new(StringComparer.OrdinalIgnoreCase);
    }

    private enum LuaTokenKind
    {
        End,
        LeftBrace,
        RightBrace,
        LeftBracket,
        RightBracket,
        Equal,
        Comma,
        Semicolon,
        Identifier,
        String,
        Number
    }

    private readonly record struct LuaToken(LuaTokenKind Kind, string Text, int Position);

    private sealed class LuaSavedVariablesParser
    {
        private readonly IReadOnlyList<LuaToken> tokens;
        private int index;

        public LuaSavedVariablesParser(string text)
        {
            tokens = new LuaTokenizer(text).Tokenize();
        }

        public Dictionary<string, LuaValue> ParseAssignments()
        {
            var assignments = new Dictionary<string, LuaValue>(StringComparer.OrdinalIgnoreCase);
            while (!Is(LuaTokenKind.End))
            {
                var name = Expect(LuaTokenKind.Identifier, "Expected saved variable name.").Text;
                Expect(LuaTokenKind.Equal, $"Expected '=' after saved variable '{name}'.");
                assignments[name] = ParseValue();
                ConsumeSeparators();
            }

            return assignments;
        }

        private LuaValue ParseValue()
        {
            if (Match(LuaTokenKind.LeftBrace))
            {
                return ParseTableBody();
            }

            if (Match(LuaTokenKind.String, out var stringToken))
            {
                return new LuaString(stringToken.Text);
            }

            if (Match(LuaTokenKind.Number, out var numberToken))
            {
                if (!double.TryParse(numberToken.Text, NumberStyles.Float, CultureInfo.InvariantCulture, out var number))
                {
                    throw new FormatException($"Invalid number '{numberToken.Text}' at position {numberToken.Position}.");
                }

                return new LuaNumber(number);
            }

            if (Match(LuaTokenKind.Identifier, out var identifierToken))
            {
                return identifierToken.Text switch
                {
                    "true" => new LuaBoolean(true),
                    "false" => new LuaBoolean(false),
                    "nil" => LuaNil.Instance,
                    _ => new LuaString(identifierToken.Text)
                };
            }

            var current = Peek();
            throw new FormatException($"Unexpected token '{current.Text}' at position {current.Position}.");
        }

        private LuaTable ParseTableBody()
        {
            var table = new LuaTable();
            ConsumeSeparators();

            while (!Match(LuaTokenKind.RightBrace))
            {
                if (Is(LuaTokenKind.End))
                {
                    throw new FormatException("Unterminated Lua table.");
                }

                if (Is(LuaTokenKind.Identifier) && Peek(1).Kind == LuaTokenKind.Equal)
                {
                    var key = Expect(LuaTokenKind.Identifier, "Expected table key.").Text;
                    Expect(LuaTokenKind.Equal, $"Expected '=' after table key '{key}'.");
                    table.Fields[key] = ParseValue();
                }
                else if (Match(LuaTokenKind.LeftBracket))
                {
                    var keyValue = ParseValue();
                    Expect(LuaTokenKind.RightBracket, "Expected ']' after table key.");
                    Expect(LuaTokenKind.Equal, "Expected '=' after bracketed table key.");
                    var value = ParseValue();
                    if (TryGetPositiveIntegerKey(keyValue, out var arrayIndex))
                    {
                        while (table.ArrayItems.Count < arrayIndex)
                        {
                            table.ArrayItems.Add(LuaNil.Instance);
                        }

                        table.ArrayItems[arrayIndex - 1] = value;
                    }
                    else
                    {
                        table.Fields[FormatTableKey(keyValue)] = value;
                    }
                }
                else
                {
                    table.ArrayItems.Add(ParseValue());
                }

                ConsumeSeparators();
            }

            return table;
        }

        private static string FormatTableKey(LuaValue value) =>
            value switch
            {
                LuaString stringValue => stringValue.Value,
                LuaNumber numberValue => numberValue.Value.ToString(CultureInfo.InvariantCulture),
                LuaBoolean booleanValue => booleanValue.Value ? "true" : "false",
                _ => string.Empty
            };

        private static bool TryGetPositiveIntegerKey(LuaValue value, out int key)
        {
            key = 0;
            if (value is not LuaNumber numberValue)
            {
                return false;
            }

            var number = numberValue.Value;
            if (!double.IsFinite(number) ||
                number < 1d ||
                Math.Abs(number - Math.Round(number)) > double.Epsilon ||
                number > int.MaxValue)
            {
                return false;
            }

            key = (int)number;
            return true;
        }

        private void ConsumeSeparators()
        {
            while (Match(LuaTokenKind.Comma) || Match(LuaTokenKind.Semicolon))
            {
            }
        }

        private bool Is(LuaTokenKind kind) => Peek().Kind == kind;

        private LuaToken Peek(int offset = 0)
        {
            var tokenIndex = index + offset;
            return tokenIndex >= tokens.Count ? tokens[^1] : tokens[tokenIndex];
        }

        private bool Match(LuaTokenKind kind) => Match(kind, out _);

        private bool Match(LuaTokenKind kind, out LuaToken token)
        {
            token = Peek();
            if (token.Kind != kind)
            {
                return false;
            }

            index++;
            return true;
        }

        private LuaToken Expect(LuaTokenKind kind, string message)
        {
            if (Match(kind, out var token))
            {
                return token;
            }

            var current = Peek();
            throw new FormatException($"{message} Found '{current.Text}' at position {current.Position}.");
        }
    }

    private sealed class LuaTokenizer
    {
        private readonly string text;
        private int index;

        public LuaTokenizer(string text)
        {
            this.text = text ?? string.Empty;
        }

        public IReadOnlyList<LuaToken> Tokenize()
        {
            var result = new List<LuaToken>();
            while (true)
            {
                SkipWhitespaceAndComments();
                if (index >= text.Length)
                {
                    result.Add(new LuaToken(LuaTokenKind.End, string.Empty, index));
                    return result;
                }

                var position = index;
                var ch = text[index];
                switch (ch)
                {
                    case '{':
                        index++;
                        result.Add(new LuaToken(LuaTokenKind.LeftBrace, "{", position));
                        break;
                    case '}':
                        index++;
                        result.Add(new LuaToken(LuaTokenKind.RightBrace, "}", position));
                        break;
                    case '[':
                        index++;
                        result.Add(new LuaToken(LuaTokenKind.LeftBracket, "[", position));
                        break;
                    case ']':
                        index++;
                        result.Add(new LuaToken(LuaTokenKind.RightBracket, "]", position));
                        break;
                    case '=':
                        index++;
                        result.Add(new LuaToken(LuaTokenKind.Equal, "=", position));
                        break;
                    case ',':
                        index++;
                        result.Add(new LuaToken(LuaTokenKind.Comma, ",", position));
                        break;
                    case ';':
                        index++;
                        result.Add(new LuaToken(LuaTokenKind.Semicolon, ";", position));
                        break;
                    case '"':
                    case '\'':
                        result.Add(new LuaToken(LuaTokenKind.String, ReadString(), position));
                        break;
                    default:
                        if (IsIdentifierStart(ch))
                        {
                            result.Add(new LuaToken(LuaTokenKind.Identifier, ReadIdentifier(), position));
                        }
                        else if (char.IsDigit(ch) || ch is '-' or '+')
                        {
                            result.Add(new LuaToken(LuaTokenKind.Number, ReadNumber(), position));
                        }
                        else
                        {
                            throw new FormatException($"Unexpected character '{ch}' at position {position}.");
                        }

                        break;
                }
            }
        }

        private void SkipWhitespaceAndComments()
        {
            while (index < text.Length)
            {
                if (char.IsWhiteSpace(text[index]))
                {
                    index++;
                    continue;
                }

                if (text[index] == '-' && index + 1 < text.Length && text[index + 1] == '-')
                {
                    index += 2;
                    while (index < text.Length && text[index] != '\r' && text[index] != '\n')
                    {
                        index++;
                    }

                    continue;
                }

                break;
            }
        }

        private string ReadString()
        {
            var quote = text[index++];
            var builder = new StringBuilder();
            while (index < text.Length)
            {
                var ch = text[index++];
                if (ch == quote)
                {
                    return builder.ToString();
                }

                if (ch == '\\' && index < text.Length)
                {
                    var escaped = text[index++];
                    builder.Append(escaped switch
                    {
                        'n' => '\n',
                        'r' => '\r',
                        't' => '\t',
                        '\\' => '\\',
                        '"' => '"',
                        '\'' => '\'',
                        _ => escaped
                    });
                    continue;
                }

                builder.Append(ch);
            }

            throw new FormatException("Unterminated Lua string.");
        }

        private string ReadIdentifier()
        {
            var start = index;
            index++;
            while (index < text.Length && IsIdentifierPart(text[index]))
            {
                index++;
            }

            return text[start..index];
        }

        private string ReadNumber()
        {
            var start = index;
            if (text[index] is '-' or '+')
            {
                index++;
            }

            while (index < text.Length && (char.IsDigit(text[index]) || text[index] == '.'))
            {
                index++;
            }

            if (index < text.Length && text[index] is 'e' or 'E')
            {
                index++;
                if (index < text.Length && text[index] is '-' or '+')
                {
                    index++;
                }

                while (index < text.Length && char.IsDigit(text[index]))
                {
                    index++;
                }
            }

            return text[start..index];
        }

        private static bool IsIdentifierStart(char ch) =>
            char.IsLetter(ch) || ch == '_';

        private static bool IsIdentifierPart(char ch) =>
            char.IsLetterOrDigit(ch) || ch == '_';
    }
}
