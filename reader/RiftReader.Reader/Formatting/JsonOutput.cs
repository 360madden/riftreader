using System.Text.Json;
using System.Text.Json.Serialization;

namespace RiftReader.Reader.Formatting;

public static class JsonOutput
{
    private static readonly JsonSerializerOptions Options = new()
    {
        WriteIndented = true,
        DefaultIgnoreCondition = JsonIgnoreCondition.WhenWritingNull
    };

    public static string Serialize<T>(T value) =>
        JsonSerializer.Serialize(value, Options);
}
