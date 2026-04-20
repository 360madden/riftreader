#Requires AutoHotkey v2.0
#SingleInstance Force

commandText := A_Args.Length >= 1 ? A_Args[1] : "/reloadui"
targetExe := A_Args.Length >= 2 ? A_Args[2] : "rift_x64.exe"
backgroundExe := A_Args.Length >= 3 ? A_Args[3] : "cheatengine-x86_64-SSE4-AVX2.exe"
activationSettleMilliseconds := A_Args.Length >= 4 ? Integer(A_Args[4]) : 500
noRefocus := A_Args.Length >= 5 ? (A_Args[5] = "1") : false

SendCommand(commandText) {
    SendEvent("{Enter}")
    Sleep(150)
    SendEvent("{Text}" commandText)
    Sleep(150)
    SendEvent("{Enter}")
}

targetWindows := WinGetList("ahk_exe " targetExe)
if (targetWindows.Length < 1)
    ExitApp(2)

targetHwnd := targetWindows[1]
previousHwnd := WinExist("A")

SetTitleMatchMode(2)
SetKeyDelay(50, 50)
SetWinDelay(50)
WinActivate("ahk_id " targetHwnd)

try {
    WinWaitActive("ahk_id " targetHwnd, , 1.5)
} catch {
    ExitApp(4)
}

Sleep(Max(activationSettleMilliseconds, 0))

try {
    SendCommand(commandText)
} catch {
    ExitApp(5)
}

if (!noRefocus) {
    if (backgroundExe != "") {
        try WinActivate("ahk_exe " backgroundExe)
    } else if (previousHwnd && previousHwnd != targetHwnd) {
        try WinActivate("ahk_id " previousHwnd)
    }
}

ExitApp(0)
