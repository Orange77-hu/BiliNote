@echo off
call "C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvars64.bat"
if errorlevel 1 (echo VCVARS_FAILED & exit /b 1)
set PATH=C:\Users\hp\.cargo\bin;%PATH%
set HTTPS_PROXY=http://127.0.0.1:7890
set HTTP_PROXY=http://127.0.0.1:7890
where link.exe
link 2>&1 | findstr /C:"GNU" >nul && (echo WRONG_LINK & exit /b 2)
cd /d D:\Hermes-Workspace\GitHub\BiliNote\BillNote_frontend
node node_modules\@tauri-apps\cli\tauri.js build
echo BUILD_EXIT=%ERRORLEVEL%
