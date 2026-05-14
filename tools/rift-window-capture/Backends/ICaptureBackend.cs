interface ICaptureBackend
{
    string Name { get; }

    Task<QualityReport> CaptureAsync(
        D3DObjects d3d,
        WindowMatch window,
        Options options,
        string output,
        string? rawOutput,
        string? cropImageRoot,
        string? cropRawRoot,
        RunArtifacts? artifacts);
}

static class CaptureBackendFactory
{
    public static ICaptureBackend Create(Options options)
    {
        if (options.CaptureDesktopDuplication)
        {
            return new DesktopDuplicationCaptureBackend();
        }

        return new WgcCaptureBackend(options.CaptureMonitor);
    }
}
