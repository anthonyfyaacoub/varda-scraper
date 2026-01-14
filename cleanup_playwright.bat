@echo off
REM Batch script to clean up Playwright browsers
REM Run as Administrator: Right-click -> Run as Administrator

echo ========================================
echo Playwright Browser Cleanup Script
echo ========================================
echo.

REM Kill any Chrome/Chromium processes
echo Step 1: Killing Chrome/Chromium processes...
taskkill /F /IM chrome.exe /T 2>nul
taskkill /F /IM chromium.exe /T 2>nul
timeout /t 2 /nobreak >nul

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
    
    REM Delete
    echo Step 5: Deleting...
    rd /s /q "%CHROMIUM_PATH%" 2>nul
    
    if exist "%CHROMIUM_PATH%" (
        echo.
        echo ERROR: Could not delete folder!
        echo Try restarting your computer and run this script again.
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
