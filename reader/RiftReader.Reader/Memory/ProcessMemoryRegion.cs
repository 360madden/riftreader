namespace RiftReader.Reader.Memory;

public sealed record ProcessMemoryRegion(
    nint BaseAddress,
    long RegionSize,
    uint State,
    uint Protect,
    uint Type)
{
    public bool IsCommitted => State == NativeMethods.MemCommit;

    public bool IsReadable =>
        (Protect & NativeMethods.PageGuard) == 0 &&
        (Protect & NativeMethods.PageNoAccess) == 0;
}
