@echo off
setlocal EnableDelayedExpansion

echo ========================================
echo   ReferenceMiner Build Script
echo ========================================
echo.

REM Check if Node.js is available
where node >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo ERROR: Node.js is not installed or not in PATH
    echo Please install Node.js from https://nodejs.org/
    exit /b 1
)

REM Check if uv is available
where uv >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo ERROR: uv is not installed or not in PATH
    echo Please install uv: https://docs.astral.sh/uv/
    exit /b 1
)

echo [1/7] Cleaning previous builds...
echo ----------------------------------------
taskkill /IM ReferenceMiner.exe /F /T >nul 2>nul
powershell -NoProfile -Command "Get-Process ReferenceMiner -ErrorAction SilentlyContinue | Stop-Process -Force" >nul 2>nul
timeout /t 1 /nobreak >nul
if exist dist (
    rmdir /S /Q dist
)
if exist dist-electron (
    rmdir /S /Q dist-electron
)
echo Clean complete.
echo.

echo [2/7] Installing Desktop Shell (Electron)...
echo ----------------------------------------
if not exist node_modules (
    echo Installing root npm dependencies...
    call npm install
    if %ERRORLEVEL% neq 0 (
        echo ERROR: npm install failed
        exit /b 1
    )
)
echo Electron dependencies ready.
echo.

echo [3/7] Building Frontend...
echo ----------------------------------------
cd frontend
if not exist node_modules (
    echo Installing npm dependencies...
    call npm install
    if %ERRORLEVEL% neq 0 (
        echo ERROR: npm install failed
        cd ..
        exit /b 1
    )
)

echo Running production build...
call npm run build
if %ERRORLEVEL% neq 0 (
    echo ERROR: Frontend build failed
    cd ..
    exit /b 1
)
cd ..
echo Frontend build complete: frontend\dist\
echo.

echo [4/7] Installing PyInstaller...
echo ----------------------------------------
uv pip install pyinstaller
echo PyInstaller ready.
echo.

echo [5/7] Building Backend Executable...
echo ----------------------------------------
echo This may take a few minutes...
uv run python -m PyInstaller referenceminer.spec --clean --noconfirm
if %ERRORLEVEL% neq 0 (
    echo ERROR: PyInstaller build failed
    exit /b 1
)
echo.

echo [6/7] Building Desktop App...
echo ----------------------------------------
call npm run electron:build
if %ERRORLEVEL% neq 0 (
    echo ERROR: Electron build failed
    exit /b 1
)
echo.

echo [7/7] Build Complete!
echo ========================================
echo.
echo Output:
echo   Portable:   dist-electron\win-unpacked\ReferenceMiner.exe
echo   Installer:  dist-electron\ReferenceMiner Setup 1.0.0.exe
echo.
echo Development:
echo   npm run electron:run
echo.
echo ========================================

endlocal
