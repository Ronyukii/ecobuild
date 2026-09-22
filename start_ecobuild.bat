@echo off
echo ==============================================================================
echo Starting EcoBuild Single-Tunnel Stack (FastAPI + Vite Proxy + Cloudflare)
echo ==============================================================================

:: 1. Start Backend (FastAPI on Port 8000)
start "EcoBuild Backend (Port 8000)" cmd /k "cd /d D:\Projects\CSP600\ecobuild\backend && python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload"

:: 2. Start Frontend (Vite on Port 5173 with /api Proxy)
start "EcoBuild Frontend (Port 5173)" cmd /k "cd /d D:\Projects\CSP600\ecobuild\frontend && npm run dev"

:: Wait 3 seconds for local servers to initialize
timeout /t 3 /nobreak >nul

:: 3. Start Single Cloudflare Tunnel (Serves Frontend + Proxies API via /api)
start "Cloudflare Public Tunnel" cmd /k "cloudflared tunnel --url http://localhost:5173"

echo.
echo ==============================================================================
echo All 3 services are running!
echo Look at the "Cloudflare Public Tunnel" window to copy your live HTTPS link.
echo ==============================================================================