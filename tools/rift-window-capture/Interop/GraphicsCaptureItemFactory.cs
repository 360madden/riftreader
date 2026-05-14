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
