import sqlite3
import os
from datetime import date, timedelta, datetime
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

    # 4. Tabla de parciales métricos kilómetro a kilómetro (estilo Strava)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS entrenamientos_splits_km (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        entrenamiento_id INTEGER NOT NULL,
        km_numero INTEGER NOT NULL,
        etiqueta TEXT NOT NULL,
        distancia_m REAL NOT NULL,
        tiempo_s REAL NOT NULL,
        tiempo_formateado TEXT NOT NULL,
        ritmo_minkm TEXT NOT NULL,
        desnivel_m REAL DEFAULT 0.0,
        desviacion_ritmo_s REAL DEFAULT 0.0,
        fc_media INTEGER,
        fc_max INTEGER,
        cadencia INTEGER,
        FOREIGN KEY (entrenamiento_id) REFERENCES entrenamientos(id) ON DELETE CASCADE
    )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_splits_entrenamiento ON entrenamientos_splits_km(entrenamiento_id)")

    # 5. Usuarios iniciales del Team Ardil si la tabla está vacía
    cursor.execute("SELECT COUNT(*) FROM usuarios")
    if cursor.fetchone()[0] == 0:
        usuarios_seed = [
            (1, 'Salva Andreo', 'salva', 'atleta', 2, 'salva@teamardil.com', 'SA', 'https://docs.google.com/document/d/1rUeBFG0vL3ZaOXP5nxQKOPA5MVtfr_NuQWOWZ51VodM/edit?usp=sharing'),
            (2, 'Míster (Team Ardil)', 'mister', 'entrenador', None, 'mister@teamardil.com', 'TA', None),
            (3, 'Atleta Compañero', 'amigo', 'atleta', 2, 'amigo@teamardil.com', 'AC', None),
            (4, 'Jose Ángel', 'joseangel', 'atleta', 2, 'joseangel@teamardil.com', 'JA', None)
        ]
        cursor.executemany("""
        INSERT INTO usuarios (id, nombre, alias, rol, entrenador_id, email, avatar, doc_plan_url)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, usuarios_seed)

    conn.commit()
    conn.close()

# ==================== FUNCIONES DE GESTIÓN DE USUARIOS / ATLETAS ====================
def persistir_base_datos(commit_msg: str = "Actualización de base de datos [skip ci]") -> bool:
    """Sincroniza sporttracks.db con el repositorio de GitHub para persistencia permanente en Streamlit Cloud."""
    try:
        import sync_sporttracks
        return sync_sporttracks.sync_file("sporttracks.db", commit_msg=commit_msg)
    except Exception as e:
        print(f"Aviso de sincronización remota de sporttracks.db: {e}")
        return False

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
                               email: str = "", avatar: str = "🏃", doc_plan_url: Optional[str] = None,
                               usuario_id: Optional[int] = None, sync_remoto: bool = True) -> int:
    """Crea un nuevo atleta o actualiza su perfil de forma segura y permanente."""
    conn = get_connection()
    cursor = conn.cursor()
    alias_clean = alias.lower().strip()

    if usuario_id:
        cursor.execute("""
        UPDATE usuarios SET
            nombre = ?,
            alias = ?,
            rol = ?,
            entrenador_id = ?,
            email = ?,
            avatar = ?,
            doc_plan_url = COALESCE(?, doc_plan_url)
        WHERE id = ?
        """, (nombre.strip(), alias_clean, rol, entrenador_id, email, avatar, doc_plan_url, usuario_id))
        conn.commit()
        conn.close()
        if sync_remoto:
            persistir_base_datos(f"Actualizado atleta '{nombre}' [skip ci]")
        return usuario_id

    # Si es alta nueva, prevenir sobrescribir el alias protegido de Salva
    if alias_clean == "salva":
        cursor.execute("SELECT id FROM usuarios WHERE alias = 'salva'")
        row = cursor.fetchone()
        conn.close()
        return row[0] if row else 1

    cursor.execute("""
    INSERT INTO usuarios (nombre, alias, rol, entrenador_id, email, avatar, doc_plan_url)
    VALUES (?, ?, ?, ?, ?, ?, ?)
    ON CONFLICT(alias) DO UPDATE SET
        nombre = excluded.nombre,
        rol = excluded.rol,
        entrenador_id = excluded.entrenador_id,
        email = excluded.email,
        avatar = excluded.avatar,
        doc_plan_url = COALESCE(excluded.doc_plan_url, usuarios.doc_plan_url)
    """, (nombre.strip(), alias_clean, rol, entrenador_id, email, avatar, doc_plan_url))
    conn.commit()
    cursor.execute("SELECT id FROM usuarios WHERE alias = ?", (alias_clean,))
    row = cursor.fetchone()
    uid = row[0] if row else cursor.lastrowid
    conn.close()
    if sync_remoto:
        persistir_base_datos(f"Alta permanente de atleta '{nombre}' [skip ci]")
    return uid

def eliminar_usuario(usuario_id: int) -> bool:
    """Elimina un atleta (excepto Salva y el Míster) y sus datos asociados."""
    if usuario_id in (1, 2):
        return False
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM entrenamientos WHERE usuario_id = ?", (usuario_id,))
    cursor.execute("DELETE FROM usuarios WHERE id = ?", (usuario_id,))
    conn.commit()
    conn.close()
    persistir_base_datos(f"Eliminado atleta id {usuario_id} [skip ci]")
    return True

def guardar_entrenamiento(datos_entreno: Dict[str, Any], laps: List[Dict[str, Any]], usuario_id: int = 1) -> Optional[int]:
    """Guarda un entrenamiento completo con sus vueltas/series para un atleta específico."""
    conn = get_connection()
    cursor = conn.cursor()

    try:
        f_hash = datos_entreno.get("fit_hash")
        fecha = datos_entreno.get("fecha")
        if f_hash:
            act_base_id = f_hash.split("_")[-1] if "_" in f_hash else f_hash
            cursor.execute(
                "SELECT id FROM entrenamientos WHERE fit_hash = ? OR fit_hash LIKE ? OR (fecha = ? AND usuario_id = ?)",
                (f_hash, f"%{act_base_id}", fecha, usuario_id)
            )
            if cursor.fetchone():
                return None
        elif fecha:
            cursor.execute("SELECT id FROM entrenamientos WHERE fecha = ? AND usuario_id = ?", (fecha, usuario_id))
            if cursor.fetchone():
                return None

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
        # 3. Recuperación: descanso parado (< 120m) o tramo a ritmo lento (> 4:40 min/km o pausas de trote/caminar)
        else:
            es_ritmo_lento = any(ritmo.startswith(p) for p in ["4:4", "4:5", "5:", "6:", "7:", "8:", "9:", "10:", "11:", "12:", "13:", "14:", "15:", "16:", "17:", "18:", "19:", "20:", "25:", "30:", "--"])
            if dist < 120 or (dist < 380 and es_ritmo_lento) or (t_s <= 300 and any(k in ritmo for k in ["10:", "11:", "12:", "15:", "20:", "25:", "30:", "--"])):
                item["tipo_clasificado"] = "Recuperación"
                num_recup += 1
            # 4. Serie principal (incluyendo series rápidas de 200m y 300m)
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

def calcular_splits_km(distancia_km: float, tiempo_total_s: float, laps: Optional[List[Dict[str, Any]]] = None) -> List[Dict[str, Any]]:
    """
    Calcula los parciales métricos kilómetro a kilómetro (estilo Strava)
    a partir de la distancia total, tiempo total y los laps registrados.
    """
    total_m = float(distancia_km or 0.0) * 1000.0
    total_s = float(tiempo_total_s or 0.0)
    if total_m <= 0 or total_s <= 0:
        return []

    ritmo_medio_seg_km = total_s / (total_m / 1000.0)

    laps = laps or []
    cum_pts = [(0.0, 0.0, None, None, None)]  # (dist_m, time_s, fc_media, fc_max, cadencia)
    cur_d = 0.0
    cur_t = 0.0
    for l in laps:
        d = float(l.get("distancia_m") or 0.0)
        t = float(l.get("tiempo_s") or 0.0)
        cur_d += d
        cur_t += t
        cum_pts.append((cur_d, cur_t, l.get("fc_media"), l.get("fc_max"), l.get("cadencia")))

    # Si no hay laps o cubren menos del 40% del recorrido, repartir linealmente por distancia total
    if cur_d < total_m * 0.4:
        cum_pts = [(0.0, 0.0, None, None, None), (total_m, total_s, None, None, None)]

    def time_and_stats_at(target_d):
        for i in range(1, len(cum_pts)):
            d0, t0, hr0, hrmax0, cad0 = cum_pts[i - 1]
            d1, t1, hr1, hrmax1, cad1 = cum_pts[i]
            if d0 <= target_d <= d1:
                frac = (target_d - d0) / (d1 - d0) if d1 > d0 else 0
                t = t0 + frac * (t1 - t0)
                hr = hr1 if hr1 is not None else hr0
                hrmax = hrmax1 if hrmax1 is not None else hrmax0
                cad = cad1 if cad1 is not None else cad0
                return t, hr, hrmax, cad
        return cum_pts[-1][1], cum_pts[-1][2], cum_pts[-1][3], cum_pts[-1][4]

    max_dist = max(total_m, cum_pts[-1][0])
    num_kms = int(max_dist // 1000)
    resto_m = max_dist % 1000

    def seg_a_fmt(s_val):
        s_int = int(round(s_val))
        h = s_int // 3600
        m = (s_int % 3600) // 60
        sec = s_int % 60
        if h > 0:
            return f"{h}:{m:02d}:{sec:02d}"
        return f"{m:02d}:{sec:02d}"

    def calc_ritmo_fmt(dist_m, dur_s):
        if dist_m <= 0 or dur_s <= 0:
            return "--:--"
        min_km = (dur_s / 60.0) / (dist_m / 1000.0)
        m = int(min_km)
        s = int(round((min_km - m) * 60))
        if s >= 60:
            m += 1
            s = 0
        return f"{m}:{s:02d}"

    splits = []
    prev_t = 0.0
    for k in range(1, num_kms + 1):
        target_d = k * 1000.0
        tk, hr, hrmax, cad = time_and_stats_at(target_d)
        dur = max(1.0, tk - prev_t)
        prev_t = tk
        diff_s = dur - ritmo_medio_seg_km
        splits.append({
            "split_numero": k,
            "etiqueta": f"Km {k}",
            "distancia_m": 1000.0,
            "tiempo_s": round(dur, 1),
            "tiempo_formateado": seg_a_fmt(dur),
            "ritmo_minkm": calc_ritmo_fmt(1000.0, dur),
            "desviacion_ritmo_s": round(diff_s, 1),
            "fc_media": int(round(hr)) if hr else None,
            "fc_max": int(round(hrmax)) if hrmax else None,
            "cadencia": int(round(cad)) if cad else None
        })

    if resto_m >= 50:
        dur = max(1.0, cum_pts[-1][1] - prev_t)
        pace_s = dur / (resto_m / 1000.0)
        diff_s = pace_s - ritmo_medio_seg_km
        splits.append({
            "split_numero": num_kms + 1,
            "etiqueta": f"Km {num_kms+1} ({int(round(resto_m))}m)",
            "distancia_m": round(resto_m, 1),
            "tiempo_s": round(dur, 1),
            "tiempo_formateado": seg_a_fmt(dur),
            "ritmo_minkm": calc_ritmo_fmt(resto_m, dur),
            "desviacion_ritmo_s": round(diff_s, 1),
            "fc_media": int(round(cum_pts[-1][2])) if cum_pts[-1][2] else None,
            "fc_max": int(round(cum_pts[-1][3])) if cum_pts[-1][3] else None,
            "cadencia": int(round(cum_pts[-1][4])) if cum_pts[-1][4] else None
        })

    return splits

def guardar_splits_km(entrenamiento_id: int, splits: List[Dict[str, Any]]):
    """Guarda o actualiza los parciales métricos kilómetro a kilómetro en la base de datos."""
    if not splits:
        return
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM entrenamientos_splits_km WHERE entrenamiento_id = ?", (entrenamiento_id,))
        for s in splits:
            cursor.execute("""
            INSERT INTO entrenamientos_splits_km (
                entrenamiento_id, km_numero, etiqueta, distancia_m, tiempo_s,
                tiempo_formateado, ritmo_minkm, desnivel_m, desviacion_ritmo_s,
                fc_media, fc_max, cadencia
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                entrenamiento_id,
                int(s.get("km_numero") or s.get("split_numero") or 1),
                s.get("etiqueta") or f"Km {s.get('km_numero', 1)}",
                float(s.get("distancia_m") or 1000.0),
                float(s.get("tiempo_s") or 0.0),
                s.get("tiempo_formateado") or "00:00",
                s.get("ritmo_minkm") or "--:--",
                float(s.get("desnivel_m") or 0.0),
                float(s.get("desviacion_ritmo_s") or 0.0),
                s.get("fc_media"),
                s.get("fc_max"),
                s.get("cadencia")
            ))
        conn.commit()
    except Exception as e:
        print(f"Error al guardar splits km en DB: {e}")
    finally:
        conn.close()

def obtener_splits_km(entrenamiento_id: int) -> List[Dict[str, Any]]:
    """Recupera los parciales métricos reales km a km almacenados para un entrenamiento."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT * FROM entrenamientos_splits_km
            WHERE entrenamiento_id = ?
            ORDER BY km_numero ASC
        """, (entrenamiento_id,))
        filas = [dict(r) for r in cursor.fetchall()]
        return filas
    except Exception as e:
        print(f"Error al obtener splits km de DB: {e}")
        return []
    finally:
        conn.close()

def obtener_resumen_equipo(entrenador_id: Optional[int] = None) -> Dict[str, Any]:
    """Obtiene el estado general de todos los atletas asignados a un entrenador."""
    conn = get_connection()
    cursor = conn.cursor()

    if entrenador_id:
        cursor.execute("SELECT * FROM usuarios WHERE rol = 'atleta' AND (entrenador_id = ? OR entrenador_id IS NULL) ORDER BY nombre ASC", (entrenador_id,))
    else:
        cursor.execute("SELECT * FROM usuarios WHERE rol = 'atleta' ORDER BY nombre ASC")

    atletas = [dict(r) for r in cursor.fetchall()]
    hoy = date.today()
    lunes_actual = (hoy - timedelta(days=hoy.weekday())).strftime("%Y-%m-%d")

    total_km_equipo = 0.0
    total_entrenos_equipo = 0

    for a in atletas:
        uid = a["id"]
        cursor.execute("SELECT COUNT(*), SUM(distancia_km) FROM entrenamientos WHERE usuario_id = ?", (uid,))
        r_stats = cursor.fetchone()
        a["total_entrenos"] = r_stats[0] or 0
        a["total_km"] = round(r_stats[1] or 0.0, 1)

        total_km_equipo += (r_stats[1] or 0.0)
        total_entrenos_equipo += (r_stats[0] or 0)

        cursor.execute("SELECT SUM(distancia_km) FROM entrenamientos WHERE usuario_id = ? AND fecha >= ?", (uid, lunes_actual))
        r_sem = cursor.fetchone()
        a["km_semana"] = round(r_sem[0] or 0.0, 1)

        cursor.execute("SELECT fecha, titulo, distancia_km, ritmo_medio_minkm, tiempo_formateado FROM entrenamientos WHERE usuario_id = ? ORDER BY fecha DESC LIMIT 1", (uid,))
        r_ult = cursor.fetchone()
        if r_ult:
            a["ultimo_fecha"] = r_ult["fecha"][:10]
            a["ultimo_titulo"] = r_ult["titulo"]
            a["ultimo_km"] = r_ult["distancia_km"]
            a["ultimo_ritmo"] = r_ult["ritmo_medio_minkm"]
            a["ultimo_tiempo"] = r_ult["tiempo_formateado"]
        else:
            a["ultimo_fecha"] = None
            a["ultimo_titulo"] = None
            a["ultimo_km"] = None
            a["ultimo_ritmo"] = None
            a["ultimo_tiempo"] = None

    conn.close()

    return {
        "total_atletas": len(atletas),
        "total_entrenos_equipo": total_entrenos_equipo,
        "total_km_equipo": round(total_km_equipo, 1),
        "atletas": atletas
    }

def obtener_ultimos_entrenos_equipo(limite: int = 15) -> List[Dict[str, Any]]:
    """Devuelve las últimas actividades de todos los atletas para el feed del Míster."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT e.id, e.fecha, e.titulo, e.distancia_km, e.tiempo_formateado, e.ritmo_medio_minkm, e.fc_media,
               u.nombre as atleta_nombre, u.avatar as atleta_avatar, u.id as usuario_id
        FROM entrenamientos e
        JOIN usuarios u ON e.usuario_id = u.id
        WHERE u.rol = 'atleta'
        ORDER BY e.fecha DESC
        LIMIT ?
    """, (limite,))
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows

if __name__ == "__main__":
    init_db()
    print("Base de datos SportTracks inicializada correctamente.")
