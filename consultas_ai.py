import re
import os
import json
import urllib.request
import urllib.error
from collections import OrderedDict
import database
import plotly.graph_objects as go
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

def llamar_gemini_api(prompt: str, api_key: str, model: str = "gemini-3.8-flash") -> str:
    """Envía un prompt a la API de Google Gemini vía REST con reintento automático de modelos."""
    modelos = [model, "gemini-flash-latest", "gemini-3.5-flash", "gemini-3.1-flash-lite"]
    for mod in modelos:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{mod}:generateContent?key={api_key}"
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
        try:
            with urllib.request.urlopen(req, timeout=12) as resp:
                res_json = json.loads(resp.read().decode("utf-8"))
                candidates = res_json.get("candidates", [])
                if candidates:
                    parts = candidates[0].get("content", {}).get("parts", [])
                    if parts:
                        return parts[0].get("text", "").strip()
        except Exception:
            continue
    return ""

def calcular_ritmo_str(tiempo_s: float, distancia_km: float) -> str:
    """Convierte tiempo y distancia a ritmo min/km formateado M:SS."""
    if distancia_km <= 0 or tiempo_s <= 0:
        return "-:--"
    ritmo_s = tiempo_s / distancia_km
    m = int(ritmo_s // 60)
    s = int(ritmo_s % 60)
    return f"{m}:{s:02d}"

def formatear_segundos(s: int) -> str:
    """Formatea segundos en HH:MM:SS o MM:SS."""
    h = s // 3600
    m = (s % 3600) // 60
    sec = s % 60
    if h > 0:
        return f"{h:02d}:{m:02d}:{sec:02d}"
    return f"{m:02d}:{sec:02d}"

def obtener_ubicaciones_conocidas() -> List[str]:
    """Obtiene las ubicaciones registradas en la base de datos."""
    try:
        filas = database.ejecutar_consulta_sql("SELECT DISTINCT LOWER(ubicacion) as u FROM entrenamientos WHERE ubicacion IS NOT NULL AND ubicacion != ''")
        res = [f["u"].strip() for f in filas if f.get("u") and len(f["u"].strip()) > 2]
        return sorted(list(set(res)), key=len, reverse=True)
    except Exception:
        return ["orihuela", "santa pola", "cartagena", "valencia", "alcantarilla", "murcia", "alhama de murcia"]

def detectar_ubicacion_en_pregunta(pregunta: str) -> Optional[str]:
    """Detecta si la pregunta del atleta menciona una ubicación o circuito conocido."""
    preg = pregunta.lower().strip()
    
    # Comprobar ubicaciones registradas en sporttracks.db
    ubicaciones = obtener_ubicaciones_conocidas()
    for u in ubicaciones:
        if u in preg:
            return u
            
    # Nombres de ciudades habituales por si acaso
    ciudades = ["orihuela", "santa pola", "cartagena", "valencia", "ibiza", "sant josep", "lorca", "san pedro"]
    for c in ciudades:
        if c in preg:
            return c
            
    # Regex genérico "¿cuantas carreras he hecho en X?", "carreras en X"
    m = re.search(r'(?:carreras?|sesiones?|competici[oó]n(?:es)?|veces?|frente\s+a\s+frente|comparativa)\s+(?:he\s+hecho\s+)?(?:en\s+|de\s+)([a-zA-ZáéíóúÁÉÍÓÚñÑ\s]+)', preg)
    if m:
        candidato = m.group(1).strip().strip("?").strip(".").strip()
        if len(candidato) > 2 and candidato not in ["total", "mi historial", "la temporada", "este año", "general"]:
            return candidato
            
    return None

def generar_datos_categoria(ediciones: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Calcula las métricas de PB, última edición, diferencias y desglose para un conjunto de ediciones."""
    if not ediciones:
        return {}
        
    pb_sesion = min(ediciones, key=lambda x: x["tiempo_total_s"])
    ultima_sesion = max(ediciones, key=lambda x: x["fecha"])
    
    tiempos_s = [x["tiempo_total_s"] for x in ediciones]
    tiempo_medio_s = int(sum(tiempos_s) / len(tiempos_s))
    dist_media_km = sum(x["distancia_km"] for x in ediciones) / len(ediciones)
    ritmo_medio_str = calcular_ritmo_str(tiempo_medio_s, dist_media_km)
    
    ediciones_detalle = []
    for e in ediciones:
        dif_s = e["tiempo_total_s"] - pb_sesion["tiempo_total_s"]
        if e["id"] == pb_sesion["id"]:
            dif_str = "🥇 PB (Récord)"
            estado = "🔥 Récord Personal"
        else:
            m_dif = dif_s // 60
            s_dif = dif_s % 60
            dif_str = f"+{m_dif}:{s_dif:02d} min"
            if dif_s <= 180:
                estado = "⚡ Muy cerca del PB"
            elif dif_s <= 360:
                estado = "💪 Gran regularidad"
            else:
                estado = "🏃 Ritmo controlado"
                
        ediciones_detalle.append({
            "id": e["id"],
            "fecha": e["fecha"][:10],
            "año": e["fecha"][:4],
            "titulo": e["titulo"],
            "distancia_km": e["distancia_km"],
            "tiempo_s": e["tiempo_total_s"],
            "tiempo_formateado": e["tiempo_formateado"],
            "ritmo_minkm": e["ritmo_medio_minkm"],
            "fc_media": e["fc_media"],
            "diferencia_vs_pb": dif_str,
            "diferencia_s": dif_s,
            "es_pb": (e["id"] == pb_sesion["id"]),
            "estado": estado
        })
        
    dif_ultima_s = ultima_sesion["tiempo_total_s"] - pb_sesion["tiempo_total_s"]
    dif_ultima_str = f"+{dif_ultima_s // 60}:{dif_ultima_s % 60:02d} min" if dif_ultima_s > 0 else "0:00 (Es PB 🥇)"
    
    return {
        "num_ediciones": len(ediciones),
        "ediciones": ediciones_detalle,
        "ediciones_cron": sorted(ediciones_detalle, key=lambda x: x["fecha"]),
        "pb": {
            "tiempo_formateado": pb_sesion["tiempo_formateado"],
            "ritmo_minkm": pb_sesion["ritmo_medio_minkm"],
            "fecha": pb_sesion["fecha"][:10],
            "año": pb_sesion["fecha"][:4],
            "titulo": pb_sesion["titulo"]
        },
        "ultima": {
            "tiempo_formateado": ultima_sesion["tiempo_formateado"],
            "ritmo_minkm": ultima_sesion["ritmo_medio_minkm"],
            "fecha": ultima_sesion["fecha"][:10],
            "año": ultima_sesion["fecha"][:4],
            "diferencia_vs_pb": dif_ultima_str,
            "diferencia_s": dif_ultima_s
        },
        "promedio": {
            "tiempo_formateado": formatear_segundos(tiempo_medio_s),
            "ritmo_minkm": ritmo_medio_str
        }
    }

def obtener_datos_frente_a_frente(lugar_o_carrera: str, api_key: str = "", usuario_id: int = 1) -> Optional[Dict[str, Any]]:
    """Recupera y estructura las ediciones históricas de una ubicación o carrera para el módulo Frente a Frente."""
    termino = f"%{lugar_o_carrera.lower().strip()}%"
    query = """
    SELECT id, fecha, titulo, distancia_km, tiempo_total_s, tiempo_formateado, ritmo_medio_minkm, fc_media, ubicacion
    FROM entrenamientos
    WHERE (LOWER(titulo) LIKE ? OR LOWER(ubicacion) LIKE ?) AND usuario_id = ?
    ORDER BY fecha DESC
    """
    filas = database.ejecutar_consulta_sql(query, (termino, termino, usuario_id))
    if not filas or "error" in filas[0]:
        return None
        
    # Filtrar micro-calentamientos (< 2.5 km si hay otra sesión el mismo día)
    fechas_map = {}
    for f in filas:
        dia = f["fecha"][:10]
        fechas_map.setdefault(dia, []).append(f)
        
    carreras = []
    for f in filas:
        dia = f["fecha"][:10]
        if f["distancia_km"] < 2.5 and len(fechas_map[dia]) > 1:
            f["es_calentamiento"] = True
        else:
            f["es_calentamiento"] = False
            carreras.append(f)
            
    if not carreras:
        carreras = filas
        
    # Agrupar por distancias
    categorias = {}
    for c in carreras:
        d = c["distancia_km"]
        if 19.5 <= d <= 23.0:
            cat = "Media Maratón (21.1 km)"
        elif 40.0 <= d <= 45.0:
            cat = "Maratón (42.2 km)"
        elif 9.0 <= d <= 12.0:
            cat = "10K / 10-12 km"
        elif 7.0 <= d < 9.0:
            cat = "Carrera Corta (8 km)"
        elif 4.5 <= d < 7.0:
            cat = "5K (~5 km)"
        else:
            cat = f"Prueba {d:.1f} km"
        categorias.setdefault(cat, []).append(c)
        
    # Elegir categoría principal (la más frecuente o de mayor distancia)
    cat_principal = max(categorias.keys(), key=lambda k: (len(categorias[k]), max(x["distancia_km"] for x in categorias[k])))
    datos_cat_principal = generar_datos_categoria(categorias[cat_principal])
    
    # Análisis táctico del entrenador (Gemini o fallback deportivo experto)
    analisis_coach = generar_analisis_tactico_coach(
        lugar_o_carrera,
        cat_principal,
        datos_cat_principal["ediciones_cron"],
        datos_cat_principal["pb"],
        datos_cat_principal["ultima"],
        api_key=api_key
    )
    
    return {
        "lugar": lugar_o_carrera.capitalize(),
        "total_sesiones": len(filas),
        "todas_filas": filas,
        "carreras_limpias": carreras,
        "categorias": categorias,
        "categoria_seleccionada": cat_principal,
        "num_ediciones": datos_cat_principal["num_ediciones"],
        "ediciones": datos_cat_principal["ediciones"],
        "ediciones_cron": datos_cat_principal["ediciones_cron"],
        "pb": datos_cat_principal["pb"],
        "ultima": datos_cat_principal["ultima"],
        "promedio": datos_cat_principal["promedio"],
        "analisis_coach": analisis_coach
    }

def generar_analisis_tactico_coach(lugar: str, cat_nombre: str, ediciones_cron: List[Dict[str, Any]], pb: Dict[str, Any], ultima: Dict[str, Any], api_key: str = "") -> str:
    """Genera un análisis táctico profesional de atletismo con voz del Team Ardil."""
    if api_key and len(ediciones_cron) >= 2:
        try:
            prompt_coach = f"""Eres el entrenador de atletismo de Salva Andreo en el Team Ardil.
Analiza sus participaciones en {lugar} ({cat_nombre}):
- Récord Personal (PB): {pb['fecha']} con tiempo {pb['tiempo_formateado']} a {pb['ritmo_minkm']} min/km.
- Última edición: {ultima['fecha']} con tiempo {ultima['tiempo_formateado']} a {ultima['ritmo_minkm']} min/km (diferencia: {ultima['diferencia_vs_pb']}).
- Total de ediciones disputadas: {len(ediciones_cron)}.
Ediciones: {json.dumps([{'año': e['año'], 'tiempo': e['tiempo_formateado'], 'ritmo': e['ritmo_minkm']} for e in ediciones_cron])}

Redacta un análisis técnico breve (máximo 4 líneas), motivador, deportivo y profesional con el tono característico del Team Ardil."""
            res = llamar_gemini_api(prompt_coach, api_key)
            if res and len(res.strip()) > 30:
                return res.strip()
        except Exception:
            pass

    # Fallback deportivo experto de atletismo Team Ardil
    if len(ediciones_cron) < 2:
        return (f"Has completado 1 edición oficial de {cat_nombre} en {lugar.capitalize()} "
                f"marcando {pb['tiempo_formateado']} ({pb['ritmo_minkm']} min/km). ¡Es tu referencia base a batir en futuras ediciones!")
                
    if ultima["año"] == pb["año"]:
        return (f"¡Circuito talismán! En {lugar.capitalize()} conseguiste tu plusmarca personal en {pb['año']} "
                f"parando el crono en {pb['tiempo_formateado']} a un ritmo demoledor de {pb['ritmo_minkm']} min/km. "
                f"Mantener ese ritmo demuestra una eficiencia aeróbica de primer nivel.")
    else:
        return (f"{lugar.capitalize()} es un escenario clave en tu historial deportivo con {len(ediciones_cron)} ediciones registradas. "
                f"Tu plusmarca histórica la fijaste en {pb['año']} con un estratosférico {pb['tiempo_formateado']} ({pb['ritmo_minkm']} min/km). "
                f"En la última cita ({ultima['año']}: {ultima['tiempo_formateado']}) demostraste una gran consistencia a {ultima['ritmo_minkm']} min/km, "
                f"a {ultima['diferencia_vs_pb']} de tu récord. Con un ciclo específico de ritmo de competición, ese registro volverá a caer.")

def generar_grafico_frente_a_frente(ediciones_cron: List[Dict[str, Any]], lugar: str, cat_nombre: str) -> go.Figure:
    """Crea un gráfico de barras interactivo con Plotly comparando las ediciones."""
    años = [f"Edición {e['año']}<br>({e['fecha']})" for e in ediciones_cron]
    tiempos_min = [round(e["tiempo_s"] / 60.0, 2) for e in ediciones_cron]
    textos = [f"{e['tiempo_formateado']}<br>({e['ritmo_minkm']} min/km)" + ("<br>🥇 <b>PB</b>" if e["es_pb"] else f"<br>{e['diferencia_vs_pb']}") for e in ediciones_cron]
    
    # Dorado (#F59E0B) para la PB, Azul (#0078D4) para el resto
    colores = ["#F59E0B" if e["es_pb"] else "#0078D4" for e in ediciones_cron]
    bordes = ["#FCD34D" if e["es_pb"] else "#60A5FA" for e in ediciones_cron]
    
    fig = go.Figure()
    
    fig.add_trace(go.Bar(
        x=años,
        y=tiempos_min,
        text=textos,
        textposition="outside",
        textfont=dict(color="white", size=12),
        marker=dict(
            color=colores,
            line=dict(color=bordes, width=2)
        ),
        hovertemplate="<b>%{x}</b><br>Tiempo: %{y:.1f} min<br>%{text}<extra></extra>"
    ))
    
    # Línea horizontal de referencia para la PB
    min_tiempo_min = min(tiempos_min)
    pb_item = min(ediciones_cron, key=lambda x: x["tiempo_s"])
    fig.add_hline(
        y=min_tiempo_min,
        line_dash="dot",
        line_color="#F59E0B",
        annotation_text=f"Récord PB ({pb_item['tiempo_formateado']})",
        annotation_position="bottom right",
        annotation_font=dict(color="#F59E0B", size=11)
    )
    
    y_max = max(tiempos_min) * 1.18
    y_min = max(0, min(tiempos_min) * 0.82)
    
    fig.update_layout(
        title=dict(
            text=f"⚔️ <b>Frente a Frente: {cat_nombre} en {lugar.capitalize()}</b>",
            font=dict(size=15, color="#FFFFFF")
        ),
        paper_bgcolor="rgba(15, 23, 42, 0.4)",
        plot_bgcolor="rgba(15, 23, 42, 0.4)",
        font=dict(color="#94A3B8"),
        margin=dict(l=15, r=15, t=50, b=40),
        yaxis=dict(
            title="Tiempo (minutos)",
            range=[y_min, y_max],
            gridcolor="rgba(255, 255, 255, 0.08)",
            zeroline=False
        ),
        xaxis=dict(
            gridcolor="rgba(255, 255, 255, 0.05)"
        ),
        showlegend=False
    )
    
    return fig

# Esquema de la base de datos para guiar a la IA
ESQUEMA_BD = """
BASE DE DATOS SQLITE (HISTORIAL DE ENTRENAMIENTOS DE ATLETISMO):

Tabla 1: 'entrenamientos' (Resumen de cada sesión)
- id: INTEGER PRIMARY KEY
- usuario_id: INTEGER (ID del atleta propietario, ej: 1 para Salva)
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

def procesar_consulta_series(pregunta: str, usuario_id: int = 1) -> Optional[str]:
    """
    Procesa consultas específicas sobre series de cualquier distancia (400m, 1000m, etc.)
    detectando la cantidad de sesiones solicitadas ('3 últimas', 'últimas 5', 'la última', etc.),
    generando una tabla comparativa entre sesiones, análisis de progresión del entrenador
    y el desglose detallado de repeticiones de cada día.
    """
    pregunta_lower = pregunta.lower().strip()
    match_serie = re.search(r'series?\s+(?:de\s+)?(\d+)\s*(?:m|metros|mtrs)?', pregunta_lower)
    if not match_serie:
        match_serie = re.search(r'(\d+)\s*(?:m|metros|mtrs)\s+series?', pregunta_lower)
    if not match_serie:
        m_alt = re.search(r'(?:veces|sesion(?:es)?|días)?\s*(?:de\s+)?(\d{3,4})\s*(?:m|metros|mtrs)', pregunta_lower)
        if m_alt and any(k in pregunta_lower for k in ["serie", "repeticion", "pista", "interval"]):
            match_serie = m_alt
        else:
            return None

    distancia = int(match_serie.group(1))

    # Detectar cantidad N solicitada (ej. "3 últimas", "últimas 5", "dos últimas")
    n_sesiones = 3
    palabras_num = {
        'una': 1, 'un': 1, 'uno': 1, 'primera': 1,
        'dos': 2, 'segunda': 2,
        'tres': 3, 'tercera': 3,
        'cuatro': 4, 'cuarta': 4,
        'cinco': 5, 'quinta': 5,
        'seis': 6, 'ocho': 8, 'diez': 10
    }
    m_num = re.search(r'(?:las|los)?\s*(\d+)\s*últim', pregunta_lower)
    if m_num:
        n_sesiones = int(m_num.group(1))
    else:
        for p, val in palabras_num.items():
            if f"{p} últim" in pregunta_lower:
                n_sesiones = val
                break
    if "la última vez" in pregunta_lower or "el último día" in pregunta_lower or "última sesión" in pregunta_lower:
        n_sesiones = 1

    # Ventana de distancia y filtro de ritmo máximo para descartar trotes/recuperaciones
    min_m = distancia * 0.88
    max_m = distancia * 1.12

    tiempo_max_serie = {
        200: 65.0,
        300: 90.0,
        400: 115.0,
        500: 145.0,
        800: 230.0,
        1000: 290.0,
        1500: 440.0,
        2000: 590.0,
        3000: 900.0,
        4000: 1220.0,
        5000: 1550.0
    }.get(distancia, (distancia / 1000.0) * 310.0)

    query = """
    SELECT e.id as entreno_id, e.fecha, e.titulo, e.ubicacion,
           s.lap_numero, s.distancia_m, s.tiempo_s, s.tiempo_formateado,
           s.ritmo_minkm, s.fc_media, s.fc_max
    FROM series_laps s
    JOIN entrenamientos e ON s.entrenamiento_id = e.id
    WHERE s.distancia_m BETWEEN ? AND ?
      AND s.tiempo_s <= ?
      AND e.usuario_id = ?
    ORDER BY e.fecha DESC, s.lap_numero ASC
    """
    filas = database.ejecutar_consulta_sql(query, (min_m, max_m, tiempo_max_serie, usuario_id))
    if not filas or "error" in filas[0]:
        query_soft = """
        SELECT e.id as entreno_id, e.fecha, e.titulo, e.ubicacion,
               s.lap_numero, s.distancia_m, s.tiempo_s, s.tiempo_formateado,
               s.ritmo_minkm, s.fc_media, s.fc_max
        FROM series_laps s
        JOIN entrenamientos e ON s.entrenamiento_id = e.id
        WHERE s.distancia_m BETWEEN ? AND ? AND e.usuario_id = ?
        ORDER BY e.fecha DESC, s.lap_numero ASC
        """
        filas = database.ejecutar_consulta_sql(query_soft, (min_m, max_m, usuario_id))
        if not filas or "error" in filas[0]:
            return f"No he encontrado series registradas de aproximadamente **{distancia}m** en tu historial."

    # Agrupar por entrenamiento
    sesiones_dict = OrderedDict()
    for f in filas:
        eid = f.get("entreno_id")
        if not eid: continue
        if eid not in sesiones_dict:
            sesiones_dict[eid] = {
                "id": eid,
                "fecha": f.get("fecha", ""),
                "titulo": f.get("titulo", "Entrenamiento"),
                "ubicacion": f.get("ubicacion") or "",
                "laps": []
            }
        sesiones_dict[eid]["laps"].append(f)

    todas_sesiones = list(sesiones_dict.values())
    if not todas_sesiones:
        return f"No he encontrado series registradas de **{distancia}m** en tu historial."

    # Priorizar sesiones de series reales (>= 3 series, luego >= 2)
    sesiones_reales = [s for s in todas_sesiones if len(s["laps"]) >= 3]
    if len(sesiones_reales) < n_sesiones:
        sesiones_reales = [s for s in todas_sesiones if len(s["laps"]) >= 2]
    if len(sesiones_reales) < n_sesiones:
        sesiones_reales = todas_sesiones

    seleccionadas = sesiones_reales[:n_sesiones]

    # Calcular estadísticas de cada sesión
    for s in seleccionadas:
        laps = s["laps"]
        s["mejor_lap"] = min(laps, key=lambda x: x["tiempo_s"])
        s["peor_lap"] = max(laps, key=lambda x: x["tiempo_s"])
        t_media = sum(l["tiempo_s"] for l in laps) / len(laps)
        s["tiempo_medio_s"] = t_media
        s["tiempo_medio_fmt"] = formatear_segundos(int(round(t_media)))
        s["ritmo_medio_fmt"] = calcular_ritmo_str(t_media, distancia / 1000.0)
        fcs = [l["fc_media"] for l in laps if l.get("fc_media")]
        s["fc_media_val"] = int(round(sum(fcs) / len(fcs))) if fcs else None

    # Récord histórico global en esa distancia
    mejor_global = min(filas, key=lambda x: x["tiempo_s"])

    texto = f"### ⚡ Historial de Series de {distancia}m ({len(seleccionadas)} {'última sesión' if len(seleccionadas) == 1 else 'últimas sesiones'})\n\n"

    if len(seleccionadas) > 1:
        texto += f"He localizado las **{len(seleccionadas)} últimas sesiones** en las que hiciste series de {distancia} metros:\n\n"
        texto += "| # | Fecha | Título / Lugar | Repeticiones | Mejor Serie | Ritmo Mejor | Media de Series | FC Media |\n"
        texto += "|---|---|---|---|---|---|---|---|\n"
        for idx, s in enumerate(seleccionadas, 1):
            fc_txt = f"{s['fc_media_val']} ppm" if s['fc_media_val'] else "- ppm"
            texto += f"| {idx} | **{s['fecha'][:10]}** | {s['titulo']} | **{len(s['laps'])}x{distancia}m** | **{s['mejor_lap']['tiempo_formateado']}** (Lap #{s['mejor_lap']['lap_numero']}) | {s['mejor_lap']['ritmo_minkm']} min/km | **{s['tiempo_medio_fmt']}** ({s['ritmo_medio_fmt']} min/km) | {fc_txt} |\n"
        texto += "\n"

        # Comparativa y análisis técnico
        s_reciente = seleccionadas[0]
        s_anterior = seleccionadas[1]
        diff_media = s_reciente["tiempo_medio_s"] - s_anterior["tiempo_medio_s"]
        if diff_media < -1.0:
            comentario = f"📈 **Evolución positiva:** En tu última sesión ({s_reciente['fecha'][:10]}) bajaste la media en **{abs(diff_media):.1f}s** respecto a la anterior ({s_anterior['fecha'][:10]}). ¡Gran progresión de velocidad!"
        elif abs(diff_media) <= 1.0:
            comentario = f"🎯 **Consistencia excelente:** Mantuviste un ritmo medio casi idéntico y muy regular entre la sesión del {s_reciente['fecha'][:10]} y la del {s_anterior['fecha'][:10]}."
        else:
            comentario = f"ℹ️ En la sesión del {s_reciente['fecha'][:10]} la media fue de {s_reciente['tiempo_medio_fmt']}, con una mejor repetición rápida de {s_reciente['mejor_lap']['tiempo_formateado']}."
        texto += f"{comentario}\n\n"
    else:
        s0 = seleccionadas[0]
        fc_txt = f" con **{s0['fc_media_val']} ppm** medias" if s0['fc_media_val'] else ""
        texto += f"**Última vez realizada:** {s0['fecha']} (*{s0['titulo']}*)\n"
        texto += f"- **Total de series completadas:** **{len(s0['laps'])}** repeticiones de {distancia}m\n"
        texto += f"- **Serie más rápida:** Lap #{s0['mejor_lap']['lap_numero']} en **{s0['mejor_lap']['tiempo_formateado']}** (ritmo {s0['mejor_lap']['ritmo_minkm']} min/km){fc_txt}\n"
        texto += f"- **Media de las series:** **{s0['tiempo_medio_fmt']}** (ritmo medio {s0['ritmo_medio_fmt']} min/km)\n\n"

    if mejor_global['tiempo_s'] < seleccionadas[0]['mejor_lap']['tiempo_s']:
        fc_g = f" ({mejor_global['fc_media']} ppm)" if mejor_global.get('fc_media') else ""
        texto += f"🔥 **Récord histórico de {distancia}m:** El **{mejor_global['fecha'][:10]}** volaste en **{mejor_global['tiempo_formateado']}** ({mejor_global['ritmo_minkm']} min/km){fc_g}.\n\n"

    # Tablas de detalle por sesión
    for idx, s in enumerate(seleccionadas, 1):
        texto += f"#### 📋 Sesión {idx}: {s['fecha'][:10]} · {s['titulo']} ({len(s['laps'])}x{distancia}m)\n"
        texto += "| # Serie | Distancia | Tiempo | Ritmo | FC Media | FC Máx |\n"
        texto += "|---|---|---|---|---|---|\n"
        for l in s["laps"]:
            fc_m = f"{l['fc_media']} ppm" if l.get("fc_media") else "- ppm"
            fc_x = f"{l['fc_max']} ppm" if l.get("fc_max") else "- ppm"
            texto += f"| #{l['lap_numero']} | {int(l['distancia_m'])}m | {l['tiempo_formateado']} | {l['ritmo_minkm']} min/km | {fc_m} | {fc_x} |\n"
        texto += "\n"

    return texto

def responder_con_text_to_sql(pregunta: str, api_key: str, usuario_id: int = 1) -> Optional[str]:
    """Motor inteligente Text-to-SQL con Gemini para preguntas deportivas generales."""
    try:
        prompt_sql = f"""Eres un experto desarrollador de bases de datos SQLite para deportes y running.
{ESQUEMA_BD}

Pregunta del atleta: "{pregunta}"
ID del atleta actual en consulta: {usuario_id}

INSTRUCCIONES OBLIGATORIAS:
- Genera ÚNICAMENTE una consulta SQL (SELECT ...) válida para SQLite que responda exactamente a la pregunta.
- Filtra siempre por el atleta actual: `e.usuario_id = {usuario_id}` en la tabla entrenamientos (o `usuario_id = {usuario_id}`).
- Para series de 400m usa: `s.distancia_m BETWEEN 380 AND 420`.
- Para series de 1000m usa: `s.distancia_m BETWEEN 950 AND 1050`.
- Para series de 2000m usa: `s.distancia_m BETWEEN 1900 AND 2100`.
- Si preguntan por la serie más rápida, ordena por `tiempo_s ASC LIMIT 1`.
- Si preguntan por la última vez, ordena por `e.fecha DESC LIMIT 1`.
- Si preguntan por totales o medias mensuales: usa `strftime('%Y-%m', fecha)`.
- Si necesitas datos de la sesión haz JOIN entre `series_laps s` y `entrenamientos e ON s.entrenamiento_id = e.id`.
- Devuelve SOLO el código SQL sin explicaciones, sin texto antes ni después, sin etiquetas ```sql."""

        sql_generado = llamar_gemini_api(prompt_sql, api_key)
        sql_limpio = re.sub(r"```(?:sql)?", "", sql_generado).strip()
        
        if not sql_limpio.upper().startswith("SELECT"):
            return None

        filas = database.ejecutar_consulta_sql(sql_limpio)
        if filas and "error" in filas[0]:
            return None

        prompt_respuesta = f"""Eres un entrenador deportivo de atletismo experto, analítico y motivador (Team Ardil).
El atleta te ha hecho esta pregunta sobre sus entrenamientos:
"{pregunta}"

Datos reales obtenidos de su base de datos Garmin:
{json.dumps(filas, ensure_ascii=False)}

INSTRUCCIONES DE RESPUESTA:
1. Responde en español de forma directa, clara y amena.
2. Destaca los números clave en negrita (fechas, ritmos min/km, tiempos, pulsaciones, kilómetros).
3. Si hay varias series o varias sesiones, preséntalas en una tabla Markdown limpia y ordenada.
4. Añade un breve comentario técnico o motivador sobre su rendimiento.
5. No inventes ningún dato que no esté en la información devuelta."""

        respuesta_ia = llamar_gemini_api(prompt_respuesta, api_key)
        if respuesta_ia:
            return respuesta_ia
    except Exception as e:
        print(f"[Text-to-SQL Exception] {e}")
        return None

    return None

def responder_consulta_entrenamientos(pregunta: str, usuario_id: int = 1) -> Any:
    """
    Función principal de consulta del Entrenador IA:
    1. Si la pregunta menciona una ubicación o carrera (ej. 'Orihuela', 'Santa Pola', etc.),
       construye la tabla oficial de participaciones y adjunta los datos estructurados para
       el botón y módulo 'FRENTE A FRENTE'.
    2. Si hay clave API de Gemini configurada, ejecuta el motor Text-to-SQL.
    3. Si no hay conexión o API, recurre al motor de reglas locales como respaldo seguro.
    """
    api_key = obtener_gemini_api_key()
    pregunta_lower = pregunta.lower().strip()

    # ==================== CASO 1: CARRERA O UBICACIÓN (FRENTE A FRENTE) ====================
    lugar = detectar_ubicacion_en_pregunta(pregunta)
    if lugar:
        faf_datos = obtener_datos_frente_a_frente(lugar, api_key=api_key, usuario_id=usuario_id)
        if faf_datos and faf_datos.get("total_sesiones", 0) > 0:
            filas = faf_datos["todas_filas"]
            respuesta_md = f"### 🏅 Historial encontrado para '{lugar.capitalize()}':\n\n"
            respuesta_md += f"Se han registrado **{len(filas)}** participaciones/sesiones:\n\n"
            respuesta_md += "| Fecha | Título / Evento | Distancia | Tiempo | Ritmo Medio | FC Media |\n"
            respuesta_md += "|---|---|---|---|---|---|\n"
            
            for f in filas:
                titulo_display = f["titulo"]
                if f.get("es_calentamiento"):
                    titulo_display += " *(Calentamiento)*"
                elif faf_datos.get("pb") and f["fecha"][:10] == faf_datos["pb"]["fecha"]:
                    titulo_display += " *(PB 🥇)*"
                    
                fc_str = f"{f['fc_media']} ppm" if f.get("fc_media") else "- ppm"
                respuesta_md += f"| {f['fecha'][:10]} | {titulo_display} | {f['distancia_km']} km | {f['tiempo_formateado']} | {f['ritmo_medio_minkm']} min/km | {fc_str} |\n"
                
            return {
                "texto": respuesta_md,
                "frente_a_frente": faf_datos
            }

    # ==================== CASO 2: ANÁLISIS DE SERIES MULTI-SESIÓN ====================
    resp_series = procesar_consulta_series(pregunta, usuario_id=usuario_id)
    if resp_series:
        return resp_series

    # ==================== CASO 3: TEXT-TO-SQL CON GEMINI ====================
    if api_key:
        respuesta_motor = responder_con_text_to_sql(pregunta, api_key, usuario_id=usuario_id)
        if respuesta_motor:
            return respuesta_motor

    # ==================== CASO 4: RESUMEN GENERAL (RESPALDO) ====================
    stats = database.obtener_resumen_estadisticas(usuario_id=usuario_id)
    return (f"📊 **Resumen de tu historial en SportTracks:**\n\n"
            f"- **Entrenamientos totales:** {stats['total_entrenos']}\n"
            f"- **Kilómetros acumulados:** {stats['total_km']} km\n"
            f"- **Series e intervalos guardados:** {stats['total_series']}\n\n"
            f"💡 *Puedes preguntarme lo que quieras: 'busca las 3 últimas veces que hice series de 400m', comparativas en Orihuela o Santa Pola, tiradas largas o medias mensuales.*")
