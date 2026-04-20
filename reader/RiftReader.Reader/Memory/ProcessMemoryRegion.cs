namespace RiftReader.Reader.Memory;

public sealed record ProcessMemoryRegion(
    nint BaseAddress,
    long RegionSize,
    uint State,
    uint Protect,
    uint Type)
{
    public nint EndAddress => new(BaseAddress.ToInt64() + RegionSize);

    public bool IsCommitted => State == NativeMethods.MemCommit;

    public bool IsReadable =>
        (Protect & NativeMethods.PageGuard) == 0 &&
        (Protect & NativeMethods.PageNoAccess) == 0;

    public bool ContainsAddress(nint address)
    {
        var value = address.ToInt64();
        var start = BaseAddress.ToInt64();
        var endExclusive = start + RegionSize;
        return value >= start && value < endExclusive;
    }
}
