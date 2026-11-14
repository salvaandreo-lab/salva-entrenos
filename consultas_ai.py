import re
import os
import json
import urllib.request
import urllib.error
import database
from typing import Dict, Any, List, Optional

def obtener_gemini_api_key() -> str:
    """Recupera la clave API de Gemini desde secrets.toml, session_state o entorno."""
    # 1. Intentar desde st.secrets si Streamlit está activo
    try:
        import streamlit as st
        if hasattr(st, "secrets") and "GEMINI_API_KEY" in st.secrets:
            k = str(st.secrets["GEMINI_API_KEY"]).strip()
            if k: return k
    except Exception:
        pass

    # 2. Leer directamente desde .streamlit/secrets.toml
    secrets_path = os.path.join(os.path.dirname(__file__), ".streamlit", "secrets.toml")
    if os.path.isfile(secrets_path):
        try:
            with open(secrets_path, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip().startswith("GEMINI_API_KEY"):
                        parts = line.split("=", 1)
                        if len(parts) == 2:
                            return parts[1].strip().strip('"').strip("'")
        except Exception:
            pass

    # 3. Variable de entorno
    return os.getenv("GEMINI_API_KEY", "").strip()

def llamar_gemini_api(prompt: str, api_key: str, model: str = "gemini-3.5-flash") -> str:
    """Envía un prompt a la API de Google Gemini vía REST de forma ultra-rápida."""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    payload = {
        "contents": [
            {"parts": [{"text": prompt}]}
        ]
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST"
    )
    with urllib.request.urlopen(req, timeout=25) as resp:
        res_json = json.loads(resp.read().decode("utf-8"))
        candidates = res_json.get("candidates", [])
        if candidates:
            parts = candidates[0].get("content", {}).get("parts", [])
            if parts:
                return parts[0].get("text", "").strip()
    return ""

# Esquema de la base de datos para guiar a la IA
ESQUEMA_BD = """
BASE DE DATOS SQLITE (HISTORIAL DE ENTRENAMIENTOS DE ATLETISMO):

Tabla 1: 'entrenamientos' (Resumen de cada sesión)
- id: INTEGER PRIMARY KEY
- fecha: TEXT (Formato 'YYYY-MM-DD HH:MM:SS')
- titulo: TEXT (Título de la sesión, ej: 'Series de 400m en Pista', 'Media Maratón de Orihuela')
- deporte: TEXT (ej: 'running')
- distancia_km: REAL (Distancia total recorrida en kilómetros)
- tiempo_total_s: INTEGER (Duración total en segundos)
- tiempo_formateado: TEXT (Formato 'HH:MM:SS' o 'MM:SS')
- ritmo_medio_minkm: TEXT (Ritmo promedio 'M:SS', ej: '4:13' min/km)
- fc_media: INTEGER (Pulsaciones cardíacas medias)
- fc_max: INTEGER (Pulsaciones máximas)
- cadencia_media: INTEGER (Pasos por minuto)
- calorias: INTEGER
- ubicacion: TEXT (Localización o ciudad, ej: 'Orihuela', 'Pista Municipal')
- notas_entrenador: TEXT

Tabla 2: 'series_laps' (Detalle de cada vuelta o serie dentro de un entreno)
- id: INTEGER PRIMARY KEY
- entrenamiento_id: INTEGER (Clave foránea hacia entrenamientos.id)
- lap_numero: INTEGER (Número de serie dentro del entreno: 1, 2, 3...)
- distancia_m: REAL (Distancia exacta del intervalo en metros, ej: 400.0, 1000.0, 5000.0)
- tiempo_s: REAL (Duración de la serie en segundos)
- tiempo_formateado: TEXT (Formato 'MM:SS' o 'HH:MM:SS', ej: '01:15')
- ritmo_minkm: TEXT (Ritmo de la serie 'M:SS', ej: '3:07' min/km)
- fc_media: INTEGER (Pulsaciones medias de la serie)
- fc_max: INTEGER (Pulsaciones máximas de la serie)
- cadencia: INTEGER
- tipo_intervalo: TEXT (ej: 'serie_400m', 'calentamiento', 'enfriamiento')
"""

def responder_con_text_to_sql(pregunta: str, api_key: str) -> Optional[str]:
    """
    Motor inteligente Text-to-SQL:
    1. Traduce la pregunta del atleta a una consulta SQL de SQLite.
    2. Ejecuta la consulta sobre sporttracks.db.
    3. Interpreta los datos y redacta una respuesta deportiva profesional.
    """
    try:
        # 1. Generar SQL
        prompt_sql = f"""Eres un experto desarrollador de bases de datos SQLite para deportes y running.
{ESQUEMA_BD}

Pregunta del atleta: "{pregunta}"

INSTRUCCIONES OBLIGATORIAS:
- Genera ÚNICAMENTE una consulta SQL (SELECT ...) válida para SQLite que responda exactamente a la pregunta.
- Para series de 400m usa un margen de GPS: `s.distancia_m BETWEEN 380 AND 420`.
- Para series de 1000m usa: `s.distancia_m BETWEEN 950 AND 1050`.
- Para series de 2000m usa: `s.distancia_m BETWEEN 1900 AND 2100`.
- Si preguntan por la serie más rápida, ordena por `tiempo_s ASC LIMIT 1`.
- Si preguntan por la última vez, ordena por `e.fecha DESC LIMIT 1`.
- Si preguntan por totales o medias mensuales: usa `strftime('%Y-%m', fecha)`.
- Si necesitas datos de la sesión (fecha, título, etc.) haz JOIN entre `series_laps s` y `entrenamientos e ON s.entrenamiento_id = e.id`.
- Devuelve SOLO el código SQL sin explicaciones, sin texto antes ni después, sin etiquetas ```sql."""

        sql_generado = llamar_gemini_api(prompt_sql, api_key)
        # Limpiar posibles bloques markdown
        sql_limpio = re.sub(r"```(?:sql)?", "", sql_generado).strip()
        
        # Filtro de seguridad: solo permitir consultas SELECT
        if not sql_limpio.upper().startswith("SELECT"):
            return None

        # 2. Ejecutar la consulta en la base de datos local
        filas = database.ejecutar_consulta_sql(sql_limpio)
        if filas and "error" in filas[0]:
            print(f"[SQL Error] {filas[0]['error']} en consulta: {sql_limpio}")
            return None

        # 3. Formular la respuesta deportiva con IA
        prompt_respuesta = f"""Eres un entrenador deportivo de atletismo experto, analítico y motivador.
El atleta te ha hecho esta pregunta sobre sus entrenamientos:
"{pregunta}"

Datos reales obtenidos de su base de datos Garmin:
{json.dumps(filas, ensure_ascii=False)}

INSTRUCCIONES DE RESPUESTA:
1. Responde en español de forma directa, clara y amena.
2. Destaca los números clave en negrita (fechas, ritmos min/km, tiempos, pulsaciones, kilómetros).
3. Si hay varias series o varias carreras, preséntalas en una tabla Markdown limpia y ordenada.
4. Añade un breve comentario técnico o motivador sobre su rendimiento o progreso.
5. No inventes ningún dato que no esté en la información devuelta."""

        respuesta_ia = llamar_gemini_api(prompt_respuesta, api_key)
        if respuesta_ia:
            return respuesta_ia
    except Exception as e:
        print(f"[Text-to-SQL Exception] {e}")
        return None

    return None

def responder_consulta_entrenamientos(pregunta: str) -> str:
    """
    Función principal de consulta:
    1. Si hay clave API de Gemini configurada, ejecuta el motor Text-to-SQL (capaz de responder CUALQUIER pregunta).
    2. Si falla o no hay conexión, recurre al motor de reglas locales como respaldo seguro.
    """
    api_key = obtener_gemini_api_key()

    if api_key:
        respuesta_motor = responder_con_text_to_sql(pregunta, api_key)
        if respuesta_motor:
            return respuesta_motor

    # ==================== MOTOR DE RESPALDO (REGLAS LOCALES) ====================
    pregunta_lower = pregunta.lower().strip()

    # Caso: Series de X metros
    match_serie = re.search(r'series?\s+(?:de\s+)?(\d+)\s*(?:m|metros)?', pregunta_lower)
    if match_serie:
        distancia = int(match_serie.group(1))
        min_m = distancia * 0.90
        max_m = distancia * 1.10

        query = """
        SELECT e.fecha, e.titulo, s.lap_numero, s.distancia_m, s.tiempo_s,
               s.tiempo_formateado, s.ritmo_minkm, s.fc_media, s.fc_max
        FROM series_laps s
        JOIN entrenamientos e ON s.entrenamiento_id = e.id
        WHERE s.distancia_m BETWEEN ? AND ?
        ORDER BY e.fecha DESC, s.lap_numero ASC
        """
        filas = database.ejecutar_consulta_sql(query, (min_m, max_m))
        if not filas:
            return f"No he encontrado series de aproximadamente {distancia} metros en tu historial registrado."

        ultima_fecha = filas[0]["fecha"]
        series_ultima_sesion = [f for f in filas if f["fecha"] == ultima_fecha]
        mas_rapida_sesion = min(series_ultima_sesion, key=lambda x: x["tiempo_s"])
        mas_rapida_historica = min(filas, key=lambda x: x["tiempo_s"])

        respuesta = f"### 🏃 Series de {distancia}m detectadas\n\n"
        respuesta += f"**Última vez realizada:** {ultima_fecha} (*{series_ultima_sesion[0]['titulo']}*)\n"
        respuesta += f"- **Total de series completadas:** {len(series_ultima_sesion)}\n"
        respuesta += f"- **Serie más rápida de ese día:** Serie #{mas_rapida_sesion['lap_numero']} en **{mas_rapida_sesion['tiempo_formateado']}** (ritmo {mas_rapida_sesion['ritmo_minkm']} min/km) con {mas_rapida_sesion['fc_media']} ppm medias.\n\n"

        if mas_rapida_historica['tiempo_s'] < mas_rapida_sesion['tiempo_s']:
            respuesta += f"⚡ **Récord histórico de {distancia}m:** El {mas_rapida_historica['fecha']} hiciste una serie en **{mas_rapida_historica['tiempo_formateado']}** (ritmo {mas_rapida_historica['ritmo_minkm']} min/km).\n\n"

        respuesta += "| # Serie | Distancia | Tiempo | Ritmo | FC Media | FC Máx |\n"
        respuesta += "|---|---|---|---|---|---|\n"
        for s in series_ultima_sesion:
            respuesta += f"| #{s['lap_numero']} | {int(s['distancia_m'])}m | {s['tiempo_formateado']} | {s['ritmo_minkm']} | {s['fc_media'] or '-'} ppm | {s['fc_max'] or '-'} ppm |\n"
        return respuesta

    # Caso: Carrera o ubicación
    for palabra_clave in ["orihuela", "carrera", "maraton", "maratón", "media", "trail"]:
        if palabra_clave in pregunta_lower:
            termino = f"%{palabra_clave}%"
            query = """
            SELECT id, fecha, titulo, distancia_km, tiempo_formateado, ritmo_medio_minkm, fc_media, ubicacion
            FROM entrenamientos
            WHERE LOWER(titulo) LIKE ? OR LOWER(ubicacion) LIKE ?
            ORDER BY fecha DESC
            """
            filas = database.ejecutar_consulta_sql(query, (termino, termino))
            if filas:
                respuesta = f"### 🏅 Historial encontrado para '{palabra_clave.capitalize()}':\n\n"
                respuesta += f"Se han registrado **{len(filas)}** participaciones/sesiones:\n\n"
                respuesta += "| Fecha | Título / Evento | Distancia | Tiempo | Ritmo Medio | FC Media |\n"
                respuesta += "|---|---|---|---|---|---|\n"
                for f in filas:
                    respuesta += f"| {f['fecha'][:10]} | {f['titulo']} | {f['distancia_km']} km | {f['tiempo_formateado']} | {f['ritmo_medio_minkm']} min/km | {f['fc_media'] or '-'} ppm |\n"
                return respuesta

    # Resumen general
    stats = database.obtener_resumen_estadisticas()
    return (f"📊 **Resumen de tu historial en SportTracks:**\n\n"
            f"- **Entrenamientos totales:** {stats['total_entrenos']}\n"
            f"- **Kilómetros acumulados:** {stats['total_km']} km\n"
            f"- **Series e intervalos guardados:** {stats['total_series']}\n\n"
            f"💡 *Puedes preguntarme lo que quieras: comparativas, records, tiradas largas o medias mensuales.*")
