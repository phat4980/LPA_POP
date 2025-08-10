@echo off
echo Building PO Merge Tool with icon...
echo.

REM Change to parent directory where source files are located
cd /d "%~dp0.."

REM Check if PyInstaller is installed
python -c "import PyInstaller" 2>nul
if errorlevel 1 (
    echo PyInstaller not found. Installing...
    pip install pyinstaller
    if errorlevel 1 (
        echo Failed to install PyInstaller. Please install manually:
        echo pip install pyinstaller
        pause
        exit /b 1
    )
)

REM Clean previous builds
echo Cleaning previous builds...
if exist "build" rmdir /s /q "build"
if exist "dist" rmdir /s /q "dist"
if exist "*.spec" del "*.spec"

REM Build the executable with enhanced icon support
echo Building executable with enhanced icon support...
pyinstaller --onefile --windowed --name "PO Management Tool" --icon "assets/icon/app.ico" src/po_merge_tool_gui.py --add-data "assets/font/Roboto-ExtraBold.ttf;font" --add-data "assets/icon;icon" --clean

if errorlevel 1 (
    echo Build failed!
    pause
    exit /b 1
)

REM Refresh Windows icon cache to ensure icon displays correctly
echo Refreshing Windows icon cache...
ie4uinit.exe -show
ie4uinit.exe -BaseSettings
ie4uinit.exe -ClearIconCache
taskkill /IM explorer.exe /F
timeout /t 2 /nobreak >nul
start explorer.exe

echo.
echo Build successful! Executable is in the dist/ folder.
echo.
echo Note: If the app still doesn't show in file explorer, try:
echo 1. Restart your computer
echo 2. Check if Windows Defender or antivirus is blocking the app
echo.
pause
