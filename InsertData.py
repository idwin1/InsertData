import os
import sys
import subprocess
import json
import csv
import threading
import io
import requests
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
    config_data = cargar_configuracion()
    
    # Intentamos obtener el nombre del primer servidor configurado para asignárselo a las BDs antiguas
    servidor_default = "Servidor_Desconocido"
    if config_data.get("Servidores_BD") and len(config_data["Servidores_BD"]) > 0:
        # Tomamos el string completo que usa el combobox (Nombre - IP (Tipo))
        primer_srv = config_data["Servidores_BD"][0]
        servidor_default = f"{primer_srv.get('nombre', 'Sin Nombre')} - {primer_srv.get('ip', 'Sin IP')} ({primer_srv.get('tipo', 'SQL Server')})"

    cambios = False
    nueva_memoria = {}
    
    for clave, contenido in memoria.items():
        # 1. Migración de la Llave: Si no tiene "|", es una BD antigua, la convertimos en compuesta
        if "|" not in clave:
            nueva_clave = f"{servidor_default}|{clave}"
            cambios = True
        else:
            nueva_clave = clave
            
        # 2. Migración de Estructura Interna: Si no tiene _configuracion_global
        if isinstance(contenido, dict) and "_configuracion_global" not in contenido:
            # Si en algún punto ya tenía 'tablas' pero no conf global, lo respetamos
            viejo_contenido = contenido.get("tablas", contenido.copy())
                
            nueva_memoria[nueva_clave] = {
                "_configuracion_global": {
                    "orden_ejecucion": [],
                    "volumen_registros": {},
                    "modo_tablas": {} 
                },
                "tablas": viejo_contenido
            }
            cambios = True
        else:
            # Si ya está bien estructurada y tiene su llave compuesta, se queda igual
            nueva_memoria[nueva_clave] = contenido
            
    if cambios:
        guardar_relaciones(nueva_memoria)
        print("✅ Archivo relaciones.json migrado exitosamente a Llaves Compuestas (Servidor|BD) y Estructura Avanzada.")

# Se ejecuta automáticamente al arrancar la app
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

        # --- NUEVO: Altura dinámica según la longitud del mensaje ---
        alto_ventana = 220
        if len(mensaje) > 200:
            alto_ventana = 310  # Más alto para mensajes largos como el de IDENTITY
        elif len(mensaje) > 100:
            alto_ventana = 260

        self.geometry(f"450x{alto_ventana}")
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

        # --- NUEVO: Control de Cancelación y Auditoría ---
        self.cancelar_proceso = False
        if not os.path.exists("logs"):
            os.makedirs("logs")
            
        # Creamos (o usamos) un archivo de log único por DÍA
        fecha_hoy = datetime.now().strftime('%Y%m%d')
        self.archivo_auditoria = f"logs/Auditoria_Cargas_{fecha_hoy}.txt"
        
        # Usamos "a" (append) para añadir texto sin borrar lo de las pruebas anteriores del día
        with open(self.archivo_auditoria, "a", encoding="utf-8") as f:
            f.write(f"\n{'='*55}\n")
            f.write(f"=== NUEVA SESIÓN DE AUDITORÍA: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===\n")
            f.write(f"{'='*55}\n")
        # -------------------------------------------------

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

        # --- NUEVO: CHECKBOX DE IDENTITY ---
        self.chk_identity_var = ctk.BooleanVar(value=True) # Por defecto activado
        self.chk_identity = ctk.CTkCheckBox(self.frame_tabla_input, text="Forzar IDs", variable=self.chk_identity_var, width=80)
        self.chk_identity.pack(side="left", padx=(15, 0))
        # -----------------------------------

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
            "📖 GUÍA AVANZADA DE SINTAXIS\n"
            "----------------------------------------------------------\n"
            "• Cross-Server (Híbrido) : [Servidor].[BD].[Tabla].columna\n"
            "• Relación Local (FK)    : tabla.columna\n"
            "• Plantilla Real (Faker) : SUCURSAL {{city}} o {{company}}\n"
            "• Lista de Opciones      : ACTIVO, INACTIVO, PENDIENTE\n"
            "• Rango Numérico         : [1-100] o LOTE-[1000-9999]\n"
            "• Patrón Texto           : FAC-####-??? (#=Núm, ?=Letra)\n"
            "• Matemáticas            : = col_precio * 1.16\n"
            "• Matemáticas Complejas  : = (col_a + col_b) / 2\n"
            "• Concatenación          : = col_nombre + ' ' + col_apellido\n"
            "• Límite Texto         : COPPEL {{city}} [max:30]\n"
            "• Inyección Sincronizada : COPPEL <<tabla.columna>>\n"
            "----------------------------------------------------------\n"
            "* Nota: Si dejas la línea en blanco, el sistema generará\n"
            "  datos automáticos basados en el tipo de columna."
        )
        ToolTip(self.lbl_ayuda, texto_ayuda)

        # Este cuadro de texto ahora abarcará toda la altura del lado derecho
        self.txt_relaciones = ctk.CTkTextbox(frame_der_main, fg_color="#1a1a1a")
        self.txt_relaciones.pack(fill="both", expand=True, padx=15, pady=(5, 10))
        self.txt_relaciones.insert("1.0", "Ej. id_rol : roles.id\nEj. codigo : CUST-####\nEj. estatus : ACTIVO, INACTIVO")

        # Contenedor para botones debajo del editor
        frame_acciones_reglas = ctk.CTkFrame(frame_der_main, fg_color="transparent")
        frame_acciones_reglas.pack(anchor="e", padx=15, pady=(0, 15), fill="x")

        # Tu botón actual de ampliar
        self.btn_ampliar = ctk.CTkButton(frame_acciones_reglas, text="🗔 Ampliar Editor", width=120, fg_color="#17a2b8", hover_color="#138496", command=self.modal_editar_reglas)
        self.btn_ampliar.pack(side="left")

        self.btn_autodescubrir = ctk.CTkButton(frame_acciones_reglas, text=" Crear reglas A.", width=120, height=28, fg_color="#1765b8", hover_color="#138496", command=self.auto_descubrir_reglas)
        self.btn_autodescubrir.pack(side = "right")

        # BLOQUE 3: Log Independiente para esta vista
        self.txt_log_dummy = ctk.CTkTextbox(self.tab_dummy, height=180, fg_color="#1a1a1a", text_color="#d63384", font=("Consolas", 12))
        self.txt_log_dummy.pack(pady=10, padx=20, fill="both", expand=True)
        self.txt_log_dummy.insert("end", "Módulo Dummy iniciado. Listo para generar datos.\n")



        # ==========================================
        # PESTAÑA 3: AMBIENTACIÓN GLOBAL (ORQUESTADOR)
        # ==========================================
        self.tabview.add("Ambientación Global")
        tab_global = self.tabview.tab("Ambientación Global")
        
        # Fila Superior: Selección como "Carrito de Compras"
        frame_top_global = ctk.CTkFrame(tab_global, fg_color="transparent")
        frame_top_global.pack(fill="x", padx=15, pady=10)
        
        # NUEVO: Selector de Servidor independiente para esta pestaña
        ctk.CTkLabel(frame_top_global, text="Servidor:").pack(side="left", padx=(0, 5))
        self.cmb_servidores_global = ctk.CTkComboBox(frame_top_global, values=["Seleccione un servidor..."], width=160, command=self.al_seleccionar_servidor_global)
        self.cmb_servidores_global.pack(side="left", padx=(0, 10))
        
        ctk.CTkLabel(frame_top_global, text="BD:").pack(side="left", padx=(0, 5))
        self.cmb_dbs_global = ctk.CTkComboBox(frame_top_global, values=["Primero conecte..."], width=150)
        self.cmb_dbs_global.pack(side="left", padx=(0, 15))
        
        # Botones de Acción
        self.btn_escanear_db = ctk.CTkButton(frame_top_global, text="➕ Agregar al Plan", fg_color="#28a745", hover_color="#218838", command=lambda: self.escanear_dependencias(usar_cache=True))
        self.btn_escanear_db.pack(side="left", padx=5)

        self.btn_forzar_escaneo = ctk.CTkButton(frame_top_global, text="🔄 Recargar", width=90, fg_color="#6c757d", hover_color="#5a6268", command=lambda: self.escanear_dependencias(usar_cache=False))
        self.btn_forzar_escaneo.pack(side="left", padx=5)
        
        # NUEVO: Botón para limpiar el carrito
        self.btn_limpiar_orquestador = ctk.CTkButton(frame_top_global, text="🗑️ Limpiar", width=80, fg_color="#e74c3c", hover_color="#c0392b", command=self.limpiar_orquestador)
        self.btn_limpiar_orquestador.pack(side="left", padx=5)

        # --- NUEVOS BOTONES DE ESCENARIO ---
        self.btn_guardar_plan = ctk.CTkButton(frame_top_global, text="💾 Guardar Plan", width=100, fg_color="#17a2b8", hover_color="#138496", command=self.guardar_escenario)
        self.btn_guardar_plan.pack(side="right", padx=5)
        
        self.btn_cargar_plan = ctk.CTkButton(frame_top_global, text="📂 Cargar Plan", width=100, fg_color="#495057", hover_color="#343a40", command=self.cargar_escenario)
        self.btn_cargar_plan.pack(side="right", padx=5)

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

        # --- NUEVO: Botón Cancelar Orquestador ---
        self.btn_cancelar_orquestador = ctk.CTkButton(frame_bot_global, text="🛑 Abortar", height=35, fg_color="#dc3545", hover_color="#c82333", font=("Arial", 13, "bold"), command=self.abortar_proceso)
        self.btn_cancelar_orquestador.pack(side="right", padx=(10, 0))
        # -----------------------------------------
        
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
        from datetime import datetime
        hora = datetime.now().strftime("%H:%M:%S")
        def actualizar_log():
            self.txt_log.insert("end", f"[{hora}] {mensaje}\n")
            self.txt_log.see("end")
        self.after(0, actualizar_log)

    def actualizar_lista_servidores(self):
        self.mapa_servidores = {}
        nombres = ["Seleccione un servidor..."] 
        
        for srv in self.config_data.get("Servidores_BD", []):
            display_str = f"{srv.get('nombre', 'Sin Nombre')} - {srv.get('ip', 'Sin IP')} ({srv.get('tipo', 'SQL Server')})"
            self.mapa_servidores[display_str] = srv
            nombres.append(display_str)

        # Actualiza LOS 3 comboboxes (Carga, Dummy y Orquestador Global)
        if len(nombres) > 1:
            self.cmb_servidores.configure(values=nombres)
            self.cmb_servidores_dummy.configure(values=nombres)
            
            # Verificamos que el componente exista para evitar errores al iniciar
            if hasattr(self, 'cmb_servidores_global'):
                self.cmb_servidores_global.configure(values=nombres)
                
        else:
            self.cmb_servidores.configure(values=["No hay servidores"])
            self.cmb_servidores_dummy.configure(values=["No hay servidores"])
            
            if hasattr(self, 'cmb_servidores_global'):
                self.cmb_servidores_global.configure(values=["No hay servidores"])

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

    def escribir_auditoria(self, mensaje):
        """Escribe silenciosamente en el archivo físico."""
        try:
            with open(self.archivo_auditoria, "a", encoding="utf-8") as f:
                f.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {mensaje}\n")
        except Exception:
            pass

    def abortar_proceso(self):
        """Activa la bandera para detener los hilos de manera segura."""
        self.cancelar_proceso = True
        self.log("🛑 Solicitud de cancelación enviada. Esperando detención segura...")
        self.log_global("🛑 Solicitud de cancelación enviada. Esperando detención segura...")
        self.escribir_auditoria("🛑 USUARIO SOLICITÓ CANCELAR EL PROCESO MASIVO.")

    def guardar_escenario(self):
        srv_name = self.cmb_servidores_global.get()
        db_name = self.cmb_dbs_global.get()
        if "Primero" in db_name or not getattr(self, 'inputs_volumen', None): return
        
        memoria = cargar_relaciones()
        clave = f"{srv_name}|{db_name}"
        if clave not in memoria:
            memoria[clave] = {"_configuracion_global": {}, "tablas": {}}
            
        plan_actual = {}
        for k, v in self.inputs_volumen.items():
            plan_actual[v["tabla"]] = {
                "modo": v["modo"].get(),
                "volumen": v["entry"].get()
            }
            
        memoria[clave]["_configuracion_global"]["escenario_guardado"] = plan_actual
        guardar_relaciones(memoria)
        self.log_global("💾 Escenario guardado. La próxima vez que escanees, presiona 'Cargar Plan'.")

    def cargar_escenario(self):
        srv_name = self.cmb_servidores_global.get()
        db_name = self.cmb_dbs_global.get()
        memoria = cargar_relaciones()
        clave = f"{srv_name}|{db_name}"
        
        plan = memoria.get(clave, {}).get("_configuracion_global", {}).get("escenario_guardado", {})
        if not plan:
            self.log_global("⚠️ No hay un escenario guardado para este servidor y BD.")
            return
            
        for k, v in self.inputs_volumen.items():
            tabla = v["tabla"]
            if tabla in plan:
                modo_guardado = plan[tabla]["modo"]
                v["modo"].set(modo_guardado)
                
                estado_actual = v["entry"].cget("state")
                if estado_actual == "disabled": v["entry"].configure(state="normal")
                v["entry"].delete(0, 'end')
                v["entry"].insert(0, plan[tabla]["volumen"])
                
                if modo_guardado != "Generar":
                    v["entry"].configure(state="disabled", text_color="#6c757d")
                else:
                    v["entry"].configure(text_color="#ffffff")
                    
        self.log_global("📂 Plan de ambientación restaurado exitosamente.")

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

            # --- NUEVO: DETECTAR ÍNDICES ---
            self.log(f"--- ⚡ ÍNDICES ---")
            if srv["tipo"] == "SQL Server":
                query_idx = f"""
                    SELECT i.name, i.type_desc 
                    FROM sys.indexes i 
                    INNER JOIN sys.tables t ON i.object_id = t.object_id 
                    WHERE t.name = '{tabla}' AND i.type > 0
                """
                cursor.execute(query_idx)
                indices = cursor.fetchall()
                if not indices:
                    self.log(" 🔸 No hay índices (Inserción ultrarrápida).")
                else:
                    for idx in indices:
                        self.log(f" 🗂️ {idx[0]} ({idx[1]})")

            # --- NUEVO: DETECTAR TRIGGERS ---
            self.log(f"--- 🎯 TRIGGERS ---")
            if srv["tipo"] == "SQL Server":
                query_trg = f"""
                    SELECT tr.name, tr.is_disabled 
                    FROM sys.triggers tr 
                    INNER JOIN sys.tables t ON tr.parent_id = t.object_id 
                    WHERE t.name = '{tabla}'
                """
                cursor.execute(query_trg)
                triggers = cursor.fetchall()
                if not triggers:
                    self.log(" 🔸 No hay triggers (No habrá cuellos de botella lógicos).")
                else:
                    for trg in triggers:
                        estado = "Apagado" if trg[1] else "ACTIVO ⚠️"
                        self.log(f" ⚙️ {trg[0]} | Estado: {estado}")

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
        def actualizar_log():
            self.txt_log_global.insert("end", f"[{hora}] {mensaje}\n")
            self.txt_log_global.see("end")
        self.after(0, actualizar_log)

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
        tabla = self.ent_tabla.get().strip() 
        
        if not self.archivo_csv:
            DialogoModerno(self, "Error", "Debe seleccionar un CSV primero.", tipo="error").obtener_resultado()
            return
        if not tabla:
            DialogoModerno(self,"Error", "Debe escribir el nombre de la tabla destino.", tipo="error").obtener_resultado()
            return

        srv = self.obtener_credenciales(srv_name)
        
        # Leemos la decisión actual del checkbox
        forzar_identity = self.chk_identity_var.get()
        
        # --- NUEVO: ESCANEO PREVIO Y CONFIRMACIÓN DE IDENTITY ---
        try:
            conn_test = self.conectar_db(srv, db_name)
            cursor_test = conn_test.cursor()
            tipo_db = srv.get("tipo", "SQL Server")
            esquema = "dbo" if tipo_db == "SQL Server" else "public"
            
            tiene_identity = False
            nombre_col_id = ""
            
            if tipo_db == "SQL Server":
                # Escaneamos si existe el candado
                cursor_test.execute(f"SELECT name FROM sys.identity_columns WHERE object_id = OBJECT_ID('{esquema}.{tabla}')")
                row_id = cursor_test.fetchone()
                if row_id:
                    tiene_identity = True
                    nombre_col_id = row_id[0]
            conn_test.close()
            
            # Si tiene Identity, validamos con el usuario según el estado de su checkbox
            if tiene_identity:
                if forzar_identity:
                    mensaje = (f"La tabla '{tabla}' tiene una columna auto-numérica protegida ('{nombre_col_id}').\n\n"
                               "Tienes marcada la opción 'Forzar IDs', por lo que el sistema forzará la inserción de los valores exactos de tu CSV.\n\n"
                               "¿Deseas continuar con esta configuración?")
                else:
                    mensaje = (f"La tabla '{tabla}' tiene una columna auto-numérica protegida ('{nombre_col_id}').\n\n"
                               "Tienes desmarcada la opción 'Forzar IDs', por lo que se recortará esa columna de tu CSV y SQL Server generará números nuevos automáticamente.\n\n"
                               "¿Deseas continuar?")
                               
                # Usamos tu DialogoModerno para bloquear la pantalla y pedir confirmación
                confirmacion = DialogoModerno(self, "Columna IDENTITY Detectada", mensaje, tipo="pregunta", con_cancelar=True).obtener_resultado()
                
                # Si el usuario presiona Cancelar, abortamos el inicio para que pueda cambiar el checkbox
                if not confirmacion:
                    return 
                    
        except Exception as e:
            self.log(f"⚠️ Aviso en pre-validación: {e}")
        # --------------------------------------------------------

        self.btn_iniciar.configure(state="disabled", text="⏳ PROCESANDO...")
        threading.Thread(target=self.procesar_csv_dual, args=(srv, db_name, tabla, forzar_identity), daemon=True).start()


    def procesar_csv_dual(self, srv, db_name, tabla, forzar_identity=True, silencioso=False):
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

            # --- NUEVO: DETECCIÓN INTELIGENTE DE IDENTITY ---
            columna_identity = None
            idx_identity = -1
            tiene_identity = False

            if tipo_db == "SQL Server":
                # Buscamos si existe alguna columna identity sin importar su nombre
                cursor.execute(f"SELECT name FROM sys.identity_columns WHERE object_id = OBJECT_ID('{esquema}.{tabla}')")
                row_id = cursor.fetchone()
                if row_id:
                    tiene_identity = True
                    columna_identity = row_id[0]
                    # Encontramos en qué posición (índice) está esa columna en nuestra lista
                    if columna_identity in columnas_sql:
                        idx_identity = columnas_sql.index(columna_identity)

                if tiene_identity:
                    if forzar_identity:
                        self.log(f"🔓 Candado abierto para inyectar IDs en '{columna_identity}'.")
                        cursor.execute(f"SET IDENTITY_INSERT {esquema}.{tabla} ON")
                    else:
                        self.log(f"⏭️ Ignorando IDs del CSV. SQL Server auto-generará '{columna_identity}'.")
                        # AMPUTAMOS la columna de la estructura SQL para que no la espere en el INSERT
                        if idx_identity != -1:
                            columnas_sql.pop(idx_identity)
                            col_count -= 1
            # ------------------------------------------------

            # 2. Configurar la lectura del CSV con Mapeo Inteligente
            with open(self.archivo_csv, 'r', encoding='utf-8', newline='') as f:
                first_line = f.readline()
                delimitador = ','
                if '\t' in first_line: delimitador = '\t'
                elif ';' in first_line: delimitador = ';'

                f.seek(0)
                reader = csv.reader(f, delimiter=delimitador)
                
                # --- MAPEO DINÁMICO (Header-to-SQL) ---
                encabezados_csv = next(reader, [])
                # Limpiar encabezados (eliminar BOM oculto y espacios)
                encabezados_csv = [str(h).strip().replace('\ufeff', '') for h in encabezados_csv]

                mapeo_indices = []
                for col_sql in columnas_sql:
                    encontrado = False
                    for i, h in enumerate(encabezados_csv):
                        if h.lower() == col_sql.lower():
                            mapeo_indices.append(i)
                            encontrado = True
                            break
                    if not encontrado:
                        mapeo_indices.append(-1) # Si la columna SQL no existe en el CSV
                # ----------------------------------------

                batch_size = 50000
                total_insertados = 0
                
                # --- RAMA 1: LOGICA SQL SERVER ---
                if tipo_db == "SQL Server":
                    # Reconstruimos el string de columnas dinámicamente (por si borramos la Identity)
                    placeholders = ",".join(["?"] * col_count)
                    cols_str = ",".join(columnas_sql)
                    insert_query = f"INSERT INTO {esquema}.{tabla} ({cols_str}) VALUES ({placeholders})"
                    cursor.fast_executemany = True

                    cursor.setinputsizes([(pyodbc.SQL_WVARCHAR, 0, 0)] * col_count)

                    batch_data = []

                    for fila_cruda in reader:
                        # --- VERIFICACIÓN DE ABORTO ---
                        if self.cancelar_proceso:
                            conn.rollback()
                            self.escribir_auditoria(f"⚠️ PROCESO ABORTADO MANUALMENTE en tabla {tabla}.")
                            raise Exception("Proceso abortado por el usuario.")
                            
                        # --- REORDENAMIENTO AUTOMÁTICO DE COLUMNAS ---
                        fila_reordenada = []
                        for idx_csv in mapeo_indices:
                            if idx_csv != -1 and idx_csv < len(fila_cruda):
                                fila_reordenada.append(fila_cruda[idx_csv])
                            else:
                                fila_reordenada.append("") # Enviar vacío para que SQL decida (NULL/Default)
                        # ---------------------------------------------

                        fila_procesada = self._transformar_fila(fila_reordenada, col_count, columnas_sql, acepta_nulos)
                        batch_data.append(fila_procesada)

                        if len(batch_data) >= batch_size:
                            try:
                                cursor.executemany(insert_query, batch_data)
                                conn.commit()
                                total_insertados += len(batch_data)
                                self.log(f"Insertados {total_insertados} registros...")
                                # --- REGISTRO DE AUDITORÍA FISICA ---
                                self.escribir_auditoria(f"✅ ÉXITO: {len(batch_data)} registros insertados en [{db_name}].{tabla}. Origen de datos: {self.archivo_csv}")
                                batch_data.clear()
                            except Exception as e_batch:
                                # 🔍 MODO FRANCOTIRADOR: Buscar la fila exacta del error
                                self.log("⚠️ Error en bloque masivo. Buscando la fila exacta que causó el problema...")

                                # ---> NUEVAS LÍNEAS DE AVISO AL USUARIO <---
                                self.log("⏳ Entrando en Modo Depuración. Esto puede tomar hasta un minuto. Por favor, no cierres la app...")
                                self.after(0, lambda: self.btn_iniciar.configure(text="🔍 RASTREANDO ERROR..."))
                                # ------------------------------------------
                                
                                # 🚑 SALVAVIDAS: Limpiar la transacción abortada
                                conn.rollback()
                                
                                # 🚨 REPARACIÓN ANTI-CRASH: Cerrar el cursor corrupto y crear uno limpio
                                cursor.close()
                                cursor_debug = conn.cursor()
                               
                                if tiene_identity and forzar_identity:
                                    cursor_debug.execute(f"SET IDENTITY_INSERT {esquema}.{tabla} ON")

                                for f_debug in batch_data:
                                    try:
                                        cursor_debug.execute(insert_query, f_debug)
                                    except Exception as e_row:
                                        datos_malos = "\n".join([f"   -> {col}: {val}" for col, val in zip(columnas_sql, f_debug)])
                                        self.log("❌ SE ENCONTRÓ UN DATO INCOMPATIBLE:")
                                        self.log(datos_malos)
                                        raise Exception(f"Fallo en la columna por tipo de dato incorrecto.\nRevisa el log para ver el valor exacto.\nDetalle: {e_row}")

                    if batch_data:
                        try:
                            cursor.executemany(insert_query, batch_data)
                            conn.commit()
                            total_insertados += len(batch_data)
                            self.log(f"Insertados {total_insertados} registros...")
                            # --- REGISTRO DE AUDITORÍA FISICA ---
                            self.escribir_auditoria(f"✅ ÉXITO: {len(batch_data)} registros insertados en [{db_name}].{tabla}. Origen de datos: {self.archivo_csv}")
                            batch_data.clear()
                        except Exception as e_batch:
                            # 🔍 MODO FRANCOTIRADOR PARA EL ÚLTIMO LOTE
                            self.log("⚠️ Error masivo en bloque final. Buscando la fila exacta...")
                            
                            # 🚑 SALVAVIDAS
                            conn.rollback()
                            
                            # 🚨 REPARACIÓN ANTI-CRASH: Cerrar el cursor corrupto y crear uno limpio
                            cursor.close()
                            cursor_debug = conn.cursor()

                            if tiene_identity and forzar_identity:
                                cursor_debug.execute(f"SET IDENTITY_INSERT {esquema}.{tabla} ON")

                            for f_debug in batch_data:
                                try:
                                    cursor_debug.execute(insert_query, f_debug)
                                except Exception as e_row:
                                    datos_malos = "\n".join([f"   -> {col}: {val}" for col, val in zip(columnas_sql, f_debug)])
                                    self.log("❌ SE ENCONTRÓ UN DATO INCOMPATIBLE:")
                                    self.log(datos_malos)
                                    raise Exception(f"Fallo en la columna por tipo de dato incorrecto.\nRevisa el log para ver el valor exacto.\nDetalle: {e_row}")

                # --- RAMA 2: LOGICA POSTGRESQL ---
                else: 
                    csv_buffer = io.StringIO()
                    writer = csv.writer(csv_buffer, delimiter='\t', quoting=csv.QUOTE_MINIMAL)
                    lineas_en_buffer = 0

                    for fila in reader:
                        # --- AGREGAR ESTA VERIFICACIÓN AQUÍ TAMBIÉN ---
                        if self.cancelar_proceso:
                            conn.rollback()
                            self.escribir_auditoria(f"⚠️ PROCESO ABORTADO MANUALMENTE en tabla {tabla}.")
                            raise Exception("Proceso abortado por el usuario.")
                        # ----------------------------------------------
                        # 
                        fila_procesada = self._transformar_fila(fila, col_count, columnas_sql, acepta_nulos)
                        fila_procesada = ["" if x is None else x for x in fila_procesada]
                        writer.writerow(fila_procesada)
                        lineas_en_buffer += 1

                        if lineas_en_buffer >= batch_size:
                            csv_buffer.seek(0)
                            cursor.copy_expert(f"COPY {esquema}.{tabla} FROM STDIN WITH (FORMAT CSV, DELIMITER '\t', NULL '')", csv_buffer)
                            conn.commit()
                            total_insertados += lineas_en_buffer
                            # --- REGISTRO DE AUDITORÍA FISICA ---
                            self.escribir_auditoria(f"✅ ÉXITO: {len(batch_data)} registros insertados en [{db_name}].{tabla}. Origen de datos: {self.archivo_csv}")
                            self.log(f"Insertados {total_insertados} registros mediante COPY...")
                            
                            csv_buffer.seek(0)
                            csv_buffer.truncate(0)
                            lineas_en_buffer = 0

                    if lineas_en_buffer > 0:
                        csv_buffer.seek(0)
                        cursor.copy_expert(f"COPY {esquema}.{tabla} FROM STDIN WITH (FORMAT CSV, DELIMITER '\t', NULL '')", csv_buffer)
                        conn.commit()
                        total_insertados += lineas_en_buffer
                        # --- REGISTRO DE AUDITORÍA FISICA ---
                        self.escribir_auditoria(f"✅ ÉXITO: {len(batch_data)} registros insertados en [{db_name}].{tabla}. Origen de datos: {self.archivo_csv}")
                        
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
            
            if 'tiene_identity' in locals() and tiene_identity and forzar_identity:
                try:
                    cur_off = conn.cursor()
                    cur_off.execute(f"SET IDENTITY_INSERT {esquema}.{tabla} OFF")
                    cur_off.close()
                except Exception:
                    pass
            

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


    def al_seleccionar_servidor_global(self, display_name):
        if display_name in ["Seleccione un servidor...", "No hay servidores"]:
            self.cmb_dbs_global.set("Primero conecte...")
            self.cmb_dbs_global.configure(values=["Primero conecte..."])
            return
            
        srv = self.obtener_credenciales(display_name)
        if not srv: return
        self.cmb_dbs_global.set("Cargando BDs...")
        
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
                    self.cmb_dbs_global.configure(values=dbs)
                    self.cmb_dbs_global.set(dbs[0])
            except Exception as e:
                self.log_global(f"Error cargando BDs globales: {e}")
            finally:
                if conn: conn.close()
                
        threading.Thread(target=cargar, daemon=True).start()

    def limpiar_orquestador(self):
        for widget in self.scroll_orquestador.winfo_children():
            widget.destroy()
        self.inputs_volumen.clear()
        self.log_global("🗑️ Plan de ambientación vaciado. Listo para agregar nuevas bases de datos.")

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
        def actualizar_log():
            self.txt_log_dummy.insert("end", f"[{hora}] {mensaje}\n")
            self.txt_log_dummy.see("end")
        self.after(0, actualizar_log)

    def validar_tabla_dummy(self):
        srv_name = self.cmb_servidores_dummy.get()
        db_name = self.cmb_dbs_dummy.get()
        tabla_input = self.ent_tabla_dummy.get().strip()
        
        if not tabla_input:
            self.lbl_tabla_status_dummy.configure(text="❌ Escriba un nombre de tabla", text_color="#ff4444")
            return

        # ==========================================
        # AUTO-COMPLETAR REGLAS (USANDO LLAVE MAESTRA)
        # ==========================================
        memoria = cargar_relaciones()
        clave_memoria = f"{srv_name}|{db_name}"
        
        # Buscamos primero con la llave nueva, si no existe, intentamos con la vieja (fallback)
        datos_db = memoria.get(clave_memoria, memoria.get(db_name, {}))
        reglas_guardadas = datos_db.get("tablas", {}).get(tabla_input.lower(), "")
        
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
        srv_name = self.cmb_servidores_dummy.get()
        db_name = self.cmb_dbs_dummy.get()
        tabla = self.ent_tabla_dummy.get().strip()

        if not tabla or "Primero conecte" in db_name:
            self.log_dummy("⚠️ Escriba el nombre de la tabla en el campo superior antes de abrir el editor.")
            return

        clave_memoria = f"{srv_name}|{db_name}" # NUEVO: Llave compuesta para el JSON

        modal = ctk.CTkToplevel(self)
        modal.title(f"Editor Avanzado de Reglas - {tabla}")
        modal.geometry("580x450")
        modal.grab_set() 
        modal.transient(self) # Mantiene el modal ligado a la ventana principal

        # 1. Contenedor superior usando Grid para esquinas y centro
        frame_header = ctk.CTkFrame(modal, fg_color="transparent")
        frame_header.pack(fill="x", padx=20, pady=(15, 0))
        
        # Le damos todo el peso a la columna central (columna 1) para que empuje a los botones
        frame_header.grid_columnconfigure(1, weight=1) 

        # Esquina Izquierda: Botón IA
        btn_config_ia = ctk.CTkButton(frame_header, text="⚙️ IA", width=40, fg_color="#343a40", hover_color="#23272b", command=self.modal_configurar_llm)
        btn_config_ia.grid(row=0, column=0, sticky="w")

        # === NUEVO: Truncado inteligente para tablas largas ===
        tabla_mostrar = tabla.upper()
        if len(tabla_mostrar) > 22:
            tabla_mostrar = tabla_mostrar[:19] + "..."

        # Centro: Título principal (Simplificado y con padding)
        ctk.CTkLabel(frame_header, text=f"Reglas: {tabla_mostrar}", font=("Arial", 15, "bold")).grid(row=0, column=1, padx=10)

        # Esquina Derecha: Botón Auto-Perfilado
        btn_auto_ia = ctk.CTkButton(frame_header, text="✨ Auto-Perfilado", width=130, fg_color="#6f42c1", hover_color="#59339d", command=self.modal_prompt_ia)
        btn_auto_ia.grid(row=0, column=2, sticky="e")

        # 2. El subtítulo se empaqueta normal abajo del frame_header, por lo que queda centrado por defecto
        ctk.CTkLabel(modal, text="Escriba una regla por línea. Use el formato: columna : tabla.columna o columna : valores", text_color="#aaaaaa").pack(pady=(5, 10))

        # --- DECLARAR Y VINCULAR EL TEXTBOX ---
        txt_modal = ctk.CTkTextbox(modal, width=540, height=280, fg_color="#1a1a1a", font=("Consolas", 13))
        txt_modal.pack(pady=5, padx=20, fill="both", expand=True)
        
        # 🔗 Guardamos la referencia para que la IA sepa a dónde enviar el texto
        self.txt_editor_activo = txt_modal

        # Evento para limpiar la referencia cuando el modal se cierre
        def al_cerrar():
            self.txt_editor_activo = None
            modal.destroy()
            
        modal.protocol("WM_DELETE_WINDOW", al_cerrar)

        reglas_actuales = self.txt_relaciones.get("1.0", "end-1c")
        if reglas_actuales.startswith("Ej."):
            txt_modal.insert("1.0", "")
        else:
            txt_modal.insert("1.0", reglas_actuales)

        def guardar_modal():
            nuevas_reglas = txt_modal.get("1.0", "end-1c").strip()
            self.txt_relaciones.delete("1.0", "end")
            self.txt_relaciones.insert("1.0", nuevas_reglas)
            
            if nuevas_reglas and not nuevas_reglas.startswith("Ej."):
                memoria = cargar_relaciones()
                if clave_memoria not in memoria:
                    memoria[clave_memoria] = {"_configuracion_global": {}, "tablas": {}}
                memoria[clave_memoria]["tablas"][tabla.lower()] = nuevas_reglas
                guardar_relaciones(memoria)
                self.log_dummy(f"💾 Reglas guardadas en entorno híbrido para '{tabla}'.")

            al_cerrar() # Usamos la nueva función de cerrado

        frame_botones = ctk.CTkFrame(modal, fg_color="transparent")
        frame_botones.pack(pady=15)
        
        # Conectamos el botón cancelar a la nueva función de cerrado
        ctk.CTkButton(frame_botones, text="❌ Cancelar", fg_color="#6c757d", hover_color="#5a6268", command=al_cerrar).pack(side="left", padx=5)
        ctk.CTkButton(frame_botones, text="🔗 Vincular Externa", fg_color="#fd7e14", hover_color="#e36414", command=lambda: self.modal_vincular_externa(txt_modal)).pack(side="left", padx=5)
        ctk.CTkButton(frame_botones, text="💾 Guardar en Interfaz", fg_color="#28a745", hover_color="#218838", command=guardar_modal).pack(side="left", padx=5)

    def modal_vincular_externa(self, txt_modal):
        modal_ext = ctk.CTkToplevel(self)
        modal_ext.title("Vincular Tabla Externa")
        modal_ext.geometry("450x380")
        modal_ext.transient(self)
        modal_ext.grab_set()

        ctk.CTkLabel(modal_ext, text="Columna Local (La que recibe el dato):", font=("Arial", 12)).pack(pady=(15,0))
        ent_local = ctk.CTkEntry(modal_ext, width=280, placeholder_text="Ej. id_cliente")
        ent_local.pack(pady=5)

        ctk.CTkLabel(modal_ext, text="1. Servidor Externo Origen:", font=("Arial", 12)).pack(pady=(10,0))
        cmb_srv = ctk.CTkComboBox(modal_ext, width=280, values=list(self.mapa_servidores.keys()))
        cmb_srv.pack(pady=5)

        ctk.CTkLabel(modal_ext, text="2. Base de Datos Externa:", font=("Arial", 12)).pack(pady=(10,0))
        ent_db = ctk.CTkEntry(modal_ext, width=280, placeholder_text="Ej. corporativo_db")
        ent_db.pack(pady=5)

        ctk.CTkLabel(modal_ext, text="3. Tabla y Columna Origen:", font=("Arial", 12)).pack(pady=(10,0))
        frame_tc = ctk.CTkFrame(modal_ext, fg_color="transparent")
        frame_tc.pack(pady=5)
        ent_tabla = ctk.CTkEntry(frame_tc, width=135, placeholder_text="Tabla (Ej. clientes)")
        ent_tabla.pack(side="left", padx=5)
        ent_col = ctk.CTkEntry(frame_tc, width=135, placeholder_text="Columna (Ej. id)")
        ent_col.pack(side="left", padx=5)

        def insertar():
            local = ent_local.get().strip()
            srv = cmb_srv.get().strip()
            db = ent_db.get().strip()
            tabla = ent_tabla.get().strip()
            col = ent_col.get().strip()

            if not all([local, srv, db, tabla, col]) or srv == "Seleccione un servidor...":
                DialogoModerno(self, "Incompleto", "Llena todos los campos y elige un servidor válido.", tipo="warning")
                return

            # Construye la sintaxis mágica: id_cliente : [Servidor_Prueba].[mi_bd].[clientes].id
            regla_generada = f"{local} : [{srv}].[{db}].[{tabla}].{col}\n"
            
            # Asegurar que se inserta en una nueva línea limpia
            if txt_modal.get("end-2c", "end-1c") != "\n":
                txt_modal.insert("end", "\n")
                
            txt_modal.insert("end", regla_generada)
            modal_ext.destroy()

        ctk.CTkButton(modal_ext, text="Insertar Regla", font=("Arial", 12, "bold"), fg_color="#fd7e14", hover_color="#e36414", command=insertar).pack(pady=20)

    # ==========================================
    # LÓGICA DE GENERACIÓN DUMMY AUTOMÁTICA
    # ==========================================

    def ejecutar_generacion_dummy(self):
        srv_name = self.cmb_servidores_dummy.get()
        db_name = self.cmb_dbs_dummy.get()
        tabla = self.ent_tabla_dummy.get().strip()
        cantidad_str = self.ent_cantidad_dummy.get().strip()
        reglas_str = self.txt_relaciones.get("1.0", "end").strip()

        if not tabla or not cantidad_str.isdigit():
            self.log_dummy("❌ Error: Especifique una tabla y una cantidad numérica válida.")
            return

        # ==========================================
        # APRENDIZAJE AUTOMÁTICO (USANDO LLAVE MAESTRA)
        # ==========================================
        clave_memoria = f"{srv_name}|{db_name}"
        if reglas_str and not reglas_str.startswith("Ej."):
            memoria = cargar_relaciones()
            if clave_memoria not in memoria:
                memoria[clave_memoria] = {"_configuracion_global": {}, "tablas": {}}
                
            if memoria[clave_memoria].get("tablas", {}).get(tabla.lower()) != reglas_str:
                memoria[clave_memoria]["tablas"][tabla.lower()] = reglas_str
                guardar_relaciones(memoria)
                self.log_dummy(f"💾 Reglas guardadas para '{tabla}' en '{clave_memoria}'.")

        srv = self.obtener_credenciales(srv_name)
        if not srv or "Primero conecte" in db_name:
            self.log_dummy("❌ Error: Seleccione un servidor y una base de datos válida.")
            return

        self.btn_generar_dummy.configure(state="disabled", text="⏳ Generando datos...")
        threading.Thread(target=self._hilo_generar_dummy, args=(srv, srv_name, db_name, tabla, int(cantidad_str), reglas_str), daemon=True).start()    

    def _hilo_generar_dummy(self, srv, srv_name, db_name, tabla, cantidad, reglas_str, silencioso=False):
        from faker import Faker
        import random
        import csv
        import re
        from datetime import datetime
        
        fake = Faker('es_MX')
        
        conn = None
        try:
            conn = self.conectar_db(srv, db_name)
            cursor = conn.cursor()
            esquema = "dbo" if srv["tipo"] == "SQL Server" else "public"

            query_cols = f"SELECT COLUMN_NAME, DATA_TYPE, CHARACTER_MAXIMUM_LENGTH FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = '{tabla}' AND TABLE_SCHEMA = '{esquema}' ORDER BY ORDINAL_POSITION"
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
                    ids = [str(row[0]) for row in cursor.fetchall() if row[0] is not None]
                    
                    if ids:
                        fks_data[col_local] = ids
                        self.log_dummy(f" ✅ Relación '{col_local}': {len(ids)} IDs extraídos de '{tabla_ref}'.")
                except Exception:
                    pass

            # =========================================================
            # MOTOR DE REGLAS Y PRE-CARGA DE CATÁLOGOS MAESTROS
            # =========================================================
            reglas_custom = {} 
            reglas_math = {} 
            tablas_maestras = {} # 🧠 NUEVO: Guardará catálogos completos para sincronización
            
            if reglas_str and not reglas_str.startswith("Ej."):
                self.log_dummy("🧠 Procesando reglas de negocio manuales...")
                lineas = reglas_str.split('\n')
                
                for linea in lineas:
                    if ':' not in linea: continue
                    col_local, regla = linea.split(':', 1)
                    col_local = col_local.strip()
                    cn = col_local.lower() 
                    regla = regla.strip()
                    
                    if regla.startswith('='):
                        reglas_math[cn] = regla[1:].strip()
                        self.log_dummy(f" 🧮 Regla matemática detectada para '{col_local}'.")
                        continue
                    
                    match_federado = re.search(r'^\[(?!\d+-\d+)(.*?)\]\.\[(?!\d+-\d+)(.*?)\]\.\[(?!\d+-\d+)(.*?)\]\.(.*)', regla)
                    
                    if match_federado:
                        srv_ext_name, db_ext, tabla_ext, col_ext = match_federado.groups()
                        srv_ext = self.obtener_credenciales(srv_ext_name)
                        if srv_ext:
                            try:
                                self.log_dummy(f"🌐 Conectando a BD externa '{db_ext}' en '{srv_ext_name}'...")
                                conn_ext = self.conectar_db(srv_ext, db_ext)
                                cur_ext = conn_ext.cursor()
                                esq_ext = "dbo" if srv_ext["tipo"] == "SQL Server" else "public"
                                
                                q_ids = f"SELECT TOP 10000 {col_ext.strip()} FROM {esq_ext}.{tabla_ext.strip()}" if srv_ext["tipo"] == "SQL Server" else f"SELECT {col_ext.strip()} FROM {esq_ext}.{tabla_ext.strip()} LIMIT 10000"
                                cur_ext.execute(q_ids)
                                ids = [str(row[0]) for row in cur_ext.fetchall() if row[0] is not None]
                                
                                if ids:
                                    fks_data[col_local] = ids
                                    self.log_dummy(f" 🔗 Cross-Server OK: {len(ids)} IDs obtenidos de '{tabla_ext}'.")
                                conn_ext.close()
                            except Exception as e:
                                self.log_dummy(f" ❌ Error en Cross-Server '{col_local}': {e}")
                        else:
                            self.log_dummy(f" ❌ Servidor externo '{srv_ext_name}' no registrado.")
                        continue 
                    
                    # === NUEVO: IDENTIFICAR TABLAS PARA SINCRONIZACIÓN MAESTRA ===
                    tablas_a_cargar = set()
                    
                    # 1. Si es una referencia directa tabla.columna
                    if '.' in regla and ',' not in regla and '#' not in regla and '?' not in regla and '[' not in regla and '<<' not in regla:
                        t_ref, c_ref = regla.split('.')
                        tablas_a_cargar.add(t_ref.strip().lower())
                    
                    # 2. Si es una plantilla con inyección <<tabla.columna>>
                    for t_match, c_match in re.findall(r'<<([^>]+)\.([^>]+)>>', regla):
                        tablas_a_cargar.add(t_match.strip().lower())

                    # Cargar los catálogos en memoria si no existen
                    for t_ref in tablas_a_cargar:
                        if t_ref not in tablas_maestras:
                            try:
                                self.log_dummy(f" 📥 Descargando catálogo '{t_ref}' para sincronización correlacionada...")
                                q_master = f"SELECT TOP 10000 * FROM {esquema}.{t_ref}" if srv["tipo"] == "SQL Server" else f"SELECT * FROM {esquema}.{t_ref} LIMIT 10000"
                                cursor.execute(q_master)
                                cols_fk = [desc[0].lower() for desc in cursor.description]
                                filas_fk = []
                                for row_data in cursor.fetchall():
                                    filas_fk.append({cols_fk[i]: row_data[i] for i in range(len(cols_fk))})
                                
                                if filas_fk:
                                    tablas_maestras[t_ref] = filas_fk
                                    self.log_dummy(f"    ✅ {len(filas_fk)} registros maestros cargados de '{t_ref}'.")
                            except Exception as e:
                                self.log_dummy(f" ⚠️ Aviso: No se pudo descargar el catálogo '{t_ref}': {e}")

                    reglas_custom[col_local] = regla
            # =========================================================

            self.log_dummy(f"🎲 Escribiendo {cantidad} registros dummy...")
            nombre_archivo = f"dummy_{tabla}_{datetime.now().strftime('%H%M%S')}.csv"
            
            with open(nombre_archivo, 'w', encoding='utf-8', newline='') as f:
                writer = csv.writer(f, delimiter=',')
                writer.writerow([c[0] for c in columnas]) 

                # =========================================================
                # PRE-CARGA DE SECUENCIAS (BUSCADOR DE HUECOS EN RAM)
                # =========================================================
                secuencias_estado = {}
                for c_loc, regla in reglas_custom.items():
                    match_seq = re.search(r'\[secuencia:(\d+)\]', regla, re.IGNORECASE)
                    if match_seq:
                        inicio = int(match_seq.group(1))
                        c_safe = f"[{c_loc}]" if srv["tipo"] == "SQL Server" else f'"{c_loc}"'
                        tabla_safe = f"[{tabla}]" if srv["tipo"] == "SQL Server" else f'"{tabla}"'
                        try:
                            self.log_dummy(f" 🔢 Mapeando IDs usados en '{c_loc}' para rellenar huecos...")
                            cursor.execute(f"SELECT {c_safe} FROM {esquema}.{tabla_safe}")
                            # Guardamos en un Set (búsqueda en O(1) ultrarrápida)
                            usados = set(int(row[0]) for row in cursor.fetchall() if row[0] is not None)
                        except Exception:
                            usados = set()

                        secuencias_estado[c_loc.lower()] = {"siguiente": inicio, "usados": usados}
                # =========================================================

                self.log_dummy(f"🎲 Escribiendo {cantidad} registros dummy...")

                for _ in range(cantidad):
                    fila_dict = {} 
                    
                    # === NUEVO: ELEGIR 1 REGISTRO MAESTRO POR CADA TABLA FORÁNEA ===
                    registros_sincronizados = {}
                    for t_ref, lista_registros in tablas_maestras.items():
                        registros_sincronizados[t_ref] = random.choice(lista_registros)

                    # FASE 1: Generar los datos normales
                    for col_name, data_type, max_len in columnas:
                        col_limpia = col_name.strip()
                        cn = col_limpia.lower()
                        
                        if cn in reglas_math:
                            fila_dict[col_limpia] = 0
                            continue

                        # 🥇 IMPORTANTE: Evaluamos las reglas manuales PRIMERO 
                        if col_limpia in reglas_custom:
                            regla = reglas_custom[col_limpia]

                            # === NUEVO: 0.1 INYECCIÓN DE SECUENCIAS INTELIGENTES ===
                            if cn in secuencias_estado:
                                estado = secuencias_estado[cn]
                                val = estado["siguiente"]
                                
                                # Si el número ya existe en la BD, saltamos al siguiente
                                while val in estado["usados"]:
                                    val += 1
                                    
                                fila_dict[col_limpia] = val
                                estado["usados"].add(val) # Lo marcamos como usado para la siguiente fila
                                estado["siguiente"] = val + 1
                                continue
                            # ========================================================
                            
                            # Caso A: Relación directa sincronizada (ej. cenciudades.Bodega)
                            if '.' in regla and ',' not in regla and '#' not in regla and '?' not in regla and '[' not in regla and '<<' not in regla:
                                t_ref, c_ref = regla.split('.')
                                t_ref = t_ref.strip().lower()
                                c_ref = c_ref.strip().lower()
                                
                                if t_ref in registros_sincronizados and c_ref in registros_sincronizados[t_ref]:
                                    fila_dict[col_limpia] = registros_sincronizados[t_ref][c_ref]
                                else:
                                    fila_dict[col_limpia] = None 
                                continue
                                
                            # Caso B: Lista estática (Enum)
                            if ',' in regla: 
                                opciones = [opt.strip() for opt in regla.split(',')]
                                fila_dict[col_limpia] = random.choice(opciones)
                                continue

                            texto_final = regla

                            # === NUEVO: 0.1. Resolver Secuencias Autoincrementales [secuencia:N] ===
                            match_seq = re.search(r'\[secuencia:(\d+)\]', texto_final, re.IGNORECASE)
                            if match_seq:
                                val_actual = int(match_seq.group(1))
                                fila_dict[col_limpia] = val_actual
                                # ¡EL TRUCO MAGICO! Actualizamos la regla original para que la SIGUIENTE fila use el +1
                                reglas_custom[col_limpia] = regla.replace(match_seq.group(0), f"[secuencia:{val_actual + 1}]")
                                continue 
                            # ========================================================================

                            # 0. Límite manual
                            limite_manual = None
                            match_max = re.search(r'\[max:(\d+)\]', texto_final, re.IGNORECASE)
                            if match_max:
                                limite_manual = int(match_max.group(1))
                                texto_final = texto_final.replace(match_max.group(0), '').strip()

                            # === NUEVO: 0.5. Resolver Inyecciones Inline de BD (ej. <<tabla.col>>) ===
                            for t_match, c_match in re.findall(r'<<([^>]+)\.([^>]+)>>', texto_final):
                                t_ref = t_match.strip().lower()
                                c_ref = c_match.strip().lower()
                                if t_ref in registros_sincronizados and c_ref in registros_sincronizados[t_ref]:
                                    valor_inyeccion = str(registros_sincronizados[t_ref][c_ref])
                                    texto_final = texto_final.replace(f"<<{t_match}.{c_match}>>", valor_inyeccion, 1)

                            # 1. Resolver Rangos
                            while re.search(r'\[(\d+)-(\d+)\]', texto_final):
                                match = re.search(r'\[(\d+)-(\d+)\]', texto_final)
                                min_v = int(match.group(1))
                                max_v = int(match.group(2))
                                num_azar = str(random.randint(min_v, max_v))
                                texto_final = texto_final.replace(match.group(0), num_azar, 1)

                            # 2. Faker
                            for etiqueta in re.findall(r'\{\{([^}]+)\}\}', texto_final):
                                metodo = etiqueta.strip()
                                if hasattr(fake, metodo):
                                    try:
                                        valor_generado = str(getattr(fake, metodo)())
                                        texto_final = texto_final.replace(f"{{{{{etiqueta}}}}}", valor_generado, 1)
                                    except Exception:
                                        pass
                            
                            # 3. Bothify y Aplicar Límite Manual
                            resultado_texto = fake.bothify(text=texto_final)
                            if limite_manual:
                                resultado_texto = resultado_texto[:limite_manual].strip()
                                
                            fila_dict[col_limpia] = resultado_texto
                            continue
                        
                        # 🥈 Evaluamos Llaves Foráneas Nativas si el usuario no escribió una regla
                        elif col_limpia in fks_data and fks_data[col_limpia]:
                            fila_dict[col_limpia] = random.choice(fks_data[col_limpia])
                            continue
                            
                        # 🥉 Datos aleatorios por defecto
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
                        if isinstance(v, str):
                            try:
                                val = float(v) if '.' in v else int(v)
                            except ValueError:
                                pass 
                        locals_eval[k.lower()] = val
                    
                    for cn_math, expresion in reglas_math.items():
                        try:
                            exp_baja = expresion.lower()
                            resultado = eval(exp_baja, {"__builtins__": None}, locals_eval)
                            
                            for original_col in fila_dict.keys():
                                if original_col.lower() == cn_math:
                                    if isinstance(resultado, (int, float)):
                                        fila_dict[original_col] = int(resultado) if isinstance(resultado, float) and resultado.is_integer() else round(resultado, 2)
                                    else:
                                        fila_dict[original_col] = str(resultado)
                                        
                                    locals_eval[cn_math] = fila_dict[original_col] 
                                    break
                        except Exception as e:
                            self.log_dummy(f"⚠️ Error matemático en '{cn_math}': Revisar variables.")
                            pass
                            
                    # FASE 3: Convertir a lista y aplicar TRUNCADO AUTOMÁTICO DE SEGURIDAD
                    fila_lista = []
                    for c in columnas:
                        nom_col = c[0].strip()
                        limite_bd = c[2] 
                        valor = fila_dict[nom_col]
                        
                        if limite_bd and limite_bd > 0 and isinstance(valor, str) and len(valor) > limite_bd:
                            self.log_dummy(f"⚠️ Aviso: Se auto-recortó la columna '{nom_col}' de {len(valor)} a {limite_bd} caracteres para evitar error en SQL.")
                            valor = valor[:limite_bd].strip() 
                            
                        fila_lista.append(valor)
                        
                    writer.writerow(fila_lista)
            
            # ... (código previo del escritor CSV)
            self.log_dummy(f"✅ Archivo '{nombre_archivo}' completado.")
            self.archivo_csv = nombre_archivo

            # --- CORRECCIÓN DE HILOS AQUÍ ---
            # Solo actualizamos la UI si NO es el orquestador global
            if not silencioso:
                def actualizar_ui_dummy():
                    self.lbl_archivo.configure(text=nombre_archivo)
                    self.cmb_servidores.set(srv_name)
                    self.cmb_dbs.configure(values=self.cmb_dbs_dummy.cget("values"))
                    self.cmb_dbs.set(db_name)
                    self.ent_tabla.delete(0, 'end')
                    self.ent_tabla.insert(0, tabla)
                    self.lbl_tabla_status.configure(text=f"✅ Datos sincronizados. Listo para cargar.", text_color="#00C851")
                    self.tabview.set("Carga Masiva")
                    
                # Mandar la actualización al hilo principal de Tkinter
                self.after(0, actualizar_ui_dummy)
                self.log("📁 CSV Dummy auto-asignado. Presione Iniciar Carga Masiva.")

        except Exception as e:
            self.log_dummy(f"❌ Error generando dummy: {e}")
            if silencioso:
                raise e # Si falla el orquestador, rompemos para que salte el log de error
        finally:
            if conn: conn.close()
            if not silencioso:
                self.after(0, lambda: self.btn_generar_dummy.configure(state="normal", text="🎲 Generar CSV Dummy"))

    def escanear_dependencias(self, usar_cache=True):
        db_name = self.cmb_dbs_global.get()
        srv_name = self.cmb_servidores_global.get()

        if srv_name in ["Seleccione un servidor...", "No hay servidores"]:
            srv_name = self.cmb_servidores_global.get()
            
        if "Primero conecte" in db_name or srv_name in ["Seleccione un servidor...", "No hay servidores"]:
            DialogoModerno(self, "Falta Conexión", "Por favor, selecciona tu servidor y conecta una BD.", tipo="warning").obtener_resultado()
            return

        self.btn_escanear_db.configure(state="disabled", text="⏳ Cargando...")
        self.update() 
        
        srv = self.obtener_credenciales(srv_name)
        if not srv: 
            self.btn_escanear_db.configure(state="normal", text="➕ Agregar al Plan")
            return


        memoria = cargar_relaciones()
        clave_memoria = f"{srv_name}|{db_name}"
        
        # Obtener datos usando la llave compuesta o la vieja como respaldo
        datos_db = memoria.get(clave_memoria, memoria.get(db_name, {}))
        conf_global = datos_db.get("_configuracion_global", {})
        
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
                if clave_memoria not in memoria: 
                    memoria[clave_memoria] = {"_configuracion_global": {}, "tablas": {}}
                memoria[clave_memoria]["_configuracion_global"]["orden_ejecucion"] = tablas_ordenadas
                memoria[clave_memoria]["_configuracion_global"]["arbol_dependencias"] = dependencias
                memoria[clave_memoria]["_configuracion_global"]["niveles"] = niveles
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

            clave_maestra = f"{srv_name}|{db_name}|{tabla}"

            if clave_maestra in self.inputs_volumen:
                continue

            row_frame = ctk.CTkFrame(self.scroll_orquestador, fg_color=("#333333" if idx % 2 == 0 else "#2a2a2a"))
            row_frame.pack(fill="x", pady=2, padx=5)
            
            # Usar .get(tabla, 0) por si el nivel no existe en alguna migración
            ctk.CTkLabel(row_frame, text=f"Lvl {niveles.get(tabla, 0)}", width=40, font=("Arial", 11, "bold"), text_color="#17a2b8").pack(side="left", padx=10)
            ctk.CTkLabel(row_frame, text=f"[{db_name}]", font=("Arial", 10, "italic"), text_color="#f39c12", width=80, anchor="w").pack(side="left")
            ctk.CTkLabel(row_frame, text=tabla, width=180, anchor="w").pack(side="left", padx=5)

            btn_reglas = ctk.CTkButton(row_frame, text="📄 Reglas", width=60, height=24, fg_color="#6c757d", hover_color="#5a6268", command=lambda t=tabla, db=db_name, srv=srv_name: self.mostrar_reglas_rapidas(t, db, srv))
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
            
            # NUEVO: Guardamos la referencia usando la clave maestra
            self.inputs_volumen[clave_maestra] = {"entry": ent_vol, "modo": cmb_modo_var, "nivel": niveles.get(tabla, 0), "frame": row_frame, "srv_name": srv_name, "db_name": db_name, "tabla": tabla}

        self.log_global(f"✅ Agregado: {db_name} ({len(tablas_ordenadas)} tablas).")
        self.btn_escanear_db.configure(state="normal", text="➕ Agregar al Plan")
    
    def ejecutar_orquestador(self):
        import re
        if not getattr(self, 'inputs_volumen', None):
            messagebox.showwarning("Atención", "Primero haz clic en 'Escanear Dependencias' para cargar el árbol de tablas.")
            return

        # 1. Recopilar todos los nodos seleccionados para "Generar" (Vértices del grafo)
        # Usamos la clave maestra: "Srv|DB|Tabla"
        nodos_generar = {}
        for clave, controles in self.inputs_volumen.items():
            if controles["modo"].get() == "Generar":
                try:
                    cantidad = int(controles["entry"].get())
                    if cantidad > 0:
                        nodos_generar[clave] = {
                            "srv_name": controles["srv_name"],
                            "db_name": controles["db_name"],
                            "tabla": controles["tabla"],
                            "cantidad": cantidad,
                            "nivel": controles.get("nivel", 0) # Traemos el nivel calculado localmente
                        }
                except ValueError:
                    pass
                    
        if not nodos_generar:
            DialogoModerno(self, "Sin acciones", "No hay tablas marcadas para 'Generar' con filas mayores a 0.", tipo="info").obtener_resultado()
            return
            
        try:
            limite_seguridad = int(self.ent_limite_tablas.get())
        except ValueError:
            limite_seguridad = 5 
            
        if len(nodos_generar) > limite_seguridad:
            DialogoModerno(self,
                "Límite de Seguridad Excedido", 
                f"Has intentado ambientar {len(nodos_generar)} tablas a la vez, pero tu límite actual es {limite_seguridad}.\n\n"
                "Por favor, regresa más tablas a 'Solo Lectura' o aumenta el límite bajo tu propio riesgo.",
            tipo="error").obtener_resultado()
            return

        # =======================================================
        # RETO 1: TOPOLOGICAL SORT GLOBAL (KAHN'S ALGORITHM)
        # =======================================================
        grafo = {clave: [] for clave in nodos_generar}      # Padre -> Lista de Hijos
        in_degree = {clave: 0 for clave in nodos_generar}   # Nodo -> Cantidad de dependencias que debe esperar

        memoria = cargar_relaciones()

        # 2. Construir Aristas (Conectar las dependencias)
        for clave, datos in nodos_generar.items():
            srv = datos["srv_name"]
            db = datos["db_name"]
            tabla = datos["tabla"]
            nivel_actual = datos["nivel"]

            # A) DEPENDENCIAS LOCALES: Respetar jerarquía nativa por cada BD independiente
            # Buscamos tablas del MISMO servidor y bd que tengan el nivel inmediatamente anterior
            niveles_menores = [
                n["nivel"] for k, n in nodos_generar.items() 
                if n["srv_name"] == srv and n["db_name"] == db and n["nivel"] < nivel_actual
            ]
            if niveles_menores:
                nivel_padre_directo = max(niveles_menores)
                for k_padre, n_padre in nodos_generar.items():
                    if n_padre["srv_name"] == srv and n_padre["db_name"] == db and n_padre["nivel"] == nivel_padre_directo:
                        grafo[k_padre].append(clave)
                        in_degree[clave] += 1

            # B) DEPENDENCIAS GLOBALES: Cruce entre servidores vía JSON
            clave_memoria = f"{srv}|{db}"
            reglas_str = memoria.get(clave_memoria, {}).get("tablas", {}).get(tabla.lower(), "")
            
            # Buscar el patrón estricto [Srv].[Db].[Tabla] (ignorando la columna al final)
            matches = re.findall(r'\[([^\]]+)\]\.\[([^\]]+)\]\.\[([^\]]+)\]', reglas_str)
            for m in matches:
                srv_ext, db_ext, tabla_ext = m
                clave_padre_global = f"{srv_ext}|{db_ext}|{tabla_ext.lower()}"
                
                # Si la tabla externa de la que depende también está en el carrito, creamos el puente
                if clave_padre_global in nodos_generar:
                    grafo[clave_padre_global].append(clave)
                    in_degree[clave] += 1
                    self.log_global(f"🔗 Enlace global inyectado: [{db}].{tabla} esperará a [{db_ext}].{tabla_ext}")

        # 3. Resolución del Grafo (Orden de Ejecución Híbrido)
        queue = [clave for clave, deg in in_degree.items() if deg == 0]
        plan_ejecucion_global = []

        while queue:
            actual = queue.pop(0) # Tomar tabla libre de dependencias
            datos_actual = nodos_generar[actual]
            
            # Guardamos un diccionario rico con todo el contexto para el Reto 2
            plan_ejecucion_global.append({
                "srv_name": datos_actual["srv_name"],
                "db_name": datos_actual["db_name"],
                "tabla": datos_actual["tabla"],
                "cantidad": datos_actual["cantidad"]
            })
            
            # Avisamos a los hijos que este padre ya terminó
            for hijo in grafo[actual]:
                in_degree[hijo] -= 1
                if in_degree[hijo] == 0:
                    queue.append(hijo)

        # 4. Validar Deadlocks (Ciclos infinitos cross-server)
        if len(plan_ejecucion_global) != len(nodos_generar):
            DialogoModerno(self, "Error: Ciclo Infinito", "Se detectó una dependencia circular entre servidores (Ej. A depende de B, y B depende de A). Imposible resolver orden.", tipo="error").obtener_resultado()
            return
            
        confirmacion = DialogoModerno(
            self, 
            "Confirmar Plan Híbrido", 
            f"Se orquestarán {len(plan_ejecucion_global)} tablas cruzando bases de datos.\nEl orden calculado garantiza integridad referencial global.\n\n¿Desea continuar?", 
            tipo="pregunta", 
            con_cancelar=True
        ).obtener_resultado()
        
        if not confirmacion:
            return
                
        self.btn_iniciar_orquestador.configure(state="disabled", text="⏳ AMBIENTANDO EN CASCADA...")
        import threading
        
        # EL RETO 2 COMIENZA AQUÍ: 
        # Enviamos 'plan_ejecucion_global', que ahora contiene el srv_name y db_name por cada tabla.
        threading.Thread(target=self._hilo_orquestador, args=(plan_ejecucion_global,), daemon=True).start()

    def _hilo_orquestador(self, plan_ejecucion_global):
        memoria = cargar_relaciones()
        self.cancelar_proceso = False # Reiniciamos la bandera al iniciar
        
        try:
            for tarea in plan_ejecucion_global:
                # --- VERIFICACIÓN DE ABORTO ---
                if self.cancelar_proceso:
                    self.log_global("⚠️ Ambientación detenida a petición del usuario.")
                    break

                srv_name = tarea["srv_name"]
                db_name = tarea["db_name"]
                tabla = tarea["tabla"]
                cantidad = tarea["cantidad"]
                
                self.log(f"\n🚀 [ORQUESTADOR] Procesando: [{db_name}].{tabla.upper()} ({cantidad} filas)")
                
                # Obtener credenciales dinámicamente para este paso específico
                srv = self.obtener_credenciales(srv_name)
                if not srv:
                    raise Exception(f"No se encontraron credenciales para el servidor '{srv_name}'")

                # Cargar reglas buscando primero por la llave compuesta segura
                clave_memoria = f"{srv_name}|{db_name}"
                reglas_db = memoria.get(clave_memoria, {}).get("tablas", {})
                
                # Fallback por si la tabla se guardó antes de la migración de la estructura JSON
                if not reglas_db:
                    reglas_db = memoria.get(db_name, {}).get("tablas", {})
                    
                reglas_str = reglas_db.get(tabla.lower(), "")
                
                # --- CORRECCIÓN AQUÍ: Pasar silencioso=True ---
                # 1. Fuerza al generador Dummy a conectarse al motor correcto y crear el CSV
                self._hilo_generar_dummy(srv, srv_name, db_name, tabla, cantidad, reglas_str, silencioso=True)
                
                # 2. Fuerza al motor de Carga Masiva a insertarlo físicamente
                if getattr(self, 'archivo_csv', None):
                    self.procesar_csv_dual(srv, db_name, tabla, silencioso=True)
                    
            # Alerta final única
            self.after(0, lambda: DialogoModerno(self, "Orquestador Finalizado", "¡La ambientación masiva híbrida ha concluido con éxito para todas las tablas y servidores!", tipo="info"))
            
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

    def mostrar_reglas_rapidas(self, tabla, db_name, srv_name):
        memoria = cargar_relaciones()
        
        # 1. Construimos la llave maestra exacta que usamos al guardar
        clave_memoria = f"{srv_name}|{db_name}"
        
        # 2. Buscamos usando esa llave. Si no existe, devuelve el diccionario vacío y luego cadena vacía
        reglas = memoria.get(clave_memoria, {}).get("tablas", {}).get(tabla.lower(), "")

        modal = ctk.CTkToplevel(self)
        # 3. Pequeño detalle de UX: Mostrar de qué BD provienen estas reglas
        modal.title(f"Reglas Actuales - {tabla} ({db_name})")
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
    
    def auto_descubrir_reglas(self):
        srv_name = self.cmb_servidores_dummy.get()
        db_name = self.cmb_dbs_dummy.get()
        tabla = self.ent_tabla_dummy.get().strip()
        
        if not tabla or "Primero conecte" in db_name:
            self.log_dummy("❌ Error: Seleccione BD y escriba una tabla.")
            return
            
        srv = self.obtener_credenciales(srv_name)
        self.btn_autodescubrir.configure(state="disabled")
        self.log_dummy(f"🔍 Escaneando tabla '{tabla}' localmente...")
        
        threading.Thread(target=self._hilo_auto_descubrir, args=(srv, srv_name, db_name, tabla), daemon=True).start()

    def _hilo_auto_descubrir(self, srv, srv_name, db_name, tabla):
        conn = None
        reglas_sugeridas = []
        orden_columnas = []
        try:
            conn = self.conectar_db(srv, db_name)
            cursor = conn.cursor()
            esquema = "dbo" if srv["tipo"] == "SQL Server" else "public"

            # === 1. DETECTAR LLAVES PRIMARIAS (PRIMARY KEYS) ===
            pks = []
            try:
                if srv["tipo"] == "SQL Server":
                    cursor.execute(f"SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE WHERE OBJECTPROPERTY(OBJECT_ID(CONSTRAINT_SCHEMA + '.' + QUOTENAME(CONSTRAINT_NAME)), 'IsPrimaryKey') = 1 AND TABLE_NAME = '{tabla}' AND TABLE_SCHEMA = '{esquema}'")
                else:
                    cursor.execute(f"SELECT a.attname FROM pg_index i JOIN pg_attribute a ON a.attrelid = i.indrelid AND a.attnum = ANY(i.indkey) WHERE i.indrelid = '{esquema}.{tabla}'::regclass AND i.indisprimary")
                pks = [row[0] for row in cursor.fetchall()]
            except Exception:
                pass

            # Obtenemos columnas en orden
            cursor.execute(f"SELECT COLUMN_NAME, DATA_TYPE FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = '{tabla}' AND TABLE_SCHEMA = '{esquema}' ORDER BY ORDINAL_POSITION")
            columnas = cursor.fetchall()
            orden_columnas = [row[0] for row in columnas]

            for col_name, data_type in columnas:
                dt = data_type.lower()
                col_safe = f"[{col_name}]" if srv["tipo"] == "SQL Server" else f'"{col_name}"'
                tabla_safe = f"[{tabla}]" if srv["tipo"] == "SQL Server" else f'"{tabla}"'
                
                # === REGLA ESTRELLA: Proteger las Primary Keys Numéricas ===
                if col_name in pks and dt in ['int', 'smallint', 'tinyint', 'decimal', 'numeric', 'bigint']:
                    reglas_sugeridas.append(f"{col_name} : [secuencia:1]")
                    continue # Evita que se procese como un rango normal
                
                # Regla 1: RANGOS NUMÉRICOS
                if dt in ['int', 'smallint', 'tinyint', 'decimal', 'numeric']:
                    try:
                        cursor.execute(f"SELECT MIN({col_safe}), MAX({col_safe}) FROM {esquema}.{tabla_safe}")
                        min_v, max_v = cursor.fetchone()
                        if min_v is not None and max_v is not None:
                            if 'int' in dt:
                                reglas_sugeridas.append(f"{col_name} : [{int(min_v)}-{int(max_v)}]")
                            else:
                                reglas_sugeridas.append(f"{col_name} : [{float(min_v):.2f}-{float(max_v):.2f}]")
                    except Exception:
                        pass
                
                # Regla 2: LISTAS CERRADAS (ENUMS) EN TEXTOS
                elif dt in ['varchar', 'nvarchar', 'char']:
                    try:
                        q_count = f"SELECT COUNT(DISTINCT {col_safe}) FROM {esquema}.{tabla_safe}"
                        cursor.execute(q_count)
                        distintos = cursor.fetchone()[0]
                        
                        if 0 < distintos <= 10:
                            cursor.execute(f"SELECT DISTINCT {col_safe} FROM {esquema}.{tabla_safe} WHERE {col_safe} IS NOT NULL")
                            valores = [str(row[0]).strip() for row in cursor.fetchall() if row[0]]
                            if valores:
                                reglas_sugeridas.append(f"{col_name} : {', '.join(valores)}")
                    except Exception:
                        pass

            if reglas_sugeridas:
                nuevas_reglas_str = "\n".join(reglas_sugeridas)
                # Reutilizamos la súper-inyección que acabamos de mejorar
                self.after(0, lambda: self._inyectar_reglas_ia(nuevas_reglas_str, orden_columnas))
            else:
                self.log_dummy("⚠️ Auto-Perfilado local: No se encontraron rangos numéricos ni listas cerradas para sugerir.")

        except Exception as e:
            self.log_dummy(f"❌ Error en auto-descubrimiento: {e}")
        finally:
            if conn: conn.close()
            self.after(0, lambda: self.btn_autodescubrir.configure(state="normal"))

    def modal_configurar_llm(self):
        import requests # Asegurar importación para el descubrimiento
        
        modal = ctk.CTkToplevel(self)
        modal.title("Configuración de Agentes IA")
        modal.geometry("450x450")
        modal.grab_set()

        # 1. URL y Token
        ctk.CTkLabel(modal, text="URL del Endpoint (API):", font=("Arial", 12)).pack(pady=(15,0), padx=20, anchor="w")
        ent_url = ctk.CTkEntry(modal, width=400, placeholder_text="Ej. http://localhost:11434/v1")
        ent_url.pack(pady=5, padx=20)
        if self.config_data.get("llm_url"): ent_url.insert(0, self.config_data.get("llm_url"))

        ctk.CTkLabel(modal, text="Token (Opcional para local):", font=("Arial", 12)).pack(pady=(5,0), padx=20, anchor="w")
        ent_token = ctk.CTkEntry(modal, width=400, show="*")
        ent_token.pack(pady=5, padx=20)
        if self.config_data.get("llm_token"): ent_token.insert(0, self.config_data.get("llm_token"))

        # Cargar lista de modelos guardada en config.json
        modelos_guardados = self.config_data.get("llm_modelos_disponibles", ["Sin descubrir..."])

        # 2. Contenedor del Modelo Principal (Generador)
        frame_gen = ctk.CTkFrame(modal, fg_color="transparent")
        frame_gen.pack(fill="x", padx=20, pady=(10, 0))
        
        ctk.CTkLabel(frame_gen, text="Modelo Principal (Generador):", font=("Arial", 12, "bold")).pack(anchor="w")
        cmb_modelo_gen = ctk.CTkComboBox(frame_gen, values=modelos_guardados, width=300)
        cmb_modelo_gen.pack(side="left", pady=5)
        if self.config_data.get("llm_modelo_generador"): cmb_modelo_gen.set(self.config_data.get("llm_modelo_generador"))

        # 3. Contenedor del Modelo Secundario (Evaluador) - Oculto por defecto
        frame_eval = ctk.CTkFrame(modal, fg_color="transparent")
        
        ctk.CTkLabel(frame_eval, text="Modelo Secundario (Auditor):", font=("Arial", 12, "bold"), text_color="#17a2b8").pack(anchor="w")
        cmb_modelo_eval = ctk.CTkComboBox(frame_eval, values=modelos_guardados, width=300)
        cmb_modelo_eval.pack(side="left", pady=5)
        if self.config_data.get("llm_modelo_evaluador"): cmb_modelo_eval.set(self.config_data.get("llm_modelo_evaluador"))

        # Lógica para mostrar/ocultar el evaluador con el botón "+"
        def toggle_evaluador():
            if frame_eval.winfo_ismapped():
                frame_eval.pack_forget()
                btn_mas_agentes.configure(text="➕ Agregar Modelo Auditor")
            else:
                # Insertarlo justo después del generador
                frame_eval.pack(fill="x", padx=20, pady=(5, 0), after=frame_gen)
                btn_mas_agentes.configure(text="➖ Quitar Modelo Auditor")

        btn_mas_agentes = ctk.CTkButton(frame_gen, text="➕", width=40, fg_color="#343a40", hover_color="#23272b", command=toggle_evaluador)
        btn_mas_agentes.pack(side="left", padx=10, pady=5)

        # Si ya había un evaluador guardado, mostrar el panel desde el inicio
        if self.config_data.get("llm_modelo_evaluador"):
            toggle_evaluador()

        # 4. Lógica de Descubrimiento Automático
        def descubrir_modelos():
            url_input = ent_url.get().strip().rstrip('/')
            token = ent_token.get().strip()
            
            if not url_input:
                DialogoModerno(self, "Error", "Ingresa una URL primero.", tipo="warning")
                return

            # --- LÓGICA CORREGIDA PARA TU API ---
            # Si pegaste la URL completa de completions, la cambiamos al formato de modelos
            if url_input.endswith("/chat/completions"):
                endpoint = url_input.replace("/chat/completions", "/models")
            else:
                # Si solo pusiste la base (ej. https://genius.c.services/api)
                endpoint = url_input + "/models"
                
            btn_descubrir.configure(state="disabled", text="⏳ Buscando...")
            modal.update()

            try:
                headers = {"Accept": "application/json"}
                if token: headers["Authorization"] = f"Bearer {token}"
                
                resp = requests.get(endpoint, headers=headers, timeout=5)
                resp.raise_for_status()
                
                try:
                    data = resp.json()
                except json.JSONDecodeError:
                    DialogoModerno(self, "Formato Incorrecto", f"El servidor no devolvió JSON.\n\nRuta intentada: {endpoint}\n\nRespuesta:\n{resp.text[:100]}...", tipo="warning")
                    return

                lista_cruda = data.get("data", []) or data.get("models", [])
                modelos_encontrados = [m.get("id") or m.get("name") for m in lista_cruda if m.get("id") or m.get("name")]
                
                if modelos_encontrados:
                    self.config_data["llm_modelos_disponibles"] = modelos_encontrados
                    guardar_configuracion(self.config_data)
                    
                    cmb_modelo_gen.configure(values=modelos_encontrados)
                    cmb_modelo_eval.configure(values=modelos_encontrados)
                    
                    if not cmb_modelo_gen.get() or cmb_modelo_gen.get() == "Sin descubrir...":
                        cmb_modelo_gen.set(modelos_encontrados[0])
                        
                    self.log_dummy(f"✅ Se encontraron {len(modelos_encontrados)} modelos.")
                else:
                    DialogoModerno(self, "Aviso", "Conexión exitosa, pero no se listaron modelos.", tipo="info")
                    
            except requests.exceptions.HTTPError as he:
                DialogoModerno(self, "Error de Endpoint", f"El servidor rechazó la ruta: {endpoint}\n\nDetalle: {he}", tipo="error")
            except Exception as e:
                DialogoModerno(self, "Error de red", f"No se pudo conectar al servidor: {e}", tipo="error")
            finally:
                btn_descubrir.configure(state="normal", text="🔍 Descubrir Modelos")

        btn_descubrir = ctk.CTkButton(modal, text="🔍 Descubrir Modelos", width=150, fg_color="#17a2b8", hover_color="#138496", command=descubrir_modelos)
        btn_descubrir.pack(pady=(15, 0))

        # 5. Guardado final
        def guardar_llm():
            self.config_data["llm_url"] = ent_url.get().strip()
            self.config_data["llm_token"] = ent_token.get().strip()
            self.config_data["llm_modelo_generador"] = cmb_modelo_gen.get().strip()
            
            # Si el panel de evaluación está visible, guardamos el modelo, si no, lo borramos
            if frame_eval.winfo_ismapped():
                self.config_data["llm_modelo_evaluador"] = cmb_modelo_eval.get().strip()
            else:
                self.config_data["llm_modelo_evaluador"] = ""
                
            guardar_configuracion(self.config_data)
            self.log_dummy("🤖 Configuración del Agente IA guardada exitosamente.")
            modal.destroy()

        ctk.CTkButton(modal, text="💾 Guardar Configuración", fg_color="#6f42c1", hover_color="#59339d", command=guardar_llm).pack(pady=20)
    
    
    def auto_descubrir_con_llm(self, instrucciones_extra=""):
        srv_name = self.cmb_servidores_dummy.get()
        db_name = self.cmb_dbs_dummy.get()
        tabla = self.ent_tabla_dummy.get().strip()
        
        url = self.config_data.get("llm_url")
        modelo = self.config_data.get("llm_modelo", "gpt-3.5-turbo")
        token = self.config_data.get("llm_token", "")
        
        if not all([tabla, url]):
            self.log_dummy("❌ Error: Necesitas configurar la URL del LLM y seleccionar una tabla.")
            return

        self.log_dummy(f"🤖 Extrayendo contexto de '{tabla}' para el Agente IA...")
        
        # Añadimos instrucciones_extra al final de los argumentos
        threading.Thread(target=self._hilo_llm_descubrimiento, args=(srv_name, db_name, tabla, url, token, modelo, instrucciones_extra), daemon=True).start()



    # === NUEVA FUNCIÓN: Abstracción de llamadas HTTP para el flujo Multi-Agente ===
    def _llamar_api_llm(self, url, token, modelo, mensajes, stream=False):
        import requests
        import json
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if token: headers["Authorization"] = f"Bearer {token}"
        
        # TRUCO MÁGICO: Siempre pedimos stream=True a nivel de red
        payload = {"model": modelo, "messages": mensajes, "temperature": 0.1, "stream": True}
        respuesta = requests.post(url, headers=headers, json=payload, stream=True, timeout=120)
        respuesta.raise_for_status()
        
        # Si nuestra UI necesita el flujo en vivo (Fase 3), devolvemos el iterador
        if stream:
            return respuesta
            
        # Si necesitamos el texto interno (Fase 1 y 2), consumimos el stream
        texto_completo = ""
        try:
            for linea in respuesta.iter_lines():
                if linea:
                    linea_decodificada = linea.decode('utf-8', errors='ignore').strip()
                    if linea_decodificada == "data: [DONE]":
                        break
                    if linea_decodificada.startswith("data: "):
                        try:
                            chunk = json.loads(linea_decodificada[6:])
                            if "choices" in chunk and len(chunk["choices"]) > 0:
                                contenido = chunk["choices"][0].get("delta", {}).get("content")
                                if contenido: 
                                    texto_completo += str(contenido)
                        except json.JSONDecodeError:
                            pass
        except Exception:
            # 🛡️ PROTECCIÓN ANTI-TIMEOUT: APIs proxy (Vercel/Cloudflare) cortan 
            # la conexión abruptamente a los 30 segundos exactos.
            # Atrapamos el error silenciosamente para devolver el texto parcial/completo
            # que el modelo haya logrado generar en lugar de crashear la aplicación.
            pass
        
        return texto_completo
    
    def _hilo_llm_descubrimiento(self, srv_name, db_name, tabla, url_base, token, modelo, instrucciones_extra):
        import requests
        import json
        
        srv = self.obtener_credenciales(srv_name)
        conn = None
        
        try:
            # === 1. AUTO-COMPLETAR Y SANITIZAR LA URL ===
            url = url_base.strip().rstrip('/')
            if "chat/completions" not in url:
                url = f"{url}/chat/completions"
                self.log_dummy(f"🔧 URL ajustada a: {url}")

            conn = self.conectar_db(srv, db_name)
            cursor = conn.cursor()
            esquema = "dbo" if srv["tipo"] == "SQL Server" else "public"

            # === 1.1 EXTRAER LLAVES PRIMARIAS PARA LA IA ===
            pks = []
            try:
                if srv["tipo"] == "SQL Server":
                    cursor.execute(f"SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE WHERE OBJECTPROPERTY(OBJECT_ID(CONSTRAINT_SCHEMA + '.' + QUOTENAME(CONSTRAINT_NAME)), 'IsPrimaryKey') = 1 AND TABLE_NAME = '{tabla}' AND TABLE_SCHEMA = '{esquema}'")
                else:
                    cursor.execute(f"SELECT a.attname FROM pg_index i JOIN pg_attribute a ON a.attrelid = i.indrelid AND a.attnum = ANY(i.indkey) WHERE i.indrelid = '{esquema}.{tabla}'::regclass AND i.indisprimary")
                pks = [row[0] for row in cursor.fetchall()]
            except Exception:
                pass

            # === 1.2 EXTRAER LLAVES FORÁNEAS (RELACIONES) PARA LA IA ===
            relaciones_fk = []
            try:
                if srv["tipo"] == "SQL Server":
                    query_fk = f"SELECT c1.name AS Col_Local, t2.name AS Tabla_Ref, c2.name AS Col_Ref FROM sys.foreign_keys fk INNER JOIN sys.foreign_key_columns fkc ON fk.object_id = fkc.constraint_object_id INNER JOIN sys.tables t1 ON fkc.parent_object_id = t1.object_id INNER JOIN sys.columns c1 ON fkc.parent_object_id = c1.object_id AND fkc.parent_column_id = c1.column_id INNER JOIN sys.tables t2 ON fkc.referenced_object_id = t2.object_id INNER JOIN sys.columns c2 ON fkc.referenced_object_id = c2.object_id AND fkc.referenced_column_id = c2.column_id WHERE t1.name = '{tabla}'"
                else:
                    query_fk = f"SELECT kcu.column_name, ccu.table_name, ccu.column_name FROM information_schema.table_constraints AS tc JOIN information_schema.key_column_usage AS kcu ON tc.constraint_name = kcu.constraint_name AND tc.table_schema = kcu.table_schema JOIN information_schema.constraint_column_usage AS ccu ON ccu.constraint_name = tc.constraint_name WHERE tc.constraint_type = 'FOREIGN KEY' AND tc.table_name='{tabla}'"
                
                cursor.execute(query_fk)
                for col_local, tabla_ref, col_ref in cursor.fetchall():
                    relaciones_fk.append(f"La columna '{col_local}' DEBE vincularse obligatoriamente con '{tabla_ref}.{col_ref}'")
            except Exception:
                pass

            # Obtener estructura con inyección de máximos
            cursor.execute(f"SELECT COLUMN_NAME, DATA_TYPE FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = '{tabla}' AND TABLE_SCHEMA = '{esquema}' ORDER BY ORDINAL_POSITION")
            estructura = []
            orden_columnas = []
            for row in cursor.fetchall():
                col_n, dt = row[0], row[1]
                orden_columnas.append(col_n)
                if col_n in pks:
                    # Traemos el máximo valor actual para ayudar a la IA
                    col_s = f"[{col_n}]" if srv["tipo"] == "SQL Server" else f'"{col_n}"'
                    try:
                        cursor.execute(f"SELECT MAX({col_s}) FROM {esquema}.{tabla}")
                        max_v = cursor.fetchone()[0]
                        max_v = int(max_v) if max_v is not None else 0
                        estructura.append(f"{col_n} ({dt}) - PRIMARY KEY (Max actual: {max_v})")
                    except:
                        estructura.append(f"{col_n} ({dt}) - PRIMARY KEY")
                else:
                    estructura.append(f"{col_n} ({dt})")
            
            # === Obtener 10 filas de muestra aleatoria (Protección para Tablas Masivas) ===
            try:
                # Intento 1: Muestreo estadístico súper rápido (lee solo el 5% de la tabla en disco)
                if srv["tipo"] == "SQL Server":
                    cursor.execute(f"SELECT TOP 100 * FROM {esquema}.{tabla} TABLESAMPLE (5 PERCENT) ORDER BY NEWID()")
                else:
                    cursor.execute(f"SELECT * FROM {esquema}.{tabla} TABLESAMPLE SYSTEM (5) ORDER BY RANDOM() LIMIT 100")
                
                filas_muestra = cursor.fetchall()
                
                if len(filas_muestra) == 0:
                    raise ValueError("Tabla pequeña")
                    
            except Exception:
                # Intento 2: Fallback tradicional (seguro para tablas pequeñas o vistas)
                if srv["tipo"] == "SQL Server":
                    cursor.execute(f"SELECT TOP 100 * FROM {esquema}.{tabla} ORDER BY NEWID()")
                else:
                    cursor.execute(f"SELECT * FROM {esquema}.{tabla} ORDER BY RANDOM() LIMIT 100")
                filas_muestra = cursor.fetchall()

            columnas_nombres = [desc[0] for desc in cursor.description]
            muestra_dicts = []
            for row in filas_muestra:
                fila_limpia = {columnas_nombres[i]: str(row[i]) for i in range(len(columnas_nombres))}
                muestra_dicts.append(fila_limpia)

            contexto_json = json.dumps({
                "estructura": estructura, 
                "dependencias_obligatorias": relaciones_fk,
                "datos_muestra": muestra_dicts
            }, indent=2, ensure_ascii=False)
            
            prompt_sistema_base = """Eres un experto en ingeniería de datos. Tu objetivo es analizar el esquema y la muestra de datos de una tabla, y devolver ÚNICAMENTE reglas de generación de datos dummy para un orquestador en Python.
            
            📖 SINTAXIS ESTRICTA (Si usas algo fuera de esto, el sistema colapsará):
            • Relación Local (FK)    : columna : tabla.columna
            • Cross-Server (Híbrido) : columna : [Servidor].[BD].[Tabla].columna
            • Secuencia Única        : columna : [secuencia:1] (Rellena huecos libres inteligentemente. Obligatorio para IDs/PKs)
            • Plantillas de Faker    : columna : {{city}}, {{date}}, {{time}}, {{company}}, {{email}}
            • Lista de Opciones      : columna : ACTIVO, INACTIVO (Ideal para decimales fijos como 1.16, 8.00)
            • Rango Numérico ENTERO  : columna : [1-100] (SOLO NÚMEROS ENTEROS. NO USAR PARA FECHAS NI DECIMALES)
            • Patrón Texto           : columna : FAC-####-??? (#=Núm, ?=Letra)
            • Matemáticas            : columna : = col_precio * 1.16
            
            🛑 REGLAS DE ORO:
            1. GENERA UNA REGLA PARA TODAS Y CADA UNA DE LAS COLUMNAS DEL ESQUEMA. NO OMITAS NINGUNA.
            2. NUNCA uses corchetes [ ] para fechas (Ej. MAL: [2000-2026]). Usa {{date}}.
            3. NUNCA uses corchetes [ ] para decimales (Ej. MAL: [1.16-16.00]). Usa listas separadas por comas (1.16, 16.00).
            4. Devuelve ÚNICAMENTE texto plano, una regla por línea. NO expliques tu respuesta.
            5. CRÍTICO: Si en el JSON se te proporciona un arreglo llamado 'dependencias_obligatorias', ESTÁS OBLIGADO a usar la sintaxis de "Relación Local (FK)" para esas columnas exactas. No intentes usar Faker ni rangos para columnas que son Llaves Foráneas."""

            mensaje_usuario = f"Genera las reglas lógicas para esta tabla basándote en este esquema y muestra:\n{contexto_json}"
            
            if instrucciones_extra:
                mensaje_usuario += f"\n\n🛑 REGLAS DE NEGOCIO ESTRICTAS DEL USUARIO:\n{instrucciones_extra}\n(Debes aplicar estas reglas obligatoriamente por encima de tus suposiciones)."

            # === VERIFICAR SI HAY EVALUADOR CONFIGURADO ===
            modelo_evaluador = self.config_data.get("llm_modelo_evaluador", "")
            
            # Si hay un evaluador configurado, usamos el flujo Multi-Agente
            if modelo_evaluador:
                # ==========================================
                # FASE 1: GENERACIÓN DEL BORRADOR
                # ==========================================
                self.log_dummy(f"🤖 Fase 1: {modelo} está redactando el borrador inicial...")
                mensajes_fase1 = [
                    {"role": "system", "content": prompt_sistema_base},
                    {"role": "user", "content": mensaje_usuario}
                ]
                borrador = self._llamar_api_llm(url, token, modelo, mensajes_fase1, stream=False)
                
                # ==========================================
                # FASE 2: EVALUACIÓN Y CRÍTICA
                # ==========================================
                self.log_dummy(f"🕵️ Fase 2: {modelo_evaluador} está auditando las reglas...")
                
                # Le decimos al auditor que también debe revisar las reglas del usuario
                prompt_auditor = """Eres un auditor estricto de calidad de datos. Revisa las reglas generadas contra el esquema proporcionado. 
                Verifica: 
                1. Que no falte ninguna columna.
                2. Que se respeten las dependencias obligatorias.
                3. Que la sintaxis sea estrictamente válida.
                4. Que se hayan cumplido las REGLAS DE NEGOCIO DEL USUARIO (si existen).
                Apunta los errores de forma directa. Si todo es perfecto, responde 'SIN ERRORES'."""
                
                # Armamos el texto que va a leer el auditor
                texto_auditoria = f"ESQUEMA ORIGINAL:\n{contexto_json}\n"
                
                # Si el usuario escribió un prompt personalizado, se lo pasamos al auditor
                if instrucciones_extra:
                    texto_auditoria += f"\n🛑 REGLAS DE NEGOCIO DEL USUARIO A VERIFICAR OBLIGATORIAMENTE:\n{instrucciones_extra}\n"
                    
                texto_auditoria += f"\nREGLAS GENERADAS POR EL MODELO ANTERIOR (Borrador):\n{borrador}\n\nEVALUACIÓN Y CRITICA:"
                
                mensajes_fase2 = [
                    {"role": "system", "content": prompt_auditor},
                    {"role": "user", "content": texto_auditoria}
                ]
                
                critica = self._llamar_api_llm(url, token, modelo_evaluador, mensajes_fase2, stream=False)
                
                # ==========================================
                # FASE 3: REFINAMIENTO Y STREAMING A INTERFAZ
                # ==========================================
                self.log_dummy(f"✨ Fase 3: {modelo} está aplicando correcciones y enviando versión final...")
                mensajes_finales = mensajes_fase1 + [
                    {"role": "assistant", "content": borrador},
                    {"role": "user", "content": f"Un auditor revisó tu trabajo y comentó lo siguiente:\n{critica}\n\nPor favor, corrige los errores y genera la VERSIÓN FINAL. Recuerda imprimir SOLO las reglas en texto plano."}
                ]
            else:
                # Si no hay evaluador, usamos el flujo normal (1 solo paso)
                self.log_dummy(f"🧠 Enviando contexto a {modelo} (Leyendo flujo de datos...)")
                mensajes_finales = [
                    {"role": "system", "content": prompt_sistema_base},
                    {"role": "user", "content": mensaje_usuario}
                ]

            # === CONSUMIR LA RESPUESTA (FINAL O ÚNICA) EN STREAMING ===
            respuesta = self._llamar_api_llm(url, token, modelo, mensajes_finales, stream=True)
            
            reglas_ia = ""
            raw_debug = "" 
            
            try:
                for linea in respuesta.iter_lines():
                    if linea:
                        linea_decodificada = linea.decode('utf-8', errors='ignore').strip()
                        
                        if len(raw_debug) < 300:
                            raw_debug += linea_decodificada + " "
                            
                        if linea_decodificada == "data: [DONE]":
                            break
                        
                        if linea_decodificada.startswith("data: "):
                            try:
                                chunk = json.loads(linea_decodificada[6:])
                                if "choices" in chunk and len(chunk["choices"]) > 0:
                                    delta = chunk["choices"][0].get("delta", {})
                                    contenido = delta.get("content")
                                    if contenido: reglas_ia += str(contenido)
                            except json.JSONDecodeError:
                                pass 
            except Exception as error_lectura:
                # 🤫 SILENCIAMOS EL ERROR DE RED SI YA OBTUVIMOS LAS REGLAS
                if not reglas_ia.strip():
                    msg_err = f"⚠️ Error de lectura de red: {error_lectura}"
                    self.log_dummy(msg_err)
                    self.escribir_auditoria(f"[ERROR AGENTE IA] {msg_err}")

            # === INYECTAR DATOS SALVADOS O MOSTRAR EL DEBUG ===
            if reglas_ia.strip():
                self.after(0, lambda: self._inyectar_reglas_ia(reglas_ia.strip(), orden_columnas))
            else:
                self.log_dummy(f"🕵️ RESPUESTA CRUDA DEL SERVIDOR:\n{raw_debug}")
                self.log_dummy("⚠️ El formato no coincide. Es posible que el modelo solo haya devuelto 'reasoning_content' y no la respuesta final.")
                
                # --- NUEVO: Escribir el error detallado en el log diario ---
                mensaje_log_archivo = (
                    f"\n{'='*55}\n"
                    f"[ERROR AGENTE IA - RESPUESTA INCOMPLETA / REASONING]\n"
                    f"Tabla: {tabla} | Modelo: {modelo}\n"
                    f"Respuesta cruda del servidor:\n{raw_debug}\n"
                    f"{'='*55}\n"
                )
                self.escribir_auditoria(mensaje_log_archivo)
            
        except requests.exceptions.ReadTimeout:
            msg = "❌ Error: El Agente IA tardó demasiado en responder (Timeout)."
            self.log_dummy(msg)
            self.escribir_auditoria(f"[ERROR RED IA] {msg}")
        except requests.exceptions.HTTPError as he:
            msg = f"❌ Error HTTP del Agente IA: {he}"
            self.log_dummy(msg)
            self.escribir_auditoria(f"[ERROR RED IA] {msg}")
        except Exception as e:
            msg = f"❌ Error inesperado en conexión multi-agente: {e}"
            self.log_dummy(msg)
            self.escribir_auditoria(f"[ERROR GLOBAL IA] {msg}")
        finally:
            if conn: conn.close()

    def _inyectar_reglas_ia(self, reglas_nuevas, orden_columnas=None):
        # 1. Leer siempre del editor activo si el modal está abierto
        editor_activo = getattr(self, 'txt_editor_activo', None)
        
        if editor_activo:
            texto_actual = editor_activo.get("1.0", "end-1c").strip()
        else:
            texto_actual = self.txt_relaciones.get("1.0", "end-1c").strip()
            
        if texto_actual == "" or texto_actual.startswith("Ej."):
            self.txt_relaciones.delete("1.0", "end")
            self.txt_relaciones.insert("end", reglas_nuevas)
            
            if editor_activo:
                editor_activo.delete("1.0", "end")
                editor_activo.insert("end", reglas_nuevas)
                
            # Auto-guardado
            srv_name = self.cmb_servidores_dummy.get()
            db_name = self.cmb_dbs_dummy.get()
            tabla = self.ent_tabla_dummy.get().strip()
            
            if reglas_nuevas:
                memoria = cargar_relaciones()
                clave_memoria = f"{srv_name}|{db_name}"
                if clave_memoria not in memoria:
                    memoria[clave_memoria] = {"_configuracion_global": {}, "tablas": {}}
                memoria[clave_memoria]["tablas"][tabla.lower()] = reglas_nuevas
                guardar_relaciones(memoria)

            self.log_dummy("✨ ¡Reglas inyectadas y guardadas exitosamente!")
        else:
            self.log_dummy("⚠️ Reglas previas detectadas. Abriendo panel de fusión...")
            self.modal_merge_reglas(texto_actual, reglas_nuevas, orden_columnas)

    def modal_prompt_ia(self):
        srv_name = self.cmb_servidores_dummy.get()
        db_name = self.cmb_dbs_dummy.get()
        tabla = self.ent_tabla_dummy.get().strip()
        
        if not tabla or "Primero conecte" in db_name:
            self.log_dummy("❌ Error: Seleccione una base de datos y escriba el nombre de la tabla primero.")
            return

        modal = ctk.CTkToplevel(self)
        modal.title(f"Instrucciones para IA - {tabla}")
        modal.geometry("480x320")
        modal.grab_set()
        modal.transient(self)

        # Usamos Grid para estructurar igual que el otro modal
        frame_header = ctk.CTkFrame(modal, fg_color="transparent")
        frame_header.pack(fill="x", padx=20, pady=(15, 5))
        
        ctk.CTkLabel(frame_header, text="Contexto adicional (Opcional):", font=("Arial", 14, "bold")).pack(anchor="w")
        ctk.CTkLabel(frame_header, text="Ej. 'Los correos deben ser @miempresa.com' o 'El estatus es 1, 2 o 3'", text_color="#aaaaaa").pack(anchor="w", pady=(0, 5))

        txt_prompt = ctk.CTkTextbox(modal, height=120, fg_color="#1a1a1a", font=("Arial", 13))
        txt_prompt.pack(padx=20, fill="x", pady=(0, 15))

        def disparar_ia():
            instrucciones = txt_prompt.get("1.0", "end-1c").strip()
            modal.destroy()
            self.auto_descubrir_con_llm(instrucciones) # Pasamos el texto personalizado

        ctk.CTkButton(modal, text="🚀 Analizar y Generar Reglas", height=35, font=("Arial", 13, "bold"), fg_color="#6f42c1", hover_color="#59339d", command=disparar_ia).pack(pady=5)

    def modal_merge_reglas(self, texto_actual, texto_nuevo, orden_columnas=None):
        def parsear_a_diccionario(texto):
            diccionario = {}
            for linea in texto.split('\n'):
                if ':' in linea:
                    partes = linea.split(':', 1)
                    if len(partes) == 2:
                        diccionario[partes[0].strip()] = partes[1].strip()
            return diccionario

        dict_act = parsear_a_diccionario(texto_actual)
        dict_nue = parsear_a_diccionario(texto_nuevo)
        
        # 1. ORDENAMIENTO ESTRUCTURAL (Basado en la BD)
        if orden_columnas:
            orden_lower = [c.lower() for c in orden_columnas]
            def get_index(c):
                try: return orden_lower.index(c.lower())
                except ValueError: return 999 # Si hay una columna inventada, va al final
            all_cols = sorted(list(set(dict_act.keys()).union(set(dict_nue.keys()))), key=get_index)
        else:
            all_cols = sorted(list(set(dict_act.keys()).union(set(dict_nue.keys()))))
            
        modal = ctk.CTkToplevel(self)
        modal.title("Fusión de Reglas (Git-Style Merge)")
        modal.geometry("850x650")
        modal.transient(self)
        modal.grab_set()

        ctk.CTkLabel(modal, text="Conflictos de Reglas Detectados", font=("Arial", 16, "bold")).pack(pady=(15, 5))
        ctk.CTkLabel(modal, text="Selecciona qué regla deseas conservar o si prefieres eliminarla.", text_color="#aaaaaa").pack(pady=(0, 10))

        frame_masivas = ctk.CTkFrame(modal, fg_color="transparent")
        frame_masivas.pack(fill="x", padx=20, pady=5)
        
        def seleccionar_todo(opcion):
            for datos in self.merge_vars.values():
                if opcion in datos["opciones"]:
                    datos["var"].set(opcion)

        ctk.CTkButton(frame_masivas, text="👉 Todas las Actuales", width=180, fg_color="#6c757d", hover_color="#5a6268", command=lambda: seleccionar_todo("Actual")).pack(side="left", padx=5)
        ctk.CTkButton(frame_masivas, text="👉 Todas las Sugeridas", width=180, fg_color="#17a2b8", hover_color="#138496", command=lambda: seleccionar_todo("Sugerida")).pack(side="left", padx=5)
        ctk.CTkButton(frame_masivas, text="🗑️ Eliminar Todas", width=150, fg_color="#dc3545", hover_color="#c82333", command=lambda: seleccionar_todo("Eliminar")).pack(side="right", padx=5)

        scroll = ctk.CTkScrollableFrame(modal, fg_color="#1a1a1a")
        scroll.pack(fill="both", expand=True, padx=20, pady=10)

        self.merge_vars = {}

        for col in all_cols:
            val_act = dict_act.get(col, "")
            val_nue = dict_nue.get(col, "")
            
            row = ctk.CTkFrame(scroll, fg_color="#2b2b2b")
            row.pack(fill="x", pady=2, padx=2)
            
            ctk.CTkLabel(row, text=col, width=150, anchor="w", font=("Arial", 12, "bold")).pack(side="left", padx=10, pady=10)
            var = ctk.StringVar()
            
            # 2. OPCIÓN ELIMINAR AGREGADA A TODOS LOS ESCENARIOS
            if val_act and val_nue and val_act != val_nue:
                var.set("Sugerida")
                opciones = ["Actual", "Sugerida", "Eliminar"]
                self.merge_vars[col] = {"var": var, "Actual": val_act, "Sugerida": val_nue, "opciones": opciones}
                
                frame_textos = ctk.CTkFrame(row, fg_color="transparent")
                frame_textos.pack(side="left", fill="x", expand=True)
                
                # AÑADIDO: wraplength=450 y justify="left"
                ctk.CTkLabel(frame_textos, text=f"Actual: {val_act}", anchor="w", justify="left", wraplength=450, text_color="#aaaaaa").pack(fill="x", pady=2)
                ctk.CTkLabel(frame_textos, text=f"Sugerida: {val_nue}", anchor="w", justify="left", wraplength=450, text_color="#17a2b8").pack(fill="x", pady=2)
                
                seg = ctk.CTkSegmentedButton(row, values=opciones, variable=var, selected_color="#6f42c1")
                seg.pack(side="right", padx=10)
                
            elif val_act and not val_nue:
                var.set("Actual")
                opciones = ["Actual", "Eliminar"]
                self.merge_vars[col] = {"var": var, "Actual": val_act, "opciones": opciones}
                # AÑADIDO: wraplength=450 y justify="left"
                ctk.CTkLabel(row, text=f"Actual: {val_act}", anchor="w", justify="left", wraplength=450, text_color="#aaaaaa").pack(side="left", fill="x", expand=True, pady=5)
                seg = ctk.CTkSegmentedButton(row, values=opciones, variable=var, selected_color="#28a745")
                seg.pack(side="right", padx=10)
                
            elif val_nue and not val_act:
                var.set("Sugerida")
                opciones = ["Sugerida", "Eliminar"]
                self.merge_vars[col] = {"var": var, "Sugerida": val_nue, "opciones": opciones}
                # AÑADIDO: wraplength=450 y justify="left"
                ctk.CTkLabel(row, text=f"Nueva: {val_nue}", anchor="w", justify="left", wraplength=450, text_color="#17a2b8").pack(side="left", fill="x", expand=True, pady=5)
                seg = ctk.CTkSegmentedButton(row, values=opciones, variable=var, selected_color="#17a2b8")
                seg.pack(side="right", padx=10)
                
            elif val_act == val_nue:
                var.set("Actual")
                opciones = ["Actual", "Eliminar"]
                self.merge_vars[col] = {"var": var, "Actual": val_act, "opciones": opciones}
                # AÑADIDO: wraplength=450 y justify="left"
                ctk.CTkLabel(row, text=f"Sin cambios: {val_act}", anchor="w", justify="left", wraplength=450, text_color="#aaaaaa").pack(side="left", fill="x", expand=True, pady=5)
                seg = ctk.CTkSegmentedButton(row, values=opciones, variable=var, selected_color="#6c757d")
                seg.pack(side="right", padx=10)

        def aplicar_fusion():
            lineas_finales = []
            # 3. EXTRAER EN ORDEN
            for c in all_cols: 
                if c in self.merge_vars:
                    datos = self.merge_vars[c]
                    seleccion = datos["var"].get()
                    
                    if seleccion != "Eliminar":
                        valor = datos.get(seleccion, "")
                        if valor:
                            lineas_finales.append(f"{c} : {valor}")
                    
            texto_final = "\n".join(lineas_finales)
            
            # 4. INYECTAR EN LA UI Y EL MODAL
            self.txt_relaciones.delete("1.0", "end")
            self.txt_relaciones.insert("end", texto_final)
            
            if getattr(self, 'txt_editor_activo', None):
                self.txt_editor_activo.delete("1.0", "end")
                self.txt_editor_activo.insert("end", texto_final)

            # === NUEVO: 5. AUTO-GUARDADO FÍSICO INMEDIATO ===
            srv_name = self.cmb_servidores_dummy.get()
            db_name = self.cmb_dbs_dummy.get()
            tabla = self.ent_tabla_dummy.get().strip()
            
            if texto_final and not texto_final.startswith("Ej."):
                memoria = cargar_relaciones()
                clave_memoria = f"{srv_name}|{db_name}"
                if clave_memoria not in memoria:
                    memoria[clave_memoria] = {"_configuracion_global": {}, "tablas": {}}
                memoria[clave_memoria]["tablas"][tabla.lower()] = texto_final
                guardar_relaciones(memoria)
                self.log_dummy(f"💾 Reglas auto-guardadas en caché para '{tabla}'.")
            # ===============================================
                
            self.log_dummy("✅ Fusión completada. Reglas ordenadas e inyectadas.")
            modal.destroy()
            
        frame_footer = ctk.CTkFrame(modal, fg_color="transparent")
        frame_footer.pack(fill="x", padx=20, pady=15)
        ctk.CTkButton(frame_footer, text="❌ Cancelar", fg_color="#dc3545", hover_color="#c82333", command=modal.destroy).pack(side="left", padx=5)
        ctk.CTkButton(frame_footer, text="💾 Aplicar Fusión", font=("Arial", 13, "bold"), fg_color="#28a745", hover_color="#218838", command=aplicar_fusion).pack(side="right", padx=5)

   
if __name__ == "__main__":
    multiprocessing.freeze_support()
    app = AplicacionCargas()
    app.mainloop()