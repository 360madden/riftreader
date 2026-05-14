sealed record WindowMatch(IntPtr Hwnd, int Pid, string ProcessName, string Title, DateTimeOffset? ProcessStartUtc);

sealed record WindowLookupResult(WindowMatch? Match, string? Blocker);

static class WindowFinder
{
    public static WindowLookupResult Find(Options options)
    {
        if (options.Hwnd is { } exactHwnd)
        {
            return FindExactHwnd(options, exactHwnd);
        }

        List<WindowMatch> matches = [];
        NativeMethods.EnumWindows((hwnd, _) =>
        {
            if (!NativeMethods.IsWindowVisible(hwnd) || NativeMethods.GetWindow(hwnd, NativeMethods.GW_OWNER) != IntPtr.Zero)
            {
                return true;
            }

            _ = NativeMethods.GetWindowThreadProcessId(hwnd, out int windowPid);
            if (windowPid <= 0)
            {
                return true;
            }

            string title = GetWindowText(hwnd);
            if (string.IsNullOrWhiteSpace(title))
            {
                return true;
            }

            ProcessIdentity processIdentity;
            try
            {
                processIdentity = ProcessIdentity.FromPid(windowPid);
            }
            catch
            {
                return true;
            }

            if (options.Pid is { } pid && windowPid != pid)
            {
                return true;
            }

            if (options.ProcessName is { Length: > 0 } expectedProcess)
            {
                string normalizedExpected = Path.GetFileNameWithoutExtension(expectedProcess);
                if (!string.Equals(processIdentity.ProcessName, normalizedExpected, StringComparison.OrdinalIgnoreCase))
                {
                    return true;
                }
            }

            if (options.ExpectedProcessStartUtc is not null && !ProcessStartMatches(processIdentity.ProcessStartUtc, options.ExpectedProcessStartUtc.Value))
            {
                return true;
            }

            if (options.TitleContains is { Length: > 0 } titleContains &&
                title.IndexOf(titleContains, StringComparison.OrdinalIgnoreCase) < 0)
            {
                return true;
            }

            matches.Add(new WindowMatch(hwnd, windowPid, processIdentity.ProcessName, title, processIdentity.ProcessStartUtc));
            return true;
        }, IntPtr.Zero);

        WindowMatch? match = matches.OrderByDescending(m => NativeMethods.GetForegroundWindow() == m.Hwnd).FirstOrDefault();
        return match is null
            ? new WindowLookupResult(null, "No matching visible top-level window was found.")
            : new WindowLookupResult(match, null);
    }

    private static WindowLookupResult FindExactHwnd(Options options, IntPtr hwnd)
    {
        if (!NativeMethods.IsWindow(hwnd))
        {
            return new WindowLookupResult(null, $"Requested --hwnd {Options.FormatHwnd(hwnd)} is not a valid window handle.");
        }

        if (!NativeMethods.IsWindowVisible(hwnd))
        {
            return new WindowLookupResult(null, $"Requested --hwnd {Options.FormatHwnd(hwnd)} is not visible.");
        }

        if (NativeMethods.GetWindow(hwnd, NativeMethods.GW_OWNER) != IntPtr.Zero)
        {
            return new WindowLookupResult(null, $"Requested --hwnd {Options.FormatHwnd(hwnd)} is an owned window, not a top-level capture target.");
        }

        _ = NativeMethods.GetWindowThreadProcessId(hwnd, out int windowPid);
        if (windowPid <= 0)
        {
            return new WindowLookupResult(null, $"Requested --hwnd {Options.FormatHwnd(hwnd)} has no owning process.");
        }

        string title = GetWindowText(hwnd);
        ProcessIdentity processIdentity;
        try
        {
            processIdentity = ProcessIdentity.FromPid(windowPid);
        }
        catch (Exception ex)
        {
            return new WindowLookupResult(null, $"Requested --hwnd {Options.FormatHwnd(hwnd)} process lookup failed: {ex.Message}");
        }

        WindowMatch match = new(hwnd, windowPid, processIdentity.ProcessName, title, processIdentity.ProcessStartUtc);

        if (options.Pid is { } pid && windowPid != pid)
        {
            return new WindowLookupResult(match, $"Requested --hwnd {Options.FormatHwnd(hwnd)} belongs to PID {windowPid}, not expected PID {pid}.");
        }

        if (options.ProcessName is { Length: > 0 } expectedProcess)
        {
            string normalizedExpected = Path.GetFileNameWithoutExtension(expectedProcess);
            if (!string.Equals(processIdentity.ProcessName, normalizedExpected, StringComparison.OrdinalIgnoreCase))
            {
                return new WindowLookupResult(match, $"Requested --hwnd {Options.FormatHwnd(hwnd)} belongs to process {processIdentity.ProcessName}, not expected process {normalizedExpected}.");
            }
        }

        if (options.TitleContains is { Length: > 0 } titleContains &&
            title.IndexOf(titleContains, StringComparison.OrdinalIgnoreCase) < 0)
        {
            return new WindowLookupResult(match, $"Requested --hwnd {Options.FormatHwnd(hwnd)} title '{title}' does not contain expected text '{titleContains}'.");
        }

        if (options.ExpectedProcessStartUtc is not null && !ProcessStartMatches(processIdentity.ProcessStartUtc, options.ExpectedProcessStartUtc.Value))
        {
            string actual = processIdentity.ProcessStartUtc?.ToString("O") ?? "unavailable";
            return new WindowLookupResult(match, $"Requested --hwnd {Options.FormatHwnd(hwnd)} process start {actual} does not match expected {options.ExpectedProcessStartUtc.Value:O} within {Defaults.ProcessStartTolerance.TotalSeconds:N0}s.");
        }

        return new WindowLookupResult(match, null);
    }

    private static bool ProcessStartMatches(DateTimeOffset? actualUtc, DateTimeOffset expectedUtc)
    {
        if (actualUtc is null)
        {
            return false;
        }

        TimeSpan delta = (actualUtc.Value.ToUniversalTime() - expectedUtc.ToUniversalTime()).Duration();
        return delta <= Defaults.ProcessStartTolerance;
    }

    private static string GetWindowText(IntPtr hwnd)
    {
        int length = NativeMethods.GetWindowTextLength(hwnd);
        if (length <= 0)
        {
            return string.Empty;
        }

        StringBuilder buffer = new(length + 1);
        _ = NativeMethods.GetWindowText(hwnd, buffer, buffer.Capacity);
        return buffer.ToString();
    }
}

sealed record ProcessIdentity(string ProcessName, DateTimeOffset? ProcessStartUtc)
{
    public static ProcessIdentity FromPid(int pid)
    {
        using Process process = Process.GetProcessById(pid);
        DateTimeOffset? startUtc = null;
        try
        {
            startUtc = new DateTimeOffset(process.StartTime.ToUniversalTime(), TimeSpan.Zero);
        }
        catch
        {
            // Some system processes deny StartTime. Keep the process usable unless an expected start gate is requested.
        }

        return new ProcessIdentity(process.ProcessName, startUtc);
    }
}
