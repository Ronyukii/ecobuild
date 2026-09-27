@echo off
title EcoBuild - Chrome CDP Debugger (Port 9222)

echo ======================================================================
echo   Launching EcoBuild Scraper Chrome (Remote Debugging Port: 9222)
echo ======================================================================

:: 1. Ensure the dedicated user profile directory exists
if not exist "D:\Projects\CSP600\ecobuild\backend\.real_chrome_profile" (
    echo [*] Creating profile folder...
    mkdir "D:\Projects\CSP600\ecobuild\backend\.real_chrome_profile"
)

:: 2. Launch Google Chrome with remote debugging enabled
start "" "C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222 --user-data-dir="D:\Projects\CSP600\ecobuild\backend\.real_chrome_profile"

echo.
echo [OK] Chrome launched on port 9222!
echo Keep the Chrome window running while scraping Shopee.
echo.

:: Automatically closes this black prompt window after 3 seconds
timeout /t 3 >nul
exit