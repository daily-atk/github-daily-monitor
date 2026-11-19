@echo off
chcp 65001 >nul
setlocal
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
cd /d "%~dp0"

rem 优先使用真实安装的 Python，避开微软商店的占位程序
set "PY=python"
for /d %%d in ("%LOCALAPPDATA%\Programs\Python\Python3*") do if exist "%%d\python.exe" set "PY=%%d\python.exe"
for /d %%d in ("%ProgramFiles%\Python3*") do if exist "%%d\python.exe" set "PY=%%d\python.exe"

echo ============================================================
echo   每日 GitHub 日报
echo   正在采集并生成报告，通常需要 1-3 分钟，请不要关闭窗口
echo ============================================================
echo.

"%PY%" monitor.py run
set "CODE=%ERRORLEVEL%"
echo.

if not "%CODE%"=="0" (
    echo [失败] 运行没有成功。
    echo 常见原因：
    echo   1. 没有安装 Python（请先看 新手使用说明.md 第 1 步）
    echo   2. 配置文件 config.json 写错了（按提示检查逗号或引号）
    echo   3. 网络无法访问 GitHub
    echo 详细错误已写入 data\run.log
    echo.
    pause
    exit /b %CODE%
)

echo [完成] 正在打开最新报告...
set "LATEST="
for /f "delims=" %%f in ('dir /b /o-d "reports\github-daily-*.html" 2^>nul') do (
    set "LATEST=reports\%%f"
    goto :open
)

:open
if defined LATEST (
    start "" "%LATEST%"
) else (
    echo [提示] reports 文件夹里没有找到报告。
)
echo.
pause
exit /b 0