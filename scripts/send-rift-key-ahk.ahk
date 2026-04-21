#Requires AutoHotkey v2.0
#SingleInstance Force

keyText := A_Args.Length >= 1 ? A_Args[1] : ""
holdMilliseconds := A_Args.Length >= 2 ? Integer(A_Args[2]) : 250
targetExe := A_Args.Length >= 3 ? A_Args[3] : "rift_x64.exe"
noRefocus := A_Args.Length >= 4 ? (A_Args[4] = "1") : false

NormalizeKey(keyValue) {
    trimmed := Trim(keyValue)
    if (trimmed = "")
        return ""

    upper := StrUpper(trimmed)
    switch upper {
        case "SPACE":
            return "Space"
        case "LEFT":
            return "Left"
        case "RIGHT":
            return "Right"
        case "UP":
            return "Up"
        case "DOWN":
            return "Down"
        case "ENTER", "RETURN":
            return "Enter"
        case "ESC", "ESCAPE":
            return "Escape"
        case "TAB":
            return "Tab"
        case "BACKSPACE":
            return "Backspace"
        default:
            return trimmed
    }
}

SendHeldKey(keyName, holdMs) {
    SendEvent("{" keyName " down}")
    Sleep(Max(holdMs, 1))
    SendEvent("{" keyName " up}")
}

if (keyText = "")
    ExitApp(1)

targetWindows := WinGetList("ahk_exe " targetExe)
if (targetWindows.Length < 1)
    ExitApp(2)

targetHwnd := targetWindows[1]
previousHwnd := WinExist("A")
keyName := NormalizeKey(keyText)
if (keyName = "")
    ExitApp(3)

SetTitleMatchMode(2)
SetKeyDelay(50, 50)
WinActivate("ahk_id " targetHwnd)

try {
    WinWaitActive("ahk_id " targetHwnd, , 1.5)
} catch {
    ExitApp(4)
}

Sleep(150)
SendHeldKey(keyName, holdMilliseconds)

if (!noRefocus && previousHwnd && previousHwnd != targetHwnd) {
    Sleep(100)
    try WinActivate("ahk_id " previousHwnd)
}

ExitApp(0)
