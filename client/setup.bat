@echo off
chcp 65001 >nul
REM Cloud Drive Client Setup Script (Windows)

echo.
echo ========================================
echo  Cloud Drive Client Setup
echo ========================================
echo.

REM Create virtual environment
if not exist "venv" (
    echo [1/4] Creating virtual environment...
    python -m venv venv
    if errorlevel 1 (
        echo ERROR: Failed to create virtual environment
        pause
        exit /b 1
    )
)

REM Activate virtual environment
echo [2/4] Activating virtual environment...
call venv\Scripts\activate.bat
if errorlevel 1 (
    echo ERROR: Failed to activate virtual environment
    pause
    exit /b 1
)

REM Install dependencies
echo [3/4] Installing dependencies...
pip install -r requirements.txt -q
if errorlevel 1 (
    echo ERROR: Failed to install dependencies
    echo Trying to install packages individually...
    pip install requests tqdm click python-dotenv
    if errorlevel 1 (
        echo ERROR: Installation failed
        pause
        exit /b 1
    )
)

REM Create configuration file
if not exist ".env" (
    echo [4/4] Creating configuration file...
    echo API_BASE_URL=http://localhost:8000 > .env
    echo USER_ID=1 >> .env
    echo DOWNLOAD_DIR=./downloads >> .env
    echo.
    echo Configuration file created: .env
    echo TIP: If backend is on remote server, edit API_BASE_URL in .env
)

REM Create download directory
if not exist "downloads" (
    mkdir downloads
)

echo.
echo ========================================
echo  Setup Complete!
echo ========================================
echo.
echo Usage:
echo   python client.py --help           Show help
echo   python client.py list             List files
echo   python client.py upload file.txt  Upload file
echo   python client.py download 1       Download file
echo.
echo To get started, make sure the backend is running, then try:
echo   python client.py list
echo.
pause

