sealed class WgcCaptureBackend : ICaptureBackend
{
    private readonly bool captureMonitor;

    public WgcCaptureBackend(bool captureMonitor)
    {
        this.captureMonitor = captureMonitor;
    }

    public string Name => captureMonitor ? "wgc-monitor" : "wgc-window";

    public async Task<QualityReport> CaptureAsync(
        D3DObjects d3d,
        WindowMatch window,
        Options options,
        string output,
        RunArtifacts? artifacts)
    {
        WgiD3D.IDirect3DDevice winrtDevice = Direct3D11Helpers.CreateDirect3DDevice(d3d.Device);
        GraphicsCaptureItem item = captureMonitor
            ? GraphicsCaptureItemFactory.CreateForMonitor(NativeMethods.MonitorFromWindow(window.Hwnd, NativeMethods.MONITOR_DEFAULTTONEAREST))
            : GraphicsCaptureItemFactory.CreateForWindow(window.Hwnd);

        SizeInt32 size = item.Size;
        if (size.Width <= 0 || size.Height <= 0)
        {
            if (!NativeMethods.GetClientRect(window.Hwnd, out RECT clientRect))
            {
                throw new InvalidOperationException($"GetClientRect failed while sizing WGC frame pool: {Marshal.GetLastWin32Error()}");
            }

            size = new SizeInt32
            {
                Width = Math.Max(0, clientRect.Right - clientRect.Left),
                Height = Math.Max(0, clientRect.Bottom - clientRect.Top),
            };
        }

        if (size.Width <= 0 || size.Height <= 0)
        {
            throw new InvalidOperationException("Matched WGC item has an empty capture size.");
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
            catch (OperationCanceledException ex)
            {
                throw new TimeoutException($"Timed out waiting for a WGC frame after {options.TimeoutMs} ms.", ex);
            }

            using (frame)
            {
                return TextureSaver.SaveFrameToImage(d3d, frame.Surface, output, options.ShouldEmitPng);
            }
        }
    }
}
