using System.ComponentModel;
using System.Diagnostics;

namespace RiftReader.Reader.Processes;

public sealed record ProcessTarget(
    int ProcessId,
    string ProcessName,
    string? ModuleName,
    string? MainWindowTitle)
{
    public static ProcessTarget FromProcess(Process process)
    {
        ArgumentNullException.ThrowIfNull(process);

        string? moduleName = null;
        string? mainWindowTitle = null;

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

        return new ProcessTarget(process.Id, process.ProcessName, moduleName, mainWindowTitle);
    }
}
