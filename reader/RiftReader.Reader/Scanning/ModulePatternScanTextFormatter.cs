namespace RiftReader.Reader.Scanning;

public static class ModulePatternScanTextFormatter
{
    public static string Format(ModulePatternScanResult result)
    {
        var lines = new List<string>
        {
            $"Process:           {result.ProcessName} ({result.ProcessId})",
            $"Module:            {result.ModuleName}",
            $"Module file:       {result.ModuleFileName}",
            $"Module base:       {result.ModuleBaseAddress}",
            $"Module size:       {result.ModuleMemorySize}",
            $"Pattern:           {result.Pattern}",
            $"Found:             {result.Found}"
        };

        if (result.Found)
        {
            lines.Add($"Relative offset:   {result.RelativeOffsetHex ?? "n/a"}");
            lines.Add($"Address:           {result.Address ?? "n/a"}");
        }

        if (!string.IsNullOrWhiteSpace(result.ContextBytesHex))
        {
            lines.Add($"Context ({result.ContextBytes} bytes):");
            lines.Add(result.ContextBytesHex);
        }

        return string.Join(Environment.NewLine, lines);
    }
}
