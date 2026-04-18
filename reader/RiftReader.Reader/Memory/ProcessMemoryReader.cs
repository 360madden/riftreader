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

    internal nint ProcessHandle => _processHandle;

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

    public bool TryReadBytes(nint address, int length, out byte[] bytes, out string? error)
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

        bytes = GC.AllocateUninitializedArray<byte>(length);

        if (!NativeMethods.ReadProcessMemory(_processHandle, address, bytes, (nuint)bytes.Length, out var bytesRead))
        {
            var win32Error = Marshal.GetLastWin32Error();
            bytes = Array.Empty<byte>();
            error = $"ReadProcessMemory failed for PID {_target.ProcessId} at 0x{address.ToInt64():X}: {FormatWin32Error(win32Error)}";
            return false;
        }

        if (bytesRead != (nuint)bytes.Length)
        {
            bytes = bytes[..(int)bytesRead];
            error = $"Partial read at 0x{address.ToInt64():X}. Requested {length} bytes, received {bytesRead}.";
            return false;
        }

        error = null;
        return true;
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

    private void ThrowIfDisposed()
    {
        ObjectDisposedException.ThrowIf(_disposed, this);
    }
}
