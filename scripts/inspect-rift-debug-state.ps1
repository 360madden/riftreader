[CmdletBinding()]
param(
    [string]$ProcessName = 'rift_x64',
    [switch]$SummaryOnly
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$typeDefinition = @'
using System;
using System.Runtime.InteropServices;

public static class RiftReaderDebugProbe
{
    [DllImport("kernel32.dll", SetLastError = true)]
    public static extern IntPtr OpenProcess(uint desiredAccess, bool inheritHandle, uint processId);

    [DllImport("kernel32.dll", SetLastError = true)]
    public static extern bool CheckRemoteDebuggerPresent(IntPtr processHandle, ref bool debuggerPresent);

    [DllImport("kernel32.dll", SetLastError = true)]
    public static extern bool CloseHandle(IntPtr handle);
}
'@

if (-not ([System.Management.Automation.PSTypeName]'RiftReaderDebugProbe').Type) {
    Add-Type -TypeDefinition $typeDefinition
}

$processQueryInformation = 0x0400
$targetExecutableName = if ($ProcessName.EndsWith('.exe', [System.StringComparison]::OrdinalIgnoreCase)) {
    $ProcessName
}
else {
    "$ProcessName.exe"
}

$allProcesses = @(Get-CimInstance Win32_Process)
$targets = @($allProcesses | Where-Object { $_.Name -ieq $targetExecutableName })

if ($targets.Count -eq 0) {
    if (-not $SummaryOnly) {
        Write-Host "[RiftDebug] No running process matched '$ProcessName'." -ForegroundColor Yellow
    }

    return
}

$results = foreach ($target in $targets) {
    $handle = [RiftReaderDebugProbe]::OpenProcess($processQueryInformation, $false, [uint32]$target.ProcessId)
    $openError = [Runtime.InteropServices.Marshal]::GetLastWin32Error()
    $debuggerPresent = $false
    $querySucceeded = $false
    $queryError = $null

    if ($handle -ne [IntPtr]::Zero) {
        $querySucceeded = [RiftReaderDebugProbe]::CheckRemoteDebuggerPresent($handle, [ref]$debuggerPresent)
        $queryError = [Runtime.InteropServices.Marshal]::GetLastWin32Error()
        [RiftReaderDebugProbe]::CloseHandle($handle) | Out-Null
    }

    $parent = $allProcesses | Where-Object { $_.ProcessId -eq $target.ParentProcessId } | Select-Object -First 1
    $children = @($allProcesses | Where-Object { $_.ParentProcessId -eq $target.ProcessId })
    $attachHelpers = @(
        $children | Where-Object {
            -not [string]::IsNullOrWhiteSpace($_.CommandLine) -and
            $_.CommandLine -match '(?i)(^|\s)-attach(\s|$)' -and
            $_.CommandLine -match ("(?i)(^|\s)-pid\s+{0}(\s|$)" -f [regex]::Escape([string]$target.ProcessId))
        }
    )

    [pscustomobject]@{
        ProcessName = $target.Name
        ProcessId = $target.ProcessId
        ParentProcess = if ($parent) { "{0} [{1}]" -f $parent.Name, $parent.ProcessId } else { '' }
        DebuggerPresent = $debuggerPresent
        QuerySucceeded = $querySucceeded
        OpenProcessError = $openError
        CheckRemoteDebuggerPresentError = $queryError
        AttachHelpers = if ($attachHelpers.Count -gt 0) {
            ($attachHelpers | ForEach-Object { "{0} [{1}]" -f $_.Name, $_.ProcessId }) -join ', '
        }
        else {
            ''
        }
        AttachHelperCommandLines = @($attachHelpers | ForEach-Object { $_.CommandLine })
    }
}

if ($SummaryOnly) {
    foreach ($result in $results) {
        if ($result.DebuggerPresent -and -not [string]::IsNullOrWhiteSpace($result.AttachHelpers)) {
            Write-Warning ("{0} [{1}] is already debugged by {2}. x64dbg attach is expected to fail until that debugger relationship changes." -f $result.ProcessName, $result.ProcessId, $result.AttachHelpers)
            continue
        }

        if ($result.DebuggerPresent) {
            Write-Warning ("{0} [{1}] is already marked as debugged. x64dbg attach may fail." -f $result.ProcessName, $result.ProcessId)
            continue
        }

        Write-Host ("[RiftDebug] {0} [{1}] is not currently marked as debugged." -f $result.ProcessName, $result.ProcessId) -ForegroundColor Green
    }

    return
}

Write-Host ''
Write-Host '# **✅ RESULT**' -ForegroundColor Green
Write-Host ''

$results |
    Select-Object ProcessName, ProcessId, ParentProcess, DebuggerPresent, AttachHelpers |
    Format-Table -AutoSize

Write-Host ''

foreach ($result in $results) {
    if ($result.DebuggerPresent -and -not [string]::IsNullOrWhiteSpace($result.AttachHelpers)) {
        Write-Warning ("{0} [{1}] is already debugged by {2}." -f $result.ProcessName, $result.ProcessId, $result.AttachHelpers)
        foreach ($commandLine in $result.AttachHelperCommandLines) {
            Write-Host ("[RiftDebug] Attach helper command line: {0}" -f $commandLine)
        }

        Write-Host "[RiftDebug] x64dbg is working correctly when it refuses a second attach in this state." -ForegroundColor Yellow
        continue
    }

    if ($result.DebuggerPresent) {
        Write-Warning ("{0} [{1}] is already marked as debugged, but no child attach helper was identified." -f $result.ProcessName, $result.ProcessId)
        continue
    }

    Write-Host ("[RiftDebug] {0} [{1}] is not currently marked as debugged." -f $result.ProcessName, $result.ProcessId) -ForegroundColor Green
}

