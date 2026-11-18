import os
import json
import urllib.request
import urllib.error
import urllib.parse
from datetime import datetime
from typing import List, Dict, Any, Tuple, Optional, Callable

import database
from garmin_sync import segundos_a_formato, calcular_ritmo

STRAVA_TOKENS_DIR = os.path.join(os.path.dirname(__file__), ".strava_tokens")
STRAVA_TOKENS_FILE = os.path.join(STRAVA_TOKENS_DIR, "strava_tokens.json")

def obtener_tokens_strava() -> Optional[Dict[str, Any]]:
    """Devuelve los datos de conexión de Strava si existen."""
    if os.path.isfile(STRAVA_TOKENS_FILE):
        try:
            with open(STRAVA_TOKENS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return None

def guardar_tokens_strava(data: Dict[str, Any]):
    """Guarda los tokens de Strava en disco."""
    os.makedirs(STRAVA_TOKENS_DIR, exist_ok=True)
    with open(STRAVA_TOKENS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

def cerrar_sesion_strava():
    """Elimina la conexión guardada con Strava."""
    if os.path.isfile(STRAVA_TOKENS_FILE):
        try:
            os.remove(STRAVA_TOKENS_FILE)
        except Exception:
            pass

def refrescar_token_strava(client_id: str, client_secret: str, refresh_token: str) -> Tuple[bool, str, Dict[str, Any]]:
    """Refresca el token OAuth de Strava expirado."""
    url = "https://www.strava.com/oauth/token"
    payload = urllib.parse.urlencode({
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token"
    }).encode("utf-8")

    try:
        req = urllib.request.Request(url, data=payload, headers={"User-Agent": "SportTracks-AI"}, method="POST")
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        
        token_info = {
            "access_token": data.get("access_token"),
            "refresh_token": data.get("refresh_token"),
            "expires_at": data.get("expires_at"),
            "client_id": client_id,
            "client_secret": client_secret,
            "athlete": data.get("athlete", {}),
            "saved_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        guardar_tokens_strava(token_info)
        return True, "Token de Strava refrescado con éxito.", token_info
    except Exception as e:
        return False, f"Error al refrescar token de Strava: {e}", {}

def conectar_strava_token_directo(access_token: str, athlete_name: str = "Atleta Strava") -> Tuple[bool, str, Dict[str, Any]]:
    """Conecta con Strava utilizando un Token de Acceso personal."""
    access_token = access_token.strip()
    if not access_token:
        return False, "Debes proporcionar un Access Token de Strava.", {}

    # Verificar token consultando el perfil del atleta
    url = "https://www.strava.com/api/v3/athlete"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "User-Agent": "SportTracks-AI"
    }
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as resp:
            athlete_data = json.loads(resp.read().decode("utf-8"))
        
        nombre = f"{athlete_data.get('firstname', '')} {athlete_data.get('lastname', '')}".strip() or athlete_name
        token_info = {
            "access_token": access_token,
            "athlete_name": nombre,
            "athlete_id": athlete_data.get("id"),
            "athlete": athlete_data,
            "saved_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        guardar_tokens_strava(token_info)
        return True, f"¡Conectado con éxito a Strava! Atleta: {nombre}", token_info
    except urllib.error.HTTPError as e:
        return False, f"Token no válido o sin permisos (HTTP {e.code}).", {}
    except Exception as e:
        return False, f"Error al conectar con Strava: {e}", {}

def parsear_actividad_strava(act: Dict[str, Any], laps: List[Dict[str, Any]] = None) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """Convierte una actividad de Strava al formato estándar de SportTracks."""
    act_id = str(act.get("id", ""))
    fit_hash = f"strava_{act_id}"

    # Fecha ISO a YYYY-MM-DD HH:MM:SS
    start_date_raw = act.get("start_date_local") or act.get("start_date") or ""
    try:
        fecha_str = start_date_raw.replace("T", " ").replace("Z", "")[:19]
    except Exception:
        fecha_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    titulo = act.get("name") or "Carrera Strava"
    distancia_m = float(act.get("distance", 0.0))
    tiempo_total_s = int(act.get("moving_time") or act.get("elapsed_time") or 0)
    distancia_km = round(distancia_m / 1000.0, 2)
    tiempo_formateado = segundos_a_formato(tiempo_total_s)
    ritmo_medio = calcular_ritmo(distancia_m, tiempo_total_s)

    fc_media = act.get("average_heartrate")
    fc_max = act.get("max_heartrate")
    calorias = act.get("calories")

    datos_entreno = {
        "fecha": fecha_str,
        "titulo": titulo,
        "deporte": "running",
        "distancia_km": distancia_km,
        "tiempo_total_s": tiempo_total_s,
        "tiempo_formateado": tiempo_formateado,
        "ritmo_medio_minkm": ritmo_medio,
        "fc_media": int(fc_media) if fc_media else None,
        "fc_max": int(fc_max) if fc_max else None,
        "cadencia_media": int(act.get("average_cadence") * 2) if act.get("average_cadence") else None,
        "calorias": int(calorias) if calorias else None,
        "ubicacion": act.get("location_city") or "Strava",
        "notas_entrenador": act.get("description") or "",
        "fit_hash": fit_hash
    }

    laps_resultado = []
    if laps:
        for idx, lap in enumerate(laps):
            lap_dist = float(lap.get("distance", 0.0))
            lap_time = float(lap.get("moving_time") or lap.get("elapsed_time") or 0.0)
            laps_resultado.append({
                "lap_numero": idx + 1,
                "distancia_m": lap_dist,
                "tiempo_s": lap_time,
                "tiempo_formateado": segundos_a_formato(lap_time),
                "ritmo_minkm": calcular_ritmo(lap_dist, lap_time),
                "fc_media": int(lap.get("average_heartrate")) if lap.get("average_heartrate") else None,
                "fc_max": int(lap.get("max_heartrate")) if lap.get("max_heartrate") else None,
                "cadencia": int(lap.get("average_cadence") * 2) if lap.get("average_cadence") else 0,
                "tipo_intervalo": "serie"
            })
    else:
        laps_resultado.append({
            "lap_numero": 1,
            "distancia_m": distancia_m,
            "tiempo_s": tiempo_total_s,
            "tiempo_formateado": tiempo_formateado,
            "ritmo_minkm": ritmo_medio,
            "fc_media": datos_entreno["fc_media"],
            "fc_max": datos_entreno["fc_max"],
            "cadencia": datos_entreno["cadencia_media"] or 0,
            "tipo_intervalo": "serie"
        })

    return datos_entreno, laps_resultado

def sincronizar_actividades_strava(progreso_callback: Optional[Callable[[int, int, str], None]] = None, max_actividades: int = 50, usuario_id: int = 1) -> Dict[str, Any]:
    """Descarga e importa actividades desde la API de Strava para un atleta específico."""
    token_info = obtener_tokens_strava()
    if not token_info or not token_info.get("access_token"):
        return {"status": "error", "mensaje": "No hay ningún token o sesión activa de Strava.", "nuevos": 0}

    access_token = token_info["access_token"]
    headers = {
        "Authorization": f"Bearer {access_token}",
        "User-Agent": "SportTracks-AI"
    }

    url_actividades = f"https://www.strava.com/api/v3/athlete/activities?per_page={max_actividades}"

    try:
        req = urllib.request.Request(url_actividades, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as resp:
            actividades = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        # Comprobar si el token expiró y tenemos refresh_token
        if e.code == 401 and token_info.get("refresh_token") and token_info.get("client_id"):
            exito, _, new_info = refrescar_token_strava(token_info["client_id"], token_info["client_secret"], token_info["refresh_token"])
            if exito:
                return sincronizar_actividades_strava(progreso_callback, max_actividades, usuario_id=usuario_id)
        return {"status": "error", "mensaje": f"Error de autenticación Strava (HTTP {e.code}).", "nuevos": 0}
    except Exception as e:
        return {"status": "error", "mensaje": f"Error de conexión con Strava: {e}", "nuevos": 0}

    if not actividades:
        return {"status": "ok", "mensaje": "No se encontraron actividades en tu cuenta de Strava.", "nuevos": 0}

    total = len(actividades)
    nuevos = 0
    ya_existentes = 0

    conn = database.get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT fit_hash FROM entrenamientos WHERE fit_hash IS NOT NULL")
    hashes_existentes = set(r[0] for r in cursor.fetchall())
    conn.close()

    for idx, act in enumerate(actividades):
        act_id = str(act.get("id"))
        fit_hash = f"strava_u{usuario_id}_{act_id}"
        nombre = act.get("name", "Actividad")

        if progreso_callback:
            progreso_callback(idx + 1, total, nombre)

        if fit_hash in hashes_existentes:
            ya_existentes += 1
            continue

        # Consultar laps si es carrera
        laps = []
        try:
            url_laps = f"https://www.strava.com/api/v3/activities/{act_id}/laps"
            req_laps = urllib.request.Request(url_laps, headers=headers)
            with urllib.request.urlopen(req_laps, timeout=8) as r_laps:
                laps = json.loads(r_laps.read().decode("utf-8"))
        except Exception:
            pass

        datos_entreno, laps_entreno = parsear_actividad_strava(act, laps)
        nid = database.guardar_entrenamiento(datos_entreno, laps_entreno, usuario_id=usuario_id)
        if nid:
            nuevos += 1
            hashes_existentes.add(fit_hash)
            # Guardar splits métricos si vienen disponibles en Strava
            splits_metric = act.get("splits_metric")
            if splits_metric:
                try:
                    splits_guardar = []
                    for s in splits_metric:
                        s_dist = float(s.get("distance", 1000.0))
                        s_dur = float(s.get("moving_time") or s.get("elapsed_time") or 0.0)
                        s_num = int(s.get("split", 1))
                        pace_str = calcular_ritmo(s_dist, s_dur)
                        desn = float(s.get("elevation_difference", 0.0))
                        splits_guardar.append({
                            "km_numero": s_num,
                            "etiqueta": f"Km {s_num}" if s_dist >= 800 else f"{s_dist/1000.0:.1f} km",
                            "distancia_m": s_dist,
                            "tiempo_s": s_dur,
                            "tiempo_formateado": segundos_a_formato(s_dur),
                            "ritmo_minkm": pace_str,
                            "desnivel_m": desn,
                            "cadencia": int(s.get("average_cadence") * 2) if s.get("average_cadence") else None,
                            "fc_media": int(s.get("average_heartrate")) if s.get("average_heartrate") else None
                        })
                    if splits_guardar:
                        database.guardar_splits_km(nid, splits_guardar)
                except Exception:
                    pass

    token_info["last_sync"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    guardar_tokens_strava(token_info)

    return {
        "status": "ok",
        "mensaje": f"Sincronización Strava completada: {nuevos} nuevos entrenamientos ({ya_existentes} ya existían).",
        "nuevos": nuevos,
        "existentes": ya_existentes,
        "total": total
    }
