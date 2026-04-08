using System.Runtime.InteropServices;

namespace RiftReader.Reader.Memory;

internal static class NativeMethods
{
    internal const uint MemCommit = 0x1000;
    internal const uint PageNoAccess = 0x01;
    internal const uint PageGuard = 0x100;

    [Flags]
    internal enum ProcessAccessRights : uint
    {
        VirtualMemoryRead = 0x0010,
        QueryInformation = 0x0400,
        QueryLimitedInformation = 0x1000
    }

    [DllImport("kernel32.dll", SetLastError = true)]
    internal static extern nint OpenProcess(
        ProcessAccessRights desiredAccess,
        [MarshalAs(UnmanagedType.Bool)] bool inheritHandle,
        int processId);

    [DllImport("kernel32.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    internal static extern bool ReadProcessMemory(
        nint processHandle,
        nint baseAddress,
        [Out] byte[] buffer,
        nuint size,
        out nuint numberOfBytesRead);

    [DllImport("kernel32.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    internal static extern bool CloseHandle(nint handle);

    [StructLayout(LayoutKind.Sequential)]
    internal struct MemoryBasicInformation
    {
        internal nint BaseAddress;
        internal nint AllocationBase;
        internal uint AllocationProtect;
        internal ushort PartitionId;
        internal nuint RegionSize;
        internal uint State;
        internal uint Protect;
        internal uint Type;
    }

    [DllImport("kernel32.dll", SetLastError = true)]
    internal static extern nuint VirtualQueryEx(
        nint processHandle,
        nint address,
        out MemoryBasicInformation buffer,
        nuint length);
}
