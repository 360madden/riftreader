using System.Runtime.InteropServices;

namespace RiftReader.Reader.Debugging;

internal static class DebugWindowsNativeMethods
{
    internal const uint ErrorSemTimeout = 121;
    internal const uint ExceptionBreakpoint = 0x80000003;
    internal const uint ExceptionSingleStep = 0x80000004;
    internal const uint DebugContinue = 0x00010002;
    internal const uint DebugExceptionNotHandled = 0x80010001;
    internal const uint ContextAmd64 = 0x00100000;
    internal const uint ContextControl = ContextAmd64 | 0x00000001;
    internal const uint ContextInteger = ContextAmd64 | 0x00000002;
    internal const uint ContextSegments = ContextAmd64 | 0x00000004;
    internal const uint ContextFloatingPoint = ContextAmd64 | 0x00000008;
    internal const uint ContextDebugRegisters = ContextAmd64 | 0x00000010;
    internal const uint ContextFull = ContextControl | ContextInteger | ContextFloatingPoint;
    internal const uint ContextAll = ContextControl | ContextInteger | ContextSegments | ContextFloatingPoint | ContextDebugRegisters;
    internal const uint Th32CsSnapThread = 0x00000004;
    internal const ushort ImageFileMachineUnknown = 0x0000;
    internal const ushort ImageFileMachineAmd64 = 0x8664;
    internal const int Infinite = -1;

    [Flags]
    internal enum ThreadAccessRights : uint
    {
        SuspendResume = 0x0002,
        GetContext = 0x0008,
        SetContext = 0x0010,
        QueryInformation = 0x0040
    }

    internal enum DebugEventType : uint
    {
        Exception = 1,
        CreateThread = 2,
        CreateProcess = 3,
        ExitThread = 4,
        ExitProcess = 5,
        LoadDll = 6,
        UnloadDll = 7,
        OutputDebugString = 8,
        Rip = 9
    }

    [DllImport("kernel32.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    internal static extern bool DebugActiveProcess(int dwProcessId);

    [DllImport("kernel32.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    internal static extern bool DebugActiveProcessStop(int dwProcessId);

    [DllImport("kernel32.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    internal static extern bool DebugSetProcessKillOnExit([MarshalAs(UnmanagedType.Bool)] bool killOnExit);

    [DllImport("kernel32.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    internal static extern bool WaitForDebugEvent(out DEBUG_EVENT lpDebugEvent, uint dwMilliseconds);

    [DllImport("kernel32.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    internal static extern bool ContinueDebugEvent(int dwProcessId, int dwThreadId, uint dwContinueStatus);

    [DllImport("kernel32.dll", SetLastError = true)]
    internal static extern nint OpenThread(ThreadAccessRights desiredAccess, [MarshalAs(UnmanagedType.Bool)] bool inheritHandle, int threadId);

    [DllImport("kernel32.dll", SetLastError = true)]
    internal static extern uint SuspendThread(nint hThread);

    [DllImport("kernel32.dll", SetLastError = true)]
    internal static extern uint ResumeThread(nint hThread);

    [DllImport("kernel32.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    internal static extern bool GetThreadContext(nint hThread, ref CONTEXT lpContext);

    [DllImport("kernel32.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    internal static extern bool SetThreadContext(nint hThread, [In] ref CONTEXT lpContext);

    [DllImport("kernel32.dll", SetLastError = true)]
    internal static extern nint CreateToolhelp32Snapshot(uint dwFlags, int th32ProcessID);

    [DllImport("kernel32.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    internal static extern bool Thread32First(nint hSnapshot, ref THREADENTRY32 lpte);

    [DllImport("kernel32.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    internal static extern bool Thread32Next(nint hSnapshot, ref THREADENTRY32 lpte);

    [DllImport("kernel32.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    internal static extern bool IsWow64Process(nint hProcess, [MarshalAs(UnmanagedType.Bool)] out bool wow64Process);

    [DllImport("kernel32.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    internal static extern bool IsWow64Process2(nint hProcess, out ushort processMachine, out ushort nativeMachine);

    [DllImport("kernel32.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    internal static extern bool CloseHandle(nint handle);

    [StructLayout(LayoutKind.Sequential)]
    internal struct THREADENTRY32
    {
        internal uint dwSize;
        internal uint cntUsage;
        internal uint th32ThreadID;
        internal uint th32OwnerProcessID;
        internal int tpBasePri;
        internal int tpDeltaPri;
        internal uint dwFlags;
    }

    [StructLayout(LayoutKind.Sequential)]
    internal struct DEBUG_EVENT
    {
        internal DebugEventType dwDebugEventCode;
        internal int dwProcessId;
        internal int dwThreadId;
        internal DEBUG_EVENT_UNION u;
    }

    [StructLayout(LayoutKind.Explicit)]
    internal struct DEBUG_EVENT_UNION
    {
        [FieldOffset(0)] internal EXCEPTION_DEBUG_INFO Exception;
        [FieldOffset(0)] internal CREATE_THREAD_DEBUG_INFO CreateThread;
        [FieldOffset(0)] internal CREATE_PROCESS_DEBUG_INFO CreateProcessInfo;
        [FieldOffset(0)] internal EXIT_THREAD_DEBUG_INFO ExitThread;
        [FieldOffset(0)] internal EXIT_PROCESS_DEBUG_INFO ExitProcess;
        [FieldOffset(0)] internal LOAD_DLL_DEBUG_INFO LoadDll;
        [FieldOffset(0)] internal UNLOAD_DLL_DEBUG_INFO UnloadDll;
        [FieldOffset(0)] internal OUTPUT_DEBUG_STRING_INFO DebugString;
        [FieldOffset(0)] internal RIP_INFO RipInfo;
    }

    [StructLayout(LayoutKind.Sequential)]
    internal struct EXCEPTION_DEBUG_INFO
    {
        internal EXCEPTION_RECORD ExceptionRecord;
        internal uint dwFirstChance;
    }

    [StructLayout(LayoutKind.Sequential)]
    internal struct EXCEPTION_RECORD
    {
        internal uint ExceptionCode;
        internal uint ExceptionFlags;
        internal nint ExceptionRecordPointer;
        internal nint ExceptionAddress;
        internal uint NumberParameters;
        internal nuint ExceptionInformation0;
        internal nuint ExceptionInformation1;
        internal nuint ExceptionInformation2;
        internal nuint ExceptionInformation3;
        internal nuint ExceptionInformation4;
        internal nuint ExceptionInformation5;
        internal nuint ExceptionInformation6;
        internal nuint ExceptionInformation7;
        internal nuint ExceptionInformation8;
        internal nuint ExceptionInformation9;
        internal nuint ExceptionInformation10;
        internal nuint ExceptionInformation11;
        internal nuint ExceptionInformation12;
        internal nuint ExceptionInformation13;
        internal nuint ExceptionInformation14;
    }

    [StructLayout(LayoutKind.Sequential)]
    internal struct CREATE_THREAD_DEBUG_INFO
    {
        internal nint hThread;
        internal nint lpThreadLocalBase;
        internal nint lpStartAddress;
    }

    [StructLayout(LayoutKind.Sequential)]
    internal struct CREATE_PROCESS_DEBUG_INFO
    {
        internal nint hFile;
        internal nint hProcess;
        internal nint hThread;
        internal nint lpBaseOfImage;
        internal uint dwDebugInfoFileOffset;
        internal uint nDebugInfoSize;
        internal nint lpThreadLocalBase;
        internal nint lpStartAddress;
        internal nint lpImageName;
        internal ushort fUnicode;
    }

    [StructLayout(LayoutKind.Sequential)]
    internal struct EXIT_THREAD_DEBUG_INFO
    {
        internal uint dwExitCode;
    }

    [StructLayout(LayoutKind.Sequential)]
    internal struct EXIT_PROCESS_DEBUG_INFO
    {
        internal uint dwExitCode;
    }

    [StructLayout(LayoutKind.Sequential)]
    internal struct LOAD_DLL_DEBUG_INFO
    {
        internal nint hFile;
        internal nint lpBaseOfDll;
        internal uint dwDebugInfoFileOffset;
        internal uint nDebugInfoSize;
        internal nint lpImageName;
        internal ushort fUnicode;
    }

    [StructLayout(LayoutKind.Sequential)]
    internal struct UNLOAD_DLL_DEBUG_INFO
    {
        internal nint lpBaseOfDll;
    }

    [StructLayout(LayoutKind.Sequential)]
    internal struct OUTPUT_DEBUG_STRING_INFO
    {
        internal nint lpDebugStringData;
        internal ushort fUnicode;
        internal ushort nDebugStringLength;
    }

    [StructLayout(LayoutKind.Sequential)]
    internal struct RIP_INFO
    {
        internal uint dwError;
        internal uint dwType;
    }

    [StructLayout(LayoutKind.Sequential)]
    internal struct M128A
    {
        internal ulong Low;
        internal long High;
    }

    [StructLayout(LayoutKind.Sequential)]
    internal struct XMM_SAVE_AREA32
    {
        internal ushort ControlWord;
        internal ushort StatusWord;
        internal byte TagWord;
        internal byte Reserved1;
        internal ushort ErrorOpcode;
        internal uint ErrorOffset;
        internal ushort ErrorSelector;
        internal ushort Reserved2;
        internal uint DataOffset;
        internal ushort DataSelector;
        internal ushort Reserved3;
        internal uint MxCsr;
        internal uint MxCsrMask;
        internal M128A FloatRegister0;
        internal M128A FloatRegister1;
        internal M128A FloatRegister2;
        internal M128A FloatRegister3;
        internal M128A FloatRegister4;
        internal M128A FloatRegister5;
        internal M128A FloatRegister6;
        internal M128A FloatRegister7;
        internal M128A XmmRegister0;
        internal M128A XmmRegister1;
        internal M128A XmmRegister2;
        internal M128A XmmRegister3;
        internal M128A XmmRegister4;
        internal M128A XmmRegister5;
        internal M128A XmmRegister6;
        internal M128A XmmRegister7;
        internal M128A XmmRegister8;
        internal M128A XmmRegister9;
        internal M128A XmmRegister10;
        internal M128A XmmRegister11;
        internal M128A XmmRegister12;
        internal M128A XmmRegister13;
        internal M128A XmmRegister14;
        internal M128A XmmRegister15;
        internal ulong Reserved40;
        internal ulong Reserved41;
        internal ulong Reserved42;
        internal ulong Reserved43;
        internal ulong Reserved44;
        internal ulong Reserved45;
        internal ulong Reserved46;
        internal ulong Reserved47;
        internal ulong Reserved48;
        internal ulong Reserved49;
        internal ulong Reserved410;
        internal ulong Reserved411;
    }

    [StructLayout(LayoutKind.Sequential)]
    internal struct CONTEXT
    {
        internal ulong P1Home;
        internal ulong P2Home;
        internal ulong P3Home;
        internal ulong P4Home;
        internal ulong P5Home;
        internal ulong P6Home;
        internal uint ContextFlags;
        internal uint MxCsr;
        internal ushort SegCs;
        internal ushort SegDs;
        internal ushort SegEs;
        internal ushort SegFs;
        internal ushort SegGs;
        internal ushort SegSs;
        internal uint EFlags;
        internal ulong Dr0;
        internal ulong Dr1;
        internal ulong Dr2;
        internal ulong Dr3;
        internal ulong Dr6;
        internal ulong Dr7;
        internal ulong Rax;
        internal ulong Rcx;
        internal ulong Rdx;
        internal ulong Rbx;
        internal ulong Rsp;
        internal ulong Rbp;
        internal ulong Rsi;
        internal ulong Rdi;
        internal ulong R8;
        internal ulong R9;
        internal ulong R10;
        internal ulong R11;
        internal ulong R12;
        internal ulong R13;
        internal ulong R14;
        internal ulong R15;
        internal ulong Rip;
        internal XMM_SAVE_AREA32 FltSave;
        internal M128A VectorRegister0;
        internal M128A VectorRegister1;
        internal M128A VectorRegister2;
        internal M128A VectorRegister3;
        internal M128A VectorRegister4;
        internal M128A VectorRegister5;
        internal M128A VectorRegister6;
        internal M128A VectorRegister7;
        internal M128A VectorRegister8;
        internal M128A VectorRegister9;
        internal M128A VectorRegister10;
        internal M128A VectorRegister11;
        internal M128A VectorRegister12;
        internal M128A VectorRegister13;
        internal M128A VectorRegister14;
        internal M128A VectorRegister15;
        internal M128A VectorRegister16;
        internal M128A VectorRegister17;
        internal M128A VectorRegister18;
        internal M128A VectorRegister19;
        internal M128A VectorRegister20;
        internal M128A VectorRegister21;
        internal M128A VectorRegister22;
        internal M128A VectorRegister23;
        internal M128A VectorRegister24;
        internal M128A VectorRegister25;
        internal ulong VectorControl;
        internal ulong DebugControl;
        internal ulong LastBranchToRip;
        internal ulong LastBranchFromRip;
        internal ulong LastExceptionToRip;
        internal ulong LastExceptionFromRip;

        internal static CONTEXT Create(uint contextFlags) =>
            new()
            {
                ContextFlags = contextFlags
            };
    }
}
