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
