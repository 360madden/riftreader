#Requires AutoHotkey v2.0

if (A_Args.Length < 3) {
    ExitApp(9)
}

keyText := A_Args[1]
holdMilliseconds := Integer(A_Args[2])
targetExe := A_Args[3]
targetWindowHandle := A_Args.Length >= 4 ? A_Args[4] : ""
targetProcessId := A_Args.Length >= 5 ? Integer(A_Args[5]) : 0

if (targetWindowHandle != "") {
    if (!WinExist("ahk_id " . targetWindowHandle)) {
        ExitApp(1)
    }

    hwnd := targetWindowHandle
    if (targetProcessId > 0 && WinGetPID("ahk_id " . hwnd) != targetProcessId) {
        ExitApp(8)
    }
} else {
    targetSpecifier := "ahk_exe " . targetExe
    windows := WinGetList(targetSpecifier)
    if (windows.Length < 1) {
        ExitApp(1)
    }

    if (windows.Length > 1 && targetProcessId <= 0) {
        ExitApp(6)
    }

    hwnd := windows[1]
    if (targetProcessId > 0) {
        hwnd := 0
        for candidateHwnd in windows {
            if (WinGetPID("ahk_id " . candidateHwnd) = targetProcessId) {
                hwnd := candidateHwnd
                break
            }
        }

        if (!hwnd) {
            ExitApp(7)
        }
    }
}

WinActivate("ahk_id " . hwnd)
if !WinWaitActive("ahk_id " . hwnd, , 2) {
    ExitApp(2)
}

SendEvent("{" . keyText . " down}")
Sleep(holdMilliseconds)
SendEvent("{" . keyText . " up}")
ExitApp(0)
