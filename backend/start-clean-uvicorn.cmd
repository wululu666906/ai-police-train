@echo off
setlocal
cd /d "%~dp0"
set PYTHONHOME=
set PYTHONPATH=
set PYTHONNOUSERSITE=
set SSL_CERT_FILE=
set SSL_CERT_DIR=
set REQUESTS_CA_BUNDLE=
set CURL_CA_BUNDLE=
"%~dp0venv\Scripts\python.exe" -m uvicorn main:app --host 127.0.0.1 --port 8000
