using System.Runtime.InteropServices;

namespace RiftReader.Reader.Memory;

internal static class NativeMethods
{
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
}
