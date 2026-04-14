#Requires AutoHotkey v2.0
if !WinExist("ahk_exe rift_x64.exe")
    ExitApp 2
WinActivate("ahk_exe rift_x64.exe")
WinWaitActive("ahk_exe rift_x64.exe",, 2)
Sleep 200
SendEvent("{Esc}")
Sleep 150
SendEvent("{w down}")
Sleep 1200
SendEvent("{w up}")
ExitApp 0
