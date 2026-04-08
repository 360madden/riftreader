using System.Diagnostics;
using System.IO;

namespace RiftReader.Reader.Processes;

public sealed class ProcessLocator
{
    public Process? FindById(int processId, out string? error)
    {
        if (processId <= 0)
        {
            error = "Process id must be greater than zero.";
            return null;
        }

        try
        {
            error = null;
            return Process.GetProcessById(processId);
        }
        catch (ArgumentException)
        {
            error = $"No running process was found for PID {processId}.";
            return null;
        }
        catch (InvalidOperationException ex)
        {
            error = $"Unable to inspect PID {processId}: {ex.Message}";
            return null;
        }
    }

    public Process? FindByName(string processName, out string? error)
    {
        if (string.IsNullOrWhiteSpace(processName))
        {
            error = "Process name must not be empty.";
            return null;
        }

        var normalizedName = Path.GetFileNameWithoutExtension(processName.Trim());
        Process[] matches;

        try
        {
            matches = Process.GetProcessesByName(normalizedName);
        }
        catch (InvalidOperationException ex)
        {
            error = $"Unable to inspect processes named '{normalizedName}': {ex.Message}";
            return null;
        }

        if (matches.Length == 0)
        {
            error = $"No running process was found with the name '{normalizedName}'.";
            return null;
        }

        if (matches.Length > 1)
        {
            var matchingProcessIds = string.Join(", ", matches.Select(process => process.Id));

            foreach (var process in matches)
            {
                process.Dispose();
            }

            error = $"Process name '{normalizedName}' matched multiple running processes ({matchingProcessIds}). Use --pid instead.";
            return null;
        }

        error = null;
        return matches[0];
    }
}
