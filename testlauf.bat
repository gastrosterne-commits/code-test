@echo off
cd /d "%~dp0"
echo Test-Lauf mit Musterdaten...
venv\Scripts\python test_run.py
pause
