@echo off
setlocal ENABLEDELAYEDEXPANSION

echo =============================================
echo  YOLOv11 Camera GUI - Setup & Run (Windows)
echo =============================================

REM Detectar Python
where python >nul 2>&1
if errorlevel 1 (
  echo [ERROR] Python no encontrado en PATH. Instala Python 3.10-3.12 y reintenta.
  pause
  exit /b 1
)

REM Crear venv si no existe
if not exist ".venv" (
  echo [INFO] Creando entorno virtual .venv ...
  python -m venv .venv
)

REM Activar venv
call .venv\Scripts\activate

REM Actualizar pip
python -m pip install --upgrade pip

REM Instalar requirements
echo [INFO] Instalando dependencias...
pip install -r requirements.txt

REM Lanzar app
echo [INFO] Lanzando aplicacion...
python app_cam_yolo_gui.py
pause
