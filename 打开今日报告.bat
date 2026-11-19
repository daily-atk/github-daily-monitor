@echo off
chcp 65001 >nul
cd /d "%~dp0"

set "LATEST="
for /f "delims=" %%f in ('dir /b /o-d "reports\github-daily-*.html" 2^>nul') do (
    set "LATEST=reports\%%f"
    goto :open
)

:open
if defined LATEST (
    start "" "%LATEST%"
    exit /b 0
)
echo [提示] 还没有报告，请先双击"运行日报.bat"。
pause
exit /b 1