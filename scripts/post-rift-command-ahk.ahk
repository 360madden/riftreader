#Requires AutoHotkey v2.0
#SingleInstance Force

WM_KEYDOWN := 0x0100
WM_KEYUP := 0x0101

commandText := A_Args.Length >= 1 ? A_Args[1] : "/reloadui"
targetExe := A_Args.Length >= 2 ? A_Args[2] : "rift_x64.exe"
backgroundExe := A_Args.Length >= 3 ? A_Args[3] : "cheatengine-x86_64-SSE4-AVX2.exe"

BuildKeyLParam(sc, isKeyUp) {
    lParam := 1 | (sc << 16)
    if isKeyUp
        lParam |= 0xC0000000
    return lParam
}

GetTargetTopHwnd(targetExe) {
    windows := WinGetList("ahk_exe " targetExe)
    if (windows.Length < 1)
        return 0

    return windows[1]
}

GetFocusedTargetHwnd(topHwnd) {
    focusedClassNN := ""
    focusedHwnd := 0

    try focusedClassNN := ControlGetFocus("ahk_id " topHwnd)

    if (focusedClassNN != "") {
        try focusedHwnd := ControlGetHwnd(focusedClassNN, "ahk_id " topHwnd)
    }

    return focusedHwnd
}

MapCharToKeyName(character) {
    switch character {
        case " ":
            return "Space"
        case "`t":
            return "Tab"
        default:
            return character
    }
}

PostKey(targetHwnd, keyName) {
    vk := GetKeyVK(keyName)
    sc := GetKeySC(keyName)

    if !vk || !sc
        throw Error("No VK/SC mapping found for key: " keyName)

    PostMessage(WM_KEYDOWN, vk, BuildKeyLParam(sc, false),, "ahk_id " targetHwnd)
    Sleep(30)
    PostMessage(WM_KEYUP, vk, BuildKeyLParam(sc, true),, "ahk_id " targetHwnd)
    Sleep(30)
}

SendCommand(targetHwnd, commandText) {
    PostKey(targetHwnd, "Enter")

    for character in StrSplit(commandText) {
        PostKey(targetHwnd, MapCharToKeyName(character))
    }

    PostKey(targetHwnd, "Enter")
}

targetTopHwnd := GetTargetTopHwnd(targetExe)
if !targetTopHwnd
    ExitApp(2)

targetHwnd := GetFocusedTargetHwnd(targetTopHwnd)
if !targetHwnd
    targetHwnd := targetTopHwnd

if (backgroundExe != "") {
    try WinActivate("ahk_exe " backgroundExe)
    Sleep(250)
}

SendCommand(targetHwnd, commandText)
ExitApp(0)
