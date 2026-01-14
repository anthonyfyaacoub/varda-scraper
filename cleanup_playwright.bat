@echo off
REM Batch script to clean up Playwright browsers
REM Run as Administrator: Right-click -> Run as Administrator

echo ========================================
echo Playwright Browser Cleanup Script
echo ========================================
echo.

REM Kill any Chrome/Chromium processes (more aggressive)
echo Step 1: Killing ALL Chrome/Chromium processes...
taskkill /F /IM chrome.exe /T 2>nul
taskkill /F /IM chromium.exe /T 2>nul
taskkill /F /IM msedge.exe /T 2>nul
wmic process where "name like '%%chrome%%' or name like '%%chromium%%'" delete 2>nul
timeout /t 3 /nobreak >nul

REM Delete the folder

echo.
echo Step 2: Deleting Playwright browser folder...
set "CHROMIUM_PATH=%LOCALAPPDATA%\ms-playwright\chromium-1200"

if exist "%CHROMIUM_PATH%" (
    echo Found: %CHROMIUM_PATH%
    
    REM Take ownership
    echo.
    echo Step 3: Taking ownership...
    takeown /F "%CHROMIUM_PATH%" /R /D Y >nul 2>&1
    
    REM Grant permissions
    echo Step 4: Granting permissions...
    icacls "%CHROMIUM_PATH%" /grant "%USERNAME%:F" /T >nul 2>&1
    
    REM Delete (try multiple methods)
    echo Step 5: Deleting folder...
    
    REM Method 1: Standard delete
    rd /s /q "%CHROMIUM_PATH%" 2>nul
    
    REM Method 2: Delete files first, then folder
    if exist "%CHROMIUM_PATH%" (
        echo   Trying alternative deletion method...
        del /f /s /q "%CHROMIUM_PATH%\*.*" 2>nul
        for /d %%p in ("%CHROMIUM_PATH%\*") do rd /s /q "%%p" 2>nul
        rd /s /q "%CHROMIUM_PATH%" 2>nul
    )
    
    REM Method 3: Use PowerShell as last resort
    if exist "%CHROMIUM_PATH%" (
        echo   Trying PowerShell deletion...
        powershell -Command "Remove-Item '%CHROMIUM_PATH%' -Recurse -Force -ErrorAction SilentlyContinue" 2>nul
    )
    
    if exist "%CHROMIUM_PATH%" (
        echo.
        echo ERROR: Could not delete folder!
        echo.
        echo The folder is locked by Windows or another process.
        echo.
        echo SOLUTIONS:
        echo   1. RESTART YOUR COMPUTER (most reliable)
        echo      After restart, run this script again
        echo.
        echo   2. Close ALL programs (VS Code, browsers, terminals)
        echo      Then run this script again
        echo.
        echo   3. Boot into Safe Mode and delete manually
        echo.
        pause
        exit /b 1
    ) else (
        echo.
        echo SUCCESS: Folder deleted!
    )
) else (
    echo Folder not found: %CHROMIUM_PATH%
    echo Nothing to delete.
)

echo.
echo Done! You can reinstall with: python -m playwright install chromium
pause
