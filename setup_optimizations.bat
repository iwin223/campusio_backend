@echo off
REM Optimization Setup Script for Windows
REM Runs after dependencies are installed to set up performance optimizations

color 0A
cls

echo.
echo ======================================================================
echo    School ERP Backend - Optimization Setup
echo ======================================================================
echo.

REM Step 1: Check Python
echo [1/4] Checking Python installation...
python --version >nul 2>&1
if %errorlevel% equ 0 (
    echo.     [OK] Python is installed
) else (
    echo.     [ERROR] Python not found. Please install Python 3.9+
    pause
    exit /b 1
)

echo.

REM Step 2: Install dependencies
echo [2/4] Installing Python dependencies...
echo.     Installing redis, aioredis, and other packages...
pip install -q redis==5.0.1 aioredis==2.0.1 >nul 2>&1

if %errorlevel% equ 0 (
    echo.     [OK] Dependencies installed
) else (
    echo.     [ERROR] Failed to install dependencies
    echo.     Run: pip install -r requirements.txt
    pause
    exit /b 1
)

echo.

REM Step 3: Create database indexes
echo [3/4] Creating database indexes...
echo.     This will optimize database query performance...
echo.

python create_indexes.py
if %errorlevel% equ 0 (
    echo.     [OK] Database indexes created
) else (
    echo.     [WARNING] Database indexes creation failed
    echo.     Make sure the database is running and accessible
)

echo.

REM Step 4: Instructions
echo [4/4] Setup complete!
echo.
echo ======================================================================
echo    IMPORTANT: Redis Setup Required
echo ======================================================================
echo.
echo Redis is required for authentication caching.
echo.
echo Option 1 - Using Docker (Recommended):
echo   1. Install Docker Desktop from: https://www.docker.com/products/docker-desktop
echo   2. Open PowerShell and run:
echo      docker run -d -p 6379:6379 --name redis redis:latest
echo   3. Verify: redis-cli ping (should show PONG)
echo.
echo Option 2 - Direct Installation:
echo   Download from: https://github.com/microsoftarchive/redis/releases
echo   Or use Windows Package Manager: choco install redis
echo.
echo ======================================================================
echo.

echo Starting backend service...
echo.
echo Python version:
python --version
echo.
echo To start the server, run:
echo   python server.py
echo.
echo Make sure Redis is running before starting the server!
echo.
pause
