@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>&1
if errorlevel 1 goto sinpython
py -3.12 -c "import sys; assert sys.maxsize > 2**32" >nul 2>&1
if errorlevel 1 goto sinpython
if not exist ".venv\Scripts\python.exe" py -3.12 -m venv .venv
if errorlevel 1 goto error
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto error
echo Instalacion completada. Abre INICIAR_HIDRO_VISION.cmd.
pause
exit /b 0
:sinpython
echo Instala Python 3.12 de 64 bits desde https://www.python.org/downloads/windows/
echo Incluye el lanzador py durante la instalacion. Luego vuelve a ejecutar este archivo.
pause
exit /b 1
:error
echo No se completo la instalacion. Revisa el mensaje anterior y tu conexion a internet.
pause
exit /b 1
