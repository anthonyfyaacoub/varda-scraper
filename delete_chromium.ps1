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

# Step 1: Kill ALL Chrome/Chromium processes aggressively
Write-Host "Step 1: Killing ALL Chrome/Chromium processes..." -ForegroundColor Cyan

# Kill by process name (more reliable)
$processes = @("chrome", "chromium", "chrome.exe", "chromium.exe", "msedge", "msedge.exe")
foreach ($procName in $processes) {
    Get-Process -Name $procName -ErrorAction SilentlyContinue | ForEach-Object {
        Write-Host "  Killing process: $($_.Name) (PID: $($_.Id))" -ForegroundColor Yellow
        Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue
    }
}

# Also kill any process with chromium in path
Get-Process | Where-Object {
    $_.Path -and (
        $_.Path -like "*chromium*" -or 
        $_.Path -like "*chrome*" -or
        $_.Path -like "*playwright*" -or
        $_.Path -like "*ms-playwright*"
    )
} | ForEach-Object {
    Write-Host "  Killing process: $($_.Name) (PID: $($_.Id))" -ForegroundColor Yellow
    Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue
}

# Use taskkill as backup
Start-Process -FilePath "taskkill" -ArgumentList "/F", "/IM", "chrome.exe", "/T" -NoNewWindow -Wait -ErrorAction SilentlyContinue
Start-Process -FilePath "taskkill" -ArgumentList "/F", "/IM", "chromium.exe", "/T" -NoNewWindow -Wait -ErrorAction SilentlyContinue

Write-Host "  Waiting for processes to fully terminate..." -ForegroundColor Yellow
Start-Sleep -Seconds 3

# Step 2: Take ownership of the folder (more aggressive)
Write-Host ""
Write-Host "Step 2: Taking ownership of folder..." -ForegroundColor Cyan
$currentUser = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name

# Take ownership recursively
$takeownResult = Start-Process -FilePath "takeown" -ArgumentList "/F", $chromiumPath, "/R", "/D", "Y" -NoNewWindow -Wait -PassThru
if ($takeownResult.ExitCode -eq 0) {
    Write-Host "  Ownership taken successfully" -ForegroundColor Green
} else {
    Write-Host "  Warning: takeown exit code: $($takeownResult.ExitCode)" -ForegroundColor Yellow
}

# Grant full control recursively
Write-Host "  Granting full permissions..." -ForegroundColor Cyan
$icaclsResult = Start-Process -FilePath "icacls" -ArgumentList $chromiumPath, "/grant", "${currentUser}:F", "/T", "/C" -NoNewWindow -Wait -PassThru
if ($icaclsResult.ExitCode -eq 0) {
    Write-Host "  Permissions granted successfully" -ForegroundColor Green
} else {
    Write-Host "  Warning: icacls exit code: $($icaclsResult.ExitCode)" -ForegroundColor Yellow
}

Start-Sleep -Seconds 1

# Step 3: Remove read-only attributes (handle errors gracefully)
Write-Host ""
Write-Host "Step 3: Removing read-only attributes..." -ForegroundColor Cyan
$errorCount = 0
Get-ChildItem $chromiumPath -Recurse -Force -ErrorAction SilentlyContinue | ForEach-Object {
    try {
        if ($_.PSIsContainer) {
            # Directory
            $_.Attributes = "Directory"
        } else {
            # File - remove read-only
            $_.Attributes = $_.Attributes -band (-bnot [System.IO.FileAttributes]::ReadOnly)
        }
    } catch {
        $errorCount++
        # Ignore individual file errors
    }
}
if ($errorCount -gt 0) {
    Write-Host "  Warning: Could not modify attributes for $errorCount items (may be locked)" -ForegroundColor Yellow
} else {
    Write-Host "  Attributes removed successfully" -ForegroundColor Green
}

# Step 4: Force delete (try multiple methods)
Write-Host ""
Write-Host "Step 4: Deleting folder..." -ForegroundColor Cyan

# Method 1: PowerShell Remove-Item
try {
    Remove-Item $chromiumPath -Recurse -Force -ErrorAction Stop
    Write-Host ""
    Write-Host "SUCCESS: Folder deleted using PowerShell!" -ForegroundColor Green
    exit 0
} catch {
    Write-Host "  Method 1 failed: $($_.Exception.Message)" -ForegroundColor Yellow
}

# Method 2: Use cmd.exe rmdir (sometimes more reliable)
Write-Host "  Trying alternative method (cmd rmdir)..." -ForegroundColor Cyan
$rmdirResult = Start-Process -FilePath "cmd.exe" -ArgumentList "/c", "rmdir", "/s", "/q", "`"$chromiumPath`"" -NoNewWindow -Wait -PassThru
if (-not (Test-Path $chromiumPath)) {
    Write-Host ""
    Write-Host "SUCCESS: Folder deleted using cmd rmdir!" -ForegroundColor Green
    exit 0
} else {
    Write-Host "  Method 2 failed (exit code: $($rmdirResult.ExitCode))" -ForegroundColor Yellow
}

# Method 3: Delete files individually, then folder
Write-Host "  Trying method 3 (delete files individually)..." -ForegroundColor Cyan
try {
    Get-ChildItem $chromiumPath -Recurse -Force -ErrorAction SilentlyContinue | 
        Where-Object { -not $_.PSIsContainer } | 
        ForEach-Object {
            try {
                Remove-Item $_.FullName -Force -ErrorAction SilentlyContinue
            } catch {
                # Ignore individual file errors
            }
        }
    
    # Now try to delete directories (bottom-up)
    Get-ChildItem $chromiumPath -Recurse -Force -ErrorAction SilentlyContinue | 
        Where-Object { $_.PSIsContainer } | 
        Sort-Object { $_.FullName.Length } -Descending | 
        ForEach-Object {
            try {
                Remove-Item $_.FullName -Force -ErrorAction SilentlyContinue
            } catch {
                # Ignore individual directory errors
            }
        }
    
    # Finally delete the main folder
    Remove-Item $chromiumPath -Force -ErrorAction SilentlyContinue
    
    if (-not (Test-Path $chromiumPath)) {
        Write-Host ""
        Write-Host "SUCCESS: Folder deleted using method 3!" -ForegroundColor Green
        exit 0
    }
} catch {
    Write-Host "  Method 3 failed" -ForegroundColor Yellow
}

# If all methods failed
Write-Host ""
Write-Host "ERROR: All deletion methods failed" -ForegroundColor Red
Write-Host ""
Write-Host "The folder is likely locked by Windows or another process." -ForegroundColor Yellow
Write-Host ""
Write-Host "Try these solutions:" -ForegroundColor Cyan
Write-Host "  1. RESTART YOUR COMPUTER (most reliable solution)" -ForegroundColor White
Write-Host "     After restart, run this script again" -ForegroundColor Gray
Write-Host ""
Write-Host "  2. Close ALL programs (especially VS Code, browsers, terminals)" -ForegroundColor White
Write-Host "     Then run this script again" -ForegroundColor Gray
Write-Host ""
Write-Host "  3. Use Windows Safe Mode:" -ForegroundColor White
Write-Host "     - Restart and hold Shift" -ForegroundColor Gray
Write-Host "     - Boot into Safe Mode" -ForegroundColor Gray
Write-Host "     - Delete the folder manually" -ForegroundColor Gray
Write-Host ""
Write-Host "  4. Use Playwright's reinstall (may work):" -ForegroundColor White
Write-Host "     python -m playwright install chromium --force" -ForegroundColor Gray
Write-Host ""
exit 1

Write-Host ""
Write-Host "Done! You can now reinstall browsers with: python -m playwright install chromium" -ForegroundColor Green
