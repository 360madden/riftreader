using System.ComponentModel;
using System.Diagnostics;
using System.Text.Json.Serialization;

namespace RiftReader.Reader.Processes;

public sealed record ProcessTarget(
    int ProcessId,
    string ProcessName,
    string? ModuleName,
    string? MainWindowTitle)
{
    [JsonIgnore]
    public string? MainWindowHandleHex { get; init; }

    public static ProcessTarget FromProcess(Process process)
    {
        ArgumentNullException.ThrowIfNull(process);

        string? moduleName = null;
        string? mainWindowTitle = null;
        string? mainWindowHandleHex = null;

        try
        {
            moduleName = process.MainModule?.ModuleName;
        }
        catch (Win32Exception)
        {
            moduleName = null;
        }
        catch (InvalidOperationException)
        {
            moduleName = null;
        }

        try
        {
            mainWindowTitle = string.IsNullOrWhiteSpace(process.MainWindowTitle)
                ? null
                : process.MainWindowTitle;
        }
        catch (InvalidOperationException)
        {
            mainWindowTitle = null;
        }

        try
        {
            var mainWindowHandle = process.MainWindowHandle;
            if (mainWindowHandle != IntPtr.Zero)
            {
                mainWindowHandleHex = $"0x{mainWindowHandle.ToInt64():X}";
            }
        }
        catch (InvalidOperationException)
        {
            mainWindowHandleHex = null;
        }

        return new ProcessTarget(process.Id, process.ProcessName, moduleName, mainWindowTitle)
        {
            MainWindowHandleHex = mainWindowHandleHex
        };
    }
}
