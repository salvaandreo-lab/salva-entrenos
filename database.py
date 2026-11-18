import sqlite3
import os
from typing import List, Dict, Any, Optional, Tuple

DB_PATH = os.path.join(os.path.dirname(__file__), "sporttracks.db")

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Crea las tablas necesarias si no existen y asegura soporte multi-atleta."""
    conn = get_connection()
    cursor = conn.cursor()

    # 1. Tabla de usuarios / atletas
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS usuarios (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre TEXT NOT NULL,
        alias TEXT UNIQUE NOT NULL,
        rol TEXT NOT NULL DEFAULT 'atleta',
        entrenador_id INTEGER,
        email TEXT,
        avatar TEXT DEFAULT '🏃',
        doc_plan_url TEXT,
        activo INTEGER DEFAULT 1,
        fecha_creacion TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (entrenador_id) REFERENCES usuarios(id)
    )
    """)

    # 2. Tabla de entrenamientos generales
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS entrenamientos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        usuario_id INTEGER DEFAULT 1,
        fecha TEXT NOT NULL,
        titulo TEXT,
        deporte TEXT DEFAULT 'running',
        distancia_km REAL,
        tiempo_total_s INTEGER,
        tiempo_formateado TEXT,
        ritmo_medio_minkm TEXT,
        fc_media INTEGER,
        fc_max INTEGER,
        cadencia_media INTEGER,
        calorias INTEGER,
        ubicacion TEXT,
        notas_entrenador TEXT,
        fit_hash TEXT UNIQUE,
        FOREIGN KEY (usuario_id) REFERENCES usuarios(id)
    )
    """)

    # Comprobar si columna usuario_id ya existe en instalaciones previas
    cursor.execute("PRAGMA table_info(entrenamientos)")
    columns = [col[1] for col in cursor.fetchall()]
    if "usuario_id" not in columns:
        cursor.execute("ALTER TABLE entrenamientos ADD COLUMN usuario_id INTEGER DEFAULT 1")
        cursor.execute("UPDATE entrenamientos SET usuario_id = 1 WHERE usuario_id IS NULL")

    # 3. Tabla de laps / series detalladas
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS series_laps (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        entrenamiento_id INTEGER NOT NULL,
        lap_numero INTEGER NOT NULL,
        distancia_m REAL,
        tiempo_s REAL,
        tiempo_formateado TEXT,
        ritmo_minkm TEXT,
        fc_media INTEGER,
        fc_max INTEGER,
        cadencia INTEGER,
        tipo_intervalo TEXT DEFAULT 'serie',
        FOREIGN KEY (entrenamiento_id) REFERENCES entrenamientos(id) ON DELETE CASCADE
    )
    """)

    # 4. Usuarios iniciales del Team Ardil si la tabla está vacía
    cursor.execute("SELECT COUNT(*) FROM usuarios")
    if cursor.fetchone()[0] == 0:
        usuarios_seed = [
            (1, 'Salva Andreo', 'salva', 'atleta', 2, 'salva@teamardil.com', 'SA', None),
            (2, 'Míster (Team Ardil)', 'mister', 'entrenador', None, 'mister@teamardil.com', 'TA', None),
            (3, 'Atleta Compañero', 'amigo', 'atleta', 2, 'amigo@teamardil.com', 'AC', None)
        ]
        cursor.executemany("""
        INSERT INTO usuarios (id, nombre, alias, rol, entrenador_id, email, avatar, doc_plan_url)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, usuarios_seed)

    conn.commit()
    conn.close()

# ==================== FUNCIONES DE GESTIÓN DE USUARIOS / ATLETAS ====================
def obtener_usuarios(filtro_rol: Optional[str] = None) -> List[Dict[str, Any]]:
    """Obtiene la lista de atletas o entrenadores."""
    conn = get_connection()
    cursor = conn.cursor()
    if filtro_rol:
        cursor.execute("SELECT * FROM usuarios WHERE rol = ? AND activo = 1 ORDER BY id ASC", (filtro_rol,))
    else:
        cursor.execute("SELECT * FROM usuarios WHERE activo = 1 ORDER BY id ASC")
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows

def obtener_usuario_por_id(usuario_id: int) -> Optional[Dict[str, Any]]:
    """Devuelve la información de perfil de un atleta."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM usuarios WHERE id = ?", (usuario_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def crear_o_actualizar_usuario(nombre: str, alias: str, rol: str = "atleta", entrenador_id: Optional[int] = 2,
                               email: str = "", avatar: str = "🏃", doc_plan_url: Optional[str] = None) -> int:
    """Crea un nuevo atleta o actualiza su perfil."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO usuarios (nombre, alias, rol, entrenador_id, email, avatar, doc_plan_url)
    VALUES (?, ?, ?, ?, ?, ?, ?)
    ON CONFLICT(alias) DO UPDATE SET
        nombre = excluded.nombre,
        rol = excluded.rol,
        entrenador_id = excluded.entrenador_id,
        email = excluded.email,
        avatar = excluded.avatar,
        doc_plan_url = excluded.doc_plan_url
    """, (nombre, alias, rol, entrenador_id, email, avatar, doc_plan_url))
    uid = cursor.lastrowid
    conn.commit()
    conn.close()
    return uid

def guardar_entrenamiento(datos_entreno: Dict[str, Any], laps: List[Dict[str, Any]], usuario_id: int = 1) -> Optional[int]:
    """Guarda un entrenamiento completo con sus vueltas/series para un atleta específico."""
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
        INSERT INTO entrenamientos (
            usuario_id, fecha, titulo, deporte, distancia_km, tiempo_total_s,
            tiempo_formateado, ritmo_medio_minkm, fc_media, fc_max,
            cadencia_media, calorias, ubicacion, notas_entrenador, fit_hash
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            usuario_id,
            datos_entreno.get("fecha"),
            datos_entreno.get("titulo", "Entrenamiento"),
            datos_entreno.get("deporte", "running"),
            datos_entreno.get("distancia_km", 0.0),
            datos_entreno.get("tiempo_total_s", 0),
            datos_entreno.get("tiempo_formateado", "00:00"),
            datos_entreno.get("ritmo_medio_minkm", "--:--"),
            datos_entreno.get("fc_media"),
            datos_entreno.get("fc_max"),
            datos_entreno.get("cadencia_media"),
            datos_entreno.get("calorias"),
            datos_entreno.get("ubicacion", ""),
            datos_entreno.get("notas_entrenador", ""),
            datos_entreno.get("fit_hash")
        ))
        entrenamiento_id = cursor.lastrowid

        for lap in laps:
            cursor.execute("""
            INSERT INTO series_laps (
                entrenamiento_id, lap_numero, distancia_m, tiempo_s,
                tiempo_formateado, ritmo_minkm, fc_media, fc_max,
                cadencia, tipo_intervalo
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                entrenamiento_id,
                lap.get("lap_numero", 1),
                lap.get("distancia_m", 0.0),
                lap.get("tiempo_s", 0.0),
                lap.get("tiempo_formateado", "00:00"),
                lap.get("ritmo_minkm", "--:--"),
                lap.get("fc_media"),
                lap.get("fc_max"),
                lap.get("cadencia"),
                lap.get("tipo_intervalo", "serie")
            ))

        conn.commit()
        return entrenamiento_id
    except sqlite3.IntegrityError:
        # Ya existía (mismo fit_hash)
        return None
    finally:
        conn.close()

def obtener_resumen_estadisticas(usuario_id: Optional[int] = None) -> Dict[str, Any]:
    """Obtiene totales para mostrar métricas clave de un atleta o globales."""
    conn = get_connection()
    cursor = conn.cursor()
    
    where_sql = "WHERE usuario_id = ?" if usuario_id else ""
    params = (usuario_id,) if usuario_id else ()

    cursor.execute(f"SELECT COUNT(*) as total_entrenos, IFNULL(SUM(distancia_km), 0) as total_km FROM entrenamientos {where_sql}", params)
    row = cursor.fetchone()
    total_entrenos = row["total_entrenos"]
    total_km = round(row["total_km"], 1)

    if usuario_id:
        cursor.execute("""
            SELECT COUNT(*) as total_series 
            FROM series_laps s
            JOIN entrenamientos e ON s.entrenamiento_id = e.id
            WHERE e.usuario_id = ?
        """, (usuario_id,))
    else:
        cursor.execute("SELECT COUNT(*) as total_series FROM series_laps")
    total_series = cursor.fetchone()["total_series"]

    conn.close()
    return {
        "total_entrenos": total_entrenos,
        "total_km": total_km,
        "total_series": total_series
    }

def ejecutar_consulta_sql(query: str, params: tuple = ()) -> List[Dict[str, Any]]:
    """Ejecuta una consulta SQL segura para el asistente IA."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(query, params)
        rows = [dict(row) for row in cursor.fetchall()]
        return rows
    except Exception as e:
        return [{"error": str(e)}]
    finally:
        conn.close()

def obtener_records_personales(usuario_id: Optional[int] = None) -> List[Dict[str, Any]]:
    """Calcula y devuelve las mejores marcas históricas en distancias clave de un atleta."""
    conn = get_connection()
    cursor = conn.cursor()
    records = []

    u_filter_series = "AND e.usuario_id = ?" if usuario_id else ""
    u_filter_entrenos = "AND usuario_id = ?" if usuario_id else ""

    # 1. Series en pista / intervalos
    intervalos = [
        ("400m (Serie)", 380, 430, "s.distancia_m BETWEEN 380 AND 430"),
        ("1.000m (Serie)", 950, 1050, "s.distancia_m BETWEEN 950 AND 1050"),
        ("2.000m (Serie)", 1900, 2100, "s.distancia_m BETWEEN 1900 AND 2100"),
    ]
    for nombre, _, _, condicion in intervalos:
        query = f"""
            SELECT '{nombre}' as categoria, s.tiempo_formateado as marca, s.ritmo_minkm as ritmo,
                   e.fecha, e.titulo, s.fc_media, s.tiempo_s
            FROM series_laps s
            JOIN entrenamientos e ON s.entrenamiento_id = e.id
            WHERE {condicion} AND s.tiempo_s > 0 {u_filter_series}
            ORDER BY s.tiempo_s ASC
            LIMIT 1
        """
        params = (usuario_id,) if usuario_id else ()
        cursor.execute(query, params)
        row = cursor.fetchone()
        if row:
            records.append(dict(row))

    # 2. Distancias estándar en entrenamientos / competiciones
    distancias_carrera = [
        ("5K", 4.9, 5.4),
        ("10K", 9.8, 10.5),
        ("Media Maratón (21.1k)", 20.8, 22.0),
        ("Maratón (42.2k)", 41.5, 43.5)
    ]
    for nombre, d_min, d_max in distancias_carrera:
        query = f"""
            SELECT ? as categoria, tiempo_formateado as marca, ritmo_medio_minkm as ritmo,
                   fecha, titulo, fc_media, tiempo_total_s as tiempo_s
            FROM entrenamientos
            WHERE distancia_km BETWEEN ? AND ? AND tiempo_total_s > 0 {u_filter_entrenos}
            ORDER BY tiempo_total_s ASC
            LIMIT 1
        """
        params = (nombre, d_min, d_max, usuario_id) if usuario_id else (nombre, d_min, d_max)
        cursor.execute(query, params)
        row = cursor.fetchone()
        if row:
            records.append(dict(row))

    # 3. Sesión más larga (tirada ultra o fondo)
    query_larga = f"""
        SELECT 'Tirada más larga' as categoria,
               PRINTF('%.2f km', distancia_km) as marca,
               ritmo_medio_minkm as ritmo,
               fecha, titulo, fc_media, tiempo_total_s as tiempo_s
        FROM entrenamientos
        WHERE 1=1 {u_filter_entrenos}
        ORDER BY distancia_km DESC
        LIMIT 1
    """
    params_larga = (usuario_id,) if usuario_id else ()
    cursor.execute(query_larga, params_larga)
    row = cursor.fetchone()
    if row:
        records.append(dict(row))

    conn.close()
    return records

def obtener_volumen_anual(usuario_id: Optional[int] = None) -> List[Dict[str, Any]]:
    """Calcula el resumen de kms y sesiones por año de un atleta."""
    conn = get_connection()
    cursor = conn.cursor()
    u_sql = "AND usuario_id = ?" if usuario_id else ""
    params = (usuario_id,) if usuario_id else ()
    cursor.execute(f"""
        SELECT strftime('%Y', fecha) as anio,
               COUNT(*) as sesiones,
               ROUND(SUM(distancia_km), 1) as total_km,
               ROUND(AVG(distancia_km), 2) as media_km
        FROM entrenamientos
        WHERE distancia_km > 0 {u_sql}
        GROUP BY anio
        ORDER BY anio DESC
    """, params)
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows

def obtener_volumen_mensual(usuario_id: Optional[int] = None) -> List[Dict[str, Any]]:
    """Calcula kms y sesiones agrupados por mes de un atleta."""
    conn = get_connection()
    cursor = conn.cursor()
    u_sql = "AND usuario_id = ?" if usuario_id else ""
    params = (usuario_id,) if usuario_id else ()
    cursor.execute(f"""
        SELECT strftime('%Y-%m', fecha) as mes,
               COUNT(*) as sesiones,
               ROUND(SUM(distancia_km), 1) as total_km
        FROM entrenamientos
        WHERE distancia_km > 0 {u_sql}
        GROUP BY mes
        ORDER BY mes ASC
    """, params)
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows

def obtener_volumen_semanal(usuario_id: Optional[int] = None) -> List[Dict[str, Any]]:
    """Calcula kms y sesiones agrupados por semana (ISO week) de un atleta."""
    conn = get_connection()
    cursor = conn.cursor()
    u_sql = "AND usuario_id = ?" if usuario_id else ""
    params = (usuario_id,) if usuario_id else ()
    cursor.execute(f"""
        SELECT strftime('%Y-W%W', fecha) as semana,
               COUNT(*) as sesiones,
               ROUND(SUM(distancia_km), 1) as total_km
        FROM entrenamientos
        WHERE distancia_km > 0 {u_sql}
        GROUP BY semana
        ORDER BY semana ASC
    """, params)
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows
    conn.close()
    return rows

def obtener_detalle_entrenamiento(entrenamiento_id: int) -> Tuple[Optional[Dict[str, Any]], List[Dict[str, Any]]]:
    """Obtiene la cabecera completa de un entrenamiento y todos sus laps/series."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM entrenamientos WHERE id = ?", (entrenamiento_id,))
    row_entreno = cursor.fetchone()
    entreno = dict(row_entreno) if row_entreno else None

    cursor.execute("""
        SELECT * FROM series_laps
        WHERE entrenamiento_id = ?
        ORDER BY lap_numero ASC
    """, (entrenamiento_id,))
    laps = [dict(r) for r in cursor.fetchall()]

    conn.close()
    return entreno, laps

def clasificar_vueltas_sesion(laps: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Clasifica de forma inteligente cada vuelta distinguiendo:
    - Calentamiento
    - Series activas (Serie #1, #2...)
    - Recuperaciones entre series (pausas de 1', trote suave)
    - Enfriamiento
    """
    total = len(laps)
    resultado = []
    num_serie = 1
    num_recup = 0
    series_distancias = []
    calentamiento_km = 0.0
    enfriamiento_km = 0.0

    for i, lap in enumerate(laps):
        item = dict(lap)
        dist = float(lap.get("distancia_m", 0.0))
        t_s = float(lap.get("tiempo_s", 0.0))
        ritmo = str(lap.get("ritmo_minkm", ""))

        # 1. Calentamiento: primer lap largo (> 1200m) en una sesión de muchas vueltas
        if i == 0 and dist >= 1200 and total > 3:
            item["tipo_clasificado"] = "Calentamiento"
            calentamiento_km = round(dist / 1000.0, 2)
        # 2. Enfriamiento: último lap largo (> 1000m)
        elif i == total - 1 and dist >= 1000 and total > 3:
            item["tipo_clasificado"] = "Enfriamiento"
            enfriamiento_km = round(dist / 1000.0, 2)
        # 3. Recuperación: tramo corto (< 250m) o tiempo de descanso a ritmo lento
        elif dist < 250 or (t_s <= 240 and any(k in ritmo for k in ["12:", "15:", "20:", "25:", "30:", "--"])):
            item["tipo_clasificado"] = "Recuperación"
            num_recup += 1
        # 4. Serie principal
        else:
            item["tipo_clasificado"] = f"Serie #{num_serie}"
            num_serie += 1
            series_distancias.append(dist)

        resultado.append(item)

    dist_media_serie = round(sum(series_distancias) / max(1, len(series_distancias))) if series_distancias else 0

    resumen = {
        "num_series": num_serie - 1,
        "distancia_aprox": dist_media_serie,
        "num_recuperaciones": num_recup,
        "calentamiento_km": calentamiento_km,
        "enfriamiento_km": enfriamiento_km
    }
    return resultado, resumen

if __name__ == "__main__":
    init_db()
    print("Base de datos SportTracks inicializada correctamente.")
