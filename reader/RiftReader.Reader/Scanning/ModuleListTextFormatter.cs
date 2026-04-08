namespace RiftReader.Reader.Scanning;

public static class ModuleListTextFormatter
{
    public static string Format(ModuleListResult result)
    {
        var lines = new List<string>
        {
            $"Process: {result.ProcessName} ({result.ProcessId})",
            $"Modules: {result.ModuleCount}"
        };

        foreach (var module in result.Modules)
        {
            lines.Add($"  - {module.ModuleName}  {module.BaseAddressHex}  size {module.ModuleMemorySize}  {module.FileName}");
        }

        return string.Join(Environment.NewLine, lines);
    }
}
