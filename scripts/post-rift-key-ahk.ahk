#Requires AutoHotkey v2.0

if (A_Args.Length < 3) {
    ExitApp(9)
}

keyText := A_Args[1]
holdMilliseconds := Integer(A_Args[2])
targetExe := A_Args[3]
targetSpecifier := "ahk_exe " . targetExe

if !WinExist(targetSpecifier) {
    ExitApp(1)
}

hwnd := WinExist(targetSpecifier)
WinActivate("ahk_id " . hwnd)
if !WinWaitActive("ahk_id " . hwnd, , 2) {
    ExitApp(2)
}

SendEvent("{" . keyText . " down}")
Sleep(holdMilliseconds)
SendEvent("{" . keyText . " up}")
ExitApp(0)
