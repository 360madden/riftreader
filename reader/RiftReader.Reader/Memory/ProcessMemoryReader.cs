using System.ComponentModel;
using System.Runtime.InteropServices;
using RiftReader.Reader.Processes;

namespace RiftReader.Reader.Memory;

public sealed class ProcessMemoryReader : IDisposable
{
    private readonly ProcessTarget _target;
    private nint _processHandle;
    private bool _disposed;

    private ProcessMemoryReader(ProcessTarget target, nint processHandle)
    {
        _target = target;
        _processHandle = processHandle;
    }

    public static ProcessMemoryReader? TryOpen(ProcessTarget target, out string? error)
    {
        ArgumentNullException.ThrowIfNull(target);

        var accessRights =
            NativeMethods.ProcessAccessRights.VirtualMemoryRead |
            NativeMethods.ProcessAccessRights.QueryInformation |
            NativeMethods.ProcessAccessRights.QueryLimitedInformation;

        var processHandle = NativeMethods.OpenProcess(accessRights, inheritHandle: false, target.ProcessId);

        if (processHandle == 0)
        {
            var win32Error = Marshal.GetLastWin32Error();
            error = $"OpenProcess failed for PID {target.ProcessId} ({target.ProcessName}): {FormatWin32Error(win32Error)}";
            return null;
        }

        error = null;
        return new ProcessMemoryReader(target, processHandle);
    }

    public bool TryReadBytes(nint address, int length, out byte[] bytes, out string? error, bool allowPartial = false)
    {
        ThrowIfDisposed();

        if (address == 0)
        {
            bytes = Array.Empty<byte>();
            error = "Address must be non-zero.";
            return false;
        }

        if (length <= 0)
        {
            bytes = Array.Empty<byte>();
            error = "Length must be greater than zero.";
            return false;
        }

        var requestedAddress = address;
        var aggregateBuffer = GC.AllocateUninitializedArray<byte>(length);
        var totalBytesRead = 0;
        string? lastError = null;

        while (totalBytesRead < length)
        {
            if (!TryQueryRegion(address, out var region, out error))
            {
                bytes = Array.Empty<byte>();
                return false;
            }

            if (!region.IsCommitted || !region.IsReadable)
            {
                lastError = FormatUnreadableRegionError(address, region);
                break;
            }

            var regionBytesRemaining = (region.BaseAddress.ToInt64() + region.RegionSize) - address.ToInt64();
            if (regionBytesRemaining <= 0)
            {
                lastError = $"Address 0x{address.ToInt64():X} did not advance within region 0x{region.BaseAddress.ToInt64():X}.";
                break;
            }

            var bytesRequestedThisPass = (int)Math.Min(length - totalBytesRead, regionBytesRemaining);
            var chunk = GC.AllocateUninitializedArray<byte>(bytesRequestedThisPass);

            var readSucceeded = NativeMethods.ReadProcessMemory(_processHandle, address, chunk, (nuint)chunk.Length, out var bytesReadThisPass);
            var readCount = checked((int)bytesReadThisPass);

            if (readCount > 0)
            {
                Buffer.BlockCopy(chunk, 0, aggregateBuffer, totalBytesRead, readCount);
                totalBytesRead += readCount;
                address = new nint(address.ToInt64() + readCount);
            }

            if (!readSucceeded)
            {
                var win32Error = Marshal.GetLastWin32Error();
                lastError = totalBytesRead > 0
                    ? $"Partial read at 0x{requestedAddress.ToInt64():X}. Requested {length} bytes, received {totalBytesRead}. Last failure near 0x{address.ToInt64():X}: {FormatWin32Error(win32Error)}"
                    : $"ReadProcessMemory failed for PID {_target.ProcessId} at 0x{requestedAddress.ToInt64():X}: {FormatWin32Error(win32Error)}";
                break;
            }

            if (readCount != bytesRequestedThisPass)
            {
                lastError = $"Partial read at 0x{requestedAddress.ToInt64():X}. Requested {length} bytes, received {totalBytesRead}.";
                break;
            }
        }

        if (totalBytesRead == length)
        {
            bytes = aggregateBuffer;
            error = null;
            return true;
        }

        if (allowPartial && totalBytesRead > 0)
        {
            bytes = aggregateBuffer[..totalBytesRead];
            error = lastError;
            return true;
        }

        bytes = Array.Empty<byte>();
        error = lastError ?? $"ReadProcessMemory failed for PID {_target.ProcessId} at 0x{requestedAddress.ToInt64():X}.";
        return false;
    }

    public IEnumerable<ProcessMemoryRegion> EnumerateMemoryRegions()
    {
        ThrowIfDisposed();

        var queryLength = (nuint)Marshal.SizeOf<NativeMethods.MemoryBasicInformation>();
        nint address = 0;

        while (true)
        {
            var result = NativeMethods.VirtualQueryEx(_processHandle, address, out var info, queryLength);
            if (result == 0)
            {
                yield break;
            }

            var regionSize = checked((long)info.RegionSize);
            if (regionSize <= 0)
            {
                yield break;
            }

            yield return new ProcessMemoryRegion(
                BaseAddress: info.BaseAddress,
                RegionSize: regionSize,
                State: info.State,
                Protect: info.Protect,
                Type: info.Type);

            var nextAddressValue = info.BaseAddress.ToInt64() + regionSize;
            if (nextAddressValue <= address.ToInt64())
            {
                yield break;
            }

            address = new nint(nextAddressValue);
        }
    }

    public void Dispose()
    {
        Dispose(disposing: true);
        GC.SuppressFinalize(this);
    }

    ~ProcessMemoryReader()
    {
        Dispose(disposing: false);
    }

    private void Dispose(bool disposing)
    {
        if (_disposed)
        {
            return;
        }

        if (_processHandle != 0)
        {
            NativeMethods.CloseHandle(_processHandle);
            _processHandle = 0;
        }

        _disposed = true;
    }

    private static string FormatWin32Error(int errorCode) =>
        $"{new Win32Exception(errorCode).Message} (Win32: {errorCode})";

    private bool TryQueryRegion(nint address, out ProcessMemoryRegion region, out string? error)
    {
        var queryLength = (nuint)Marshal.SizeOf<NativeMethods.MemoryBasicInformation>();
        var result = NativeMethods.VirtualQueryEx(_processHandle, address, out var info, queryLength);
        if (result == 0)
        {
            var win32Error = Marshal.GetLastWin32Error();
            region = new ProcessMemoryRegion(0, 0, 0, 0, 0);
            error = $"VirtualQueryEx failed for PID {_target.ProcessId} at 0x{address.ToInt64():X}: {FormatWin32Error(win32Error)}";
            return false;
        }

        region = new ProcessMemoryRegion(
            BaseAddress: info.BaseAddress,
            RegionSize: checked((long)info.RegionSize),
            State: info.State,
            Protect: info.Protect,
            Type: info.Type);
        error = null;
        return true;
    }

    private string FormatUnreadableRegionError(nint address, ProcessMemoryRegion region)
    {
        var regionDescription = region.State switch
        {
            NativeMethods.MemCommit => "committed but not readable",
            NativeMethods.MemReserve => "reserved",
            NativeMethods.MemFree => "free",
            _ => $"state 0x{region.State:X}"
        };

        return $"Address 0x{address.ToInt64():X} is in a {regionDescription} region (base=0x{region.BaseAddress.ToInt64():X}, size=0x{region.RegionSize:X}, protect=0x{region.Protect:X}, type=0x{region.Type:X}). The cached address is likely stale.";
    }

    private void ThrowIfDisposed()
    {
        ObjectDisposedException.ThrowIf(_disposed, this);
    }
}
