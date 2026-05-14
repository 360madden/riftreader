sealed class DesktopDuplicationCaptureBackend : ICaptureBackend
{
    public string Name => "dxgi-desktop";

    public Task<QualityReport> CaptureAsync(
        D3DObjects d3d,
        WindowMatch window,
        Options options,
        string output,
        RunArtifacts? artifacts)
    {
        IntPtr monitor = NativeMethods.MonitorFromWindow(window.Hwnd, NativeMethods.MONITOR_DEFAULTTONEAREST);
        QualityReport quality = DesktopDuplicationCapture.CaptureNearestMonitor(
            d3d,
            monitor,
            output,
            options.TimeoutMs,
            options.CaptureAttempts,
            options.ShouldEmitPng);

        return Task.FromResult(quality);
    }
}
