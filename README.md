# YOLOv11 Camera GUI (Visual Studio / VS Code)

Aplicación de escritorio (Tkinter) para ejecutar detección en vivo con YOLOv11 sobre webcam o RTSP.

## Contenido
- `app_cam_yolo_gui.py`: aplicación principal con interfaz (Tkinter).
- `requirements.txt`: dependencias mínimas.
- `run.bat`: crea un entorno virtual, instala dependencias y lanza la app.
- `settings.example.json`: ejemplo de configuración (ruta del modelo, fuente).
- Carpeta `snapshots/`: se crean automáticamente las capturas.

## Requisitos
- Windows 10/11
- Python 3.10–3.12 (64-bit) instalado y en PATH
- Visual Studio 2022 con workload de Python **o** VS Code

## Pasos rápidos (Visual Studio 2022)
1. **File → Open → Folder...** y elige esta carpeta del proyecto.
2. En el Explorador de Soluciones, clic derecho a `app_cam_yolo_gui.py` → **Set as Startup File**.
3. Ejecuta con el botón **Run** (▶️) o `Ctrl+F5`.

> Alternativa rápida en terminal: doble clic a `run.bat` o ejecútalo desde PowerShell.

## Configuración
- Por defecto el app busca `best.pt` en la misma carpeta.
- Para IP cam: pon en el campo **Fuente** la URL RTSP, p. ej. `rtsp://user:pass@192.168.1.120:554/stream1`.
- Ajusta la **confianza** con el slider para filtrar detecciones bajas.

## Consejos de rendimiento
- Si la ventana va lenta, baja `conf` o cambia `imgsz` interno a 512.
- Si tienes GPU NVIDIA y CUDA correctamente instalados, Ultralytics/torch la usarán automáticamente.
