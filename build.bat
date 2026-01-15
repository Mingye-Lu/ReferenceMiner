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

echo [1/4] Building Frontend...
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

echo [2/4] Installing PyInstaller...
echo ----------------------------------------
uv pip install pyinstaller
echo PyInstaller ready.
echo.

echo [3/4] Building Executable...
echo ----------------------------------------
echo This may take a few minutes...
uv run python -m PyInstaller referenceminer.spec --clean --noconfirm
if %ERRORLEVEL% neq 0 (
    echo ERROR: PyInstaller build failed
    exit /b 1
)
echo.

echo [4/4] Build Complete!
echo ========================================
echo.
echo Executable location:
echo   dist\ReferenceMiner.exe
echo.
echo To run:
echo   1. Copy dist\ReferenceMiner.exe to any folder
echo   2. Run it - browser will open automatically
echo   3. Place PDF/DOCX files in the 'references' folder
echo.
echo ========================================

endlocal
