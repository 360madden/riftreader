using System.Globalization;
using System.Text;

namespace RiftReader.Reader.Lua;

internal sealed class LuaTable
{
    public Dictionary<string, object?> Fields { get; } = new(StringComparer.Ordinal);

    public List<object?> Items { get; } = [];

    public LuaTable? GetTable(string key) =>
        Fields.TryGetValue(key, out var value)
            ? value as LuaTable
            : null;

    public string? GetString(string key) =>
        Fields.TryGetValue(key, out var value)
            ? value as string
            : null;

    public double? GetDouble(string key) =>
        Fields.TryGetValue(key, out var value)
            ? LuaScalarConversions.ToDouble(value)
            : null;

    public long? GetInt64(string key) =>
        Fields.TryGetValue(key, out var value)
            ? LuaScalarConversions.ToInt64(value)
            : null;

    public int? GetInt32(string key)
    {
        var value = GetInt64(key);
        return value.HasValue && value.Value is >= int.MinValue and <= int.MaxValue
            ? (int)value.Value
            : null;
    }

    public bool? GetBoolean(string key) =>
        Fields.TryGetValue(key, out var value) && value is bool boolean
            ? boolean
            : null;

    public double? GetItemDouble(int zeroBasedIndex) =>
        zeroBasedIndex >= 0 && zeroBasedIndex < Items.Count
            ? LuaScalarConversions.ToDouble(Items[zeroBasedIndex])
            : null;
}

internal static class LuaAssignmentParser
{
    public static bool TryParse(string text, out LuaAssignmentDocument? document, out string? error)
    {
        var parser = new Parser(text);
        return parser.TryParse(out document, out error);
    }

    private sealed class Parser(string text)
    {
        private readonly string _text = text;
        private int _index;

        public bool TryParse(out LuaAssignmentDocument? document, out string? error)
        {
            document = null;
            error = null;

            SkipTrivia();

            if (!TryParseIdentifier(out var variableName))
            {
                error = "Unable to parse the root Lua variable name.";
                return false;
            }

            SkipTrivia();

            if (!TryRead('='))
            {
                error = "Expected '=' after the root Lua variable name.";
                return false;
            }

            SkipTrivia();

            if (!TryParseValue(out var value, out error))
            {
                return false;
            }

            SkipTrivia();

            if (!IsAtEnd)
            {
                error = $"Unexpected trailing content near index {_index}.";
                return false;
            }

            document = new LuaAssignmentDocument(variableName!, value);
            return true;
        }

        private bool TryParseValue(out object? value, out string? error)
        {
            error = null;

            if (IsAtEnd)
            {
                value = null;
                error = "Unexpected end of input while parsing a Lua value.";
                return false;
            }

            var current = Current;

            if (current == '{')
            {
                return TryParseTable(out value, out error);
            }

            if (current is '"' or '\'')
            {
                return TryParseString(out value, out error);
            }

            if (char.IsDigit(current) || current is '-' or '+')
            {
                return TryParseNumber(out value, out error);
            }

            if (TryParseIdentifier(out var identifier))
            {
                switch (identifier)
                {
                    case "true":
                        value = true;
                        return true;
                    case "false":
                        value = false;
                        return true;
                    case "nil":
                        value = null;
                        return true;
                    default:
                        value = identifier;
                        return true;
                }
            }

            value = null;
            error = $"Unexpected character '{current}' at index {_index}.";
            return false;
        }

        private bool TryParseTable(out object? value, out string? error)
        {
            value = null;
            error = null;

            if (!TryRead('{'))
            {
                error = "Expected '{' at the start of a Lua table.";
                return false;
            }

            var table = new LuaTable();

            while (true)
            {
                SkipTrivia();

                if (TryRead('}'))
                {
                    value = table;
                    return true;
                }

                var entryStart = _index;

                if (TryParseField(table, out error))
                {
                    SkipTrivia();

                    if (TryRead(',') || TryRead(';'))
                    {
                        continue;
                    }

                    if (Peek('}'))
                    {
                        continue;
                    }

                    error = $"Expected ',' or '}}' near index {_index}.";
                    return false;
                }

                _index = entryStart;

                if (!TryParseValue(out var itemValue, out error))
                {
                    return false;
                }

                table.Items.Add(itemValue);

                SkipTrivia();

                if (TryRead(',') || TryRead(';'))
                {
                    continue;
                }

                if (Peek('}'))
                {
                    continue;
                }

                error = $"Expected ',' or '}}' near index {_index}.";
                return false;
            }
        }

        private bool TryParseField(LuaTable table, out string? error)
        {
            error = null;
            var start = _index;

            if (TryRead('['))
            {
                SkipTrivia();

                if (!TryParseValue(out var keyValue, out error))
                {
                    return false;
                }

                SkipTrivia();

                if (!TryRead(']'))
                {
                    error = "Expected closing ']' in Lua table key.";
                    return false;
                }

                SkipTrivia();

                if (!TryRead('='))
                {
                    _index = start;
                    error = null;
                    return false;
                }

                SkipTrivia();

                if (!TryParseValue(out var value, out error))
                {
                    return false;
                }

                table.Fields[ConvertKeyToString(keyValue)] = value;
                return true;
            }

            if (!TryParseIdentifier(out var identifier))
            {
                _index = start;
                return false;
            }

            SkipTrivia();

            if (!TryRead('='))
            {
                _index = start;
                return false;
            }

            SkipTrivia();

            if (!TryParseValue(out var fieldValue, out error))
            {
                return false;
            }

            table.Fields[identifier!] = fieldValue;
            return true;
        }

        private bool TryParseString(out object? value, out string? error)
        {
            error = null;
            value = null;

            if (IsAtEnd)
            {
                error = "Unexpected end of input while parsing a Lua string.";
                return false;
            }

            var quote = Current;
            _index++;
            var builder = new StringBuilder();

            while (!IsAtEnd)
            {
                var current = Current;
                _index++;

                if (current == quote)
                {
                    value = builder.ToString();
                    return true;
                }

                if (current == '\\' && !IsAtEnd)
                {
                    var escaped = Current;
                    _index++;
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

                builder.Append(current);
            }

            error = "Unterminated Lua string literal.";
            return false;
        }

        private bool TryParseNumber(out object? value, out string? error)
        {
            error = null;
            value = null;

            var start = _index;

            if (Current is '+' or '-')
            {
                _index++;
            }

            while (!IsAtEnd && char.IsDigit(Current))
            {
                _index++;
            }

            var hasDecimal = false;

            if (!IsAtEnd && Current == '.')
            {
                hasDecimal = true;
                _index++;

                while (!IsAtEnd && char.IsDigit(Current))
                {
                    _index++;
                }
            }

            if (!IsAtEnd && (Current is 'e' or 'E'))
            {
                hasDecimal = true;
                _index++;

                if (!IsAtEnd && (Current is '+' or '-'))
                {
                    _index++;
                }

                while (!IsAtEnd && char.IsDigit(Current))
                {
                    _index++;
                }
            }

            var text = _text[start.._index];

            if (hasDecimal)
            {
                if (!double.TryParse(text, NumberStyles.Float, CultureInfo.InvariantCulture, out var doubleValue))
                {
                    error = $"Invalid Lua number '{text}'.";
                    return false;
                }

                value = doubleValue;
                return true;
            }

            if (!long.TryParse(text, NumberStyles.Integer, CultureInfo.InvariantCulture, out var longValue))
            {
                error = $"Invalid Lua integer '{text}'.";
                return false;
            }

            value = longValue;
            return true;
        }

        private bool TryParseIdentifier(out string? identifier)
        {
            identifier = null;

            if (IsAtEnd || !(char.IsLetter(Current) || Current == '_'))
            {
                return false;
            }

            var start = _index;
            _index++;

            while (!IsAtEnd && (char.IsLetterOrDigit(Current) || Current == '_'))
            {
                _index++;
            }

            identifier = _text[start.._index];
            return true;
        }

        private void SkipTrivia()
        {
            while (!IsAtEnd)
            {
                if (char.IsWhiteSpace(Current))
                {
                    _index++;
                    continue;
                }

                if (Current == '-' && Peek('-', 1))
                {
                    _index += 2;

                    while (!IsAtEnd && Current != '\n')
                    {
                        _index++;
                    }

                    continue;
                }

                break;
            }
        }

        private bool TryRead(char expected)
        {
            if (!IsAtEnd && Current == expected)
            {
                _index++;
                return true;
            }

            return false;
        }

        private bool Peek(char expected, int offset = 0) =>
            _index + offset < _text.Length && _text[_index + offset] == expected;

        private bool IsAtEnd => _index >= _text.Length;

        private char Current => _text[_index];

        private static string ConvertKeyToString(object? keyValue) =>
            keyValue switch
            {
                null => string.Empty,
                string text => text,
                long number => number.ToString(CultureInfo.InvariantCulture),
                double number => number.ToString(CultureInfo.InvariantCulture),
                bool boolean => boolean ? "true" : "false",
                _ => keyValue.ToString() ?? string.Empty
            };
    }
}

internal static class LuaScalarConversions
{
    public static double? ToDouble(object? value) =>
        value switch
        {
            double number => number,
            long number => number,
            int number => number,
            _ => null
        };

    public static long? ToInt64(object? value) =>
        value switch
        {
            long number => number,
            int number => number,
            double number when Math.Abs(number % 1) < double.Epsilon => (long)number,
            _ => null
        };
}
