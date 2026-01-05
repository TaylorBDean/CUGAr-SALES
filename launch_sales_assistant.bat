@echo off
REM CUGAr Sales Assistant Launcher for Windows
REM Simple one-click startup for sales reps

SETLOCAL EnableDelayedExpansion

echo ================================================
echo    CUGAr Sales Assistant - Local Launcher
echo ================================================
echo.

REM Get script directory
set "PROJECT_ROOT=%~dp0"
cd /d "%PROJECT_ROOT%"

REM Check Python installation
python --version >nul 2>&1
if errorlevel 1 (
    echo [X] Python is not installed
    echo Please install Python 3.9+ from https://www.python.org/
    pause
    exit /b 1
)

echo [OK] Python found
python --version

REM Check Node.js installation
node --version >nul 2>&1
if errorlevel 1 (
    echo [X] Node.js is not installed
    echo Please install Node.js from https://nodejs.org/
    pause
    exit /b 1
)

echo [OK] Node.js found
node --version
echo.

REM First run check
if not exist ".env.sales" (
    echo [!] First time setup detected
    echo Launching setup wizard...
    echo.
    
    python -m cuga.frontend.setup_wizard
    
    if errorlevel 1 (
        echo [X] Setup wizard failed
        pause
        exit /b 1
    )
    
    echo.
    echo [OK] Setup complete!
    echo.
)

REM Install Python dependencies if needed
if not exist "venv" (
    echo Installing Python dependencies...
    python -m venv venv
    call venv\Scripts\activate.bat
    pip install -e .
) else (
    call venv\Scripts\activate.bat
)

REM Install Node dependencies if needed
set "FRONTEND_DIR=%PROJECT_ROOT%src\frontend_workspaces\agentic_chat"
if not exist "%FRONTEND_DIR%\node_modules" (
    echo Installing Node dependencies...
    cd "%FRONTEND_DIR%"
    call npm install
    cd "%PROJECT_ROOT%"
)

echo.
echo Starting CUGAr Sales Assistant...
echo.

REM Start backend
echo [->] Starting backend server (port 8000)...
start "CUGAr Backend" /MIN python -m uvicorn cuga.backend.server.main:app --host 127.0.0.1 --port 8000 --log-level info

REM Wait for backend
echo [...] Waiting for backend to start...
timeout /t 5 /nobreak >nul

echo [OK] Backend is running
echo.

REM Start frontend
echo [->] Starting frontend (port 3000)...
cd "%FRONTEND_DIR%"
start "CUGAr Frontend" /MIN cmd /c "npm run dev"

REM Wait for frontend
timeout /t 3 /nobreak >nul

echo.
echo ================================================
echo    CUGAr Sales Assistant is ready!
echo ================================================
echo.
echo   Backend:  http://localhost:8000
echo   Frontend: http://localhost:3000
echo.
echo Opening browser...
echo.

REM Open browser
timeout /t 2 /nobreak >nul
start http://localhost:3000

echo.
echo Press any key to stop the application...
pause >nul

REM Cleanup
echo.
echo Shutting down...
taskkill /FI "WINDOWTITLE eq CUGAr Backend*" /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq CUGAr Frontend*" /F >nul 2>&1
echo [OK] Stopped

ENDLOCAL
