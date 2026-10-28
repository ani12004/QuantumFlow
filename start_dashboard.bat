@echo off
cd /d "%~dp0"
echo Opening QuantumFlow at http://127.0.0.1:8765
echo Keep this window open while using the dashboard. Press Ctrl+C to stop.
python scripts\serve_dashboard.py --open
if errorlevel 1 pause
