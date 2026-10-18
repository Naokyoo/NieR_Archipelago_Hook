@echo off
setlocal

call "C:\Program Files\Microsoft Visual Studio\18\Community\VC\Auxiliary\Build\vcvars64.bat"

cl /LD /O2 /EHsc /std:c++17 ^
    /I. /Iminhook/include /Iimgui ^
    dllmain.cpp ^
    ArchipelagoUI.cpp ^
    imgui/imgui.cpp ^
    imgui/imgui_draw.cpp ^
    imgui/imgui_tables.cpp ^
    imgui/imgui_widgets.cpp ^
    imgui/imgui_impl_win32.cpp ^
    imgui/imgui_impl_dx11.cpp ^
    minhook/src/buffer.c ^
    minhook/src/hook.c ^
    minhook/src/trampoline.c ^
    minhook/src/hde/hde64.c ^
    minhook/src/hde/hde32.c ^
    user32.lib ws2_32.lib d3d11.lib dxgi.lib ^
    /link /DEF:dinput8.def /OUT:dinput8.dll

if %ERRORLEVEL% equ 0 (
    echo [SUCCESS] dinput8.dll with ImGui YoRHa Overlay compiled successfully!
) else (
    echo [ERROR] Compilation failed with error %ERRORLEVEL%
)

endlocal
