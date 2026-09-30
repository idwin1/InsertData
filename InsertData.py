import os
import sys
import subprocess
import json
import csv
import threading
import io
from datetime import datetime
from faker import Faker
import random


# ==========================================
# 1. AUTO-INSTALADOR DE LIBRERÍAS
# ==========================================
LIBRERIAS_REQUERIDAS = {
    "colorama": "colorama",
    "customtkinter": "customtkinter",
    "pyodbc": "pyodbc",
    "psycopg2": "psycopg2-binary", 
    "PIL": "pillow"
}

def verificar_e_instalar_librerias():
    if getattr(sys, 'frozen', False):
        return

    for import_name, pip_name in LIBRERIAS_REQUERIDAS.items():
        try:
            __import__(import_name)
        except ImportError:
            print(f"[!] La librería '{import_name}' no está instalada.")
            print(f"[+] Instalando '{pip_name}' automáticamente...")
            try:
                subprocess.check_call([sys.executable, "-m", "pip", "install", pip_name])
                print(f"[✔] '{pip_name}' instalada con éxito.\n")
            except Exception as e:
                print(f"[❌] Error crítico al intentar instalar {pip_name}: {e}")
                sys.exit(1)

verificar_e_instalar_librerias()

import tkinter as tk
from tkinter import messagebox, filedialog
import customtkinter as ctk
import pyodbc
import psycopg2
import multiprocessing

# ==========================================
# 2. GESTIÓN DE CONFIGURACIÓN
# ==========================================
CONFIG_FILE = "config.json"
RELACIONES_FILE = "relaciones.json"

def cargar_configuracion():
    if not os.path.exists(CONFIG_FILE):
        return {"Servidores_BD": []}
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            datos = json.load(f)
            if "Servidores_SQL" in datos:
                datos["Servidores_BD"] = datos.pop("Servidores_SQL")
            elif "Servidores_BD" not in datos:
                datos["Servidores_BD"] = []
            return datos
    except Exception as e:
        print(f"Error al leer config.json: {e}")
        return {"Servidores_BD": []}

def guardar_configuracion(datos):
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(datos, f, indent=4, ensure_ascii=False)
    except Exception as e:
        messagebox.showerror("Error", f"No se pudo guardar la configuración: {e}")

def obtener_driver_sql():
    drivers = [x for x in pyodbc.drivers() if 'SQL Server' in x]
    return drivers[-1] if drivers else 'SQL Server'

def cargar_relaciones():
    # Si no existe, lo creamos inmediatamente con un JSON vacío
    if not os.path.exists(RELACIONES_FILE):
        try:
            with open(RELACIONES_FILE, "w", encoding="utf-8") as f:
                json.dump({}, f)
        except Exception as e:
            print(f"Advertencia: No se pudo crear el archivo {RELACIONES_FILE}: {e}")
        return {}
        
    try:
        with open(RELACIONES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

    

def guardar_relaciones(datos):
    try:
        with open(RELACIONES_FILE, "w", encoding="utf-8") as f:
            json.dump(datos, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"Error al guardar relaciones: {e}")

def migrar_estructura_json():
    memoria = cargar_relaciones()
    cambios = False
    
    for db_name, contenido in memoria.items():
        if "_configuracion_global" not in contenido:
            viejo_contenido = contenido.copy()
            memoria[db_name] = {
                "_configuracion_global": {
                    "orden_ejecucion": [],
                    "volumen_registros": {},
                    "modo_tablas": {} # NUEVO: Guardará si es "Generar" o "Solo Lectura"
                },
                "tablas": viejo_contenido
            }
            cambios = True
            
    if cambios:
        guardar_relaciones(memoria)
        print("✅ Archivo relaciones.json migrado a la estructura de Orquestador con Modos de Lectura.")

migrar_estructura_json()

# =========================================================
# 3. Class ToolTip: para agregar mensajes emergentes a cualquier widget de Tkinter
# =========================================================
class ToolTip:
    def __init__(self, widget, text, delay=600):
        self.widget = widget
        self.text = text
        self.delay = delay  # Tiempo en milisegundos (600ms = 0.6 segundos)
        self.tooltip_window = None
        self.timer_id = None
        
        try:
            self.widget.bind("<Enter>", self.al_entrar)
            self.widget.bind("<Leave>", self.al_salir)
            self.widget.bind("<ButtonPress>", self.al_salir)
        except NotImplementedError:
            # Si el widget (como CTkSegmentedButton) bloquea el .bind(),
            # lo vinculamos directamente a su lienzo (_canvas) interno.
            if hasattr(self.widget, "_canvas"):
                self.widget._canvas.bind("<Enter>", self.al_entrar)
                self.widget._canvas.bind("<Leave>", self.al_salir)
                self.widget._canvas.bind("<ButtonPress>", self.al_salir)

    def al_entrar(self, event=None):
        self.cancelar_temporizador() # Asegura que no haya duplicados
        # Programa la aparición de la ventana después de 'delay' milisegundos
        self.timer_id = self.widget.after(self.delay, self.mostrar_tooltip)

    def al_salir(self, event=None):
        self.cancelar_temporizador()
        self.ocultar_tooltip()

    def cancelar_temporizador(self):
        if self.timer_id:
            self.widget.after_cancel(self.timer_id)
            self.timer_id = None

    def mostrar_tooltip(self):
        if self.tooltip_window:
            return
            
        self.tooltip_window = tk.Toplevel(self.widget)
        self.tooltip_window.wm_overrideredirect(True)
        
        # 1. TRUCO DE TRANSPARENCIA MEJORADO
        # Usamos un negro casi puro ("#000001") en lugar de magenta para 
        # que el suavizado de bordes se funda con el tema oscuro sin dejar rastro.
        color_invisible = "#000001"
        self.tooltip_window.configure(bg=color_invisible)
        self.tooltip_window.wm_attributes("-transparentcolor", color_invisible)

        # 2. CONTENEDOR CON BORDES REDONDEADOS
        frame_tooltip = ctk.CTkFrame(self.tooltip_window, 
                                     fg_color="#1e293b",       
                                     corner_radius=10,         
                                     border_width=1,           
                                     border_color="#3b82f6")   
        frame_tooltip.pack(padx=2, pady=2) 

        # 3. TEXTO
        label = ctk.CTkLabel(frame_tooltip, 
                             text=self.text, 
                             text_color="white",
                             fg_color="transparent",
                             font=("Segoe UI", 12),
                             wraplength=250, 
                             justify="left")
        label.pack(padx=12, pady=8)

        # 4. OBTENER TAMAÑO SOLICITADO
        self.tooltip_window.update_idletasks() 
        ancho_tooltip = frame_tooltip.winfo_reqwidth()
        alto_tooltip = frame_tooltip.winfo_reqheight()
        
        ancho_pantalla = self.widget.winfo_screenwidth()
        alto_pantalla = self.widget.winfo_screenheight()
        
        # 5. POSICIÓN (Centrado y ABAJO del componente)
        x = int(self.widget.winfo_rootx() + (self.widget.winfo_width() / 2) - (ancho_tooltip / 2))
        y = int(self.widget.winfo_rooty() + self.widget.winfo_height() + 10)
        
        # 6. CORRECCIÓN DE BORDES
        # Evitar que se salga por los lados
        if x < 0:
            x = 10
        elif (x + ancho_tooltip) > ancho_pantalla:
            x = ancho_pantalla - ancho_tooltip - 10
            
        # Evitar que se salga por abajo (si topa abajo, lo pasa para arriba)
        if (y + alto_tooltip) > alto_pantalla: 
            y = int(self.widget.winfo_rooty() - alto_tooltip - 10)
            
        self.tooltip_window.wm_geometry(f"+{x}+{y}")
    
    def ocultar_tooltip(self):
        if self.tooltip_window:
            self.tooltip_window.destroy()
            self.tooltip_window = None

# =========================================================
# 4 Class DialogoModerno: Alertas y confirmaciones personalizadas
# =========================================================
class DialogoModerno(ctk.CTkToplevel):
    def __init__(self, master, titulo, mensaje, tipo="info", con_cancelar=False):
        super().__init__(master)
        self.title(titulo)
        self.geometry("450x220")
        self.attributes("-topmost", True)
        self.resizable(False, False)

        # Bloquear la ventana principal hasta que se cierre esta
        self.transient(master)
        self.grab_set()

        # Centrar la ventanita respecto a la PANTALLA completa
        self.update_idletasks()
        ancho_pantalla = self.winfo_screenwidth()
        alto_pantalla = self.winfo_screenheight()
        
        x = (ancho_pantalla // 2) - (250 // 2)
        y = (alto_pantalla // 2) - (180 // 2)
        self.geometry(f"+{x}+{y}")
        
        self.resultado = False
        
        # Paleta de colores según el tipo de alerta
        colores = {
            "info": "#17a2b8",      # Azul claro
            "warning": "#f39c12",   # Naranja
            "error": "#e74c3c",     # Rojo
            "pregunta": "#6f42c1"   # Morado
        }
        color_tema = colores.get(tipo, "#17a2b8")

        # Construcción de la interfaz del modal
        ctk.CTkLabel(self, text=titulo, font=("Arial", 16, "bold"), text_color=color_tema).pack(pady=(20, 10))
        ctk.CTkLabel(self, text=mensaje, font=("Arial", 13), wraplength=400, justify="center").pack(pady=(0, 20), padx=20, fill="both", expand=True)

        frame_btns = ctk.CTkFrame(self, fg_color="transparent")
        frame_btns.pack(pady=(0, 20))

        if con_cancelar:
            ctk.CTkButton(frame_btns, text="Cancelar", width=100, fg_color="#6c757d", hover_color="#5a6268", 
                          command=lambda: self.accionar(False)).pack(side="left", padx=10)
            ctk.CTkButton(frame_btns, text="Aceptar", width=100, fg_color=color_tema, hover_color=color_tema, 
                          command=lambda: self.accionar(True)).pack(side="left", padx=10)
        else:
            ctk.CTkButton(frame_btns, text="Aceptar", width=120, fg_color=color_tema, hover_color=color_tema, 
                          command=lambda: self.accionar(True)).pack(side="left", padx=10)

        # Captura el foco para que el usuario no pueda dar clic en la ventana principal
        self.grab_set()

    def accionar(self, resultado):
        self.resultado = resultado
        self.destroy()

    def obtener_resultado(self):
        # Detiene la ejecución de la función que lo llamó hasta que esta ventana se cierre
        self.master.wait_window(self)
        return self.resultado

# ==========================================
# 5. INTERFAZ GRÁFICA PRINCIPAL
# ==========================================
class AplicacionCargas(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Carga Masiva Multi-BD - Pro")
        self.geometry("950x680")
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.config_data = cargar_configuracion()
        self.archivo_csv = ""
        self.driver_sql = obtener_driver_sql()
        self.mapa_servidores = {}

        self.crear_interfaz()
        self.actualizar_lista_servidores()

    def crear_interfaz(self):
        # 1. Título General (Se queda en la ventana principal)
        self.frame_header = ctk.CTkFrame(self, fg_color="transparent")
        self.frame_header.pack(pady=(15, 5), padx=20, fill="x")
        ctk.CTkLabel(self.frame_header, text="⚡ Carga Masiva (SQL Server & Postgres)", font=("Arial", 20, "bold")).pack(side="left")

        # 2. Crear el Tabview Principal
        self.tabview = ctk.CTkTabview(self)
        self.tabview.pack(pady=5, padx=20, fill="both", expand=True)

        # 3. Agregar las dos pestañas
        self.tab_carga = self.tabview.add("Carga Masiva")
        self.tab_dummy = self.tabview.add("Generador Dummy")

        # ========================================================
        # PESTAÑA 1: CARGA MASIVA (Tu código actual modificado)
        # ========================================================

        # --- SECCIÓN 1: SERVIDOR ---
        self.frame_srv = ctk.CTkFrame(self.tab_carga, fg_color="#2b2b2b", corner_radius=10)
        self.frame_srv.pack(pady=10, padx=20, fill="x")
        
        ctk.CTkLabel(self.frame_srv, text="1. Servidor de Base de Datos", font=("Arial", 14, "bold")).grid(row=0, column=0, padx=15, pady=(10,5), sticky="w")
        
        self.cmb_servidores = ctk.CTkComboBox(self.frame_srv, width=280, values=["Seleccione un servidor..."], command=self.al_seleccionar_servidor)
        self.cmb_servidores.grid(row=1, column=0, padx=15, pady=(0, 15), sticky="w")

        btn_nuevo_srv = ctk.CTkButton(self.frame_srv, text="➕ Nuevo Servidor", fg_color="#28a745", hover_color="#218838", command=self.modal_nuevo_servidor)
        btn_nuevo_srv.grid(row=1, column=1, padx=10, pady=(0, 15), sticky="w")

        # --- SECCIÓN 2: BASE DE DATOS Y TABLA ---
        self.frame_db = ctk.CTkFrame(self.tab_carga, fg_color="#2b2b2b", corner_radius=10)
        self.frame_db.pack(pady=10, padx=20, fill="x")

        ctk.CTkLabel(self.frame_db, text="2. Destino (BD y Tabla)", font=("Arial", 14, "bold")).grid(row=0, column=0, columnspan=2, padx=15, pady=(10,5), sticky="w")

        self.cmb_dbs = ctk.CTkComboBox(self.frame_db, width=280, values=["Primero conecte al servidor"], command=self.al_seleccionar_db)
        self.cmb_dbs.grid(row=1, column=0, padx=15, pady=(0, 15), sticky="nw") 

        self.frame_tabla_contenedor = ctk.CTkFrame(self.frame_db, fg_color="transparent")
        self.frame_tabla_contenedor.grid(row=1, column=1, padx=10, pady=(0, 15), sticky="nw")

        self.frame_tabla_input = ctk.CTkFrame(self.frame_tabla_contenedor, fg_color="transparent")
        self.frame_tabla_input.pack(fill="x")

        self.ent_tabla = ctk.CTkEntry(self.frame_tabla_input, width=170, placeholder_text="Nombre de la tabla...")
        self.ent_tabla.pack(side="left", padx=(0, 5))

        self.btn_validar = ctk.CTkButton(self.frame_tabla_input, text="🔍 Validar", width=70, command=self.validar_tabla)
        self.btn_validar.pack(side="left")

        # NUEVO BOTÓN: Ver Estructura
        self.btn_estructura = ctk.CTkButton(self.frame_tabla_input, text="📊 Estructura", width=80, fg_color="#17a2b8", hover_color="#138496", command=self.consultar_estructura)
        self.btn_estructura.pack(side="left", padx=(5, 0))

        self.lbl_tabla_status = ctk.CTkLabel(self.frame_tabla_contenedor, text="Esperando BD...", text_color="#aaaaaa", font=("Arial", 11, "italic"))
        self.lbl_tabla_status.pack(anchor="w", pady=(2, 0))

        # --- SECCIÓN 3: ARCHIVO CSV ---
        self.frame_archivo = ctk.CTkFrame(self.tab_carga, fg_color="#2b2b2b", corner_radius=10)
        self.frame_archivo.pack(pady=10, padx=20, fill="x")
        
        ctk.CTkLabel(self.frame_archivo, text="3. Archivo Origen", font=("Arial", 14, "bold")).pack(anchor="w", padx=15, pady=(10,0))
        
        frame_btn_arch = ctk.CTkFrame(self.frame_archivo, fg_color="transparent")
        frame_btn_arch.pack(fill="x", padx=15, pady=10)
        
        ctk.CTkButton(frame_btn_arch, text="📂 Seleccionar CSV", command=self.seleccionar_archivo, width=150).pack(side="left")
        self.lbl_archivo = ctk.CTkLabel(frame_btn_arch, text="Ningún archivo seleccionado...", text_color="#aaaaaa")
        self.lbl_archivo.pack(side="left", padx=15)

        # --- SECCIÓN 4: ACCIÓN Y LOGS (MODIFICADA) ---
        self.frame_acciones = ctk.CTkFrame(self.tab_carga, fg_color="transparent")
        self.frame_acciones.pack(pady=10, padx=20, fill="x")

        # El botón de carga ahora es más pequeño y comparte línea
        self.btn_iniciar = ctk.CTkButton(self.frame_acciones, text="🚀 INICIAR CARGA MASIVA", font=("Arial", 13, "bold"), height=35, fg_color="#0056b3", hover_color="#004085", command=self.iniciar_proceso)
        self.btn_iniciar.pack(side="left", fill="x", expand=True, padx=(0, 10))

        # NUEVO BOTÓN: Limpiar Log
        self.btn_limpiar = ctk.CTkButton(self.frame_acciones, text="🧹 Limpiar Salida", font=("Arial", 12), height=35, width=120, fg_color="#6c757d", hover_color="#5a6268", command=self.limpiar_log)
        self.btn_limpiar.pack(side="right")

        self.txt_log = ctk.CTkTextbox(self.tab_carga, height=200, fg_color="#1a1a1a", text_color="#00ff00", font=("Consolas", 12))
        self.txt_log.pack(pady=10, padx=20, fill="both", expand=True)
        self.log("Sistema multi-motor iniciado. Listo para cargar.")

        # ----------------------------------------------------
        # VISTA 2: GENERADOR DUMMY (Totalmente independiente)
        # ----------------------------------------------------
        # ========================================================
        # PESTAÑA 2: DATOS DUMMY 
        # ========================================================

        # CONTENEDOR MAESTRO DIVIDIDO EN 2 COLUMNAS (50/50)
        self.frame_split_dummy = ctk.CTkFrame(self.tab_dummy, fg_color="transparent")
        self.frame_split_dummy.pack(pady=10, padx=20, fill="both", expand=True)
        
        self.frame_split_dummy.grid_columnconfigure(0, weight=1) # Columna Izquierda
        self.frame_split_dummy.grid_columnconfigure(1, weight=1) # Columna Derecha
        self.frame_split_dummy.grid_rowconfigure(0, weight=1)

        # ==========================================
        # COLUMNA IZQUIERDA: Origen y Configuración
        # ==========================================
        frame_izq_main = ctk.CTkFrame(self.frame_split_dummy, fg_color="transparent")
        frame_izq_main.grid(row=0, column=0, sticky="nsew", padx=(0, 10))

        # BLOQUE 1: Conexión
        self.frame_conn_dummy = ctk.CTkFrame(frame_izq_main, fg_color="#2b2b2b", corner_radius=10)
        self.frame_conn_dummy.pack(fill="x", pady=(0, 2))

        ctk.CTkLabel(self.frame_conn_dummy, text="1. Origen de Datos", font=("Arial", 14, "bold")).pack(anchor="w", padx=15, pady=(10, 5))
        
        self.cmb_servidores_dummy = ctk.CTkComboBox(self.frame_conn_dummy, width=280, values=["Seleccione un servidor..."], command=self.al_seleccionar_servidor_dummy)
        self.cmb_servidores_dummy.pack(anchor="w", padx=15, pady=(0, 10))

        self.cmb_dbs_dummy = ctk.CTkComboBox(self.frame_conn_dummy, width=280, values=["Primero conecte..."])
        self.cmb_dbs_dummy.pack(anchor="w", padx=15, pady=(0, 2))

        # BLOQUE 2: Configuración del Generador
        self.frame_params_dummy = ctk.CTkFrame(frame_izq_main, fg_color="#2b2b2b", corner_radius=10)
        self.frame_params_dummy.pack(fill="both", expand=True)

        ctk.CTkLabel(self.frame_params_dummy, text="2. Configuración de Generación", font=("Arial", 14, "bold")).pack(anchor="w", padx=15, pady=(0, 1))

        ctk.CTkLabel(self.frame_params_dummy, text="Tabla destino:", font=("Arial", 12)).pack(anchor="w", padx=15, pady=(0, 2))
        
        self.frame_tabla_dummy_input = ctk.CTkFrame(self.frame_params_dummy, fg_color="transparent")
        self.frame_tabla_dummy_input.pack(fill="x", padx=15, pady=(0, 1))
        
        self.ent_tabla_dummy = ctk.CTkEntry(self.frame_tabla_dummy_input, width=180, placeholder_text="Nombre de la tabla...")
        self.ent_tabla_dummy.pack(side="left", padx=(0, 5))
        
        self.btn_validar_dummy = ctk.CTkButton(self.frame_tabla_dummy_input, text="🔍 Validar", width=70, command=self.validar_tabla_dummy)
        self.btn_validar_dummy.pack(side="left")

        # Etiqueta arriba
        ctk.CTkLabel(self.frame_params_dummy, text="Volumen a generar:", font=("Arial", 12)).pack(anchor="w", padx=15, pady=(5, 2))
        
        # NUEVO: Contenedor horizontal para Entry y Botón
        frame_generar_input = ctk.CTkFrame(self.frame_params_dummy, fg_color="transparent")
        frame_generar_input.pack(fill="x", padx=15, pady=(0, 5))
        
        self.ent_cantidad_dummy = ctk.CTkEntry(frame_generar_input, width=120, placeholder_text="Filas (Ej. 500)")
        self.ent_cantidad_dummy.pack(side="left", padx=(0, 10))

        self.btn_generar_dummy = ctk.CTkButton(frame_generar_input, text="🎲 Generar CSV Dummy", font=("Arial", 12, "bold"), fg_color="#6f42c1", hover_color="#59339d", command=self.ejecutar_generacion_dummy)
        self.btn_generar_dummy.pack(side="left")

        # El status queda empaquetado de forma normal en el contenedor principal (abajo del frame horizontal)
        self.lbl_tabla_status_dummy = ctk.CTkLabel(self.frame_params_dummy, text="✨ Status: Escriba la tabla y presione Validar.", text_color="#aaaaaa", font=("Arial", 11, "italic"))
        self.lbl_tabla_status_dummy.pack(anchor="w", padx=15, pady=(0, 10))

        # ==========================================
        # COLUMNA DERECHA: Editor de Reglas Gigante
        # ==========================================
        frame_der_main = ctk.CTkFrame(self.frame_split_dummy, fg_color="#2b2b2b", corner_radius=10)
        frame_der_main.grid(row=0, column=1, sticky="nsew", padx=(10, 0))

        frame_header_reglas = ctk.CTkFrame(frame_der_main, fg_color="transparent")
        frame_header_reglas.pack(fill="x", padx=15, pady=(10, 2))
        
        ctk.CTkLabel(frame_header_reglas, text="Reglas de Negocio:", font=("Arial", 14, "bold")).pack(side="left")
        
        self.lbl_ayuda = ctk.CTkLabel(frame_header_reglas, text="❔", font=("Arial", 18), text_color="#17a2b8", cursor="hand2")
        self.lbl_ayuda.pack(side="right")
        
        texto_ayuda = (
            "📖 GUÍA DE SINTAXIS\n"
            "----------------------------\n"
            "• Relación FK  : tabla.columna\n"
            "• Lista Fija   : opcion1, opcion2\n"
            "• Rango Núm.   : [1-100]\n"
            "• Patrón Texto : FAC-####-???\n"
            "• Matemáticas  : = col1 + col2\n"
            "• Concatenar   : = col1 + '-' + col2"
        )
        ToolTip(self.lbl_ayuda, texto_ayuda)

        # Este cuadro de texto ahora abarcará toda la altura del lado derecho
        self.txt_relaciones = ctk.CTkTextbox(frame_der_main, fg_color="#1a1a1a")
        self.txt_relaciones.pack(fill="both", expand=True, padx=15, pady=(5, 10))
        self.txt_relaciones.insert("1.0", "Ej. id_rol : roles.id\nEj. codigo : CUST-####\nEj. estatus : ACTIVO, INACTIVO")

        self.btn_ampliar = ctk.CTkButton(frame_der_main, text="🗔 Ampliar Editor", width=120, height=28, fg_color="#17a2b8", hover_color="#138496", command=self.modal_editar_reglas)
        self.btn_ampliar.pack(anchor="e", padx=15, pady=(0, 15))


        # BLOQUE 3: Log Independiente para esta vista
        self.txt_log_dummy = ctk.CTkTextbox(self.tab_dummy, height=180, fg_color="#1a1a1a", text_color="#d63384", font=("Consolas", 12))
        self.txt_log_dummy.pack(pady=10, padx=20, fill="both", expand=True)
        self.txt_log_dummy.insert("end", "Módulo Dummy iniciado. Listo para generar datos.\n")



        # ==========================================
        # PESTAÑA 3: AMBIENTACIÓN GLOBAL (ORQUESTADOR)
        # ==========================================
        self.tabview.add("Ambientación Global")
        tab_global = self.tabview.tab("Ambientación Global")
        
        # Fila Superior: Selección y Escaneo
        frame_top_global = ctk.CTkFrame(tab_global, fg_color="transparent")
        frame_top_global.pack(fill="x", padx=15, pady=10)
        
        ctk.CTkLabel(frame_top_global, text="Base de Datos a Orquestar:").pack(side="left", padx=(0, 10))
        self.cmb_dbs_global = ctk.CTkComboBox(frame_top_global, values=["Primero conecte un servidor"], width=200)
        self.cmb_dbs_global.pack(side="left", padx=10)
        
        # Botón Principal (Carga Instantánea desde Local Memory)
        self.btn_escanear_db = ctk.CTkButton(frame_top_global, text="⚡ Cargar Árbol (Caché)", fg_color="#28a745", hover_color="#218838", command=lambda: self.escanear_dependencias(usar_cache=True))
        self.btn_escanear_db.pack(side="left", padx=(20, 5))

        # Botón Secundario (Escaneo forzado a la BD)
        self.btn_forzar_escaneo = ctk.CTkButton(frame_top_global, text="🔄 Escaneo Profundo", width=130, fg_color="#6c757d", hover_color="#5a6268", command=lambda: self.escanear_dependencias(usar_cache=False))
        self.btn_forzar_escaneo.pack(side="left")

        # Contenedor Central: Lista de Tablas y Volúmenes
        ctk.CTkLabel(tab_global, text="Árbol de Ejecución y Volumetría:", font=("Arial", 14, "bold")).pack(anchor="w", padx=15, pady=(10, 0))

        # Controles unificados: Acción Masiva (Izquierda) y Buscador (Derecha)
        frame_controles = ctk.CTkFrame(tab_global, fg_color="transparent")
        frame_controles.pack(fill="x", padx=15, pady=(5, 5))
        
        # --- Bloque Izquierdo: Acciones Masivas ---
        ctk.CTkButton(frame_controles, text="👁️ Todo a Solo Lectura", width=140, fg_color="#495057", command=lambda: self.cambiar_modo_masivo("Solo Lectura")).pack(side="left", padx=(0, 5))
        ctk.CTkButton(frame_controles, text="⚡ Todo a Generar", width=130, fg_color="#28a745", command=lambda: self.cambiar_modo_masivo("Generar")).pack(side="left", padx=5)
        
        ctk.CTkLabel(frame_controles, text="Filas:").pack(side="left", padx=(10, 2))
        ent_vol_masivo = ctk.CTkEntry(frame_controles, width=60)
        ent_vol_masivo.insert(0, "1000")
        ent_vol_masivo.pack(side="left")
        ctk.CTkButton(frame_controles, text="Aplicar", width=60, command=lambda: self.aplicar_volumen_masivo(ent_vol_masivo.get())).pack(side="left", padx=(2, 5))

        # --- Bloque Derecho: Buscador Inteligente ---
        # Empaquetamos con side="right" para que se alineen al extremo derecho
        btn_aislar = ctk.CTkButton(frame_controles, text="🎯 Aislar (Dependencias)", fg_color="#fd7e14", hover_color="#e36414", command=self.aislar_tabla)
        btn_aislar.pack(side="right", padx=(5, 0))
        
        self.ent_buscar_tabla = ctk.CTkEntry(frame_controles, width=130, placeholder_text="Ej. usuarios")
        self.ent_buscar_tabla.pack(side="right", padx=5)

        # NUEVO: Evento para filtrar en tiempo real mientras se escribe
        self.ent_buscar_tabla.bind("<KeyRelease>", self.filtrar_tablas)
        
        ctk.CTkLabel(frame_controles, text="Focalizar:", font=("Arial", 12, "bold")).pack(side="right", padx=(5, 5))

        # Frame scrolleable donde inyectaremos la interfaz de cada tabla dinámicamente
        self.scroll_orquestador = ctk.CTkScrollableFrame(tab_global, height=250, fg_color="#1a1a1a")
        self.scroll_orquestador.pack(fill="both", expand=True, padx=15, pady=5)
        
        # Fila Inferior: Botón de Ejecución Maestra y Límite de Seguridad
        frame_bot_global = ctk.CTkFrame(tab_global, fg_color="transparent")
        frame_bot_global.pack(fill="x", padx=15, pady=10)
        
        # NUEVO: Control de límite
        ctk.CTkLabel(frame_bot_global, text="Límite de tablas a procesar:", font=("Arial", 12, "bold"), text_color="#f39c12").pack(side="left", padx=(0, 5))
        self.ent_limite_tablas = ctk.CTkEntry(frame_bot_global, width=50, justify="center")
        self.ent_limite_tablas.insert(0, "5") # Empezamos con 5 por seguridad
        self.ent_limite_tablas.pack(side="left")
        
        self.btn_iniciar_orquestador = ctk.CTkButton(frame_bot_global, text="🚀 Iniciar Ambientación Masiva", height=35, fg_color="#6f42c1", hover_color="#59339d", font=("Arial", 13, "bold"), command=self.ejecutar_orquestador)
        self.btn_iniciar_orquestador.pack(side="right")

        # Consola de logs independiente para el Orquestador
        self.txt_log_global = ctk.CTkTextbox(tab_global, height=130, fg_color="#1a1a1a", text_color="#00ffff", font=("Consolas", 12))
        self.txt_log_global.pack(pady=(15, 0), padx=15, fill="x")
        self.txt_log_global.insert("end", "Módulo Orquestador iniciado. Listo para escanear dependencias.\n")
        
        # Diccionario temporal para guardar las referencias a las cajas de texto (volumen) de la UI
        self.inputs_volumen = {}

    # ==========================================
    # LÓGICA DE UI Y EVENTOS
    # ==========================================
    def log(self, mensaje):
        hora = datetime.now().strftime("%H:%M:%S")
        self.txt_log.insert("end", f"[{hora}] {mensaje}\n")
        self.txt_log.see("end")

    def actualizar_lista_servidores(self):
        self.mapa_servidores = {}
        nombres = ["Seleccione un servidor..."]
        for srv in self.config_data.get("Servidores_BD", []):
            tipo = srv.get("tipo", "SQL Server")
            ip = srv.get("ip", "Sin IP")
            nombre = srv.get("nombre", "Sin Nombre")
            display_str = f"{nombre} - {ip} ({tipo})"
            self.mapa_servidores[display_str] = srv
            nombres.append(display_str)

        if len(nombres) > 1:
            self.cmb_servidores.configure(values=nombres)
            # Seteamos el texto por defecto SIN llamar a la conexión
            self.cmb_servidores.set("Seleccione un servidor...") 
        else:
            self.cmb_servidores.configure(values=["No hay servidores"])
            self.cmb_servidores.set("No hay servidores")

    def obtener_credenciales(self, display_name):
        srv = self.mapa_servidores.get(display_name)
        if srv and "tipo" not in srv: 
            srv["tipo"] = "SQL Server"
        return srv

    def conectar_db(self, srv, db_name=None):
        tipo = srv.get("tipo", "SQL Server")
        if tipo == "SQL Server":
            db_part = f"DATABASE={db_name};" if db_name else ""
            conn_str = f"DRIVER={{{self.driver_sql}}};SERVER={srv['ip']};{db_part}UID={srv['user']};PWD={srv['pwd']};"
            return pyodbc.connect(conn_str, autocommit=(db_name is None))
        elif tipo == "PostgreSQL":
            db = db_name if db_name else 'postgres'
            return psycopg2.connect(host=srv['ip'], user=srv['user'], password=srv['pwd'], dbname=db)

    def al_seleccionar_servidor(self, display_name):
        # Bloqueamos la conexión si elige la opción por defecto
        if display_name in ["Seleccione un servidor...", "No hay servidores"]:
            self.cmb_dbs.set("Primero conecte al servidor")
            self.cmb_dbs.configure(values=["Primero conecte al servidor"])
            return
            
        srv = self.obtener_credenciales(display_name)
        if not srv: return
        self.cmb_dbs.set("Cargando bases de datos...")
        import threading
        threading.Thread(target=self.cargar_bases_de_datos, args=(srv,), daemon=True).start()

    def cargar_bases_de_datos(self, srv):
        conn = None
        try:
            conn = self.conectar_db(srv)
            cursor = conn.cursor()
            
            if srv["tipo"] == "SQL Server":
                cursor.execute("SELECT name FROM sys.databases WHERE state = 0 ORDER BY name")
            else:
                cursor.execute("SELECT datname FROM pg_database WHERE datistemplate = false ORDER BY datname")
                
            dbs = [row[0] for row in cursor.fetchall()]
            
            if dbs:
                self.cmb_dbs.configure(values=dbs)
                self.cmb_dbs.set(dbs[0])
                
                # NUEVO: Actualizar el selector de la pestaña Ambientación Global
                self.cmb_dbs_global.configure(values=dbs)
                self.cmb_dbs_global.set(dbs[0])
                
                self.al_seleccionar_db(dbs[0])
            self.log(f"Conectado a {srv['tipo']}: {srv['nombre']}.")
        except Exception as e:
            self.cmb_dbs.set("Error de conexión")
            self.log(f"Error conectando a {srv['ip']}: {e}")
        finally:
            if conn: conn.close()

    def al_seleccionar_db(self, db_name):
        srv_name = self.cmb_servidores.get()
        srv = self.obtener_credenciales(srv_name)
        if not srv or db_name == "Error de conexión": return
        
        # Limpiamos el campo y evitamos congelar la app cargando miles de tablas
        self.ent_tabla.delete(0, 'end')
        self.lbl_tabla_status.configure(text="Escriba la tabla y presione Validar.", text_color="#aaaaaa")

    # === NUEVA LÓGICA DE VALIDACIÓN EXACTA ===
    def validar_tabla(self):
        srv_name = self.cmb_servidores.get()
        db_name = self.cmb_dbs.get()
        tabla_input = self.ent_tabla.get().strip()
        
        if not tabla_input:
            self.lbl_tabla_status.configure(text="❌ Escriba un nombre de tabla", text_color="#ff4444")
            return
            
        srv = self.obtener_credenciales(srv_name)
        if not srv or db_name == "Error de conexión" or "Primero conecte" in db_name:
            return

        self.btn_validar.configure(state="disabled")
        self.lbl_tabla_status.configure(text="⏳ Buscando en el servidor...", text_color="#f1c40f")
        
        # Consultar en hilo secundario para no trabar la interfaz
        threading.Thread(target=self._hilo_validar_tabla, args=(srv, db_name, tabla_input), daemon=True).start()

    def limpiar_log(self):
        self.txt_log.delete("1.0", "end")
        self.log("Salida limpiada.")

    def _hilo_validar_tabla(self, srv, db_name, tabla):
        # Esta función ahora solo valida si la tabla existe (como era originalmente)
        conn = None
        try:
            conn = self.conectar_db(srv, db_name)
            cursor = conn.cursor()
            esquema = "dbo" if srv["tipo"] == "SQL Server" else "public"
            
            query = f"SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_TYPE = 'BASE TABLE' AND TABLE_SCHEMA = '{esquema}' AND TABLE_NAME = '{tabla}'"
            cursor.execute(query)
            existe = cursor.fetchone()[0] > 0
            
            if existe:
                self.lbl_tabla_status.configure(text=f"✅ ¡La tabla '{tabla}' existe y está lista!", text_color="#00C851")
            else:
                self.lbl_tabla_status.configure(text=f"❌ La tabla '{tabla}' NO fue encontrada", text_color="#ff4444")
                
        except Exception as e:
            self.lbl_tabla_status.configure(text="❌ Error al consultar servidor", text_color="#ff4444")
            self.log(f"Error validando tabla: {e}")
        finally:
            if conn: conn.close()
            self.btn_validar.configure(state="normal")

    def consultar_estructura(self):
        # Función disparada por el nuevo botón "Estructura"
        srv_name = self.cmb_servidores.get()
        db_name = self.cmb_dbs.get()
        tabla = self.ent_tabla.get().strip()
        
        if not tabla:
            self.lbl_tabla_status.configure(text="❌ Escriba un nombre de tabla primero", text_color="#ff4444")
            return
            
        srv = self.obtener_credenciales(srv_name)
        if not srv or "Primero conecte" in db_name:
            return

        self.btn_estructura.configure(state="disabled")
        threading.Thread(target=self._hilo_estructura_tabla, args=(srv, db_name, tabla), daemon=True).start()

    def _hilo_estructura_tabla(self, srv, db_name, tabla):
        conn = None
        try:
            conn = self.conectar_db(srv, db_name)
            cursor = conn.cursor()
            esquema = "dbo" if srv["tipo"] == "SQL Server" else "public"
            
            self.log(f"\n--- 📊 ESTRUCTURA DE LA TABLA: {tabla.upper()} ---")
            
            query_cols = f"SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = '{tabla}' AND TABLE_SCHEMA = '{esquema}' ORDER BY ORDINAL_POSITION"
            cursor.execute(query_cols)
            for col in cursor.fetchall():
                nulo = "NULL" if col[2] == 'YES' else "NOT NULL"
                self.log(f" 🔹 Columna: {col[0]} | Tipo: {col[1]} | {nulo}")

            self.log(f"--- 🔑 LLAVES FORÁNEAS ---")
            
            if srv["tipo"] == "SQL Server":
                query_fk = f"""
                    SELECT c1.name AS Columna, t2.name AS Tabla_Ref, c2.name AS Columna_Ref
                    FROM sys.foreign_keys fk
                    INNER JOIN sys.foreign_key_columns fkc ON fk.object_id = fkc.constraint_object_id
                    INNER JOIN sys.tables t1 ON fkc.parent_object_id = t1.object_id
                    INNER JOIN sys.columns c1 ON fkc.parent_object_id = c1.object_id AND fkc.parent_column_id = c1.column_id
                    INNER JOIN sys.tables t2 ON fkc.referenced_object_id = t2.object_id
                    INNER JOIN sys.columns c2 ON fkc.referenced_object_id = c2.object_id AND fkc.referenced_column_id = c2.column_id
                    WHERE t1.name = '{tabla}'
                """
            else: 
                query_fk = f"""
                    SELECT kcu.column_name, ccu.table_name AS foreign_table_name, ccu.column_name AS foreign_column_name 
                    FROM information_schema.table_constraints AS tc 
                    JOIN information_schema.key_column_usage AS kcu ON tc.constraint_name = kcu.constraint_name AND tc.table_schema = kcu.table_schema
                    JOIN information_schema.constraint_column_usage AS ccu ON ccu.constraint_name = tc.constraint_name
                    WHERE tc.constraint_type = 'FOREIGN KEY' AND tc.table_name='{tabla}'
                """
            
            cursor.execute(query_fk)
            fks = cursor.fetchall()
            
            if not fks:
                self.log(" 🔸 No se encontraron llaves foráneas estrictas.")
            else:
                for fk in fks:
                    self.log(f" 🔗 {fk[0]} ---> Depende de la tabla '{fk[1]}' (columna: {fk[2]})")
            
            self.log("-------------------------------------------\n")
                
        except Exception as e:
            self.log(f"Error consultando estructura: {e}")
        finally:
            if conn: conn.close()
            self.btn_estructura.configure(state="normal")


    def seleccionar_archivo(self):
        ruta = filedialog.askopenfilename(title="Seleccionar archivo CSV", filetypes=[("Archivos CSV", "*.csv"), ("Todos", "*.*")])
        if ruta:
            self.archivo_csv = ruta
            self.lbl_archivo.configure(text=os.path.basename(ruta))

    def log_global(self, mensaje):
        from datetime import datetime
        hora = datetime.now().strftime("%H:%M:%S")
        self.txt_log_global.insert("end", f"[{hora}] {mensaje}\n")
        self.txt_log_global.see("end")

    def cambiar_modo_masivo(self, nuevo_modo):
        # Verifica que ya se haya escaneado el árbol
        if not getattr(self, 'inputs_volumen', None):
            return
            
        for tabla, controles in self.inputs_volumen.items():
            # Actualizamos el valor del menú desplegable
            controles["modo"].set(nuevo_modo)
            
            # Bloqueamos o desbloqueamos la caja de texto según el modo
            if nuevo_modo == "Generar":
                controles["entry"].configure(state="normal", text_color="#ffffff")
            else:
                controles["entry"].configure(state="disabled", text_color="#6c757d")
                
        self.log_global(f"🔄 Todas las tablas cambiadas a modo: {nuevo_modo}")

    def aplicar_volumen_masivo(self, volumen_str):
        if not getattr(self, 'inputs_volumen', None):
            return
            
        if not volumen_str.isdigit():
            from tkinter import messagebox
            messagebox.showwarning("Valor Inválido", "Por favor, ingrese un número válido para las filas.")
            return
            
        for tabla, controles in self.inputs_volumen.items():
            # Si la caja está bloqueada (Solo Lectura), la desbloqueamos un segundo para poder inyectar el texto
            estado_actual = controles["entry"].cget("state")
            if estado_actual == "disabled":
                controles["entry"].configure(state="normal")
            
            controles["entry"].delete(0, 'end')
            controles["entry"].insert(0, volumen_str)
            
            # La regresamos a su estado original (bloqueada o normal)
            if estado_actual == "disabled":
                controles["entry"].configure(state="disabled")
                
        self.log_global(f"🔄 Volumen de {volumen_str} filas aplicado a todas las tablas.")
    # ==========================================
    # MODAL PARA NUEVO SERVIDOR
    # ==========================================
    def modal_nuevo_servidor(self):
        modal = ctk.CTkToplevel(self)
        modal.title("Registrar Servidor")
        modal.geometry("380x450")
        modal.grab_set()

        ctk.CTkLabel(modal, text="Motor de Base de Datos:").pack(pady=(15,0), padx=20, anchor="w")
        cmb_tipo = ctk.CTkOptionMenu(modal, values=["SQL Server", "PostgreSQL"], width=300)
        cmb_tipo.pack(pady=5, padx=20)

        ctk.CTkLabel(modal, text="Alias (Ej. Producción PgSQL):").pack(pady=(10,0), padx=20, anchor="w")
        ent_nombre = ctk.CTkEntry(modal, width=300)
        ent_nombre.pack(pady=5, padx=20)

        ctk.CTkLabel(modal, text="Servidor / IP:").pack(pady=(10,0), padx=20, anchor="w")
        ent_ip = ctk.CTkEntry(modal, width=300)
        ent_ip.pack(pady=5, padx=20)

        ctk.CTkLabel(modal, text="Usuario:").pack(pady=(10,0), padx=20, anchor="w")
        ent_user = ctk.CTkEntry(modal, width=300)
        ent_user.pack(pady=5, padx=20)

        ctk.CTkLabel(modal, text="Contraseña:").pack(pady=(10,0), padx=20, anchor="w")
        ent_pwd = ctk.CTkEntry(modal, width=300, show="*")
        ent_pwd.pack(pady=5, padx=20)

        def guardar():
            nuevo = {
                "tipo": cmb_tipo.get(),
                "nombre": ent_nombre.get(),
                "ip": ent_ip.get(),
                "user": ent_user.get(),
                "pwd": ent_pwd.get()
            }
            if all(nuevo.values()):
                self.config_data["Servidores_BD"].append(nuevo)
                guardar_configuracion(self.config_data)
                self.actualizar_lista_servidores()
                modal.destroy()
                self.log(f"Servidor '{nuevo['nombre']}' registrado exitosamente.")
            else:
                messagebox.showwarning("Incompleto", "Por favor llene todos los campos.")

        ctk.CTkButton(modal, text="Guardar", command=guardar).pack(pady=25)

    # ==========================================
    # CORE: LÓGICA DE CARGA MASIVA (DUAL ENGINE)
    # ==========================================
    def iniciar_proceso(self):
        srv_name = self.cmb_servidores.get()
        db_name = self.cmb_dbs.get()
        tabla = self.ent_tabla.get().strip() # Ahora leemos directamente de la caja de texto
        
        if not self.archivo_csv:
            DialogoModerno(self, "Error", "Debe seleccionar un CSV primero.", tipo="error").obtener_resultado()
            return
        if not tabla:
            DialogoModerno(self,"Error", "Debe escribir el nombre de la tabla destino.", tipo="error").obtener_resultado()
            return

        srv = self.obtener_credenciales(srv_name)
        self.btn_iniciar.configure(state="disabled", text="⏳ PROCESANDO...")
        threading.Thread(target=self.procesar_csv_dual, args=(srv, db_name, tabla), daemon=True).start()

    def procesar_csv_dual(self, srv, db_name, tabla, silencioso=False):
        conn = None
        try:
            tipo_db = srv.get("tipo", "SQL Server")
            esquema = "dbo" if tipo_db == "SQL Server" else "public"
            self.log(f"Iniciando carga hacia {tipo_db} -> {esquema}.{tabla}...")
            
            conn = self.conectar_db(srv, db_name)
            cursor = conn.cursor()

            # 1. Obtener metadatos de columnas
            cursor.execute(f"""
                SELECT COLUMN_NAME, IS_NULLABLE 
                FROM INFORMATION_SCHEMA.COLUMNS 
                WHERE TABLE_NAME = '{tabla}' AND TABLE_SCHEMA = '{esquema}'
                ORDER BY ORDINAL_POSITION
            """)
            columnas_sql = []
            acepta_nulos = {}
            for row in cursor.fetchall():
                col_name = row[0]
                columnas_sql.append(col_name)
                acepta_nulos[col_name] = (row[1] == 'YES')

            col_count = len(columnas_sql)
            if col_count == 0:
                raise Exception("La tabla no existe o no tiene permisos. ¿Escribió el nombre correctamente?")

            # 2. Configurar la lectura del CSV
            with open(self.archivo_csv, 'r', encoding='utf-8', newline='') as f:
                first_line = f.readline()
                delimitador = ','
                if '\t' in first_line: delimitador = '\t'
                elif ';' in first_line: delimitador = ';'

                f.seek(0)
                reader = csv.reader(f, delimiter=delimitador)
                next(reader, None)

                batch_size = 50000
                total_insertados = 0
                
                # --- RAMA 1: LOGICA SQL SERVER ---
                if tipo_db == "SQL Server":
                    placeholders = ",".join(["?"] * col_count)
                    cols_str = ",".join(columnas_sql)
                    insert_query = f"INSERT INTO {esquema}.{tabla} ({cols_str}) VALUES ({placeholders})"
                    cursor.fast_executemany = True

                    cursor.setinputsizes([(pyodbc.SQL_WVARCHAR, 0, 0)] * col_count)

                    batch_data = []

                    for fila in reader:
                        fila_procesada = self._transformar_fila(fila, col_count, columnas_sql, acepta_nulos)
                        batch_data.append(fila_procesada)

                        if len(batch_data) >= batch_size:
                            cursor.executemany(insert_query, batch_data)
                            conn.commit()
                            total_insertados += len(batch_data)
                            self.log(f"Insertados {total_insertados} registros...")
                            batch_data.clear()

                    if batch_data:
                        cursor.executemany(insert_query, batch_data)
                        conn.commit()
                        total_insertados += len(batch_data)

                # --- RAMA 2: LOGICA POSTGRESQL ---
                else: 
                    csv_buffer = io.StringIO()
                    writer = csv.writer(csv_buffer, delimiter='\t', quoting=csv.QUOTE_MINIMAL)
                    lineas_en_buffer = 0

                    for fila in reader:
                        fila_procesada = self._transformar_fila(fila, col_count, columnas_sql, acepta_nulos)
                        fila_procesada = ["" if x is None else x for x in fila_procesada]
                        writer.writerow(fila_procesada)
                        lineas_en_buffer += 1

                        if lineas_en_buffer >= batch_size:
                            csv_buffer.seek(0)
                            cursor.copy_expert(f"COPY {esquema}.{tabla} FROM STDIN WITH (FORMAT CSV, DELIMITER '\t', NULL '')", csv_buffer)
                            conn.commit()
                            total_insertados += lineas_en_buffer
                            self.log(f"Insertados {total_insertados} registros mediante COPY...")
                            
                            csv_buffer.seek(0)
                            csv_buffer.truncate(0)
                            lineas_en_buffer = 0

                    if lineas_en_buffer > 0:
                        csv_buffer.seek(0)
                        cursor.copy_expert(f"COPY {esquema}.{tabla} FROM STDIN WITH (FORMAT CSV, DELIMITER '\t', NULL '')", csv_buffer)
                        conn.commit()
                        total_insertados += lineas_en_buffer
                        
                    csv_buffer.close()

            self.log(f"✅ CARGA FINALIZADA EXITOSAMENTE. Total: {total_insertados} filas.")
            # SOLUCIÓN: Enviar la orden de crear la UI al hilo principal
            if not silencioso:
                self.after(0, lambda: DialogoModerno(self, "Éxito", f"Se insertaron {total_insertados} registros en {tabla} ({tipo_db}).", tipo="info"))
            
        except Exception as e:
            self.log(f"❌ ERROR: {str(e)}")
            if not silencioso:
                self.after(0, lambda: DialogoModerno(self, "Error de Inserción", str(e), tipo="error"))
            else:
                raise e # Si está en modo silencioso, le pasa el error al Orquestador para que lo atrape
        finally:
            if conn: conn.close()
            if not silencioso:
                self.after(0, lambda: self.btn_iniciar.configure(state="normal", text="🚀 INICIAR CARGA MASIVA"))

    def _transformar_fila(self, fila, col_count, columnas_sql, acepta_nulos):
        fila_procesada = []
        if len(fila) < col_count:
            fila.extend([''] * (col_count - len(fila)))
        elif len(fila) > col_count:
            fila = fila[:col_count]

        for i in range(col_count):
            col_name = columnas_sql[i]
            # Sanitizar saltos de línea y retornos de carro
            if isinstance(fila[i], str):
                val = fila[i].strip().replace('\n', ' ').replace('\r', '')
            else:
                val = fila[i]

            if val == "" or str(val).upper() == "NULL":
                if acepta_nulos[col_name]:
                    fila_procesada.append(None)
                else:
                    fila_procesada.append(0)
            else:
                val_upper = str(val).upper()
                if val_upper in ["T", "S", "TRUE", "1"]:
                    fila_procesada.append(1)
                elif val_upper in ["F", "N", "FALSE", "0"]:
                    fila_procesada.append(0)
                else:
                    fila_procesada.append(val)
        return fila_procesada

    def obtener_llaves_existentes(self, srv, db_name, tabla_padre, columna_id="id"):
        """Consulta la base de datos y retorna una lista de IDs válidos para relacionar."""
        conn = None
        llaves = []
        try:
            conn = self.conectar_db(srv, db_name) # Utiliza el método de conexión existente
            cursor = conn.cursor()
            esquema = "dbo" if srv.get("tipo") == "SQL Server" else "public"
            
            cursor.execute(f"SELECT {columna_id} FROM {esquema}.{tabla_padre}")
            llaves = [row[0] for row in cursor.fetchall()]
            
            self.log(f"Se obtuvieron {len(llaves)} llaves de {tabla_padre}.")
            return llaves
        except Exception as e:
            self.log(f"Error obteniendo llaves de {tabla_padre}: {e}")
            return []
        finally:
            if conn: conn.close()

    def actualizar_lista_servidores(self):
        self.mapa_servidores = {}
        nombres = ["Seleccione un servidor..."] 
        
        for srv in self.config_data.get("Servidores_BD", []):
            display_str = f"{srv.get('nombre', 'Sin Nombre')} - {srv.get('ip', 'Sin IP')} ({srv.get('tipo', 'SQL Server')})"
            self.mapa_servidores[display_str] = srv
            nombres.append(display_str)

        # Actualiza AMBOS comboboxes
        if len(nombres) > 1:
            self.cmb_servidores.configure(values=nombres)
            self.cmb_servidores_dummy.configure(values=nombres)
        else:
            self.cmb_servidores.configure(values=["No hay servidores"])
            self.cmb_servidores_dummy.configure(values=["No hay servidores"])

    # ==========================================
    # LÓGICA DE DUMMY 
    # ==========================================
    def al_seleccionar_servidor_dummy(self, display_name):
        if display_name in ["Seleccione un servidor...", "No hay servidores"]:
            self.cmb_dbs_dummy.set("Primero conecte al servidor")
            self.cmb_dbs_dummy.configure(values=["Primero conecte al servidor"])
            return
            
        srv = self.obtener_credenciales(display_name)
        if not srv: return
        self.cmb_dbs_dummy.set("Cargando bases de datos...")
        import threading
        
        # Usamos un hilo para cargar la BD en el combobox correcto
        def cargar():
            conn = None
            try:
                conn = self.conectar_db(srv)
                cursor = conn.cursor()
                if srv["tipo"] == "SQL Server":
                    cursor.execute("SELECT name FROM sys.databases WHERE state = 0 ORDER BY name")
                else:
                    cursor.execute("SELECT datname FROM pg_database WHERE datistemplate = false ORDER BY datname")
                    
                dbs = [row[0] for row in cursor.fetchall()]
                if dbs:
                    self.cmb_dbs_dummy.configure(values=dbs)
                    self.cmb_dbs_dummy.set(dbs[0])
                    
                    # NUEVO: Actualizar el selector de la pestaña Ambientación Global
                    self.cmb_dbs_global.configure(values=dbs)
                    self.cmb_dbs_global.set(dbs[0])
                self.log_dummy(f"Conectado a {srv['tipo']}: {srv['nombre']}.")
            except Exception as e:
                self.cmb_dbs_dummy.set("Error de conexión")
                self.log_dummy(f"Error conectando: {e}")
            finally:
                if conn: conn.close()
                
        threading.Thread(target=cargar, daemon=True).start()

    def log_dummy(self, mensaje):
        from datetime import datetime
        hora = datetime.now().strftime("%H:%M:%S")
        self.txt_log_dummy.insert("end", f"[{hora}] {mensaje}\n")
        self.txt_log_dummy.see("end")

    def validar_tabla_dummy(self):
        srv_name = self.cmb_servidores_dummy.get()
        db_name = self.cmb_dbs_dummy.get()
        tabla_input = self.ent_tabla_dummy.get().strip()
        
        if not tabla_input:
            self.lbl_tabla_status_dummy.configure(text="❌ Escriba un nombre de tabla", text_color="#ff4444")
            return

        # ==========================================
        # AUTO-COMPLETAR REGLAS (POR BASE DE DATOS)
        # ==========================================
        memoria = cargar_relaciones()
        
        # Inicializamos la BD en el diccionario si no existe con su estructura base
        if db_name not in memoria:
            memoria[db_name] = {"_configuracion_global": {}, "tablas": {}}
            
        # AQUÍ ESTÁ EL CAMBIO: Entrar primero a .get("tablas", {})
        reglas_guardadas = memoria[db_name].get("tablas", {}).get(tabla_input.lower(), "")
        
        self.txt_relaciones.delete("1.0", "end")
        if reglas_guardadas:
            self.txt_relaciones.insert("1.0", reglas_guardadas)
            self.log_dummy(f"🧠 Reglas cargadas para '{tabla_input}' en '{db_name}'.")
        # ==========================================
            
        srv = self.obtener_credenciales(srv_name)
        if not srv or db_name == "Error de conexión" or "Primero conecte" in db_name:
            self.lbl_tabla_status_dummy.configure(text="❌ Conecte un servidor y BD primero", text_color="#ff4444")
            return

        self.btn_validar_dummy.configure(state="disabled")
        self.lbl_tabla_status_dummy.configure(text="⏳ Buscando en el servidor...", text_color="#f1c40f")
        
        threading.Thread(target=self._hilo_validar_tabla_dummy, args=(srv, db_name, tabla_input), daemon=True).start()

    def _hilo_validar_tabla_dummy(self, srv, db_name, tabla):
        conn = None
        try:
            conn = self.conectar_db(srv, db_name)
            cursor = conn.cursor()
            esquema = "dbo" if srv["tipo"] == "SQL Server" else "public"
            
            query = f"SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_TYPE = 'BASE TABLE' AND TABLE_SCHEMA = '{esquema}' AND TABLE_NAME = '{tabla}'"
            cursor.execute(query)
            existe = cursor.fetchone()[0] > 0
            
            if existe:
                self.lbl_tabla_status_dummy.configure(text=f"✅ ¡La tabla '{tabla}' existe y está lista!", text_color="#00C851")
                self.log_dummy(f"✅ Validación exitosa: La tabla '{tabla}' existe.")
            else:
                self.lbl_tabla_status_dummy.configure(text=f"❌ La tabla '{tabla}' NO fue encontrada", text_color="#ff4444")
                self.log_dummy(f"❌ Error de validación: La tabla '{tabla}' no existe en {db_name}.")
                
        except Exception as e:
            self.lbl_tabla_status_dummy.configure(text="❌ Error al consultar servidor", text_color="#ff4444")
            self.log_dummy(f"Error validando tabla: {e}")
        finally:
            if conn: conn.close()
            self.btn_validar_dummy.configure(state="normal")

    def modal_editar_reglas(self):
        db_name = self.cmb_dbs_dummy.get()
        tabla = self.ent_tabla_dummy.get().strip()

        if not tabla or "Primero conecte" in db_name:
            self.log_dummy("⚠️ Escriba el nombre de la tabla en el campo superior antes de abrir el editor.")
            return

        # Crear ventana emergente
        modal = ctk.CTkToplevel(self)
        modal.title(f"Editor Avanzado de Reglas - {tabla}")
        modal.geometry("550x450")
        modal.grab_set() # Bloquea la ventana principal hasta que cierres esta

        ctk.CTkLabel(modal, text=f"Reglas para la tabla: {tabla.upper()}", font=("Arial", 15, "bold")).pack(pady=(15, 5))
        ctk.CTkLabel(modal, text="Escriba una regla por línea. Use el formato: columna : tabla.columna o columna : valores", text_color="#aaaaaa").pack(pady=(0, 10))

        # Cuadro de texto gigante
        txt_modal = ctk.CTkTextbox(modal, width=500, height=280, fg_color="#1a1a1a", font=("Consolas", 13))
        txt_modal.pack(pady=5, padx=20, fill="both", expand=True)

        # Copiar lo que haya en el recuadro pequeño al modal
        reglas_actuales = self.txt_relaciones.get("1.0", "end-1c")
        if reglas_actuales.startswith("Ej."):
            txt_modal.insert("1.0", "")
        else:
            txt_modal.insert("1.0", reglas_actuales)

        def guardar_modal():
            nuevas_reglas = txt_modal.get("1.0", "end-1c").strip()
            
            # 1. Actualizar en la interfaz principal
            self.txt_relaciones.delete("1.0", "end")
            self.txt_relaciones.insert("1.0", nuevas_reglas)
            
            # 2. Guardar físicamente en el archivo JSON
            if nuevas_reglas and not nuevas_reglas.startswith("Ej."):
                memoria = cargar_relaciones()
                if db_name not in memoria:
                    memoria[db_name] = {}
                memoria[db_name]["tablas"][tabla.lower()] = nuevas_reglas
                guardar_relaciones(memoria)
                self.log_dummy(f"💾 Reglas guardadas en el archivo JSON para '{tabla}'.")

            modal.destroy()
            self.log_dummy("✅ Editor avanzado cerrado.")

        # Botones de acción
        frame_botones = ctk.CTkFrame(modal, fg_color="transparent")
        frame_botones.pack(pady=15)
        
        ctk.CTkButton(frame_botones, text="❌ Cancelar", fg_color="#6c757d", hover_color="#5a6268", command=modal.destroy).pack(side="left", padx=10)
        ctk.CTkButton(frame_botones, text="💾 Guardar en Interfaz", fg_color="#28a745", hover_color="#218838", command=guardar_modal).pack(side="left", padx=10)
    # ==========================================
    # LÓGICA DE GENERACIÓN DUMMY AUTOMÁTICA
    # ==========================================
    def ejecutar_generacion_dummy(self):
        # Ahora leemos de los campos de la pestaña Dummy
        srv_name = self.cmb_servidores_dummy.get()
        db_name = self.cmb_dbs_dummy.get()
        tabla = self.ent_tabla_dummy.get().strip()
        cantidad_str = self.ent_cantidad_dummy.get().strip()
        reglas_str = self.txt_relaciones.get("1.0", "end").strip()

        if not tabla or not cantidad_str.isdigit():
            # Cambiado a log_dummy y mensaje actualizado
            self.log_dummy("❌ Error: Especifique una tabla y una cantidad numérica válida.")
            return

        # ==========================================
        # APRENDIZAJE AUTOMÁTICO (POR BASE DE DATOS)
        # ==========================================
        if reglas_str and not reglas_str.startswith("Ej."):
            memoria = cargar_relaciones()
            if db_name not in memoria:
                # Inicializar correctamente la estructura anidada
                memoria[db_name] = {"_configuracion_global": {}, "tablas": {}}
                
            # Modificar la lectura para comparar entrando a "tablas"
            if memoria[db_name].get("tablas", {}).get(tabla.lower()) != reglas_str:
                memoria[db_name]["tablas"][tabla.lower()] = reglas_str
                guardar_relaciones(memoria)
                self.log_dummy(f"💾 Reglas guardadas para '{tabla}' en '{db_name}'.")

        srv = self.obtener_credenciales(srv_name)
        if not srv or "Primero conecte" in db_name:
            self.log_dummy("❌ Error: Seleccione un servidor y una base de datos válida.")
            return

        self.btn_generar_dummy.configure(state="disabled", text="⏳ Generando datos...")
        threading.Thread(target=self._hilo_generar_dummy, args=(srv, srv_name, db_name, tabla, int(cantidad_str), reglas_str), daemon=True).start()

    def _hilo_generar_dummy(self, srv, srv_name, db_name, tabla, cantidad, reglas_str):
        from faker import Faker
        import random
        import csv
        from datetime import datetime
        
        fake = Faker('es_MX')
        
        conn = None
        try:
            conn = self.conectar_db(srv, db_name)
            cursor = conn.cursor()
            esquema = "dbo" if srv["tipo"] == "SQL Server" else "public"

            query_cols = f"SELECT COLUMN_NAME, DATA_TYPE FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = '{tabla}' AND TABLE_SCHEMA = '{esquema}' ORDER BY ORDINAL_POSITION"
            cursor.execute(query_cols)
            columnas = cursor.fetchall()

            if not columnas:
                self.log_dummy(f"❌ La tabla '{tabla}' no existe en la BD.")
                return

            self.log_dummy("🔍 Analizando llaves foráneas nativas...")
            fks_data = {} 

            if srv["tipo"] == "SQL Server":
                query_fk = f"SELECT c1.name AS Col_Local, t2.name AS Tabla_Ref, c2.name AS Col_Ref FROM sys.foreign_keys fk INNER JOIN sys.foreign_key_columns fkc ON fk.object_id = fkc.constraint_object_id INNER JOIN sys.tables t1 ON fkc.parent_object_id = t1.object_id INNER JOIN sys.columns c1 ON fkc.parent_object_id = c1.object_id AND fkc.parent_column_id = c1.column_id INNER JOIN sys.tables t2 ON fkc.referenced_object_id = t2.object_id INNER JOIN sys.columns c2 ON fkc.referenced_object_id = c2.object_id AND fkc.referenced_column_id = c2.column_id WHERE t1.name = '{tabla}'"
            else:
                query_fk = f"SELECT kcu.column_name, ccu.table_name, ccu.column_name FROM information_schema.table_constraints AS tc JOIN information_schema.key_column_usage AS kcu ON tc.constraint_name = kcu.constraint_name AND tc.table_schema = kcu.table_schema JOIN information_schema.constraint_column_usage AS ccu ON ccu.constraint_name = tc.constraint_name WHERE tc.constraint_type = 'FOREIGN KEY' AND tc.table_name='{tabla}'"
            
            cursor.execute(query_fk)
            for col_local, tabla_ref, col_ref in cursor.fetchall():
                try:
                    q_ids = f"SELECT TOP 10000 {col_ref} FROM {esquema}.{tabla_ref}" if srv["tipo"] == "SQL Server" else f"SELECT {col_ref} FROM {esquema}.{tabla_ref} LIMIT 10000"
                    cursor.execute(q_ids)
                    ids = [row[0] for row in cursor.fetchall() if row[0] is not None]
                    
                    if ids:
                        fks_data[col_local] = ids
                        self.log_dummy(f" ✅ Relación '{col_local}': {len(ids)} IDs extraídos de '{tabla_ref}'.")
                except Exception:
                    pass

            # =========================================================
            # MOTOR DE REGLAS (RELACIONES + RESTRICCIONES + MATEMÁTICAS)
            # =========================================================
            reglas_custom = {} 
            reglas_math = {} # NUEVO: Guardará las fórmulas
            
            if reglas_str and not reglas_str.startswith("Ej."):
                self.log_dummy("🧠 Procesando reglas de negocio manuales...")
                lineas = reglas_str.split('\n')
                
                for linea in lineas:
                    if ':' not in linea: continue
                    col_local, regla = linea.split(':', 1)
                    col_local = col_local.strip()
                    cn = col_local.lower() # Nombre en minúscula para búsquedas
                    regla = regla.strip()
                    
                    # NUEVO: Si empieza con "=", es una fórmula
                    if regla.startswith('='):
                        reglas_math[cn] = regla[1:].strip()
                        self.log_dummy(f" 🧮 Regla matemática detectada para '{col_local}'.")
                        continue
                    
                    if '.' in regla and ',' not in regla and '#' not in regla and '?' not in regla and '[' not in regla:
                        try:
                            tabla_ref, col_ref = regla.split('.')
                            q_ids = f"SELECT TOP 10000 {col_ref.strip()} FROM {esquema}.{tabla_ref.strip()}" if srv["tipo"] == "SQL Server" else f"SELECT {col_ref.strip()} FROM {esquema}.{tabla_ref.strip()} LIMIT 10000"
                            cursor.execute(q_ids)
                            ids = [row[0] for row in cursor.fetchall() if row[0] is not None]
                            if ids:
                                fks_data[col_local] = ids
                                self.log_dummy(f" 🔗 Relación lógica '{col_local}': {len(ids)} IDs.")
                        except Exception as e:
                            self.log_dummy(f" ⚠️ Aviso: No se pudo conectar la relación '{linea}'.")
                    else:
                        reglas_custom[col_local] = regla
                        self.log_dummy(f" 📐 Regla estricta aplicada a '{col_local}'.")
            # =========================================================

            self.log_dummy(f"🎲 Escribiendo {cantidad} registros dummy...")
            nombre_archivo = f"dummy_{tabla}_{datetime.now().strftime('%H%M%S')}.csv"
            
            with open(nombre_archivo, 'w', encoding='utf-8', newline='') as f:
                writer = csv.writer(f, delimiter=',')
                writer.writerow([c[0] for c in columnas]) 

                for _ in range(cantidad):
                    fila_dict = {} # NUEVO: Usamos un diccionario por fila
                    
                    # FASE 1: Generar los datos normales
                    for col_name, data_type in columnas:
                        col_limpia = col_name.strip()
                        cn = col_limpia.lower()
                        
                        # Si tiene fórmula matemática, ponemos un 0 temporal y la saltamos
                        if cn in reglas_math:
                            fila_dict[col_limpia] = 0
                            continue

                        if col_limpia in fks_data and fks_data[col_limpia]:
                            fila_dict[col_limpia] = random.choice(fks_data[col_limpia])
                            continue
                            
                        if col_limpia in reglas_custom:
                            regla = reglas_custom[col_limpia]
                            if ',' in regla: 
                                opciones = [opt.strip() for opt in regla.split(',')]
                                fila_dict[col_limpia] = random.choice(opciones)
                            elif '[' in regla and ']' in regla:
                                import re
                                texto_final = regla
                                
                                # Bucle: Mientras siga encontrando rangos [x-y], los resuelve uno por uno
                                while re.search(r'\[(\d+)-(\d+)\]', texto_final):
                                    match = re.search(r'\[(\d+)-(\d+)\]', texto_final)
                                    min_v = int(match.group(1))
                                    max_v = int(match.group(2))
                                    num_azar = str(random.randint(min_v, max_v))
                                    
                                    # Reemplazamos solo esa ocurrencia exacta (count=1)
                                    texto_final = texto_final.replace(match.group(0), num_azar, 1)
                                
                                # Lo pasamos por bothify al final por si también combinaste con ### o ???
                                fila_dict[col_limpia] = fake.bothify(text=texto_final)
                            else: 
                                fila_dict[col_limpia] = fake.bothify(text=regla)
                            continue
                        
                        dt = data_type.lower()
                        
                        if dt == 'tinyint':
                            fila_dict[col_limpia] = random.randint(0, 255)
                        elif dt == 'smallint':
                            fila_dict[col_limpia] = random.randint(0, 32767)
                        elif 'int' in dt or dt == 'numeric':
                            fila_dict[col_limpia] = random.randint(100, 90000) if 'id' in cn else random.randint(1, 100)
                        elif 'date' in dt or 'time' in dt:
                            fila_dict[col_limpia] = fake.date_between(start_date='-1y', end_date='today').isoformat()
                        elif 'varchar' in dt or 'text' in dt or 'char' in dt or 'nvarchar' in dt:
                            if 'correo' in cn or 'email' in cn: fila_dict[col_limpia] = fake.unique.email()
                            elif 'nombre' in cn: fila_dict[col_limpia] = fake.first_name()
                            elif 'apellido' in cn: fila_dict[col_limpia] = fake.last_name()
                            elif 'rfc' in cn: fila_dict[col_limpia] = fake.lexify(text='????######???').upper()
                            elif 'tel' in cn or 'phone' in cn: fila_dict[col_limpia] = fake.phone_number()[:15]
                            else: fila_dict[col_limpia] = fake.word()
                        elif dt == 'bit' or dt == 'boolean':
                            fila_dict[col_limpia] = random.choice([0, 1])
                        elif 'decimal' in dt or 'float' in dt:
                            fila_dict[col_limpia] = round(random.uniform(10.0, 5000.0), 2)
                        else:
                            fila_dict[col_limpia] = fake.word()
                            
                    # FASE 2: Resolver operaciones matemáticas
                    locals_eval = {}
                    for k, v in fila_dict.items():
                        val = v
                        # NUEVO: Intentar convertir textos a números reales para evitar concatenaciones
                        if isinstance(v, str):
                            try:
                                val = float(v) if '.' in v else int(v)
                            except ValueError:
                                pass # Si es un texto puro (ej. "ACTIVO"), se queda como string
                        locals_eval[k.lower()] = val
                    
                    for cn_math, expresion in reglas_math.items():
                        try:
                            # Reemplazamos las variables de la expresión a minúsculas y calculamos
                            exp_baja = expresion.lower()
                            resultado = eval(exp_baja, {"__builtins__": None}, locals_eval)
                            
                            # Asignamos el resultado a la columna original correcta
                            for original_col in fila_dict.keys():
                                if original_col.lower() == cn_math:
                                    
                                    # NUEVO: Validamos si el resultado es número o texto
                                    if isinstance(resultado, (int, float)):
                                        fila_dict[original_col] = int(resultado) if isinstance(resultado, float) and resultado.is_integer() else round(resultado, 2)
                                    else:
                                        fila_dict[original_col] = str(resultado)
                                        
                                    # Actualizamos contexto por si otra fórmula depende de esta
                                    locals_eval[cn_math] = fila_dict[original_col] 
                                    break
                        except Exception as e:
                            self.log_dummy(f"⚠️ Error matemático en '{cn_math}': Revisar variables.")
                            pass
                            
                    # FASE 3: Convertir el diccionario a lista en el orden exacto de la base de datos
                    fila_lista = [fila_dict[c[0].strip()] for c in columnas]
                    writer.writerow(fila_lista)
            
            self.log_dummy(f"✅ Archivo '{nombre_archivo}' completado.")
            self.archivo_csv = nombre_archivo
            self.lbl_archivo.configure(text=nombre_archivo)
            self.cmb_servidores.set(srv_name)
            self.cmb_dbs.configure(values=self.cmb_dbs_dummy.cget("values"))
            self.cmb_dbs.set(db_name)
            self.ent_tabla.delete(0, 'end')
            self.ent_tabla.insert(0, tabla)
            self.lbl_tabla_status.configure(text=f"✅ Datos sincronizados. Listo para cargar.", text_color="#00C851")
            self.tabview.set("Carga Masiva")
            self.log("📁 CSV Dummy auto-asignado. Presione Iniciar Carga Masiva.")

        except Exception as e:
            self.log_dummy(f"❌ Error generando dummy: {e}")
        finally:
            if conn: conn.close()
            self.btn_generar_dummy.configure(state="normal", text="🎲 Generar CSV Dummy")

    def escanear_dependencias(self, usar_cache=True):
        db_name = self.cmb_dbs_global.get()
        srv_name = self.cmb_servidores.get()
        if srv_name in ["Seleccione un servidor...", "No hay servidores"]:
            srv_name = self.cmb_servidores_dummy.get()
            
        if "Primero conecte" in db_name or srv_name in ["Seleccione un servidor...", "No hay servidores"]:
            DialogoModerno(self, "Falta Conexión", "Por favor, selecciona tu servidor SQL y conecta una base de datos primero.", tipo="warning").obtener_resultado()
            return

        self.btn_escanear_db.configure(state="disabled", text="⏳ Cargando...")
        self.update() 
        
        srv = self.obtener_credenciales(srv_name)
        if not srv: 
            self.btn_escanear_db.configure(state="normal", text="⚡ Cargar Árbol (Caché)")
            return

        # Limpiar la interfaz anterior
        for widget in self.scroll_orquestador.winfo_children():
            widget.destroy()
        self.inputs_volumen.clear()

        memoria = cargar_relaciones()
        conf_global = memoria.get(db_name, {}).get("_configuracion_global", {})
        
        tablas_ordenadas = []
        niveles = {}
        dependencias = {}

        # ==========================================
        # 1. INTENTO DE CARGA DESDE LOCAL MEMORY
        # ==========================================
        if usar_cache and conf_global.get("orden_ejecucion") and conf_global.get("arbol_dependencias"):
            self.log_global("⚡ Cargando estructura instantáneamente desde Local Memory...")
            tablas_ordenadas = conf_global["orden_ejecucion"]
            self.arbol_dependencias = conf_global["arbol_dependencias"]
            niveles = conf_global.get("niveles", {})
            volumenes_guardados = conf_global.get("volumen_registros", {})
            
        # ==========================================
        # 2. ESCANEO PROFUNDO A LA BASE DE DATOS
        # ==========================================
        else:
            self.log_global(f"🔍 Iniciando escaneo profundo de la BD '{db_name}'...")
            self.update()
            conn = None
            try:
                conn = self.conectar_db(srv, db_name)
                cursor = conn.cursor()
                
                if srv["tipo"] == "SQL Server":
                    cursor.execute("SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_TYPE = 'BASE TABLE' AND TABLE_SCHEMA = 'dbo'")
                else:
                    cursor.execute("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
                todas_tablas = [row[0].lower() for row in cursor.fetchall()]

                self.log_global(f"Mapeando llaves foráneas para {len(todas_tablas)} tablas...")
                self.update()

                dependencias = {t: [] for t in todas_tablas}
                if srv["tipo"] == "SQL Server":
                    cursor.execute("SELECT t1.name AS Tabla, t2.name AS TablaRef FROM sys.foreign_keys fk INNER JOIN sys.foreign_key_columns fkc ON fk.object_id = fkc.constraint_object_id INNER JOIN sys.tables t1 ON fkc.parent_object_id = t1.object_id INNER JOIN sys.tables t2 ON fkc.referenced_object_id = t2.object_id")
                    for tabla, tabla_ref in cursor.fetchall():
                        if tabla.lower() != tabla_ref.lower():
                            dependencias[tabla.lower()].append(tabla_ref.lower())
                
                self.arbol_dependencias = dependencias 

                self.log_global("Calculando Topological Sort...")
                self.update()
                
                tablas_restantes = set(todas_tablas)
                nivel_actual = 0
                
                while tablas_restantes:
                    tablas_listas = [t for t in tablas_restantes if all(d not in tablas_restantes for d in dependencias.get(t, []))]
                    
                    if not tablas_listas:
                        self.log_global("⚠️ Dependencia circular detectada. Resolviendo forzosamente.")
                        tablas_listas = list(tablas_restantes)
                    
                    for t in tablas_listas:
                        niveles[t] = nivel_actual
                        tablas_restantes.remove(t)
                    nivel_actual += 1

                tablas_ordenadas = sorted(niveles.keys(), key=lambda t: niveles[t])
                volumenes_guardados = conf_global.get("volumen_registros", {})

                # GUARDAR EN LOCAL MEMORY PARA FUTURAS CARGAS RÁPIDAS
                if db_name not in memoria: 
                    memoria[db_name] = {"_configuracion_global": {}, "tablas": {}}
                memoria[db_name]["_configuracion_global"]["orden_ejecucion"] = tablas_ordenadas
                memoria[db_name]["_configuracion_global"]["arbol_dependencias"] = dependencias
                memoria[db_name]["_configuracion_global"]["niveles"] = niveles
                guardar_relaciones(memoria)
                self.log_global("💾 Estructura guardada en Caché Local exitosamente.")

            except Exception as e:
                self.log_global(f"❌ Error escaneando dependencias: {e}")
                self.btn_escanear_db.configure(state="normal", text="⚡ Cargar Árbol (Caché)")
                return
            finally:
                if conn: conn.close()

        # ==========================================
        # 3. RENDERIZADO DE INTERFAZ
        # ==========================================
        for idx, tabla in enumerate(tablas_ordenadas):
            row_frame = ctk.CTkFrame(self.scroll_orquestador, fg_color=("#333333" if idx % 2 == 0 else "#2a2a2a"))
            row_frame.pack(fill="x", pady=2, padx=5)
            
            # Usar .get(tabla, 0) por si el nivel no existe en alguna migración
            ctk.CTkLabel(row_frame, text=f"Lvl {niveles.get(tabla, 0)}", width=40, font=("Arial", 11, "bold"), text_color="#17a2b8").pack(side="left", padx=10)
            ctk.CTkLabel(row_frame, text=tabla, width=180, anchor="w").pack(side="left", padx=5)

            btn_reglas = ctk.CTkButton(row_frame, text="📄 Reglas", width=60, height=24, fg_color="#6c757d", hover_color="#5a6268", command=lambda t=tabla: self.mostrar_reglas_rapidas(t))
            btn_reglas.pack(side="left", padx=5)

            modo_actual = "Solo Lectura" 
            cmb_modo_var = ctk.StringVar(value=modo_actual)
            cmb_modo = ctk.CTkOptionMenu(row_frame, values=["Generar", "Solo Lectura", "Ignorar"], variable=cmb_modo_var, width=110, fg_color="#495057", button_color="#343a40")
            cmb_modo.pack(side="right", padx=15)
            
            ent_vol = ctk.CTkEntry(row_frame, width=70)
            ent_vol.insert(0, str(volumenes_guardados.get(tabla, 100)))
            ent_vol.pack(side="right", padx=5)
            ctk.CTkLabel(row_frame, text="Filas:").pack(side="right", padx=0)
            
            def toggle_volumen(modo_seleccionado, entry_widget=ent_vol):
                if modo_seleccionado == "Generar":
                    entry_widget.configure(state="normal", text_color="#ffffff")
                else:
                    entry_widget.configure(state="disabled", text_color="#6c757d")
            
            cmb_modo.configure(command=lambda m, e=ent_vol: toggle_volumen(m, e))
            toggle_volumen(modo_actual) 
            
            self.inputs_volumen[tabla] = {"entry": ent_vol, "modo": cmb_modo_var, "nivel": niveles.get(tabla, 0), "frame": row_frame}

        self.log_global(f"✅ Interfaz lista. {len(tablas_ordenadas)} tablas cargadas en el árbol.")
        self.btn_escanear_db.configure(state="normal", text="⚡ Cargar Árbol (Caché)")
    
    def ejecutar_orquestador(self):
        srv_name = self.cmb_servidores.get()
        db_name = self.cmb_dbs_global.get()
        
        if not getattr(self, 'inputs_volumen', None):
            messagebox.showwarning("Atención", "Primero haz clic en 'Escanear Dependencias' para cargar el árbol de tablas.")
            return
            
        srv = self.obtener_credenciales(srv_name)
        
        # Recopilar la configuración de la interfaz (ignora las tablas en 'Solo Lectura')
        plan_ejecucion = []
        for tabla, controles in self.inputs_volumen.items():
            if controles["modo"].get() == "Generar":
                try:
                    cantidad = int(controles["entry"].get())
                    if cantidad > 0: plan_ejecucion.append((tabla, cantidad))
                except ValueError:
                    pass
                    
        # Validar si no hay tablas seleccionadas
        if not plan_ejecucion:
            messagebox.showinfo("Sin acciones", "No hay tablas marcadas para 'Generar' con filas mayores a 0.")
            return
            
        # NUEVO: Validar el límite de seguridad
        try:
            limite_seguridad = int(self.ent_limite_tablas.get())
        except ValueError:
            limite_seguridad = 5 # Si el usuario borra el texto o pone letras, usamos 5
            
        if len(plan_ejecucion) > limite_seguridad:
            DialogoModerno(self,
                "Límite de Seguridad Excedido", 
                f"Has intentado ambientar {len(plan_ejecucion)} tablas a la vez, pero tu límite actual es {limite_seguridad}.\n\n"
                "Por favor, regresa más tablas a 'Solo Lectura' o aumenta el límite bajo tu propio riesgo.",
            tipo="error").obtener_resultado()
            return
            
        confirmacion = DialogoModerno(
            self, 
            "Confirmar Ambientación", 
            f"Se generarán e insertarán datos para {len(plan_ejecucion)} tablas en cascada.\n\n¿Desea continuar?", 
            tipo="pregunta", 
            con_cancelar=True
        ).obtener_resultado()
        
        if not confirmacion:
            return
                
        self.btn_iniciar_orquestador.configure(state="disabled", text="⏳ AMBIENTANDO EN CASCADA...")
        import threading
        threading.Thread(target=self._hilo_orquestador, args=(srv, srv_name, db_name, plan_ejecucion), daemon=True).start()

    def _hilo_orquestador(self, srv, srv_name, db_name, plan_ejecucion):
        memoria = cargar_relaciones()
        reglas_db = memoria.get(db_name, {}).get("tablas", {})
        
        try:
            for tabla, cantidad in plan_ejecucion:
                self.log(f"\n🚀 [ORQUESTADOR] Procesando tabla: {tabla.upper()} ({cantidad} filas)")
                reglas_str = reglas_db.get(tabla, "")
                
                # 1. Fuerza al generador Dummy a crear el archivo CSV con tus reglas lógicas
                self._hilo_generar_dummy(srv, srv_name, db_name, tabla, cantidad, reglas_str)
                
                # 2. Fuerza al motor de Carga Masiva a insertarlo físicamente en la BD
                if getattr(self, 'archivo_csv', None):
                    # AQUÍ ESTÁ EL CAMBIO: Le pasamos silencioso=True
                    self.procesar_csv_dual(srv, db_name, tabla, silencioso=True)
                    
            # Al final del ciclo, el Orquestador da su única alerta global
            self.after(0, lambda: DialogoModerno(self, "Orquestador Finalizado", "¡La ambientación masiva ha concluido con éxito para todas las tablas seleccionadas!", tipo="info"))
        except Exception as e:
            self.after(0, lambda: DialogoModerno(self, "Error en Cascada", f"El proceso se detuvo por un error en una tabla: {e}", tipo="error"))
        finally:
            self.after(0, lambda: self.btn_iniciar_orquestador.configure(state="normal", text="🚀 Iniciar Ambientación Masiva"))


    def filtrar_tablas(self, event=None):
        busqueda = self.ent_buscar_tabla.get().strip().lower()
        
        # 1. Ocultar todos primero usando pack_forget()
        for tabla, controles in self.inputs_volumen.items():
            controles["frame"].pack_forget()
            
        # 2. Volver a empaquetar solo los que coinciden (mantiene el orden original)
        for tabla, controles in self.inputs_volumen.items():
            if busqueda in tabla.lower():
                controles["frame"].pack(fill="x", pady=2, padx=5)

    def aislar_tabla(self):
        busqueda = self.ent_buscar_tabla.get().strip().lower()
        if not busqueda:
            self.log_global("⚠️ Escriba el nombre de una tabla para buscar y aislar.")
            return

        if not hasattr(self, 'arbol_dependencias'):
            self.log_global("⚠️ Primero debe escanear las dependencias.")
            return

        tablas_objetivo = set()
        for t in self.inputs_volumen.keys():
            if busqueda in t.lower():
                tablas_objetivo.add(t.lower())

        if not tablas_objetivo:
            self.log_global(f"⚠️ No se encontró ninguna tabla que coincida con '{busqueda}'.")
            return

        padres_necesarios = set(tablas_objetivo)
        cola = list(tablas_objetivo)

        while cola:
            actual = cola.pop(0)
            padres = self.arbol_dependencias.get(actual, [])
            for p in padres:
                if p not in padres_necesarios:
                    padres_necesarios.add(p)
                    cola.append(p)

        # 3. Actualizar UI: SOLO ACTIVAMOS (SUMAMOS), YA NO APAGAMOS LAS DEMÁS
        for tabla in padres_necesarios:
            if tabla in self.inputs_volumen:
                controles = self.inputs_volumen[tabla]
                controles["modo"].set("Generar")
                controles["entry"].configure(state="normal", text_color="#ffffff")

        self.log_global(f"🎯 Sumado a Generar: '{busqueda}' y sus dependencias ({len(padres_necesarios)} tablas en total).")
        
        # 4. Limpiar el buscador para revelar toda la lista nuevamente
        self.ent_buscar_tabla.delete(0, 'end')
        self.filtrar_tablas()

    def mostrar_reglas_rapidas(self, tabla):
        db_name = self.cmb_dbs_global.get()
        memoria = cargar_relaciones()
        # Busca las reglas en la memoria, si no hay, devuelve un texto por defecto
        reglas = memoria.get(db_name, {}).get("tablas", {}).get(tabla.lower(), "")

        modal = ctk.CTkToplevel(self)
        modal.title(f"Reglas Actuales - {tabla}")
        modal.geometry("450x300")
        modal.grab_set()

        ctk.CTkLabel(modal, text=f"Reglas configuradas para: {tabla.upper()}", font=("Arial", 14, "bold")).pack(pady=(15, 5))
        
        txt = ctk.CTkTextbox(modal, width=400, height=180, fg_color="#1a1a1a", font=("Consolas", 12))
        txt.pack(padx=20, pady=10)
        
        if reglas and not reglas.startswith("Ej."):
            txt.insert("1.0", reglas)
        else:
            txt.insert("1.0", "⚠️ No hay reglas personalizadas guardadas para esta tabla.\nSe generarán datos aleatorios nativos.")
            txt.configure(text_color="#aaaaaa")
            
        txt.configure(state="disabled") # Modal de solo lectura
        ctk.CTkButton(modal, text="Cerrar", command=modal.destroy, fg_color="#495057").pack(pady=5)
   
if __name__ == "__main__":
    multiprocessing.freeze_support()
    app = AplicacionCargas()
    app.mainloop()