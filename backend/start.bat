@echo off
chcp 65001 >nul
REM Cloud Drive Backend Service Startup Script (Windows)

echo.
echo ========================================
echo  Cloud Drive Backend Service
echo ========================================
echo.

REM Check virtual environment
if not exist "venv" (
    echo [1/5] Creating virtual environment...
    python -m venv venv
    if errorlevel 1 (
        echo ERROR: Failed to create virtual environment
        pause
        exit /b 1
    )
)

REM Activate virtual environment
echo [2/5] Activating virtual environment...
call venv\Scripts\activate.bat
if errorlevel 1 (
    echo ERROR: Failed to activate virtual environment
    pause
    exit /b 1
)

REM Install dependencies
echo [3/5] Installing dependencies...
pip install -r requirements.txt -q
if errorlevel 1 (
    echo ERROR: Failed to install dependencies
    pause
    exit /b 1
)

REM Check .env file
if not exist ".env" (
    echo.
    echo WARNING: .env file not found
    if exist "env.example" (
        copy env.example .env >nul
        echo Created .env file from template
        echo Please edit .env and configure your AWS credentials
        echo.
        notepad .env
        pause
        exit /b 1
    ) else (
        echo ERROR: env.example not found
        pause
        exit /b 1
    )
)

REM Initialize database
echo [4/5] Initializing database...
python -c "from app.models.database import init_db; init_db()" 2>nul
if errorlevel 1 (
    echo WARNING: Database initialization had issues, continuing...
)

REM Start service
echo [5/5] Starting service...
echo.
echo ========================================
echo  Service Information
echo ========================================
echo  API Address:  http://localhost:8000
echo  API Docs:     http://localhost:8000/docs
echo  Health Check: http://localhost:8000/health
echo ========================================
echo.
echo Press Ctrl+C to stop the server
echo.

python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

pause

