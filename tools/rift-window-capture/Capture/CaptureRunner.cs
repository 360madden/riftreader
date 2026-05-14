static class CaptureRunner
{
    public static int GetExitCode(CaptureReport report, Options options)
    {
        if (report.Ok && (!options.RequireUsable || report.Usable))
        {
            return 0;
        }

        return report.KnownBlocker ? 2 : 1;
    }

    public static async Task<CaptureReport> CaptureOnceAsync(Options options, RunArtifacts? artifacts)
    {
        if (!options.CaptureDesktopDuplication && !GraphicsCaptureSession.IsSupported())
        {
            return CaptureReport.Error(options, "Windows Graphics Capture is not supported on this OS/session.", null);
        }

        artifacts?.Log("info", "target.resolve.start", new
        {
            options.Pid,
            hwnd = Options.FormatHwnd(options.Hwnd),
            options.ProcessName,
            options.TitleContains,
            expectedProcessStartUtc = options.ExpectedProcessStartUtc?.ToString("O"),
        });
        WindowLookupResult lookup = WindowFinder.Find(options);
        if (lookup.Blocker is not null)
        {
            artifacts?.Log("warning", "target.resolve.blocked", new { lookup.Blocker });
            return CaptureReport.Error(options, lookup.Blocker, null, lookup.Match);
        }

        WindowMatch window = lookup.Match ?? new WindowMatch(IntPtr.Zero, 0, string.Empty, string.Empty, null);
        if (window.Hwnd == IntPtr.Zero)
        {
            return CaptureReport.Error(options, "No matching visible top-level window was found.", null);
        }

        artifacts?.Log("info", "target.resolve.done", new
        {
            hwnd = Options.FormatHwnd(window.Hwnd),
            pid = window.Pid,
            processName = window.ProcessName,
            title = window.Title,
            processStartUtc = window.ProcessStartUtc?.ToString("O"),
        });

        if (!NativeMethods.GetClientRect(window.Hwnd, out RECT clientRect))
        {
            return CaptureReport.Error(options, $"GetClientRect failed: {Marshal.GetLastWin32Error()}", null, window);
        }

        int width = Math.Max(0, clientRect.Right - clientRect.Left);
        int height = Math.Max(0, clientRect.Bottom - clientRect.Top);
        if (width <= 0 || height <= 0)
        {
            return CaptureReport.Error(options, "Matched window has an empty client rectangle, likely minimized.", null, window);
        }

        string output = Path.GetFullPath(options.Output ?? artifacts?.ImagePath ?? Defaults.CreateDefaultOutputPath());
        Directory.CreateDirectory(Path.GetDirectoryName(output) ?? Environment.CurrentDirectory);

        ICaptureBackend backend = CaptureBackendFactory.Create(options);
        artifacts?.Log("info", "backend.selected", new { backend = backend.Name });

        try
        {
            using D3DObjects d3d = D3DObjects.Create();
            QualityReport quality = await backend.CaptureAsync(d3d, window, options, output, artifacts).ConfigureAwait(false);
            artifacts?.Log("info", "frame.acquired", new { backend = backend.Name, quality.Width, quality.Height, quality.Output, quality.Usable });
            return CaptureReport.Success(options, window, quality.Output, quality);
        }
        catch (Exception ex)
        {
            return CaptureReport.Error(options, $"{backend.Name} capture failed: {ex.Message}", ex.GetType().Name, window);
        }
    }
}
