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
        if (!GraphicsCaptureSession.IsSupported())
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

        using D3DObjects d3d = D3DObjects.Create();

        if (options.CaptureDesktopDuplication)
        {
            try
            {
                artifacts?.Log("info", "backend.selected", new { backend = "dxgi-desktop" });
                IntPtr monitor = NativeMethods.MonitorFromWindow(window.Hwnd, NativeMethods.MONITOR_DEFAULTTONEAREST);
                QualityReport quality = DesktopDuplicationCapture.CaptureNearestMonitor(
                    d3d,
                    monitor,
                    output,
                    options.TimeoutMs,
                    options.CaptureAttempts,
                    options.ShouldEmitPng);
                artifacts?.Log("info", "frame.acquired", new { quality.Width, quality.Height, quality.Output, quality.Usable });
                return CaptureReport.Success(options, window, quality.Output, quality);
            }
            catch (Exception ex)
            {
                return CaptureReport.Error(options, $"DXGI Desktop Duplication failed: {ex}", ex.GetType().Name, window);
            }
        }

        WgiD3D.IDirect3DDevice winrtDevice;
        try
        {
            winrtDevice = Direct3D11Helpers.CreateDirect3DDevice(d3d.Device);
        }
        catch (Exception ex)
        {
            return CaptureReport.Error(options, $"CreateDirect3DDevice failed: {ex.Message}", ex.GetType().Name, window);
        }

        GraphicsCaptureItem item;
        try
        {
            artifacts?.Log("info", "backend.selected", new { backend = options.CaptureMonitor ? "wgc-monitor" : "wgc-window" });
            item = options.CaptureMonitor
                ? GraphicsCaptureItemFactory.CreateForMonitor(NativeMethods.MonitorFromWindow(window.Hwnd, NativeMethods.MONITOR_DEFAULTTONEAREST))
                : GraphicsCaptureItemFactory.CreateForWindow(window.Hwnd);
        }
        catch (Exception ex)
        {
            string captureSource = options.CaptureMonitor ? "CreateForMonitor" : "CreateForWindow";
            return CaptureReport.Error(options, $"{captureSource} failed: {ex.Message}", ex.GetType().Name, window);
        }
        SizeInt32 size = item.Size;
        if (size.Width <= 0 || size.Height <= 0)
        {
            size = new SizeInt32 { Width = width, Height = height };
        }

        using Direct3D11CaptureFramePool framePool = Direct3D11CaptureFramePool.CreateFreeThreaded(
            winrtDevice,
            DirectXPixelFormat.B8G8R8A8UIntNormalized,
            1,
            size);

        using GraphicsCaptureSession session = framePool.CreateCaptureSession(item);
        TaskCompletionSource<Direct3D11CaptureFrame> tcs = new(TaskCreationOptions.RunContinuationsAsynchronously);
        framePool.FrameArrived += (_, _) =>
        {
            try
            {
                Direct3D11CaptureFrame? frame = framePool.TryGetNextFrame();
                if (frame is not null)
                {
                    tcs.TrySetResult(frame);
                }
            }
            catch (Exception ex)
            {
                tcs.TrySetException(ex);
            }
        };

        session.StartCapture();

        using CancellationTokenSource timeout = new(options.TimeoutMs);
        await using (timeout.Token.Register(() => tcs.TrySetCanceled(timeout.Token)))
        {
            Direct3D11CaptureFrame frame;
            try
            {
                frame = await tcs.Task.ConfigureAwait(false);
            }
            catch (OperationCanceledException)
            {
                return CaptureReport.Error(options, $"Timed out waiting for a WGC frame after {options.TimeoutMs} ms.", null, window);
            }

            using (frame)
            {
                QualityReport quality = TextureSaver.SaveFrameToImage(d3d, frame.Surface, output, options.ShouldEmitPng);
                artifacts?.Log("info", "frame.acquired", new { quality.Width, quality.Height, quality.Output, quality.Usable });
                return CaptureReport.Success(options, window, quality.Output, quality);
            }
        }
    }
}
