using System.ComponentModel;
using System.Diagnostics;

namespace RiftReader.Reader.Processes;

public static class ProcessModuleLocator
{
    public static IReadOnlyList<ProcessModuleInfo> ListModules(Process process)
    {
        ArgumentNullException.ThrowIfNull(process);

        try
        {
            return process.Modules
                .Cast<ProcessModule>()
                .OrderBy(static module => module.BaseAddress.ToInt64())
                .Select(ToModuleInfo)
                .ToArray();
        }
        catch (Win32Exception ex)
        {
            throw new InvalidOperationException($"Unable to enumerate process modules: {ex.Message}", ex);
        }
        catch (InvalidOperationException ex)
        {
            throw new InvalidOperationException($"Unable to enumerate process modules: {ex.Message}", ex);
        }
    }

    public static ProcessModule? FindModule(Process process, string? moduleName, out string? error)
    {
        ArgumentNullException.ThrowIfNull(process);

        error = null;

        try
        {
            var modules = process.Modules.Cast<ProcessModule>().ToArray();
            if (modules.Length == 0)
            {
                error = "The target process did not expose any modules.";
                return null;
            }

            if (string.IsNullOrWhiteSpace(moduleName))
            {
                return process.MainModule ?? modules[0];
            }

            var normalized = Path.GetFileName(moduleName.Trim());
            var matches = modules
                .Where(module =>
                    string.Equals(module.ModuleName, normalized, StringComparison.OrdinalIgnoreCase) ||
                    string.Equals(Path.GetFileName(module.FileName), normalized, StringComparison.OrdinalIgnoreCase))
                .ToArray();

            if (matches.Length == 0)
            {
                error = $"No module named '{normalized}' was found in process {process.ProcessName} ({process.Id}).";
                return null;
            }

            if (matches.Length > 1)
            {
                var names = string.Join(", ", matches.Select(static module => module.ModuleName));
                error = $"Module name '{normalized}' matched multiple modules: {names}.";
                return null;
            }

            return matches[0];
        }
        catch (Win32Exception ex)
        {
            error = $"Unable to enumerate process modules: {ex.Message}";
            return null;
        }
        catch (InvalidOperationException ex)
        {
            error = $"Unable to enumerate process modules: {ex.Message}";
            return null;
        }
    }

    private static ProcessModuleInfo ToModuleInfo(ProcessModule module)
    {
        var baseAddress = module.BaseAddress.ToInt64();
        return new ProcessModuleInfo(
            ModuleName: module.ModuleName,
            FileName: module.FileName,
            BaseAddressHex: $"0x{baseAddress:X}",
            BaseAddress: baseAddress,
            ModuleMemorySize: module.ModuleMemorySize);
    }
}
