@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Primero ejecuta INSTALAR_WINDOWS.cmd.
  pause
  exit /b 1
)
echo Abre http://127.0.0.1:8765/ en tu navegador.
echo Manten esta ventana abierta. Para detener el servidor pulsa Ctrl+C.
".venv\Scripts\python.exe" server.py
pause
