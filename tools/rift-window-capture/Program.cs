using System.Diagnostics;
using System.Drawing;
using System.Drawing.Imaging;
using System.Runtime.InteropServices;
using System.Text;
using System.Text.Json;
using System.Text.Json.Serialization;
using SharpGen.Runtime;
using Vortice.Direct3D;
using Vortice.Direct3D11;
using Vortice.DXGI;
using WinRT;
using Windows.Graphics;
using Windows.Graphics.Capture;
using Windows.Graphics.DirectX;
using WgiD3D = Windows.Graphics.DirectX.Direct3D11;

Options options;
try
{
    options = Options.Parse(args);
}
catch (Exception ex)
{
    Console.Error.WriteLine(ex.Message);
    Console.Error.WriteLine(Options.Usage);
    Environment.Exit(64);
    return;
}

CaptureReport report;
try
{
    report = await CaptureOnceAsync(options);
}
catch (Exception ex)
{
    report = CaptureReport.Error(options, ex.ToString(), ex.GetType().Name);
}

if (options.Json)
{
    Console.WriteLine(JsonSerializer.Serialize(report, CaptureJsonContext.Default.CaptureReport));
}
else
{
    Console.WriteLine(report.Ok
        ? $"Captured {report.Width}x{report.Height} to {report.Output} (usable={report.Usable}, blackRatio={report.BlackPixelRatio:P1}, stdDev={report.LumaStdDev:F2})"
        : $"Capture failed: {report.Message}");
}

Environment.Exit(report.Ok && (!options.RequireUsable || report.Usable) ? 0 : report.Ok ? 2 : 1);

static async Task<CaptureReport> CaptureOnceAsync(Options options)
{
    if (!GraphicsCaptureSession.IsSupported())
    {
        return CaptureReport.Error(options, "Windows Graphics Capture is not supported on this OS/session.", null);
    }

    WindowMatch window = WindowFinder.Find(options);
    if (window.Hwnd == IntPtr.Zero)
    {
        return CaptureReport.Error(options, "No matching visible top-level window was found.", null);
    }

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

    string output = Path.GetFullPath(options.Output ?? Defaults.CreateDefaultOutputPath());
    Directory.CreateDirectory(Path.GetDirectoryName(output) ?? Environment.CurrentDirectory);

    using D3DObjects d3d = D3DObjects.Create();

    if (options.CaptureDesktopDuplication)
    {
        try
        {
            IntPtr monitor = NativeMethods.MonitorFromWindow(window.Hwnd, NativeMethods.MONITOR_DEFAULTTONEAREST);
            QualityReport quality = DesktopDuplicationCapture.CaptureNearestMonitor(d3d, monitor, output, options.TimeoutMs, options.CaptureAttempts);
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
            QualityReport quality = TextureSaver.SaveFrameToImage(d3d, frame.Surface, output);
            return CaptureReport.Success(options, window, quality.Output, quality);
        }
    }
}

sealed record Options(
    string? ProcessName,
    int? Pid,
    string? TitleContains,
    string? Output,
    bool Json,
    int TimeoutMs,
    bool CaptureMonitor,
    bool CaptureDesktopDuplication,
    int CaptureAttempts,
    bool RequireUsable)
{
    public static string Usage => "Usage: RiftWindowCapture --process-name rift_x64 | --pid <pid> | --title-contains <text> [--output <image>] [--json] [--timeout-ms <n>] [--capture-monitor | --desktop-duplication] [--attempts <n>] [--require-usable]";

    public string CaptureMethod => CaptureDesktopDuplication
        ? "DXGIDesktopDuplication"
        : CaptureMonitor
            ? "WindowsGraphicsCaptureMonitor"
            : "WindowsGraphicsCaptureWindow";

    public static Options Parse(string[] args)
    {
        string? processName = null;
        int? pid = null;
        string? titleContains = null;
        string? output = null;
        bool json = false;
        int timeoutMs = Defaults.TimeoutMs;
        bool captureMonitor = false;
        bool captureDesktopDuplication = false;
        int captureAttempts = 1;
        bool requireUsable = false;

        for (int i = 0; i < args.Length; i++)
        {
            string arg = args[i];
            switch (arg)
            {
                case "--process-name":
                    processName = RequireValue(args, ref i, arg);
                    break;
                case "--pid":
                    if (!int.TryParse(RequireValue(args, ref i, arg), out int parsedPid) || parsedPid <= 0)
                    {
                        throw new ArgumentException("--pid must be a positive integer.");
                    }
                    pid = parsedPid;
                    break;
                case "--title-contains":
                    titleContains = RequireValue(args, ref i, arg);
                    break;
                case "--output":
                    output = RequireValue(args, ref i, arg);
                    break;
                case "--json":
                    json = true;
                    break;
                case "--capture-monitor":
                    captureMonitor = true;
                    break;
                case "--desktop-duplication":
                    captureDesktopDuplication = true;
                    break;
                case "--timeout-ms":
                    if (!int.TryParse(RequireValue(args, ref i, arg), out timeoutMs) || timeoutMs < 250)
                    {
                        throw new ArgumentException("--timeout-ms must be at least 250.");
                    }
                    break;
                case "--attempts":
                    if (!int.TryParse(RequireValue(args, ref i, arg), out captureAttempts) || captureAttempts < 1)
                    {
                        throw new ArgumentException("--attempts must be at least 1.");
                    }
                    break;
                case "--require-usable":
                    requireUsable = true;
                    break;
                case "--help":
                case "-h":
                case "/?":
                    throw new ArgumentException(Usage);
                default:
                    throw new ArgumentException($"Unknown argument: {arg}");
            }
        }

        if (processName is null && pid is null && titleContains is null)
        {
            processName = "rift_x64";
        }

        if (captureMonitor && captureDesktopDuplication)
        {
            throw new ArgumentException("--capture-monitor and --desktop-duplication are mutually exclusive.");
        }

        return new Options(processName, pid, titleContains, output, json, timeoutMs, captureMonitor, captureDesktopDuplication, captureAttempts, requireUsable);
    }

    private static string RequireValue(string[] args, ref int index, string name)
    {
        if (index + 1 >= args.Length || args[index + 1].StartsWith("--", StringComparison.Ordinal))
        {
            throw new ArgumentException($"{name} requires a value.");
        }

        index++;
        return args[index];
    }
}

sealed record WindowMatch(IntPtr Hwnd, int Pid, string ProcessName, string Title);

static class WindowFinder
{
    public static WindowMatch Find(Options options)
    {
        List<WindowMatch> matches = [];
        NativeMethods.EnumWindows((hwnd, _) =>
        {
            if (!NativeMethods.IsWindowVisible(hwnd) || NativeMethods.GetWindow(hwnd, NativeMethods.GW_OWNER) != IntPtr.Zero)
            {
                return true;
            }

            _ = NativeMethods.GetWindowThreadProcessId(hwnd, out int windowPid);
            if (windowPid <= 0)
            {
                return true;
            }

            string title = GetWindowText(hwnd);
            if (string.IsNullOrWhiteSpace(title))
            {
                return true;
            }

            string processName;
            try
            {
                processName = Process.GetProcessById(windowPid).ProcessName;
            }
            catch
            {
                return true;
            }

            if (options.Pid is { } pid && windowPid != pid)
            {
                return true;
            }

            if (options.ProcessName is { Length: > 0 } expectedProcess)
            {
                string normalizedExpected = Path.GetFileNameWithoutExtension(expectedProcess);
                if (!string.Equals(processName, normalizedExpected, StringComparison.OrdinalIgnoreCase))
                {
                    return true;
                }
            }

            if (options.TitleContains is { Length: > 0 } titleContains &&
                title.IndexOf(titleContains, StringComparison.OrdinalIgnoreCase) < 0)
            {
                return true;
            }

            matches.Add(new WindowMatch(hwnd, windowPid, processName, title));
            return true;
        }, IntPtr.Zero);

        return matches.OrderByDescending(m => NativeMethods.GetForegroundWindow() == m.Hwnd).FirstOrDefault()
            ?? new WindowMatch(IntPtr.Zero, 0, string.Empty, string.Empty);
    }

    private static string GetWindowText(IntPtr hwnd)
    {
        int length = NativeMethods.GetWindowTextLength(hwnd);
        if (length <= 0)
        {
            return string.Empty;
        }

        StringBuilder buffer = new(length + 1);
        _ = NativeMethods.GetWindowText(hwnd, buffer, buffer.Capacity);
        return buffer.ToString();
    }
}

sealed class D3DObjects : IDisposable
{
    public required ID3D11Device Device { get; init; }
    public required ID3D11DeviceContext Context { get; init; }

    public static D3DObjects Create()
    {
        FeatureLevel[] featureLevels =
        [
            FeatureLevel.Level_12_1,
            FeatureLevel.Level_12_0,
            FeatureLevel.Level_11_1,
            FeatureLevel.Level_11_0,
        ];

                SharpGen.Runtime.Result result = D3D11.D3D11CreateDevice(
            IntPtr.Zero,
            DriverType.Hardware,
            DeviceCreationFlags.BgraSupport,
            featureLevels,
            out ID3D11Device device,
            out _,
            out ID3D11DeviceContext context);

        if (result.Failure)
        {
            throw new InvalidOperationException($"D3D11CreateDevice failed: 0x{result.Code:X8}");
        }

        return new D3DObjects { Device = device, Context = context };
    }

    public void Dispose()
    {
        Context.Dispose();
        Device.Dispose();
    }
}

static class Defaults
{
    public const int TimeoutMs = 2_500;

    public static string CreateDefaultOutputPath()
    {
        string root = Path.Combine(Path.GetTempPath(), "RiftReader-window-capture", "wgc");
        return Path.Combine(root, $"capture-{DateTime.Now:yyyyMMdd-HHmmss-fff}.bmp");
    }
}

static class GraphicsCaptureItemFactory
{
    private static readonly Guid IID_IGraphicsCaptureItem = new("79C3F95B-31F7-4EC2-A464-632EF5D30760");
    private static readonly Guid IID_IGraphicsCaptureItemInterop = new("3628E81B-3CAC-4C60-B7F4-23CE0E0C3356");

    public static GraphicsCaptureItem CreateForWindow(IntPtr hwnd)
    {
        return Create(hwnd, captureMonitor: false);
    }

    public static GraphicsCaptureItem CreateForMonitor(IntPtr monitor)
    {
        return Create(monitor, captureMonitor: true);
    }

    private static GraphicsCaptureItem Create(IntPtr handle, bool captureMonitor)
    {
        IntPtr className = IntPtr.Zero;
        IntPtr factoryPtr = IntPtr.Zero;
        IntPtr itemPtr = IntPtr.Zero;
        try
        {
            Guid interopIid = IID_IGraphicsCaptureItemInterop;
            Guid itemIid = IID_IGraphicsCaptureItem;
            int hr = NativeMethods.WindowsCreateString("Windows.Graphics.Capture.GraphicsCaptureItem", 44, out className);
            ThrowIfFailed(hr, "WindowsCreateString(GraphicsCaptureItem)");

            hr = NativeMethods.RoGetActivationFactory(className, ref interopIid, out factoryPtr);
            ThrowIfFailed(hr, "RoGetActivationFactory(IGraphicsCaptureItemInterop)");

            IGraphicsCaptureItemInterop factory = (IGraphicsCaptureItemInterop)Marshal.GetObjectForIUnknown(factoryPtr);
            hr = captureMonitor
                ? factory.CreateForMonitor(handle, ref itemIid, out itemPtr)
                : factory.CreateForWindow(handle, ref itemIid, out itemPtr);
            ThrowIfFailed(hr, captureMonitor
                ? "IGraphicsCaptureItemInterop.CreateForMonitor"
                : "IGraphicsCaptureItemInterop.CreateForWindow");

            return MarshalInspectable<GraphicsCaptureItem>.FromAbi(itemPtr);
        }
        finally
        {
            if (itemPtr != IntPtr.Zero)
            {
                Marshal.Release(itemPtr);
            }
            if (factoryPtr != IntPtr.Zero)
            {
                Marshal.Release(factoryPtr);
            }
            if (className != IntPtr.Zero)
            {
                _ = NativeMethods.WindowsDeleteString(className);
            }
        }
    }

    private static void ThrowIfFailed(int hr, string api)
    {
        if (hr < 0)
        {
            Marshal.ThrowExceptionForHR(hr);
        }
    }
}

static class Direct3D11Helpers
{
    private static readonly Guid IID_ID3D11Texture2D = new("6f15aaf2-d208-4e89-9ab4-489535d34f9c");

    public static WgiD3D.IDirect3DDevice CreateDirect3DDevice(ID3D11Device d3dDevice)
    {
        using IDXGIDevice dxgiDevice = d3dDevice.QueryInterface<IDXGIDevice>();
        IntPtr dxgiDevicePtr = dxgiDevice.NativePointer;
        int hr = NativeMethods.CreateDirect3D11DeviceFromDXGIDevice(dxgiDevicePtr, out IntPtr inspectablePtr);
        if (hr < 0)
        {
            Marshal.ThrowExceptionForHR(hr);
        }

        try
        {
            return MarshalInterface<WgiD3D.IDirect3DDevice>.FromAbi(inspectablePtr);
        }
        finally
        {
            Marshal.Release(inspectablePtr);
        }
    }

    public static ID3D11Texture2D GetTexture2D(WgiD3D.IDirect3DSurface surface)
    {
        IObjectReference surfaceReference = MarshalInterface<WgiD3D.IDirect3DSurface>.CreateMarshaler(surface);
        IntPtr surfaceUnknown = MarshalInterface<WgiD3D.IDirect3DSurface>.GetAbi(surfaceReference);
        IntPtr accessPtr = IntPtr.Zero;
        IntPtr texturePtr = IntPtr.Zero;
        try
        {
            Guid textureIid = IID_ID3D11Texture2D;
            int hr = Marshal.QueryInterface(surfaceUnknown, typeof(IDirect3DDxgiInterfaceAccess).GUID, out accessPtr);
            if (hr < 0)
            {
                Marshal.ThrowExceptionForHR(hr);
            }

            IDirect3DDxgiInterfaceAccess access = (IDirect3DDxgiInterfaceAccess)Marshal.GetObjectForIUnknown(accessPtr);
            hr = access.GetInterface(ref textureIid, out texturePtr);
            if (hr < 0)
            {
                Marshal.ThrowExceptionForHR(hr);
            }

            ID3D11Texture2D texture = new(texturePtr);
            texturePtr = IntPtr.Zero;
            return texture;
        }
        finally
        {
            if (texturePtr != IntPtr.Zero)
            {
                Marshal.Release(texturePtr);
            }
            if (accessPtr != IntPtr.Zero)
            {
                Marshal.Release(accessPtr);
            }
            MarshalInterface<WgiD3D.IDirect3DSurface>.DisposeMarshaler(surfaceReference);
        }
    }
}

static class DesktopDuplicationCapture
{
    public static QualityReport CaptureNearestMonitor(D3DObjects d3d, IntPtr monitor, string output, int timeoutMs, int captureAttempts)
    {
        using IDXGIOutput1 output1 = FindOutputForMonitor(d3d.Device, monitor, out OutputDescription outputDescription);
        using IDXGIOutputDuplication duplication = output1.DuplicateOutput(d3d.Device);
        OutduplDescription duplicationDescription = duplication.Description;

        QualityReport? best = null;
        Exception? lastException = null;
        int completedAttempts = 0;

        for (int attempt = 1; attempt <= captureAttempts; attempt++)
        {
            bool frameAcquired = false;
            IDXGIResource? desktopResource = null;
            try
            {
                Result result = duplication.AcquireNextFrame((uint)timeoutMs, out OutduplFrameInfo frameInfo, out desktopResource);
                result.CheckError();
                frameAcquired = true;
                completedAttempts++;

                using ID3D11Texture2D desktopTexture = desktopResource.QueryInterface<ID3D11Texture2D>();
                string attemptOutput = captureAttempts == 1 ? output : TextureSaver.CreateAttemptOutputPath(output, attempt);
                QualityReport quality = TextureSaver.SaveTextureToImage(d3d, desktopTexture, attemptOutput) with
                {
                    CaptureAttemptCount = captureAttempts,
                    CompletedAttemptCount = completedAttempts,
                    SelectedAttempt = attempt,
                    DesktopDuplicationDeviceName = outputDescription.DeviceName,
                    DesktopDuplicationDesktopCoordinates = outputDescription.DesktopCoordinates.ToString(),
                    DesktopDuplicationRotation = outputDescription.Rotation.ToString(),
                    DesktopDuplicationModeDescription = duplicationDescription.ModeDescription.ToString(),
                    DesktopDuplicationModeFormat = duplicationDescription.ModeDescription.Format.ToString(),
                    DesktopDuplicationDesktopImageInSystemMemory = duplicationDescription.DesktopImageInSystemMemory,
                    DesktopDuplicationAccumulatedFrames = (int)frameInfo.AccumulatedFrames,
                    DesktopDuplicationProtectedContentMaskedOut = frameInfo.ProtectedContentMaskedOut,
                    DesktopDuplicationPointerVisible = frameInfo.PointerPosition.Visible,
                    DesktopDuplicationPointerPosition = frameInfo.PointerPosition.Position.ToString(),
                };

                if (best is null || IsBetter(quality, best))
                {
                    best = quality;
                }
            }
            catch (Exception ex) when (best is not null)
            {
                lastException = ex;
                break;
            }
            finally
            {
                desktopResource?.Dispose();
                if (frameAcquired)
                {
                    duplication.ReleaseFrame().CheckError();
                }
            }
        }

        if (best is null)
        {
            throw lastException ?? new InvalidOperationException("DXGI Desktop Duplication did not return a frame.");
        }

        string finalOutput = TextureSaver.NormalizeBmpOutputPath(output);
        if (!string.Equals(best.Output, finalOutput, StringComparison.OrdinalIgnoreCase))
        {
            Directory.CreateDirectory(Path.GetDirectoryName(finalOutput) ?? Environment.CurrentDirectory);
            File.Copy(best.Output, finalOutput, overwrite: true);
            best = best with { Output = finalOutput };
        }

        return best with
        {
            CompletedAttemptCount = completedAttempts,
            LastAttemptError = lastException?.Message,
        };
    }

    private static bool IsBetter(QualityReport candidate, QualityReport incumbent)
    {
        if (candidate.Usable != incumbent.Usable)
        {
            return candidate.Usable;
        }

        if (candidate.ContentBlackPixelRatio != incumbent.ContentBlackPixelRatio)
        {
            return candidate.ContentBlackPixelRatio < incumbent.ContentBlackPixelRatio;
        }

        return candidate.ContentLumaStdDev > incumbent.ContentLumaStdDev;
    }

    private static IDXGIOutput1 FindOutputForMonitor(ID3D11Device device, IntPtr monitor, out OutputDescription matchedDescription)
    {
        using IDXGIDevice dxgiDevice = device.QueryInterface<IDXGIDevice>();
        dxgiDevice.GetAdapter(out IDXGIAdapter adapter).CheckError();
        using (adapter)
        {
            for (uint i = 0; ; i++)
            {
                Result result = adapter.EnumOutputs(i, out IDXGIOutput output);
                if (result.Failure)
                {
                    break;
                }

                OutputDescription description = output.Description;
                if (description.Monitor == monitor)
                {
                    try
                    {
                        matchedDescription = description;
                        return output.QueryInterface<IDXGIOutput1>();
                    }
                    finally
                    {
                        output.Dispose();
                    }
                }

                output.Dispose();
            }
        }

        matchedDescription = default;
        throw new InvalidOperationException("No DXGI output matched the Rift window's nearest monitor.");
    }
}

static class TextureSaver
{
    public static QualityReport SaveFrameToImage(D3DObjects d3d, WgiD3D.IDirect3DSurface surface, string output)
    {
        using ID3D11Texture2D source = Direct3D11Helpers.GetTexture2D(surface);
        return SaveTextureToImage(d3d, source, output);
    }

    public static QualityReport SaveTextureToImage(D3DObjects d3d, ID3D11Texture2D source, string output)
    {
        Texture2DDescription sourceDescription = source.Description;
        int width = (int)sourceDescription.Width;
        int height = (int)sourceDescription.Height;

        Texture2DDescription stagingDescription = new(
            Format.B8G8R8A8_UNorm,
            (uint)width,
            (uint)height,
            1,
            1,
            BindFlags.None,
            ResourceUsage.Staging,
            CpuAccessFlags.Read,
            1,
            0,
            ResourceOptionFlags.None);

        using ID3D11Texture2D staging = d3d.Device.CreateTexture2D(stagingDescription);
        d3d.Context.CopyResource(staging, source);

        d3d.Context.Map(staging, 0, MapMode.Read, Vortice.Direct3D11.MapFlags.None, out MappedSubresource mapped).CheckError();
        try
        {
            return SaveMappedBgraBmp(mapped, width, height, output) with
            {
                SourceTextureFormat = sourceDescription.Format.ToString(),
                SourceTextureUsage = sourceDescription.Usage.ToString(),
                SourceTextureBindFlags = sourceDescription.BindFlags.ToString(),
                SourceTextureCpuAccessFlags = sourceDescription.CPUAccessFlags.ToString(),
                SourceTextureMiscFlags = sourceDescription.MiscFlags.ToString(),
            };
        }
        finally
        {
            d3d.Context.Unmap(staging, 0);
        }
    }

    private static QualityReport SaveMappedBgraBmp(MappedSubresource mapped, int width, int height, string output)
    {
        long pixelCount = (long)width * height;
        long blackPixels = 0;
        long transparentPixels = 0;
        double lumaSum = 0;
        double lumaSquaredSum = 0;
        const int contentTop = 40;
        long contentPixelCount = 0;
        long contentBlackPixels = 0;
        long contentTransparentPixels = 0;
        double contentLumaSum = 0;
        double contentLumaSquaredSum = 0;
        byte[] row = new byte[width * 4];
        byte[] image = new byte[checked(width * height * 4)];

        for (int y = 0; y < height; y++)
        {
            IntPtr sourceRow = IntPtr.Add(mapped.DataPointer, y * (int)mapped.RowPitch);
            Marshal.Copy(sourceRow, row, 0, row.Length);
            Buffer.BlockCopy(row, 0, image, y * row.Length, row.Length);

            for (int x = 0; x < row.Length; x += 4)
            {
                byte b = row[x];
                byte g = row[x + 1];
                byte r = row[x + 2];
                byte a = row[x + 3];
                if (a == 0)
                {
                    transparentPixels++;
                }

                if (r < 4 && g < 4 && b < 4)
                {
                    blackPixels++;
                }

                double luma = (0.2126 * r) + (0.7152 * g) + (0.0722 * b);
                lumaSum += luma;
                lumaSquaredSum += luma * luma;

                if (y >= contentTop)
                {
                    contentPixelCount++;
                    if (a == 0)
                    {
                        contentTransparentPixels++;
                    }

                    if (r < 4 && g < 4 && b < 4)
                    {
                        contentBlackPixels++;
                    }

                    contentLumaSum += luma;
                    contentLumaSquaredSum += luma * luma;
                }
            }
        }

        string actualOutput = NormalizeBmpOutputPath(output);
        WriteTopDownBgraBmp(actualOutput, width, height, image);

        double mean = pixelCount == 0 ? 0 : lumaSum / pixelCount;
        double variance = pixelCount == 0 ? 0 : Math.Max(0, (lumaSquaredSum / pixelCount) - (mean * mean));
        double stdDev = Math.Sqrt(variance);
        double blackRatio = pixelCount == 0 ? 1 : blackPixels / (double)pixelCount;
        double transparentRatio = pixelCount == 0 ? 1 : transparentPixels / (double)pixelCount;
        double contentMean = contentPixelCount == 0 ? 0 : contentLumaSum / contentPixelCount;
        double contentVariance = contentPixelCount == 0 ? 0 : Math.Max(0, (contentLumaSquaredSum / contentPixelCount) - (contentMean * contentMean));
        double contentStdDev = Math.Sqrt(contentVariance);
        double contentBlackRatio = contentPixelCount == 0 ? 1 : contentBlackPixels / (double)contentPixelCount;
        double contentTransparentRatio = contentPixelCount == 0 ? 1 : contentTransparentPixels / (double)contentPixelCount;
        bool usable = contentPixelCount > 0 && contentTransparentRatio < 0.95 && contentBlackRatio < 0.98 && contentStdDev >= 2.0;

        return new QualityReport(width, height, blackRatio, transparentRatio, stdDev, contentBlackRatio, contentTransparentRatio, contentStdDev, usable, actualOutput);
    }

    private static void WriteTopDownBgraBmp(string output, int width, int height, byte[] bgraPixels)
    {
        output = Path.GetFullPath(output);
        string parent = Path.GetDirectoryName(output) ?? Environment.CurrentDirectory;
        Directory.CreateDirectory(parent);

        int imageBytes = checked(width * height * 4);
        int fileBytes = checked(14 + 40 + imageBytes);

        using FileStream stream = new(output, FileMode.Create, FileAccess.Write, FileShare.Read);
        using BinaryWriter writer = new(stream, Encoding.UTF8, leaveOpen: false);
        writer.Write((byte)'B');
        writer.Write((byte)'M');
        writer.Write(fileBytes);
        writer.Write(0);
        writer.Write(14 + 40);
        writer.Write(40);
        writer.Write(width);
        writer.Write(-height);
        writer.Write((ushort)1);
        writer.Write((ushort)32);
        writer.Write(0);
        writer.Write(imageBytes);
        writer.Write(2835);
        writer.Write(2835);
        writer.Write(0);
        writer.Write(0);
        writer.Write(bgraPixels);
    }

    public static string NormalizeBmpOutputPath(string output)
    {
        return Path.ChangeExtension(Path.GetFullPath(output), ".bmp");
    }

    public static string CreateAttemptOutputPath(string output, int attempt)
    {
        string bmpOutput = NormalizeBmpOutputPath(output);
        string directory = Path.GetDirectoryName(bmpOutput) ?? Environment.CurrentDirectory;
        string fileName = Path.GetFileNameWithoutExtension(bmpOutput);
        return Path.Combine(directory, $"{fileName}.attempt{attempt}.bmp");
    }
}

sealed record QualityReport(
    int Width,
    int Height,
    double BlackPixelRatio,
    double TransparentPixelRatio,
    double LumaStdDev,
    double ContentBlackPixelRatio,
    double ContentTransparentPixelRatio,
    double ContentLumaStdDev,
    bool Usable,
    string Output)
{
    public string? SourceTextureFormat { get; init; }
    public string? SourceTextureUsage { get; init; }
    public string? SourceTextureBindFlags { get; init; }
    public string? SourceTextureCpuAccessFlags { get; init; }
    public string? SourceTextureMiscFlags { get; init; }
    public int? CaptureAttemptCount { get; init; }
    public int? CompletedAttemptCount { get; init; }
    public int? SelectedAttempt { get; init; }
    public string? LastAttemptError { get; init; }
    public string? DesktopDuplicationDeviceName { get; init; }
    public string? DesktopDuplicationDesktopCoordinates { get; init; }
    public string? DesktopDuplicationRotation { get; init; }
    public string? DesktopDuplicationModeDescription { get; init; }
    public string? DesktopDuplicationModeFormat { get; init; }
    public bool? DesktopDuplicationDesktopImageInSystemMemory { get; init; }
    public int? DesktopDuplicationAccumulatedFrames { get; init; }
    public bool? DesktopDuplicationProtectedContentMaskedOut { get; init; }
    public bool? DesktopDuplicationPointerVisible { get; init; }
    public string? DesktopDuplicationPointerPosition { get; init; }
}

sealed record CaptureReport(
    bool Ok,
    bool Usable,
    string CaptureMethod,
    string? Output,
    string? Message,
    string? ErrorType,
    string? ProcessName,
    int? Pid,
    string? TitleContains,
    string? WindowProcessName,
    int? WindowPid,
    string? WindowTitle,
    string? Hwnd,
    int Width,
    int Height,
    double BlackPixelRatio,
    double TransparentPixelRatio,
    double LumaStdDev,
    double ContentBlackPixelRatio,
    double ContentTransparentPixelRatio,
    double ContentLumaStdDev,
    QualityReport? Quality)
{
    public static CaptureReport Success(Options options, WindowMatch window, string output, QualityReport quality) => new(
        true,
        quality.Usable,
        options.CaptureMethod,
        output,
        quality.Usable ? "Captured a non-empty WGC frame." : "Captured a frame, but pixel statistics look black/flat/transparent.",
        null,
        options.ProcessName,
        options.Pid,
        options.TitleContains,
        window.ProcessName,
        window.Pid,
        window.Title,
        $"0x{window.Hwnd.ToInt64():X}",
        quality.Width,
        quality.Height,
        quality.BlackPixelRatio,
        quality.TransparentPixelRatio,
        quality.LumaStdDev,
        quality.ContentBlackPixelRatio,
        quality.ContentTransparentPixelRatio,
        quality.ContentLumaStdDev,
        quality);

    public static CaptureReport Error(Options options, string message, string? errorType, WindowMatch? window = null) => new(
        false,
        false,
        options.CaptureMethod,
        options.Output is null ? null : Path.GetFullPath(options.Output),
        message,
        errorType,
        options.ProcessName,
        options.Pid,
        options.TitleContains,
        window?.ProcessName,
        window?.Pid,
        window?.Title,
        window?.Hwnd == IntPtr.Zero || window is null ? null : $"0x{window.Hwnd.ToInt64():X}",
        0,
        0,
        1,
        1,
        0,
        1,
        1,
        0,
        null);
}

[JsonSerializable(typeof(QualityReport))]
[JsonSerializable(typeof(CaptureReport))]
[JsonSourceGenerationOptions(WriteIndented = true)]
partial class CaptureJsonContext : JsonSerializerContext;

[ComImport]
[Guid("3628E81B-3CAC-4C60-B7F4-23CE0E0C3356")]
[InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
interface IGraphicsCaptureItemInterop
{
    [PreserveSig]
    int CreateForWindow(IntPtr window, ref Guid iid, out IntPtr result);

    [PreserveSig]
    int CreateForMonitor(IntPtr monitor, ref Guid iid, out IntPtr result);
}

[ComImport]
[Guid("A9B3D012-3DF2-4EE3-B8D1-8695F457D3C1")]
[InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
interface IDirect3DDxgiInterfaceAccess
{
    [PreserveSig]
    int GetInterface(ref Guid iid, out IntPtr p);
}

[StructLayout(LayoutKind.Sequential)]
struct RECT
{
    public int Left;
    public int Top;
    public int Right;
    public int Bottom;
}

static partial class NativeMethods
{
    public const uint GW_OWNER = 4;
    public const uint MONITOR_DEFAULTTONEAREST = 2;

    public delegate bool EnumWindowsProc(IntPtr hwnd, IntPtr lParam);

    [LibraryImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    public static partial bool EnumWindows(EnumWindowsProc lpEnumFunc, IntPtr lParam);

    [LibraryImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    public static partial bool IsWindowVisible(IntPtr hWnd);

    [LibraryImport("user32.dll")]
    public static partial IntPtr GetWindow(IntPtr hWnd, uint uCmd);

    [LibraryImport("user32.dll")]
    public static partial IntPtr GetForegroundWindow();

    [LibraryImport("user32.dll")]
    public static partial IntPtr MonitorFromWindow(IntPtr hwnd, uint dwFlags);

    [LibraryImport("user32.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    public static partial bool GetClientRect(IntPtr hWnd, out RECT lpRect);

    [LibraryImport("user32.dll", SetLastError = true)]
    public static partial int GetWindowThreadProcessId(IntPtr hWnd, out int lpdwProcessId);

    [DllImport("user32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    public static extern int GetWindowText(IntPtr hWnd, StringBuilder lpString, int nMaxCount);

    [LibraryImport("user32.dll", EntryPoint = "GetWindowTextLengthW", SetLastError = true)]
    public static partial int GetWindowTextLength(IntPtr hWnd);

    [LibraryImport("combase.dll")]
    public static partial int WindowsCreateString([MarshalAs(UnmanagedType.LPWStr)] string sourceString, int length, out IntPtr hstring);

    [LibraryImport("combase.dll")]
    public static partial int WindowsDeleteString(IntPtr hstring);

    [LibraryImport("combase.dll")]
    public static partial int RoGetActivationFactory(IntPtr activatableClassId, ref Guid iid, out IntPtr factory);

    [LibraryImport("d3d11.dll")]
    public static partial int CreateDirect3D11DeviceFromDXGIDevice(IntPtr dxgiDevice, out IntPtr graphicsDevice);
}
