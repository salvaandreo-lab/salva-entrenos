import sqlite3
import os
from typing import List, Dict, Any, Optional, Tuple

DB_PATH = os.path.join(os.path.dirname(__file__), "sporttracks.db")

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Crea las tablas necesarias si no existen."""
    conn = get_connection()
    cursor = conn.cursor()

    # Tabla de entrenamientos generales
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS entrenamientos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
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
        fit_hash TEXT UNIQUE
    )
    """)

    # Tabla de laps / series detalladas
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

    conn.commit()
    conn.close()

def guardar_entrenamiento(datos_entreno: Dict[str, Any], laps: List[Dict[str, Any]]) -> Optional[int]:
    """Guarda un entrenamiento completo con sus vueltas/series."""
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
        INSERT INTO entrenamientos (
            fecha, titulo, deporte, distancia_km, tiempo_total_s,
            tiempo_formateado, ritmo_medio_minkm, fc_media, fc_max,
            cadencia_media, calorias, ubicacion, notas_entrenador, fit_hash
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
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

def obtener_resumen_estadisticas() -> Dict[str, Any]:
    """Obtiene totales para mostrar métricas clave."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) as total_entrenos, IFNULL(SUM(distancia_km), 0) as total_km FROM entrenamientos")
    row = cursor.fetchone()
    total_entrenos = row["total_entrenos"]
    total_km = round(row["total_km"], 1)

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

def obtener_records_personales() -> List[Dict[str, Any]]:
    """Calcula y devuelve las mejores marcas históricas en distancias clave."""
    conn = get_connection()
    cursor = conn.cursor()
    records = []

    # 1. Series en pista / intervalos
    intervalos = [
        ("400m (Serie)", 380, 430, "s.distancia_m BETWEEN 380 AND 430"),
        ("1.000m (Serie)", 950, 1050, "s.distancia_m BETWEEN 950 AND 1050"),
        ("2.000m (Serie)", 1900, 2100, "s.distancia_m BETWEEN 1900 AND 2100"),
    ]
    for nombre, _, _, condicion in intervalos:
        cursor.execute(f"""
            SELECT '{nombre}' as categoria, s.tiempo_formateado as marca, s.ritmo_minkm as ritmo,
                   e.fecha, e.titulo, s.fc_media, s.tiempo_s
            FROM series_laps s
            JOIN entrenamientos e ON s.entrenamiento_id = e.id
            WHERE {condicion} AND s.tiempo_s > 0
            ORDER BY s.tiempo_s ASC
            LIMIT 1
        """)
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
        cursor.execute("""
            SELECT ? as categoria, tiempo_formateado as marca, ritmo_medio_minkm as ritmo,
                   fecha, titulo, fc_media, tiempo_total_s as tiempo_s
            FROM entrenamientos
            WHERE distancia_km BETWEEN ? AND ? AND tiempo_total_s > 0
            ORDER BY tiempo_total_s ASC
            LIMIT 1
        """, (nombre, d_min, d_max))
        row = cursor.fetchone()
        if row:
            records.append(dict(row))

    # 3. Sesión más larga (tirada ultra o fondo)
    cursor.execute("""
        SELECT 'Tirada más larga' as categoria,
               PRINTF('%.2f km', distancia_km) as marca,
               ritmo_medio_minkm as ritmo,
               fecha, titulo, fc_media, tiempo_total_s as tiempo_s
        FROM entrenamientos
        ORDER BY distancia_km DESC
        LIMIT 1
    """)
    row = cursor.fetchone()
    if row:
        records.append(dict(row))

    conn.close()
    return records

def obtener_volumen_anual() -> List[Dict[str, Any]]:
    """Calcula el resumen de kms y sesiones por año."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT strftime('%Y', fecha) as anio,
               COUNT(*) as sesiones,
               ROUND(SUM(distancia_km), 1) as total_km,
               ROUND(AVG(distancia_km), 2) as media_km
        FROM entrenamientos
        WHERE distancia_km > 0
        GROUP BY anio
        ORDER BY anio DESC
    """)
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows

def obtener_volumen_mensual() -> List[Dict[str, Any]]:
    """Calcula kms y sesiones agrupados por mes."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT strftime('%Y-%m', fecha) as mes,
               COUNT(*) as sesiones,
               ROUND(SUM(distancia_km), 1) as total_km
        FROM entrenamientos
        WHERE distancia_km > 0
        GROUP BY mes
        ORDER BY mes ASC
    """)
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows

def obtener_volumen_semanal() -> List[Dict[str, Any]]:
    """Calcula kms y sesiones agrupados por semana (ISO week)."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT strftime('%Y-W%W', fecha) as semana,
               COUNT(*) as sesiones,
               ROUND(SUM(distancia_km), 1) as total_km
        FROM entrenamientos
        WHERE distancia_km > 0
        GROUP BY semana
        ORDER BY semana ASC
    """)
    rows = [dict(r) for r in cursor.fetchall()]
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
