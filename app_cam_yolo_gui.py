import threading
import time
import cv2
import torch
from ultralytics import YOLO
from tkinter import Tk, Label, Button, Entry, StringVar, DoubleVar, Scale, HORIZONTAL, filedialog, ttk
from PIL import Image, ImageTk
import os
import json
import tempfile
from yt_dlp import YoutubeDL

SETTINGS_FILE = "settings.json"

class YoloCamApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Sistema de Inspección Visual por IA - Control de Calidad")
        self.root.geometry("1280x800")
        # Configurar tema y estilos
        self.setup_styles()
        
        # Cargar logo de la empresa
        self.load_company_logo()

        # --- Estado ---
        self.model = None
        self.cap = None
        self.running = False
        self.frame_lock = threading.Lock()
        self.current_frame = None
        self.device = "cuda:0" if torch.cuda.is_available() else "cpu"
        self.yt_video_path = None
        self.youtube_url = StringVar()
        self.cookie_path = StringVar(value="")

        # Cargar settings si existen
        self.settings = self.load_settings()

        # --- Variables UI ---
        self.model_path = StringVar(value=self.settings.get("MODEL_PATH", "best.pt"))
        self.source_str = StringVar(value=str(self.settings.get("SOURCE", "0")))
        self.confidence = DoubleVar(value=float(self.settings.get("CONFIDENCE", 0.30)))

        # --- Panel principal ---
        main_container = ttk.Frame(root, style="Corporate.TFrame")
        main_container.pack(fill="both", expand=True, padx=10, pady=5)

        # Header con logo y título
        header_frame = ttk.Frame(main_container, style="Corporate.TFrame")
        header_frame.pack(fill="x", pady=(0, 10))
        
        # Frame para el logo
        self.logo_frame = ttk.Frame(header_frame, style="Corporate.TFrame", width=260, height=100)
        self.logo_frame.pack(side="left", padx=(15,25), pady=10)
        self.logo_frame.pack_propagate(False)  # Mantener tamaño fijo
        
        # Label para el logo
        self.logo_label = ttk.Label(self.logo_frame, style="Corporate.TLabel", background=self.COLORS["secondary"])
        self.logo_label.pack(fill="both", expand=True, padx=5)
        
        # Título
        title_label = ttk.Label(header_frame, 
                              text="Sistema de Inspección Visual Automatizada",
                              style="Header.TLabel")
        title_label.pack(side="left", pady=5)

        # Panel de configuración
        config_frame = ttk.LabelFrame(main_container, text="Configuración del Sistema", style="Corporate.TFrame")
        config_frame.pack(fill="x", padx=5, pady=5)

        # Frame para modelo
        model_frame = ttk.Frame(config_frame, style="Corporate.TFrame")
        model_frame.pack(fill="x", padx=10, pady=5)
        ttk.Label(model_frame, text="Modelo de IA:", style="Corporate.TLabel").pack(side="left")
        self.entry_model = ttk.Entry(model_frame, textvariable=self.model_path, style="Corporate.TEntry")
        self.entry_model.pack(side="left", fill="x", expand=True, padx=5)
        ttk.Button(model_frame, text="📁 Buscar", 
                   command=self.browse_model, style="Corporate.TButton").pack(side="left", padx=2)
        ttk.Button(model_frame, text="Cargar Modelo", 
                   command=self.load_model, style="Corporate.TButton").pack(side="left", padx=2)

        # Frame para fuente de video
        source_frame = ttk.Frame(config_frame, style="Corporate.TFrame")
        source_frame.pack(fill="x", padx=10, pady=5)
        ttk.Label(source_frame, text="Fuente de Video:", 
                 style="Corporate.TLabel").pack(side="left")
        self.entry_source = ttk.Entry(source_frame, textvariable=self.source_str, 
                                    style="Corporate.TEntry")
        self.entry_source.pack(side="left", fill="x", expand=True, padx=5)

        # Frame para parámetros
        params_frame = ttk.LabelFrame(config_frame, text="Parámetros de Detección", 
                                    style="Corporate.TFrame")
        params_frame.pack(fill="x", padx=10, pady=5)
        
        # Configuración de confianza
        conf_frame = ttk.Frame(params_frame, style="Corporate.TFrame")
        conf_frame.pack(fill="x", padx=10, pady=5)
        ttk.Label(conf_frame, text="Umbral de Confianza:", 
                 style="Corporate.TLabel").pack(side="left")
        Scale(conf_frame, from_=0.05, to=0.90, resolution=0.05,
              orient=HORIZONTAL, variable=self.confidence, 
              length=240, bg=self.COLORS["secondary"],
              troughcolor=self.COLORS["primary"],
              activebackground=self.COLORS["primary"]).pack(side="left", padx=10)

        # Panel de fuentes de video
        sources_frame = ttk.LabelFrame(main_container, text="Fuentes de Video", 
                                     style="Corporate.TFrame")
        sources_frame.pack(fill="x", padx=5, pady=5)

        # Pestañas de fuentes
        self.tab_control = ttk.Notebook(sources_frame, style="Corporate.TNotebook")
        
        # Pestaña de cámara/RTSP
        self.tab_camera = ttk.Frame(self.tab_control, style="Corporate.TFrame")
        self.tab_control.add(self.tab_camera, text='Cámara IP/RTSP')
        
        # Pestaña de video local
        self.tab_video = ttk.Frame(self.tab_control, style="Corporate.TFrame")
        self.tab_control.add(self.tab_video, text='Video Local')
        
        # Pestaña de inspección de soldadura
        self.tab_weld = ttk.Frame(self.tab_control, style="Corporate.TFrame")
        self.tab_control.add(self.tab_weld, text='Inspección de Soldadura')
        
        self.tab_control.pack(expand=1, fill="x", padx=5, pady=5)
        
        # Variables para control de video
        self.video_path = StringVar()
        self.video_position = DoubleVar(value=0.0)
        self.is_playing = False
        self.total_frames = 0
        self.current_frame_pos = 0
        
        # Configurar pestaña de video local
        video_content = ttk.Frame(self.tab_video, style="Corporate.TFrame")
        video_content.pack(fill="both", expand=True, padx=10, pady=10)

        # Sección de selección de archivo
        file_section = ttk.LabelFrame(video_content, text="Archivo de Video", 
                                    style="Corporate.TFrame")
        file_section.pack(fill="x", pady=(0, 10))
        
        file_frame = ttk.Frame(file_section, style="Corporate.TFrame")
        file_frame.pack(fill="x", padx=10, pady=5)
        self.video_entry = ttk.Entry(file_frame, textvariable=self.video_path, 
                                   style="Corporate.TEntry")
        self.video_entry.pack(side="left", fill="x", expand=True, padx=(0,5))
        ttk.Button(file_frame, text="📁 Abrir Video", 
                  command=self.browse_video, 
                  style="Corporate.TButton").pack(side="left")

        # Controles de reproducción
        playback_section = ttk.LabelFrame(video_content, text="Control de Reproducción", 
                                        style="Corporate.TFrame")
        playback_section.pack(fill="x")
        
        # Barra de progreso
        progress_frame = ttk.Frame(playback_section, style="Corporate.TFrame")
        progress_frame.pack(fill="x", padx=10, pady=5)
        self.progress_scale = ttk.Scale(progress_frame, from_=0, to=100,
                                      orient="horizontal", variable=self.video_position,
                                      command=self.seek_video)
        self.progress_scale.pack(fill="x", padx=5)
        
        # Botones de control
        controls_frame = ttk.Frame(playback_section, style="Corporate.TFrame")
        controls_frame.pack(fill="x", padx=10, pady=5)
        
        ttk.Button(controls_frame, text="⏮ Inicio", 
                  command=self.video_to_start,
                  style="Corporate.TButton").pack(side="left", padx=2)
        self.play_button = ttk.Button(controls_frame, text="▶ Reproducir", 
                                    command=self.toggle_play,
                                    style="Corporate.TButton")
        self.play_button.pack(side="left", padx=2)
        ttk.Button(controls_frame, text="⏸ Pausar", 
                  command=self.pause_video,
                  style="Corporate.TButton").pack(side="left", padx=2)
        
        # Frame counter
        self.frame_label = ttk.Label(controls_frame, 
                                   text="Frame: 0/0",
                                   style="Status.TLabel")
        self.frame_label.pack(side="right", padx=5)

        # Configurar pestaña de inspección de soldadura
        weld_content = ttk.Frame(self.tab_weld, style="Corporate.TFrame")
        weld_content.pack(fill="both", expand=True, padx=10, pady=10)

        # Sección de carga de imagen
        img_section = ttk.LabelFrame(weld_content, text="Imagen de Soldadura", 
                                   style="Corporate.TFrame")
        img_section.pack(fill="x", pady=(0, 10))
        
        img_frame = ttk.Frame(img_section, style="Corporate.TFrame")
        img_frame.pack(fill="x", padx=10, pady=5)
        ttk.Button(img_frame, text="📁 Cargar Imagen", 
                  command=self.load_weld_image, 
                  style="Corporate.TButton").pack(side="left")
        ttk.Button(img_frame, text="🔍 Analizar Soldadura", 
                  command=self.analyze_weld,
                  style="Corporate.TButton").pack(side="left", padx=5)

        # Parámetros de análisis
        params_section = ttk.LabelFrame(weld_content, text="Parámetros de Análisis", 
                                      style="Corporate.TFrame")
        params_section.pack(fill="x")
        
        # Aquí puedes agregar más parámetros específicos para el análisis de soldadura
        
        # Panel de visualización
        display_frame = ttk.LabelFrame(main_container, text="Visualización en Tiempo Real", 
                                     style="Corporate.TFrame")
        display_frame.pack(fill="both", expand=True, padx=5, pady=5)

        # Controles principales
        controls_frame = ttk.Frame(display_frame, style="Corporate.TFrame")
        controls_frame.pack(fill="x", padx=5, pady=5)
        
        # Grupo de botones principales
        main_btns = ttk.Frame(controls_frame, style="Corporate.TFrame")
        main_btns.pack(side="left")
        ttk.Button(main_btns, text="▶️ Iniciar Inspección", 
                  command=self.start_camera, style="Corporate.TButton").pack(side="left", padx=2)
        ttk.Button(main_btns, text="⏹ Detener", 
                  command=self.stop_camera, style="Corporate.TButton").pack(side="left", padx=2)
        ttk.Button(main_btns, text="� Capturar", 
                  command=self.save_snapshot, style="Corporate.TButton").pack(side="left", padx=2)
        
        # Grupo de botones secundarios
        secondary_btns = ttk.Frame(controls_frame, style="Corporate.TFrame")
        secondary_btns.pack(side="right")
        ttk.Button(secondary_btns, text="💾 Guardar Config", 
                  command=self.save_settings, style="Corporate.TButton").pack(side="left", padx=2)
        ttk.Button(secondary_btns, text="Salir", 
                  command=self.on_close, style="Corporate.TButton").pack(side="left", padx=2)

        # Panel de estado
        status_frame = ttk.Frame(display_frame, style="Corporate.TFrame")
        status_frame.pack(fill="x", padx=5)
        
        self.info_label = ttk.Label(status_frame, 
                                  text=f"Estado: Sistema Listo | Dispositivo: {self.device} | Modelo: (no cargado)", 
                                  style="Status.TLabel")
        self.info_label.pack(side="left", padx=5)
        
        self.fps_label = ttk.Label(status_frame, text="FPS: -", 
                                 style="Status.TLabel")
        self.fps_label.pack(side="right", padx=5)

        # Área de visualización
        self.img_label = Label(display_frame, bg="#000000")
        self.img_label.pack(fill="both", expand=True, padx=5, pady=5)

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    # --- Settings ---
    def load_settings(self):
        try:
            if os.path.exists(SETTINGS_FILE):
                with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception as e:
            print(f"[WARN] No se pudieron cargar settings: {e}")
        return {}

    def save_settings(self):
        data = {
            "MODEL_PATH": self.model_path.get().strip(),
            "SOURCE": self.source_str.get().strip(),
            "CONFIDENCE": float(self.confidence.get())
        }
        try:
            with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            self.info_label.config(text="✅ Configuración guardada en settings.json")
        except Exception as e:
            self.info_label.config(text=f"❌ Error al guardar settings: {e}")

    # --- Acciones UI ---
    def browse_model(self):
        path = filedialog.askopenfilename(
            title="Selecciona tu modelo .pt",
            filetypes=[("PyTorch model", "*.pt"), ("Todos", "*.*")]
        )
        if path:
            self.model_path.set(path)

    def load_model(self):
        path = self.model_path.get().strip()
        if not os.path.exists(path):
            self.info_label.config(text=f"❌ Modelo no encontrado: {path}")
            return
        try:
            self.model = YOLO(path)
            self.info_label.config(text=f"Dispositivo: {self.device} | Modelo cargado: {os.path.basename(path)}")
        except Exception as e:
            self.info_label.config(text=f"❌ Error al cargar modelo: {e}")

    def start_camera(self):
        if self.running:
            return
        if self.model is None:
            self.info_label.config(text="❗ Carga primero un modelo (.pt).")
            return

        source = self.source_str.get().strip()
        # Soporta índice numérico (webcam) o URL (RTSP/HTTP)
        src = int(source) if source.isdigit() else source

        self.cap = cv2.VideoCapture(src)
        if not self.cap.isOpened():
            self.info_label.config(text=f"❌ No se pudo abrir la fuente: {source}")
            return

        self.running = True
        self.info_label.config(text=f"▶️ Cámara iniciada ({source}) con {os.path.basename(self.model_path.get())} en {self.device}")
        threading.Thread(target=self.loop, daemon=True).start()
        self.update_ui_frame()

    def stop_camera(self):
        self.running = False
        if self.cap and self.cap.isOpened():
            self.cap.release()
        self.img_label.config(image="")
        self.fps_label.config(text="FPS: -")
        self.info_label.config(text="⏹ Cámara detenida.")

    def save_snapshot(self):
        if self.current_frame is not None:
            filename = f"snapshot_{int(time.time())}.jpg"
            with self.frame_lock:
                cv2.imwrite(filename, self.current_frame)
            self.info_label.config(text=f"✅ Snapshot guardado: {filename}")
            
    def browse_video(self):
        path = filedialog.askopenfilename(
            title="Seleccionar Video",
            filetypes=[("Videos", "*.mp4 *.avi *.mkv"), ("Todos", "*.*")]
        )
        if path:
            self.video_path.set(path)
            self.load_video_file(path)
    
    def load_video_file(self, path):
        try:
            self.cap = cv2.VideoCapture(path)
            if not self.cap.isOpened():
                raise Exception("No se pudo abrir el archivo de video")
            
            # Obtener información del video
            self.total_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
            self.fps = self.cap.get(cv2.CAP_PROP_FPS)
            self.current_frame_pos = 0
            
            # Configurar barra de progreso
            self.progress_scale.configure(to=self.total_frames)
            self.video_position.set(0)
            self.update_frame_counter()
            
            # Actualizar fuente
            self.source_str.set(path)
            self.info_label.config(text=f"✅ Video cargado: {os.path.basename(path)}")
            
        except Exception as e:
            self.info_label.config(text=f"❌ Error al cargar video: {str(e)}")
            
    def seek_video(self, *args):
        if self.cap and self.cap.isOpened():
            pos = int(self.video_position.get())
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, pos)
            self.current_frame_pos = pos
            self.update_frame_counter()
            
    def toggle_play(self):
        if not self.running:
            self.is_playing = True
            self.play_button.configure(text="⏸ Pausar")
            self.start_camera()
        else:
            self.pause_video()
            
    def pause_video(self):
        self.is_playing = False
        self.running = False
        self.play_button.configure(text="▶ Reproducir")
        
    def video_to_start(self):
        if self.cap and self.cap.isOpened():
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            self.current_frame_pos = 0
            self.video_position.set(0)
            self.update_frame_counter()
            
    def update_frame_counter(self):
        self.frame_label.configure(text=f"Frame: {self.current_frame_pos}/{self.total_frames}")
        
    def load_weld_image(self):
        path = filedialog.askopenfilename(
            title="Seleccionar Imagen de Soldadura",
            filetypes=[("Imágenes", "*.jpg *.jpeg *.png *.bmp"), ("Todos", "*.*")]
        )
        if path:
            try:
                # Cargar imagen
                self.current_frame = cv2.imread(path)
                if self.current_frame is None:
                    raise Exception("No se pudo cargar la imagen")
                
                # Mostrar en interfaz
                self.source_str.set(path)
                self.info_label.config(text=f"✅ Imagen cargada: {os.path.basename(path)}")
                
                # Actualizar visualización
                frame_rgb = cv2.cvtColor(self.current_frame, cv2.COLOR_BGR2RGB)
                self.update_image_display(frame_rgb)
                
            except Exception as e:
                self.info_label.config(text=f"❌ Error al cargar imagen: {str(e)}")
                
    def analyze_weld(self):
        if self.current_frame is None:
            self.info_label.config(text="❌ Primero carga una imagen de soldadura")
            return
            
        try:
            if self.model is None:
                self.info_label.config(text="❗ Carga primero un modelo (.pt)")
                return
                
            # Realizar inferencia
            results = self.model.predict(
                self.current_frame,
                conf=float(self.confidence.get()),
                imgsz=640,
                device=self.device,
                verbose=False
            )
            
            # Procesar resultados
            annotated = results[0].plot()
            
            # Mostrar resultados
            frame_rgb = cv2.cvtColor(annotated, cv2.COLOR_BGR2RGB)
            self.update_image_display(frame_rgb)
            
            # Actualizar info
            num_defects = len(results[0].boxes)
            self.info_label.config(text=f"✅ Análisis completado: {num_defects} defectos detectados")
            
        except Exception as e:
            self.info_label.config(text=f"❌ Error en análisis: {str(e)}")
            
    def update_image_display(self, frame):
        if frame is not None:
            img_pil = Image.fromarray(frame)
            w = self.img_label.winfo_width() or 960
            h = self.img_label.winfo_height() or 540
            img_pil = img_pil.resize(self.fit_within(img_pil.size, (w, h)), Image.LANCZOS)
            imgtk = ImageTk.PhotoImage(image=img_pil)
            self.img_label.imgtk = imgtk
            self.img_label.configure(image=imgtk)
            
    def load_company_logo(self):
        """Cargar y mostrar el logo de la empresa"""
        try:
            # Cargar y redimensionar el logo
            logo_img = Image.open("logo.png")
            
            # Calcular nuevo tamaño manteniendo proporción
            logo_width = 240  # Ancho máximo deseado
            aspect_ratio = logo_img.width / logo_img.height
            logo_height = int(logo_width / aspect_ratio)
            
            # Asegurarse de que la altura no exceda el máximo
            max_height = 90
            if logo_height > max_height:
                logo_height = max_height
                logo_width = int(max_height * aspect_ratio)
            
            logo_img = logo_img.resize((logo_width, logo_height), Image.Resampling.LANCZOS)
            logo_photo = ImageTk.PhotoImage(logo_img)
            
            # Mostrar el logo
            self.logo_label.configure(image=logo_photo)
            self.logo_label.image = logo_photo  # Mantener referencia
            
            # Ajustar el tamaño del frame del logo
            self.logo_frame.configure(width=logo_width + 20, height=logo_height + 10)
            
        except Exception as e:
            print(f"Error al cargar el logo: {e}")
            
    def load_youtube_video(self):
        try:
            url = self.youtube_url.get()
            if not url:
                self.info_label.config(text="❌ Por favor, introduce una URL de YouTube")
                return
                
            self.info_label.config(text="⏳ Descargando video de YouTube...")
            self.root.update()
            # Convertir URL de shorts a formato normal (si aplica)
            if '/shorts/' in url:
                video_id = url.split('/shorts/')[1].split('?')[0]
                url = f'https://www.youtube.com/watch?v={video_id}'

            # Crear directorio temporal si no existe
            temp_dir = os.path.join(tempfile.gettempdir(), "yolo_cam_gui")
            os.makedirs(temp_dir, exist_ok=True)

            # Primero intentamos obtener una URL directa de streaming (sin descargar completo)
            ytdl_opts_stream = {
                'format': 'best',
                'noplaylist': True,
                'quiet': True,
                'no_warnings': True,
                'geo_bypass': True,
            }
            # Añadir cookiefile si fue proporcionado
            if self.cookie_path.get():
                ytdl_opts_stream['cookiefile'] = self.cookie_path.get()

            direct_url = None
            info = None
            try:
                with YoutubeDL(ytdl_opts_stream) as ydl:
                    info = ydl.extract_info(url, download=False)
                    # Buscar en formatos una URL http/https/m3u8 que OpenCV pueda abrir
                    formats = info.get('formats') if isinstance(info, dict) else None
                    if formats:
                        # Prefer mp4/http progressive formats
                        for f in reversed(formats):
                            fproto = f.get('protocol')
                            fext = f.get('ext')
                            furl = f.get('url')
                            if not furl:
                                continue
                            if fproto in ('https', 'http', 'm3u8_native', 'm3u8_dash'):
                                # prefer mp4/webm if present
                                if fext in ('mp4', 'webm') or 'dash' in fproto or 'm3u8' in fproto:
                                    direct_url = furl
                                    break
                        # If still not found, take best format url
                        if not direct_url and formats:
                            direct_url = formats[-1].get('url')
            except Exception as e_stream:
                # no pasa nada, intentamos fallback a descarga completa
                print('yt-dlp extract_info stream failed:', e_stream)

            # Si tenemos una URL directa, intentamos usarla sin descargar
            if direct_url:
                # Probar abrir con OpenCV
                test_cap = cv2.VideoCapture(direct_url)
                time.sleep(0.5)
                if test_cap.isOpened():
                    test_cap.release()
                    self.source_str.set(direct_url)
                    title = info.get('title') if isinstance(info, dict) else 'YouTube stream'
                    self.info_label.config(text=f"✅ Stream directo disponible: {title}")
                    return
                else:
                    print('OpenCV no pudo abrir el stream directo, fallback a descarga')
                    try:
                        test_cap.release()
                    except:
                        pass

            # Si no hay URL directa o OpenCV no la abrió, descargamos el archivo localmente
            ytdl_opts_download = {
                'format': 'mp4[ext=mp4]+bestaudio/best',
                'outtmpl': os.path.join(temp_dir, 'yt_video_%(id)s.%(ext)s'),
                'noplaylist': True,
                'quiet': True,
                'no_warnings': True,
                'retries': 3,
                'geo_bypass': True,
            }
            if self.cookie_path.get():
                ytdl_opts_download['cookiefile'] = self.cookie_path.get()

            with YoutubeDL(ytdl_opts_download) as ydl:
                info = ydl.extract_info(url, download=True)
                vid_id = info.get('id') if isinstance(info, dict) else None
                ext = info.get('ext') if isinstance(info, dict) else 'mp4'
                if vid_id:
                    self.yt_video_path = os.path.join(temp_dir, f"yt_video_{vid_id}.{ext}")
                else:
                    files = [os.path.join(temp_dir, f) for f in os.listdir(temp_dir)]
                    files = [f for f in files if os.path.isfile(f)]
                    files.sort(key=lambda x: os.path.getmtime(x), reverse=True)
                    self.yt_video_path = files[0] if files else None

            # Verificar que el archivo se descargó correctamente
            if not self.yt_video_path or not os.path.exists(self.yt_video_path) or os.path.getsize(self.yt_video_path) == 0:
                raise Exception('Error en la descarga del archivo con yt-dlp')

            # Actualizar fuente local
            self.source_str.set(self.yt_video_path)
            title = info.get('title') if isinstance(info, dict) else os.path.basename(self.yt_video_path)
            self.info_label.config(text=f"✅ Video descargado: {title}")
            
        except Exception as e:
            error_msg = str(e)
            if "HTTP Error 400" in error_msg:
                error_msg = "Error al acceder al video. Asegúrate de que el video es público y la URL es correcta."
            self.info_label.config(text=f"❌ Error al cargar video: {error_msg}")
            print(f"Error detallado: {error_msg}")

    def on_close(self):
        self.stop_camera()
        self.root.after(200, self.root.destroy)

    def browse_cookies(self):
        path = filedialog.askopenfilename(
            title="Selecciona cookies.txt (opcional)",
            filetypes=[("Cookies", "*.txt;*.cookies"), ("Todos", "*")]
        )
        if path:
            self.cookie_path.set(path)

    # --- Bucle de captura e inferencia (thread) ---
    def loop(self):
        prev_time = time.time()
        while self.running and self.cap and self.cap.isOpened():
            if hasattr(self, 'video_path') and self.video_path.get():
                # Modo reproducción de video
                if not self.is_playing:
                    time.sleep(0.1)
                    continue
                    
                ok, frame_bgr = self.cap.read()
                if not ok:
                    # Fin del video
                    self.pause_video()
                    continue
                    
                # Actualizar posición
                self.current_frame_pos = int(self.cap.get(cv2.CAP_PROP_POS_FRAMES))
                self.video_position.set(self.current_frame_pos)
                self.update_frame_counter()
            else:
                # Modo cámara en vivo
                ok, frame_bgr = self.cap.read()
                if not ok:
                    time.sleep(0.01)
                    continue

            # Inferencia
            try:
                results = self.model.predict(
                    frame_bgr,
                    conf=float(self.confidence.get()),
                    imgsz=640,
                    device=self.device,
                    verbose=False
                )
                annotated = results[0].plot()  # BGR
                
                # Agregar información de defectos si es análisis de soldadura
                if hasattr(self, 'tab_weld'):
                    num_defects = len(results[0].boxes)
                    cv2.putText(annotated, f"Defectos: {num_defects}", (10, 60),
                              cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                    
            except Exception as e:
                annotated = frame_bgr
                cv2.putText(annotated, f"Error inferencia: {e}", (10, 30),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

            # BGR->RGB para Tkinter
            frame_rgb = cv2.cvtColor(annotated, cv2.COLOR_BGR2RGB)

            # FPS simple
            now = time.time()
            fps = 1.0 / max(1e-6, (now - prev_time))
            prev_time = now
            cv2.putText(frame_rgb, f"FPS: {fps:.1f}", (10, 30),
                       cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)

            with self.frame_lock:
                self.current_frame = frame_rgb

        # Fin del hilo
        self.running = False

    # --- Refresco UI (main thread) ---
    def update_ui_frame(self):
        with self.frame_lock:
            frame = self.current_frame.copy() if self.current_frame is not None else None

        if frame is not None:
            img_pil = Image.fromarray(frame)
            # Ajuste a la ventana manteniendo proporción
            w = self.img_label.winfo_width() or 960
            h = self.img_label.winfo_height() or 540
            img_pil = img_pil.resize(self.fit_within(img_pil.size, (w, h)), Image.LANCZOS)
            imgtk = ImageTk.PhotoImage(image=img_pil)
            self.img_label.imgtk = imgtk  # evitar GC
            self.img_label.configure(image=imgtk)

        if self.running:
            self.root.after(15, self.update_ui_frame)  # ~66 FPS máx UI
        else:
            self.img_label.config(image="")

    @staticmethod
    def fit_within(img_size, box_size):
        iw, ih = img_size
        bw, bh = box_size
        scale = min(bw / max(1, iw), bh / max(1, ih))
        return (max(1, int(iw * scale)), max(1, int(ih * scale)))


    def setup_styles(self):
        style = ttk.Style()
        # Usar tema clam como base
        try:
            style.theme_use("clam")
        except:
            pass

        # Colores corporativos
        PRIMARY_COLOR = "#004d99"  # Azul corporativo
        SECONDARY_COLOR = "#e6e6e6"  # Gris claro
        ACCENT_COLOR = "#00264d"  # Azul oscuro
        SUCCESS_COLOR = "#006633"  # Verde oscuro
        WARNING_COLOR = "#cc6600"  # Naranja
        ERROR_COLOR = "#990000"  # Rojo oscuro

        # Configurar estilos personalizados
        style.configure("Corporate.TFrame", background=SECONDARY_COLOR)
        style.configure("Corporate.TLabel", background=SECONDARY_COLOR, foreground="#000000", font=("Segoe UI", 10))
        style.configure("Header.TLabel", background=PRIMARY_COLOR, foreground="white", font=("Segoe UI", 11, "bold"))
        style.configure("Status.TLabel", background="#f0f0f0", foreground="#333333", font=("Segoe UI", 9))
        style.configure("Corporate.TButton", 
                    background=PRIMARY_COLOR, 
                    foreground="white",
                    padding=(10, 5),
                    font=("Segoe UI", 9, "bold"))
        style.map("Corporate.TButton",
                background=[("active", ACCENT_COLOR), ("disabled", SECONDARY_COLOR)],
                foreground=[("disabled", "#666666")])
        
        # Estilo para pestañas
        style.configure("Corporate.TNotebook", background=SECONDARY_COLOR, padding=2)
        style.configure("Corporate.TNotebook.Tab", 
                    padding=(10, 4),
                    font=("Segoe UI", 9))
        style.map("Corporate.TNotebook.Tab",
                background=[("selected", PRIMARY_COLOR), ("!selected", SECONDARY_COLOR)],
                foreground=[("selected", "white"), ("!selected", "black")])

        # Estilo para entradas
        style.configure("Corporate.TEntry", 
                    padding=5,
                    selectbackground=PRIMARY_COLOR)

        # Configurar colores de mensajes
        self.COLORS = {
            "success": SUCCESS_COLOR,
            "warning": WARNING_COLOR,
            "error": ERROR_COLOR,
            "primary": PRIMARY_COLOR,
            "secondary": SECONDARY_COLOR
        }

if __name__ == "__main__":
    app = Tk()
    app.configure(background="#e6e6e6")  # Fondo principal
    YoloCamApp(app)
    app.mainloop()
