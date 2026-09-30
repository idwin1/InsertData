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

# ==========================================
# 3. INTERFAZ GRÁFICA PRINCIPAL
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

        # ========================================================
        # PESTAÑA 2: DATOS DUMMY (Espacio preparado)
        # ========================================================
        # ----------------------------------------------------
        # VISTA 2: GENERADOR DUMMY (Totalmente independiente)
        # ----------------------------------------------------
        # ========================================================
        # PESTAÑA 2: DATOS DUMMY 
        # ========================================================
        
        # BLOQUE 1: Conexión (Servidor y BD en la misma tarjeta)
        self.frame_conn_dummy = ctk.CTkFrame(self.tab_dummy, fg_color="#2b2b2b", corner_radius=10)
        self.frame_conn_dummy.pack(pady=10, padx=20, fill="x")

        ctk.CTkLabel(self.frame_conn_dummy, text="1. Origen de Datos (Lectura de Esquema)", font=("Arial", 14, "bold")).grid(row=0, column=0, columnspan=2, padx=15, pady=(10,5), sticky="w")
        
        self.cmb_servidores_dummy = ctk.CTkComboBox(self.frame_conn_dummy, width=280, values=["Seleccione un servidor..."], command=self.al_seleccionar_servidor_dummy)
        self.cmb_servidores_dummy.grid(row=1, column=0, padx=15, pady=(0, 15), sticky="w")

        self.cmb_dbs_dummy = ctk.CTkComboBox(self.frame_conn_dummy, width=280, values=["Primero conecte..."])
        self.cmb_dbs_dummy.grid(row=1, column=1, padx=15, pady=(0, 15), sticky="w")

        # BLOQUE 2: Configuración del CSV Dummy
        self.frame_params_dummy = ctk.CTkFrame(self.tab_dummy, fg_color="#2b2b2b", corner_radius=10)
        self.frame_params_dummy.pack(pady=10, padx=20, fill="x")

        ctk.CTkLabel(self.frame_params_dummy, text="2. Configuración de Generación", font=("Arial", 14, "bold")).grid(row=0, column=0, columnspan=3, padx=15, pady=(10,5), sticky="w")

        # Fila 1: Tabla, Cantidad y Botón Generar
        self.frame_tabla_dummy_input = ctk.CTkFrame(self.frame_params_dummy, fg_color="transparent")
        self.frame_tabla_dummy_input.grid(row=1, column=0, padx=15, pady=(0, 5), sticky="w")
        self.ent_tabla_dummy = ctk.CTkEntry(self.frame_tabla_dummy_input, width=160, placeholder_text="Nombre de la tabla...")
        self.ent_tabla_dummy.pack(side="left", padx=(0, 5))
        self.btn_validar_dummy = ctk.CTkButton(self.frame_tabla_dummy_input, text="🔍 Validar", width=70, command=self.validar_tabla_dummy)
        self.btn_validar_dummy.pack(side="left")

        self.ent_cantidad_dummy = ctk.CTkEntry(self.frame_params_dummy, width=120, placeholder_text="Filas (Ej. 500)")
        self.ent_cantidad_dummy.grid(row=1, column=1, padx=10, pady=(0, 5), sticky="w")
        self.btn_generar_dummy = ctk.CTkButton(self.frame_params_dummy, text="🎲 Generar CSV Dummy", font=("Arial", 12, "bold"), fg_color="#6f42c1", hover_color="#59339d", command=self.ejecutar_generacion_dummy)
        self.btn_generar_dummy.grid(row=1, column=2, padx=10, pady=(0, 5), sticky="w")

        # Fila 2: Campo Multilínea para Reglas y Relaciones
        ctk.CTkLabel(self.frame_params_dummy, text="Reglas y Relaciones (Una por línea):").grid(row=2, column=0, padx=15, pady=(5, 5), sticky="nw")
        
        frame_lbl_reglas = ctk.CTkFrame(self.frame_params_dummy, fg_color="transparent")
        frame_lbl_reglas.grid(row=2, column=0, padx=15, pady=(5, 5), sticky="nw")
        
        ctk.CTkLabel(frame_lbl_reglas, text="Reglas y Relaciones:").pack(anchor="w")
        self.btn_ampliar = ctk.CTkButton(frame_lbl_reglas, text="🗔 Ampliar Editor", width=120, height=28, fg_color="#17a2b8", hover_color="#138496", command=self.modal_editar_reglas)
        self.btn_ampliar.pack(anchor="w", pady=(10,0))
        
        self.txt_relaciones = ctk.CTkTextbox(self.frame_params_dummy, width=350, height=80, fg_color="#1a1a1a")
        self.txt_relaciones.grid(row=2, column=1, columnspan=2, padx=10, pady=(5, 5), sticky="w")
        self.txt_relaciones.insert("1.0", "Ej. id_rol : roles.id\nEj. codigo : CUST-####\nEj. estatus : ACTIVO, INACTIVO")

        # Fila 3: Etiqueta de estado
        self.lbl_tabla_status_dummy = ctk.CTkLabel(self.frame_params_dummy, text="Escriba la tabla y presione Validar.", text_color="#aaaaaa", font=("Arial", 11, "italic"))
        self.lbl_tabla_status_dummy.grid(row=3, column=0, columnspan=3, padx=15, pady=(0, 10), sticky="w")

        # BLOQUE 3: Log Independiente para esta vista
        self.txt_log_dummy = ctk.CTkTextbox(self.tab_dummy, height=180, fg_color="#1a1a1a", text_color="#d63384", font=("Consolas", 12))
        self.txt_log_dummy.pack(pady=10, padx=20, fill="both", expand=True)
        self.txt_log_dummy.insert("end", "Módulo Dummy iniciado. Listo para generar datos.\n")

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
            messagebox.showerror("Error", "Debe seleccionar un CSV primero.")
            return
        if not tabla:
            messagebox.showerror("Error", "Debe escribir el nombre de la tabla destino.")
            return

        srv = self.obtener_credenciales(srv_name)
        self.btn_iniciar.configure(state="disabled", text="⏳ PROCESANDO...")
        threading.Thread(target=self.procesar_csv_dual, args=(srv, db_name, tabla), daemon=True).start()

    def procesar_csv_dual(self, srv, db_name, tabla):
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
            messagebox.showinfo("Éxito", f"Se insertaron {total_insertados} registros en {tabla} ({tipo_db}).")

        except Exception as e:
            self.log(f"❌ ERROR: {str(e)}")
            messagebox.showerror("Error de Inserción", str(e))
        finally:
            if conn: conn.close()
            self.btn_iniciar.configure(state="normal", text="🚀 INICIAR CARGA MASIVA")

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
        
        # Inicializamos la BD en el diccionario si no existe
        if db_name not in memoria:
            memoria[db_name] = {}
            
        reglas_guardadas = memoria[db_name].get(tabla_input.lower(), "")
        
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
                memoria[db_name][tabla.lower()] = nuevas_reglas
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
                memoria[db_name] = {}
                
            if memoria[db_name].get(tabla.lower()) != reglas_str:
                memoria[db_name][tabla.lower()] = reglas_str
                guardar_relaciones(memoria)
                self.log_dummy(f"💾 Reglas guardadas para '{tabla}' en '{db_name}'.")
        # ==========================================

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
                                    fila_dict[original_col] = int(resultado) if isinstance(resultado, float) and resultado.is_integer() else round(resultado, 2)
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
   
if __name__ == "__main__":
    multiprocessing.freeze_support()
    app = AplicacionCargas()
    app.mainloop()