using System.Diagnostics;
using System.Globalization;
using RiftReader.Reader.Models;

namespace RiftReader.Reader.Navigation;

internal static class NavigationProofCoordAnchorRefresher
{
    public static bool TryRefresh(string processName, int processId, out string? error)
    {
        error = null;

        if (string.IsNullOrWhiteSpace(processName))
        {
            error = "Navigation proof coord anchor refresh requires a target process name.";
            return false;
        }

        var cachedProofAnchor = ProofCoordAnchorCacheLoader.TryLoad(null, out _);
        if (cachedProofAnchor is not null &&
            !string.IsNullOrWhiteSpace(cachedProofAnchor.CoordRegionAddress) &&
            string.Equals(cachedProofAnchor.ProcessName, processName, StringComparison.OrdinalIgnoreCase) &&
            (!processId.Equals(default(int)) ? cachedProofAnchor.ProcessId == processId : true) &&
            cachedProofAnchor.Match?.CoordMatchesWithinTolerance == true)
        {
            return true;
        }

        var repoRoot = NavigationPathResolver.TryFindRepoRoot(Directory.GetCurrentDirectory()) ?? Directory.GetCurrentDirectory();
        var scriptFile = Path.Combine(repoRoot, "scripts", "resolve-proof-coord-anchor.ps1");
        if (!File.Exists(scriptFile))
        {
            error = $"Navigation proof coord anchor refresh script was not found: '{scriptFile}'.";
            return false;
        }

        using var process = new Process
        {
            StartInfo = new ProcessStartInfo
            {
                FileName = "pwsh",
                RedirectStandardOutput = true,
                RedirectStandardError = true,
                UseShellExecute = false,
                CreateNoWindow = true
            }
        };

        process.StartInfo.ArgumentList.Add("-NoProfile");
        process.StartInfo.ArgumentList.Add("-ExecutionPolicy");
        process.StartInfo.ArgumentList.Add("Bypass");
        process.StartInfo.ArgumentList.Add("-File");
        process.StartInfo.ArgumentList.Add(scriptFile);
        process.StartInfo.ArgumentList.Add("-ProcessName");
        process.StartInfo.ArgumentList.Add(processName);
        if (processId > 0)
        {
            process.StartInfo.ArgumentList.Add("-ProcessId");
            process.StartInfo.ArgumentList.Add(processId.ToString(CultureInfo.InvariantCulture));
        }

        process.StartInfo.ArgumentList.Add("-RefreshAttempts");
        process.StartInfo.ArgumentList.Add("0");
        process.StartInfo.ArgumentList.Add("-SkipRefresh");
        process.StartInfo.ArgumentList.Add("-Json");

        try
        {
            process.Start();
        }
        catch (Exception ex)
        {
            error = $"Unable to start navigation proof coord anchor refresh: {ex.Message}";
            return false;
        }

        var stdout = process.StandardOutput.ReadToEnd().Trim();
        var stderr = process.StandardError.ReadToEnd().Trim();
        process.WaitForExit();

        if (process.ExitCode == 0)
        {
            return true;
        }

        error = string.IsNullOrWhiteSpace(stderr)
            ? (string.IsNullOrWhiteSpace(stdout)
                ? $"Navigation proof coord anchor refresh exited with code {process.ExitCode}."
                : stdout)
            : stderr;
        return false;
    }
}
