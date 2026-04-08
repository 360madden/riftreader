[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("find", "inspect", "focus", "capture", "click", "send-key", "wait-for-change")]
    [string]$Operation,

    [string]$ProcessName,
    [string]$TitleContains,
    [string]$WindowHandle,
    [string]$OutputPath,
    [string]$BaselinePath,
    [int]$ClientX,
    [int]$ClientY,
    [string]$KeyChord,
    [int]$HoldMilliseconds = 80,
    [int]$ClickDelayMilliseconds = 50,
    [int]$ExpectedProcessId = 0,
    [string]$ExpectedProcessName,
    [string]$ExpectedTitleContains,
    [int]$TimeoutMilliseconds = 3000,
    [int]$PollIntervalMilliseconds = 150,
    [double]$ChangeThresholdPercent = 0.5,
    [int]$RegionX = -1,
    [int]$RegionY = -1,
    [int]$RegionWidth = -1,
    [int]$RegionHeight = -1
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

Add-Type -AssemblyName System.Drawing
Add-Type -AssemblyName System.Windows.Forms

Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;
using System.Text;

public static class RiftGameWindowNative
{
    [StructLayout(LayoutKind.Sequential)]
    public struct RECT
    {
        public int Left;
        public int Top;
        public int Right;
        public int Bottom;
    }

    [StructLayout(LayoutKind.Sequential)]
    public struct POINT
    {
        public int X;
        public int Y;
    }

    [StructLayout(LayoutKind.Sequential)]
    public struct INPUT
    {
        public uint type;
        public InputUnion U;
    }

    [StructLayout(LayoutKind.Explicit)]
    public struct InputUnion
    {
        [FieldOffset(0)]
        public MOUSEINPUT mi;

        [FieldOffset(0)]
        public KEYBDINPUT ki;
    }

    [StructLayout(LayoutKind.Sequential)]
    public struct MOUSEINPUT
    {
        public int dx;
        public int dy;
        public uint mouseData;
        public uint dwFlags;
        public uint time;
        public IntPtr dwExtraInfo;
    }

    [StructLayout(LayoutKind.Sequential)]
    public struct KEYBDINPUT
    {
        public ushort wVk;
        public ushort wScan;
        public uint dwFlags;
        public uint time;
        public IntPtr dwExtraInfo;
    }

    [DllImport("user32.dll", SetLastError = true)]
    public static extern bool IsWindow(IntPtr hWnd);

    [DllImport("user32.dll", SetLastError = true)]
    public static extern bool IsWindowVisible(IntPtr hWnd);

    [DllImport("user32.dll", SetLastError = true)]
    public static extern bool IsIconic(IntPtr hWnd);

    [DllImport("user32.dll", SetLastError = true)]
    public static extern IntPtr GetForegroundWindow();

    [DllImport("user32.dll", SetLastError = true)]
    public static extern bool SetForegroundWindow(IntPtr hWnd);

    [DllImport("user32.dll", SetLastError = true)]
    public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);

    [DllImport("user32.dll", SetLastError = true)]
    public static extern uint GetWindowThreadProcessId(IntPtr hWnd, out uint processId);

    [DllImport("user32.dll", SetLastError = true)]
    public static extern int GetWindowTextLength(IntPtr hWnd);

    [DllImport("user32.dll", SetLastError = true)]
    public static extern int GetWindowText(IntPtr hWnd, StringBuilder lpString, int nMaxCount);

    [DllImport("user32.dll", SetLastError = true)]
    public static extern bool GetWindowRect(IntPtr hWnd, out RECT lpRect);

    [DllImport("user32.dll", SetLastError = true)]
    public static extern bool GetClientRect(IntPtr hWnd, out RECT lpRect);

    [DllImport("user32.dll", SetLastError = true)]
    public static extern bool ClientToScreen(IntPtr hWnd, ref POINT lpPoint);

    [DllImport("user32.dll", SetLastError = true)]
    public static extern bool SetCursorPos(int X, int Y);

    [DllImport("user32.dll", SetLastError = true)]
    public static extern uint SendInput(uint nInputs, INPUT[] pInputs, int cbSize);

    [DllImport("user32.dll", SetLastError = true)]
    public static extern short VkKeyScan(char ch);
}
"@

$SW_RESTORE = 9
$INPUT_MOUSE = 0
$INPUT_KEYBOARD = 1
$MOUSEEVENTF_LEFTDOWN = 0x0002
$MOUSEEVENTF_LEFTUP = 0x0004
$KEYEVENTF_KEYUP = 0x0002
$MaxComparisonDimension = 160
$PixelDifferenceThreshold = 24

$modifierKeys = @{
    "SHIFT" = 0x10
    "CTRL" = 0x11
    "CONTROL" = 0x11
    "ALT" = 0x12
}

$namedKeys = @{
    "ENTER" = 0x0D
    "RETURN" = 0x0D
    "TAB" = 0x09
    "SPACE" = 0x20
    "ESC" = 0x1B
    "ESCAPE" = 0x1B
    "BACKSPACE" = 0x08
    "DELETE" = 0x2E
    "INSERT" = 0x2D
    "INS" = 0x2D
    "UP" = 0x26
    "DOWN" = 0x28
    "LEFT" = 0x25
    "RIGHT" = 0x27
    "HOME" = 0x24
    "END" = 0x23
    "PGUP" = 0x21
    "PRIOR" = 0x21
    "PAGEUP" = 0x21
    "PGDN" = 0x22
    "NEXT" = 0x22
    "PAGEDOWN" = 0x22
}

for ($i = 1; $i -le 12; $i++) {
    $namedKeys["F$i"] = 0x6F + $i
}

function Get-LastWin32ErrorMessage {
    $lastError = [Runtime.InteropServices.Marshal]::GetLastWin32Error()
    return "Win32 error $lastError."
}

function ConvertTo-IntPtr {
    param([string]$HandleText)

    if ([string]::IsNullOrWhiteSpace($HandleText)) {
        return [IntPtr]::Zero
    }

    if ($HandleText.StartsWith("0x", [System.StringComparison]::OrdinalIgnoreCase)) {
        $raw = [UInt64]::Parse($HandleText.Substring(2), [System.Globalization.NumberStyles]::AllowHexSpecifier, [System.Globalization.CultureInfo]::InvariantCulture)
        return [IntPtr]([Int64]$raw)
    }

    return [IntPtr]([Int64]::Parse($HandleText, [System.Globalization.CultureInfo]::InvariantCulture))
}

function Convert-RectToObject {
    param([RiftGameWindowNative+RECT]$Rect)

    return [pscustomobject]@{
        left = $Rect.Left
        top = $Rect.Top
        right = $Rect.Right
        bottom = $Rect.Bottom
        width = $Rect.Right - $Rect.Left
        height = $Rect.Bottom - $Rect.Top
    }
}

function Get-WindowTitle {
    param([IntPtr]$Handle)

    $length = [RiftGameWindowNative]::GetWindowTextLength($Handle)
    if ($length -le 0) {
        return ""
    }

    $builder = New-Object System.Text.StringBuilder ($length + 1)
    [void][RiftGameWindowNative]::GetWindowText($Handle, $builder, $builder.Capacity)
    return $builder.ToString()
}

function Get-ClientRectOnScreen {
    param([IntPtr]$Handle)

    $clientRect = New-Object RiftGameWindowNative+RECT
    if (-not [RiftGameWindowNative]::GetClientRect($Handle, [ref]$clientRect)) {
        throw "GetClientRect failed. $(Get-LastWin32ErrorMessage)"
    }

    $origin = New-Object RiftGameWindowNative+POINT
    $origin.X = 0
    $origin.Y = 0

    if (-not [RiftGameWindowNative]::ClientToScreen($Handle, [ref]$origin)) {
        throw "ClientToScreen failed. $(Get-LastWin32ErrorMessage)"
    }

    $screenRect = New-Object RiftGameWindowNative+RECT
    $screenRect.Left = $origin.X
    $screenRect.Top = $origin.Y
    $screenRect.Right = $origin.X + ($clientRect.Right - $clientRect.Left)
    $screenRect.Bottom = $origin.Y + ($clientRect.Bottom - $clientRect.Top)

    return (Convert-RectToObject -Rect $screenRect)
}

function Get-WindowSnapshot {
    param([IntPtr]$Handle)

    if ($Handle -eq [IntPtr]::Zero) {
        throw "A non-zero window handle is required."
    }

    if (-not [RiftGameWindowNative]::IsWindow($Handle)) {
        throw "Window handle $Handle is not valid."
    }

    $processId = 0
    [void][RiftGameWindowNative]::GetWindowThreadProcessId($Handle, [ref]$processId)
    if ($processId -eq 0) {
        throw "No process id was found for window handle $Handle."
    }

    $process = Get-Process -Id $processId -ErrorAction Stop

    $windowRect = New-Object RiftGameWindowNative+RECT
    if (-not [RiftGameWindowNative]::GetWindowRect($Handle, [ref]$windowRect)) {
        throw "GetWindowRect failed. $(Get-LastWin32ErrorMessage)"
    }

    $foregroundHandle = [RiftGameWindowNative]::GetForegroundWindow()

    return [pscustomobject]@{
        windowHandle = $Handle.ToInt64().ToString([System.Globalization.CultureInfo]::InvariantCulture)
        windowHandleHex = ("0x{0:X}" -f $Handle.ToInt64())
        processId = $process.Id
        processName = $process.ProcessName
        title = (Get-WindowTitle -Handle $Handle)
        isForeground = ($foregroundHandle -eq $Handle)
        isVisible = [RiftGameWindowNative]::IsWindowVisible($Handle)
        isMinimized = [RiftGameWindowNative]::IsIconic($Handle)
        windowRect = (Convert-RectToObject -Rect $windowRect)
        clientRect = (Get-ClientRectOnScreen -Handle $Handle)
    }
}

function Test-TitleContains {
    param(
        [string]$Title,
        [string]$ExpectedText
    )

    if ([string]::IsNullOrWhiteSpace($ExpectedText)) {
        return $true
    }

    return $Title.IndexOf($ExpectedText, [System.StringComparison]::OrdinalIgnoreCase) -ge 0
}

function Assert-WindowMatchesExpectations {
    param([psobject]$Window)

    if ($ExpectedProcessId -gt 0 -and $Window.processId -ne $ExpectedProcessId) {
        throw "Bound window process id changed. Expected $ExpectedProcessId, found $($Window.processId)."
    }

    if (-not [string]::IsNullOrWhiteSpace($ExpectedProcessName) -and $Window.processName -ne $ExpectedProcessName) {
        throw "Bound window process changed. Expected '$ExpectedProcessName', found '$($Window.processName)'."
    }

    if (-not (Test-TitleContains -Title $Window.title -ExpectedText $ExpectedTitleContains)) {
        throw "Bound window title mismatch. Expected title containing '$ExpectedTitleContains', found '$($Window.title)'."
    }
}

function Resolve-WindowSnapshot {
    if (-not [string]::IsNullOrWhiteSpace($WindowHandle)) {
        $snapshot = Get-WindowSnapshot -Handle (ConvertTo-IntPtr -HandleText $WindowHandle)
        Assert-WindowMatchesExpectations -Window $snapshot
        return $snapshot
    }

    if ([string]::IsNullOrWhiteSpace($ProcessName)) {
        throw "Either WindowHandle or ProcessName is required."
    }

    $candidates = Get-Process -Name $ProcessName -ErrorAction SilentlyContinue |
        Where-Object { $_.MainWindowHandle -ne 0 }

    if (-not [string]::IsNullOrWhiteSpace($TitleContains)) {
        $candidates = $candidates | Where-Object {
            $_.MainWindowTitle -and $_.MainWindowTitle.IndexOf($TitleContains, [System.StringComparison]::OrdinalIgnoreCase) -ge 0
        }
    }

    $candidate = $candidates | Select-Object -First 1
    if (-not $candidate) {
        if ([string]::IsNullOrWhiteSpace($TitleContains)) {
            throw "No windowed process named '$ProcessName' was found."
        }

        throw "No windowed process named '$ProcessName' with a title containing '$TitleContains' was found."
    }

    return Get-WindowSnapshot -Handle ([IntPtr]$candidate.MainWindowHandle)
}

function New-KeyboardInput {
    param(
        [int]$VirtualKey,
        [switch]$KeyUp
    )

    $input = New-Object RiftGameWindowNative+INPUT
    $input.type = $INPUT_KEYBOARD
    $input.U.ki.wVk = [uint16]$VirtualKey
    $input.U.ki.wScan = 0
    $input.U.ki.dwFlags = if ($KeyUp) { $KEYEVENTF_KEYUP } else { 0 }
    $input.U.ki.time = 0
    $input.U.ki.dwExtraInfo = [IntPtr]::Zero
    return $input
}

function New-MouseInput {
    param([uint32]$Flags)

    $input = New-Object RiftGameWindowNative+INPUT
    $input.type = $INPUT_MOUSE
    $input.U.mi.dx = 0
    $input.U.mi.dy = 0
    $input.U.mi.mouseData = 0
    $input.U.mi.dwFlags = $Flags
    $input.U.mi.time = 0
    $input.U.mi.dwExtraInfo = [IntPtr]::Zero
    return $input
}

function Invoke-SendInput {
    param([RiftGameWindowNative+INPUT[]]$Inputs)

    $size = [Runtime.InteropServices.Marshal]::SizeOf([type][RiftGameWindowNative+INPUT])
    $sent = [RiftGameWindowNative]::SendInput([uint32]$Inputs.Length, $Inputs, $size)
    if ($sent -ne $Inputs.Length) {
        throw "SendInput failed. $(Get-LastWin32ErrorMessage)"
    }
}

function Convert-ClientPointToScreenPoint {
    param(
        [IntPtr]$Handle,
        [int]$X,
        [int]$Y
    )

    $point = New-Object RiftGameWindowNative+POINT
    $point.X = $X
    $point.Y = $Y

    if (-not [RiftGameWindowNative]::ClientToScreen($Handle, [ref]$point)) {
        throw "ClientToScreen failed. $(Get-LastWin32ErrorMessage)"
    }

    return [pscustomobject]@{
        x = $point.X
        y = $point.Y
    }
}

function Resolve-KeyPlan {
    param([string]$Chord)

    if ([string]::IsNullOrWhiteSpace($Chord)) {
        throw "A key chord is required."
    }

    $tokens = $Chord.Split('+', [System.StringSplitOptions]::RemoveEmptyEntries) |
        ForEach-Object { $_.Trim() } |
        Where-Object { $_ }

    if (-not $tokens -or $tokens.Count -eq 0) {
        throw "A key chord is required."
    }

    $explicitModifiers = New-Object System.Collections.Generic.List[int]
    $mainKeys = New-Object System.Collections.Generic.List[object]

    foreach ($token in $tokens) {
        $upperToken = $token.ToUpperInvariant()

        if ($modifierKeys.ContainsKey($upperToken)) {
            if (-not $explicitModifiers.Contains($modifierKeys[$upperToken])) {
                $explicitModifiers.Add($modifierKeys[$upperToken])
            }

            continue
        }

        if ($namedKeys.ContainsKey($upperToken)) {
            $mainKeys.Add([pscustomobject]@{
                    virtualKey = $namedKeys[$upperToken]
                    impliedModifiers = @()
                })
            continue
        }

        if ($token.Length -eq 1) {
            $character = if ($token -cmatch '^[A-Za-z]$') { [char]::ToLowerInvariant($token[0]) } else { $token[0] }
            $vkScan = [RiftGameWindowNative]::VkKeyScan($character)
            if ($vkScan -eq -1) {
                throw "No virtual-key mapping was found for '$token'."
            }

            $virtualKey = $vkScan -band 0xFF
            $shiftState = ($vkScan -shr 8) -band 0xFF
            $impliedModifiers = New-Object System.Collections.Generic.List[int]

            if (($shiftState -band 1) -ne 0) {
                $impliedModifiers.Add(0x10)
            }
            if (($shiftState -band 2) -ne 0) {
                $impliedModifiers.Add(0x11)
            }
            if (($shiftState -band 4) -ne 0) {
                $impliedModifiers.Add(0x12)
            }

            $mainKeys.Add([pscustomobject]@{
                    virtualKey = $virtualKey
                    impliedModifiers = @($impliedModifiers.ToArray())
                })
            continue
        }

        throw "Unsupported key token '$token'."
    }

    if ($mainKeys.Count -eq 0) {
        throw "At least one non-modifier key is required."
    }

    $allModifiers = New-Object System.Collections.Generic.List[int]
    foreach ($modifier in $explicitModifiers) {
        if (-not $allModifiers.Contains($modifier)) {
            $allModifiers.Add($modifier)
        }
    }

    foreach ($mainKey in $mainKeys) {
        foreach ($modifier in $mainKey.impliedModifiers) {
            if (-not $allModifiers.Contains($modifier)) {
                $allModifiers.Add($modifier)
            }
        }
    }

    return [pscustomobject]@{
        modifiers = @($allModifiers.ToArray())
        keys = @($mainKeys.ToArray())
    }
}

function Send-KeyPlan {
    param(
        [psobject]$Plan,
        [int]$HoldMilliseconds
    )

    foreach ($modifier in $Plan.modifiers) {
        Invoke-SendInput -Inputs @((New-KeyboardInput -VirtualKey $modifier))
        Start-Sleep -Milliseconds 10
    }

    foreach ($key in $Plan.keys) {
        Invoke-SendInput -Inputs @((New-KeyboardInput -VirtualKey $key.virtualKey))
    }

    Start-Sleep -Milliseconds $HoldMilliseconds

    for ($i = $Plan.keys.Count - 1; $i -ge 0; $i--) {
        Invoke-SendInput -Inputs @((New-KeyboardInput -VirtualKey $Plan.keys[$i].virtualKey -KeyUp))
        Start-Sleep -Milliseconds 10
    }

    for ($i = $Plan.modifiers.Count - 1; $i -ge 0; $i--) {
        Invoke-SendInput -Inputs @((New-KeyboardInput -VirtualKey $Plan.modifiers[$i] -KeyUp))
        Start-Sleep -Milliseconds 10
    }
}

function Get-RegionRectangle {
    param(
        [int]$ImageWidth,
        [int]$ImageHeight
    )

    $hasExplicitRegion = $RegionX -ge 0 -or $RegionY -ge 0 -or $RegionWidth -gt 0 -or $RegionHeight -gt 0
    if (-not $hasExplicitRegion) {
        return [System.Drawing.Rectangle]::new(0, 0, $ImageWidth, $ImageHeight)
    }

    if ($RegionX -lt 0 -or $RegionY -lt 0 -or $RegionWidth -le 0 -or $RegionHeight -le 0) {
        throw "RegionX, RegionY, RegionWidth, and RegionHeight must all be provided together and be positive."
    }

    if ($RegionX + $RegionWidth -gt $ImageWidth -or $RegionY + $RegionHeight -gt $ImageHeight) {
        throw "Requested comparison region lies outside the captured client image."
    }

    return [System.Drawing.Rectangle]::new($RegionX, $RegionY, $RegionWidth, $RegionHeight)
}

function Convert-RectangleToRegionObject {
    param([System.Drawing.Rectangle]$Rectangle)

    return [pscustomobject]@{
        x = $Rectangle.X
        y = $Rectangle.Y
        width = $Rectangle.Width
        height = $Rectangle.Height
    }
}

function New-WindowClientBitmap {
    param([psobject]$Window)

    if ($Window.isMinimized) {
        throw "Cannot capture a minimized window. Focus or restore it first."
    }

    $rect = $Window.clientRect
    if ($rect.width -le 0 -or $rect.height -le 0) {
        throw "Window client area has invalid dimensions."
    }

    $bitmap = New-Object System.Drawing.Bitmap $rect.width, $rect.height
    $graphics = [System.Drawing.Graphics]::FromImage($bitmap)

    try {
        $graphics.CopyFromScreen($rect.left, $rect.top, 0, 0, [System.Drawing.Size]::new($rect.width, $rect.height))
    }
    finally {
        $graphics.Dispose()
    }

    return $bitmap
}

function Save-BitmapPng {
    param(
        [System.Drawing.Bitmap]$Bitmap,
        [string]$Path
    )

    $directory = [System.IO.Path]::GetDirectoryName($Path)
    if (-not [string]::IsNullOrWhiteSpace($directory)) {
        [System.IO.Directory]::CreateDirectory($directory) | Out-Null
    }

    $Bitmap.Save($Path, [System.Drawing.Imaging.ImageFormat]::Png)
    return [System.IO.Path]::GetFullPath($Path)
}

function Capture-WindowClientArea {
    param(
        [psobject]$Window,
        [string]$Path
    )

    $bitmap = New-WindowClientBitmap -Window $Window
    try {
        $fullPath = Save-BitmapPng -Bitmap $bitmap -Path $Path
        return [pscustomobject]@{
            screenshotPath = $fullPath
            imageSize = [pscustomobject]@{
                width = $bitmap.Width
                height = $bitmap.Height
            }
        }
    }
    finally {
        $bitmap.Dispose()
    }
}

function New-ScaledRegionBitmap {
    param(
        [System.Drawing.Bitmap]$Bitmap,
        [System.Drawing.Rectangle]$Region
    )

    $scale = [Math]::Min(1.0, [Math]::Min($MaxComparisonDimension / [double]$Region.Width, $MaxComparisonDimension / [double]$Region.Height))
    $targetWidth = [Math]::Max(1, [int][Math]::Round($Region.Width * $scale))
    $targetHeight = [Math]::Max(1, [int][Math]::Round($Region.Height * $scale))

    $scaled = New-Object System.Drawing.Bitmap $targetWidth, $targetHeight
    $graphics = [System.Drawing.Graphics]::FromImage($scaled)
    try {
        $graphics.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBilinear
        $graphics.PixelOffsetMode = [System.Drawing.Drawing2D.PixelOffsetMode]::HighQuality
        $graphics.DrawImage(
            $Bitmap,
            [System.Drawing.Rectangle]::new(0, 0, $targetWidth, $targetHeight),
            $Region,
            [System.Drawing.GraphicsUnit]::Pixel)
    }
    finally {
        $graphics.Dispose()
    }

    return $scaled
}

function Get-ImageChangePercent {
    param(
        [System.Drawing.Bitmap]$BaselineBitmap,
        [System.Drawing.Bitmap]$CurrentBitmap,
        [System.Drawing.Rectangle]$Region
    )

    $baselineScaled = New-ScaledRegionBitmap -Bitmap $BaselineBitmap -Region $Region
    $currentScaled = New-ScaledRegionBitmap -Bitmap $CurrentBitmap -Region $Region

    try {
        $changedPixels = 0
        $totalPixels = $baselineScaled.Width * $baselineScaled.Height

        for ($x = 0; $x -lt $baselineScaled.Width; $x++) {
            for ($y = 0; $y -lt $baselineScaled.Height; $y++) {
                $baselineColor = $baselineScaled.GetPixel($x, $y)
                $currentColor = $currentScaled.GetPixel($x, $y)
                $difference = [Math]::Abs($baselineColor.R - $currentColor.R) +
                    [Math]::Abs($baselineColor.G - $currentColor.G) +
                    [Math]::Abs($baselineColor.B - $currentColor.B)

                if ($difference -ge $PixelDifferenceThreshold) {
                    $changedPixels++
                }
            }
        }

        return [Math]::Round(($changedPixels * 100.0) / [Math]::Max(1, $totalPixels), 4)
    }
    finally {
        $baselineScaled.Dispose()
        $currentScaled.Dispose()
    }
}

function Wait-ForWindowFrameChange {
    param(
        [psobject]$Window,
        [string]$BaselineScreenshotPath,
        [string]$ResultPath
    )

    if (-not (Test-Path -LiteralPath $BaselineScreenshotPath)) {
        throw "Baseline screenshot was not found: $BaselineScreenshotPath"
    }

    $baselineBitmap = New-Object System.Drawing.Bitmap $BaselineScreenshotPath
    $lastBitmap = $null
    $attempts = 0
    $lastChangePercent = 0.0
    $changed = $false
    $startedAt = Get-Date
    $deadline = $startedAt.AddMilliseconds($TimeoutMilliseconds)

    try {
        $region = Get-RegionRectangle -ImageWidth $baselineBitmap.Width -ImageHeight $baselineBitmap.Height

        do {
            if ($lastBitmap) {
                $lastBitmap.Dispose()
                $lastBitmap = $null
            }

            $attempts++
            $lastBitmap = New-WindowClientBitmap -Window $Window

            if ($lastBitmap.Width -ne $baselineBitmap.Width -or $lastBitmap.Height -ne $baselineBitmap.Height) {
                $lastChangePercent = 100.0
                $changed = $true
            }
            else {
                $lastChangePercent = Get-ImageChangePercent -BaselineBitmap $baselineBitmap -CurrentBitmap $lastBitmap -Region $region
                $changed = $lastChangePercent -ge $ChangeThresholdPercent
            }

            if ($changed) {
                break
            }

            Start-Sleep -Milliseconds $PollIntervalMilliseconds
        }
        while ((Get-Date) -lt $deadline)

        if (-not $lastBitmap) {
            $attempts++
            $lastBitmap = New-WindowClientBitmap -Window $Window
        }

        $savedPath = Save-BitmapPng -Bitmap $lastBitmap -Path $ResultPath
        $elapsedMilliseconds = [int][Math]::Round(((Get-Date) - $startedAt).TotalMilliseconds)

        return [pscustomobject]@{
            changed = $changed
            screenshotPath = $savedPath
            imageSize = [pscustomobject]@{
                width = $lastBitmap.Width
                height = $lastBitmap.Height
            }
            attempts = $attempts
            elapsedMilliseconds = $elapsedMilliseconds
            changePercent = $lastChangePercent
            region = (Convert-RectangleToRegionObject -Rectangle $region)
        }
    }
    finally {
        $baselineBitmap.Dispose()
        if ($lastBitmap) {
            $lastBitmap.Dispose()
        }
    }
}

try {
    $result = switch ($Operation) {
        "find" {
            Resolve-WindowSnapshot
            break
        }
        "inspect" {
            Resolve-WindowSnapshot
            break
        }
        "focus" {
            $window = Resolve-WindowSnapshot
            [void][RiftGameWindowNative]::ShowWindow((ConvertTo-IntPtr -HandleText $window.windowHandle), $SW_RESTORE)
            [void][RiftGameWindowNative]::SetForegroundWindow((ConvertTo-IntPtr -HandleText $window.windowHandle))
            Start-Sleep -Milliseconds 250
            Get-WindowSnapshot -Handle (ConvertTo-IntPtr -HandleText $window.windowHandle)
            break
        }
        "capture" {
            $window = Resolve-WindowSnapshot
            $capture = Capture-WindowClientArea -Window $window -Path $OutputPath
            [pscustomobject]@{
                window = (Get-WindowSnapshot -Handle (ConvertTo-IntPtr -HandleText $window.windowHandle))
                screenshotPath = $capture.screenshotPath
                imageSize = $capture.imageSize
            }
            break
        }
        "wait-for-change" {
            $window = Resolve-WindowSnapshot
            $waitResult = Wait-ForWindowFrameChange -Window $window -BaselineScreenshotPath $BaselinePath -ResultPath $OutputPath
            [pscustomobject]@{
                window = (Get-WindowSnapshot -Handle (ConvertTo-IntPtr -HandleText $window.windowHandle))
                changed = $waitResult.changed
                screenshotPath = $waitResult.screenshotPath
                imageSize = $waitResult.imageSize
                attempts = $waitResult.attempts
                elapsedMilliseconds = $waitResult.elapsedMilliseconds
                changePercent = $waitResult.changePercent
                region = $waitResult.region
            }
            break
        }
        "click" {
            $window = Resolve-WindowSnapshot
            Assert-WindowMatchesExpectations -Window $window

            if (-not $window.isForeground) {
                throw "Refusing click because the bound game window is not the foreground window. Call focus_game_window first."
            }

            if ($window.isMinimized) {
                throw "Cannot click a minimized window."
            }

            $screenPoint = Convert-ClientPointToScreenPoint -Handle (ConvertTo-IntPtr -HandleText $window.windowHandle) -X $ClientX -Y $ClientY
            if (-not [RiftGameWindowNative]::SetCursorPos($screenPoint.x, $screenPoint.y)) {
                throw "SetCursorPos failed. $(Get-LastWin32ErrorMessage)"
            }

            Start-Sleep -Milliseconds 30
            Invoke-SendInput -Inputs @((New-MouseInput -Flags $MOUSEEVENTF_LEFTDOWN))
            Start-Sleep -Milliseconds $ClickDelayMilliseconds
            Invoke-SendInput -Inputs @((New-MouseInput -Flags $MOUSEEVENTF_LEFTUP))

            [pscustomobject]@{
                window = (Get-WindowSnapshot -Handle (ConvertTo-IntPtr -HandleText $window.windowHandle))
                screenPoint = $screenPoint
            }
            break
        }
        "send-key" {
            $window = Resolve-WindowSnapshot
            Assert-WindowMatchesExpectations -Window $window

            if (-not $window.isForeground) {
                throw "Refusing key input because the bound game window is not the foreground window. Call focus_game_window first."
            }

            if ($window.isMinimized) {
                throw "Cannot send keys to a minimized window."
            }

            $plan = Resolve-KeyPlan -Chord $KeyChord
            Send-KeyPlan -Plan $plan -HoldMilliseconds $HoldMilliseconds

            [pscustomobject]@{
                window = (Get-WindowSnapshot -Handle (ConvertTo-IntPtr -HandleText $window.windowHandle))
                keyChord = $KeyChord
                holdMilliseconds = $HoldMilliseconds
            }
            break
        }
    }

    $result | ConvertTo-Json -Depth 8 -Compress
}
catch {
    [Console]::Error.WriteLine($_.Exception.Message)
    exit 1
}
