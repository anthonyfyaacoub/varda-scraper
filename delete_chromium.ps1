# PowerShell script to force delete Playwright Chromium folder
# Run as Administrator: Right-click PowerShell -> Run as Administrator

Write-Host "=== Force Delete Playwright Chromium Folder ===" -ForegroundColor Cyan
Write-Host ""

$chromiumPath = "$env:LOCALAPPDATA\ms-playwright\chromium-1200"

if (-not (Test-Path $chromiumPath)) {
    Write-Host "Folder not found: $chromiumPath" -ForegroundColor Yellow
    Write-Host "Nothing to delete." -ForegroundColor Green
    exit 0
}

Write-Host "Found folder: $chromiumPath" -ForegroundColor Yellow
Write-Host ""

# Step 1: Kill any processes using files in this folder
Write-Host "Step 1: Killing processes that might be using the folder..." -ForegroundColor Cyan
Get-Process | Where-Object {
    $_.Path -like "*chromium*" -or 
    $_.Path -like "*chrome*" -or
    $_.Path -like "*playwright*"
} | ForEach-Object {
    Write-Host "  Killing process: $($_.Name) (PID: $($_.Id))" -ForegroundColor Yellow
    Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue
}

Start-Sleep -Seconds 2

# Step 2: Take ownership of the folder
Write-Host ""
Write-Host "Step 2: Taking ownership of folder..." -ForegroundColor Cyan
try {
    $currentUser = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
    takeown /F $chromiumPath /R /D Y 2>&1 | Out-Null
    icacls $chromiumPath /grant "${currentUser}:F" /T 2>&1 | Out-Null
    Write-Host "  Ownership taken successfully" -ForegroundColor Green
} catch {
    Write-Host "  Warning: Could not take ownership (may need to run as Admin)" -ForegroundColor Yellow
}

# Step 3: Remove read-only attributes
Write-Host ""
Write-Host "Step 3: Removing read-only attributes..." -ForegroundColor Cyan
Get-ChildItem $chromiumPath -Recurse -Force | ForEach-Object {
    $_.Attributes = $_.Attributes -band (-bnot [System.IO.FileAttributes]::ReadOnly)
}

# Step 4: Force delete
Write-Host ""
Write-Host "Step 4: Deleting folder..." -ForegroundColor Cyan
try {
    Remove-Item $chromiumPath -Recurse -Force -ErrorAction Stop
    Write-Host ""
    Write-Host "SUCCESS: Folder deleted!" -ForegroundColor Green
} catch {
    Write-Host ""
    Write-Host "ERROR: Could not delete folder" -ForegroundColor Red
    Write-Host "Error: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host ""
    Write-Host "Try these alternatives:" -ForegroundColor Yellow
    Write-Host "  1. Restart your computer and try again" -ForegroundColor Yellow
    Write-Host "  2. Use Playwright's cleanup: python -m playwright install --help" -ForegroundColor Yellow
    Write-Host "  3. Use Unlocker tool: https://www.emptyloop.com/unlocker/" -ForegroundColor Yellow
    exit 1
}

Write-Host ""
Write-Host "Done! You can now reinstall browsers with: python -m playwright install chromium" -ForegroundColor Green
