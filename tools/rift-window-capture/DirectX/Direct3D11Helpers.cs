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
