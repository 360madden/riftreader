sealed class DesktopDuplicationCaptureBackend : ICaptureBackend
{
    public string Name => "dxgi-desktop";

    public Task<QualityReport> CaptureAsync(
        D3DObjects d3d,
        WindowMatch window,
        Options options,
        string output,
        string? rawOutput,
        string? cropImageRoot,
        string? cropRawRoot,
        RunArtifacts? artifacts)
    {
        IntPtr monitor = NativeMethods.MonitorFromWindow(window.Hwnd, NativeMethods.MONITOR_DEFAULTTONEAREST);
        QualityReport quality = DesktopDuplicationCapture.CaptureNearestMonitor(
            d3d,
            monitor,
            output,
            rawOutput,
            cropImageRoot,
            cropRawRoot,
            options.CropProfiles,
            options.TimeoutMs,
            options.CaptureAttempts,
            options.ShouldEmitPng);

        return Task.FromResult(quality);
    }
}
