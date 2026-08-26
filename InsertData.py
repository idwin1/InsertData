import os
import sys
import subprocess
import json
import csv
import threading
import io
from datetime import datetime

# ==========================================
# 1. AUTO-INSTALADOR DE LIBRERÍAS
# ==========================================
LIBRERIAS_REQUERIDAS = {
    "colorama": "colorama",
    "customtkinter": "customtkinter",
    "pyodbc": "pyodbc",
    "psycopg2": "psycopg2-binary", # Usamos binary para evitar errores de compilación en Windows
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
# 2. GESTIÓN DE CONFIGURACIÓN (JSON COMPARTIDO)
# ==========================================
CONFIG_FILE = "config.json"

def cargar_configuracion():
    if not os.path.exists(CONFIG_FILE):
        return {"Servidores_BD": []}
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            datos = json.load(f)
            # Manejar compatibilidad si ya existía la clave de la versión anterior
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

# ==========================================
# 3. INTERFAZ GRÁFICA PRINCIPAL
# ==========================================
class AplicacionCargas(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Carga Masiva Multi-BD - Pro")
        self.geometry("680x780")
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.config_data = cargar_configuracion()
        self.archivo_csv = ""
        self.driver_sql = obtener_driver_sql()
        self.mapa_servidores = {}

        self.crear_interfaz()
        self.actualizar_lista_servidores()

    def crear_interfaz(self):
        # --- HEADER ---
        self.frame_header = ctk.CTkFrame(self, fg_color="transparent")
        self.frame_header.pack(pady=(15, 5), padx=20, fill="x")
        ctk.CTkLabel(self.frame_header, text="⚡ Carga Masiva (SQL Server & Postgres)", font=("Arial", 20, "bold")).pack(side="left")

        # --- SECCIÓN 1: SERVIDOR ---
        self.frame_srv = ctk.CTkFrame(self, fg_color="#2b2b2b", corner_radius=10)
        self.frame_srv.pack(pady=10, padx=20, fill="x")
        
        ctk.CTkLabel(self.frame_srv, text="1. Servidor de Base de Datos", font=("Arial", 14, "bold")).grid(row=0, column=0, padx=15, pady=(10,5), sticky="w")
        
        self.cmb_servidores = ctk.CTkComboBox(self.frame_srv, width=280, values=["Seleccione un servidor..."], command=self.al_seleccionar_servidor)
        self.cmb_servidores.grid(row=1, column=0, padx=15, pady=(0, 15), sticky="w")

        btn_nuevo_srv = ctk.CTkButton(self.frame_srv, text="➕ Nuevo Servidor", fg_color="#28a745", hover_color="#218838", command=self.modal_nuevo_servidor)
        btn_nuevo_srv.grid(row=1, column=1, padx=10, pady=(0, 15), sticky="w")

        # --- SECCIÓN 2: BASE DE DATOS Y TABLA ---
        self.frame_db = ctk.CTkFrame(self, fg_color="#2b2b2b", corner_radius=10)
        self.frame_db.pack(pady=10, padx=20, fill="x")

        ctk.CTkLabel(self.frame_db, text="2. Destino (BD y Tabla)", font=("Arial", 14, "bold")).grid(row=0, column=0, padx=15, pady=(10,5), sticky="w")

        self.cmb_dbs = ctk.CTkComboBox(self.frame_db, width=280, values=["Primero conecte al servidor"], command=self.al_seleccionar_db)
        self.cmb_dbs.grid(row=1, column=0, padx=15, pady=(0, 15), sticky="w")

        self.cmb_tablas = ctk.CTkComboBox(self.frame_db, width=280, values=["Esperando BD..."])
        self.cmb_tablas.grid(row=1, column=1, padx=10, pady=(0, 15), sticky="w")

        # --- SECCIÓN 3: ARCHIVO CSV ---
        self.frame_archivo = ctk.CTkFrame(self, fg_color="#2b2b2b", corner_radius=10)
        self.frame_archivo.pack(pady=10, padx=20, fill="x")
        
        ctk.CTkLabel(self.frame_archivo, text="3. Archivo Origen", font=("Arial", 14, "bold")).pack(anchor="w", padx=15, pady=(10,0))
        
        frame_btn_arch = ctk.CTkFrame(self.frame_archivo, fg_color="transparent")
        frame_btn_arch.pack(fill="x", padx=15, pady=10)
        
        ctk.CTkButton(frame_btn_arch, text="📂 Seleccionar CSV", command=self.seleccionar_archivo, width=150).pack(side="left")
        self.lbl_archivo = ctk.CTkLabel(frame_btn_arch, text="Ningún archivo seleccionado...", text_color="#aaaaaa")
        self.lbl_archivo.pack(side="left", padx=15)

        # --- SECCIÓN 4: ACCIÓN Y LOGS ---
        self.btn_iniciar = ctk.CTkButton(self, text="🚀 INICIAR CARGA MASIVA", font=("Arial", 14, "bold"), height=40, fg_color="#0056b3", hover_color="#004085", command=self.iniciar_proceso)
        self.btn_iniciar.pack(pady=10, padx=20, fill="x")

        self.txt_log = ctk.CTkTextbox(self, height=200, fg_color="#1a1a1a", text_color="#00ff00", font=("Consolas", 12))
        self.txt_log.pack(pady=10, padx=20, fill="both", expand=True)
        self.log("Sistema multi-motor iniciado. Listo para cargar.")

    # ==========================================
    # LÓGICA DE UI Y EVENTOS
    # ==========================================
    def log(self, mensaje):
        hora = datetime.now().strftime("%H:%M:%S")
        self.txt_log.insert("end", f"[{hora}] {mensaje}\n")
        self.txt_log.see("end")

    def actualizar_lista_servidores(self):
        self.mapa_servidores = {}
        nombres = []
        
        for srv in self.config_data.get("Servidores_BD", []):
            tipo = srv.get("tipo", "SQL Server")
            ip = srv.get("ip", "Sin IP")
            nombre = srv.get("nombre", "Sin Nombre")
            
            # Aquí definimos cómo se ve en la interfaz (Ej: "Guias - 192.168.1.100 (SQL Server)")
            display_str = f"{nombre} - {ip} ({tipo})"
            
            # Guardamos la relación texto -> datos reales
            self.mapa_servidores[display_str] = srv
            nombres.append(display_str)

        if nombres:
            self.cmb_servidores.configure(values=nombres)
            self.cmb_servidores.set(nombres[0])
            self.al_seleccionar_servidor(nombres[0])
        else:
            self.cmb_servidores.configure(values=["No hay servidores"])
            self.cmb_servidores.set("No hay servidores")

    def obtener_credenciales(self, display_name):
        # Ahora simplemente buscamos el texto exacto en nuestro mapa
        srv = self.mapa_servidores.get(display_name)
        if srv and "tipo" not in srv: 
            srv["tipo"] = "SQL Server"
        return srv

    def conectar_db(self, srv, db_name=None):
        """Generador de conexiones universales."""
        tipo = srv.get("tipo", "SQL Server")
        
        if tipo == "SQL Server":
            db_part = f"DATABASE={db_name};" if db_name else ""
            conn_str = f"DRIVER={{{self.driver_sql}}};SERVER={srv['ip']};{db_part}UID={srv['user']};PWD={srv['pwd']};"
            return pyodbc.connect(conn_str, autocommit=(db_name is None))
            
        elif tipo == "PostgreSQL":
            # Postgres requiere conectar a una base, usamos 'postgres' por defecto si no se pasa una
            db = db_name if db_name else 'postgres'
            return psycopg2.connect(host=srv['ip'], user=srv['user'], password=srv['pwd'], dbname=db)

    def al_seleccionar_servidor(self, display_name):
        srv = self.obtener_credenciales(display_name)
        if not srv: return
        self.cmb_dbs.set("Cargando bases de datos...")
        threading.Thread(target=self.cargar_bases_de_datos, args=(srv,), daemon=True).start()

    def cargar_bases_de_datos(self, srv):
        conn = None
        try:
            conn = self.conectar_db(srv)
            cursor = conn.cursor()
            
            if srv["tipo"] == "SQL Server":
                cursor.execute("SELECT name FROM sys.databases WHERE state = 0 ORDER BY name")
            else: # PostgreSQL
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
        self.cmb_tablas.set("Cargando tablas...")
        threading.Thread(target=self.cargar_tablas, args=(srv, db_name), daemon=True).start()

    def cargar_tablas(self, srv, db_name):
        conn = None
        try:
            conn = self.conectar_db(srv, db_name)
            cursor = conn.cursor()
            
            esquema = "dbo" if srv["tipo"] == "SQL Server" else "public"
            cursor.execute(f"SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_TYPE = 'BASE TABLE' AND TABLE_SCHEMA = '{esquema}' ORDER BY TABLE_NAME")
            
            tablas = [row[0] for row in cursor.fetchall()]

            if tablas:
                self.cmb_tablas.configure(values=tablas)
                self.cmb_tablas.set(tablas[0])
            else:
                self.cmb_tablas.configure(values=["No hay tablas"])
                self.cmb_tablas.set("No hay tablas")
        except Exception as e:
            self.cmb_tablas.set("Error al cargar")
            self.log(f"Error cargando tablas de {db_name}: {e}")
        finally:
            if conn: conn.close()

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
        tabla = self.cmb_tablas.get()
        
        if not self.archivo_csv:
            messagebox.showerror("Error", "Debe seleccionar un CSV primero.")
            return
        if "Esperando" in tabla or "Error" in tabla or "No hay" in tabla:
            messagebox.showerror("Error", "Seleccione una tabla válida.")
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
                # En psycopg2 devuelve 'YES', en pyodbc también.
                acepta_nulos[col_name] = (row[1] == 'YES')

            col_count = len(columnas_sql)
            if col_count == 0:
                raise Exception("La tabla no existe o no tiene permisos.")

            # 2. Configurar la lectura del CSV
            with open(self.archivo_csv, 'r', encoding='utf-8', newline='') as f:
                first_line = f.readline()
                delimitador = ','
                if '\t' in first_line: delimitador = '\t'
                elif ';' in first_line: delimitador = ';'

                f.seek(0)
                reader = csv.reader(f, delimiter=delimitador)
                next(reader, None) # Saltar cabecera

                batch_size = 50000
                total_insertados = 0
                
                # --- RAMA 1: LOGICA SQL SERVER (Fast ExecuteMany) ---
                if tipo_db == "SQL Server":
                    placeholders = ",".join(["?"] * col_count)
                    cols_str = ",".join(columnas_sql)
                    insert_query = f"INSERT INTO {esquema}.{tabla} ({cols_str}) VALUES ({placeholders})"
                    cursor.fast_executemany = True
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

                # --- RAMA 2: LOGICA POSTGRESQL (Memory Buffer + COPY) ---
                else: 
                    csv_buffer = io.StringIO()
                    writer = csv.writer(csv_buffer, delimiter='\t')
                    lineas_en_buffer = 0

                    for fila in reader:
                        fila_procesada = self._transformar_fila(fila, col_count, columnas_sql, acepta_nulos)
                        # Reemplazamos los None de Python por un string vacío para el COPY de Postgres
                        fila_procesada = ["" if x is None else x for x in fila_procesada]
                        writer.writerow(fila_procesada)
                        lineas_en_buffer += 1

                        if lineas_en_buffer >= batch_size:
                            csv_buffer.seek(0)
                            # Usar COPY (ultra rápido)
                            cursor.copy_expert(f"COPY {esquema}.{tabla} FROM STDIN WITH (FORMAT CSV, DELIMITER '\t', NULL '')", csv_buffer)
                            conn.commit()
                            total_insertados += lineas_en_buffer
                            self.log(f"Insertados {total_insertados} registros mediante COPY...")
                            
                            # Limpiar buffer
                            csv_buffer.seek(0)
                            csv_buffer.truncate(0)
                            lineas_en_buffer = 0

                    # Inserción de las líneas sobrantes
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
        """Aplica las reglas de negocio, recortes, control de nulos y conversiones de bit."""
        fila_procesada = []
        if len(fila) < col_count:
            fila.extend([''] * (col_count - len(fila)))
        elif len(fila) > col_count:
            fila = fila[:col_count]

        for i in range(col_count):
            col_name = columnas_sql[i]
            val = fila[i].strip() if isinstance(fila[i], str) else fila[i]

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

if __name__ == "__main__":
    multiprocessing.freeze_support()
    app = AplicacionCargas()
    app.mainloop()