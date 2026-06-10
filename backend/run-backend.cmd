@echo off
cd /d "%~dp0"
"D:\APP\load\Miniconda3\python.exe" run_backend.py 1>>backend-run.log 2>>backend-run.err.log
pause
