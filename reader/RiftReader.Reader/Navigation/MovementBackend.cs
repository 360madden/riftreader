using System.Diagnostics;
using System.Text;

namespace RiftReader.Reader.Navigation;

public interface IMovementBackend
{
    MovementCommandResult PressKey(string key, int holdMilliseconds);
}

public sealed record MovementCommandResult(
    bool IsSuccess,
    string? ErrorMessage);

public sealed class PowerShellMovementBackend(string scriptFile, string targetProcessName) : IMovementBackend
{
    private const int MinimumCommandTimeoutMilliseconds = 5000;

    public MovementCommandResult PressKey(string key, int holdMilliseconds)
    {
        if (string.IsNullOrWhiteSpace(key))
        {
            return new MovementCommandResult(false, "Movement key was blank.");
        }

        if (!File.Exists(scriptFile))
        {
            return new MovementCommandResult(false, $"Movement helper script was not found: '{scriptFile}'.");
        }

        using var process = new Process
        {
            StartInfo = BuildStartInfo(key.Trim(), holdMilliseconds)
        };

        try
        {
            process.Start();
        }
        catch (Exception ex)
        {
            return new MovementCommandResult(false, $"Unable to start PowerShell movement helper: {ex.Message}");
        }

        var timeoutMilliseconds = Math.Max(MinimumCommandTimeoutMilliseconds, holdMilliseconds + 4000);
        if (!process.WaitForExit(timeoutMilliseconds))
        {
            try
            {
                process.Kill(entireProcessTree: true);
            }
            catch
            {
                // Best effort only.
            }

            return new MovementCommandResult(false, $"Movement helper timed out after {timeoutMilliseconds} ms.");
        }

        var output = new StringBuilder();
        var standardOutput = process.StandardOutput.ReadToEnd().Trim();
        var standardError = process.StandardError.ReadToEnd().Trim();

        if (!string.IsNullOrWhiteSpace(standardOutput))
        {
            output.Append(standardOutput);
        }

        if (!string.IsNullOrWhiteSpace(standardError))
        {
            if (output.Length > 0)
            {
                output.Append(' ');
            }

            output.Append(standardError);
        }

        return process.ExitCode == 0
            ? new MovementCommandResult(true, null)
            : new MovementCommandResult(false, string.IsNullOrWhiteSpace(output.ToString()) ? $"Movement helper exited with code {process.ExitCode}." : output.ToString());
    }

    private ProcessStartInfo BuildStartInfo(string key, int holdMilliseconds)
    {
        var startInfo = new ProcessStartInfo
        {
            FileName = "pwsh",
            UseShellExecute = false,
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            CreateNoWindow = true
        };

        startInfo.ArgumentList.Add("-NoProfile");
        startInfo.ArgumentList.Add("-ExecutionPolicy");
        startInfo.ArgumentList.Add("Bypass");
        startInfo.ArgumentList.Add("-File");
        startInfo.ArgumentList.Add(scriptFile);
        startInfo.ArgumentList.Add("-Key");
        startInfo.ArgumentList.Add(key);
        startInfo.ArgumentList.Add("-HoldMilliseconds");
        startInfo.ArgumentList.Add(holdMilliseconds.ToString(System.Globalization.CultureInfo.InvariantCulture));
        startInfo.ArgumentList.Add("-TargetProcessName");
        startInfo.ArgumentList.Add(targetProcessName);
        startInfo.ArgumentList.Add("-SkipBackgroundFocus");

        return startInfo;
    }
}
