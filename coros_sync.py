import os
import json
import hashlib
import urllib.request
import urllib.error
import urllib.parse
from datetime import datetime
from typing import List, Dict, Any, Tuple, Optional, Callable

import database
from garmin_sync import segundos_a_formato, calcular_ritmo

COROS_TOKENS_DIR = os.path.join(os.path.dirname(__file__), ".coros_tokens")
COROS_TOKENS_FILE = os.path.join(COROS_TOKENS_DIR, "coros_tokens.json")

REGIONS = {
    "eu": {
        "name": "Europa (trainingeu.coros.com)",
        "api_base": "https://teameuapi.coros.com"
    },
    "global": {
        "name": "Global / América (training.coros.com)",
        "api_base": "https://teamapi.coros.com"
    }
}

def obtener_tokens_guardados() -> Optional[Dict[str, Any]]:
    """Devuelve los datos de sesión de COROS si existen."""
    if os.path.isfile(COROS_TOKENS_FILE):
        try:
            with open(COROS_TOKENS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return None

def guardar_tokens_coros(data: Dict[str, Any]):
    """Guarda los tokens de sesión de COROS en disco."""
    os.makedirs(COROS_TOKENS_DIR, exist_ok=True)
    with open(COROS_TOKENS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

def cerrar_sesion_coros():
    """Elimina la sesión guardada de COROS."""
    if os.path.isfile(COROS_TOKENS_FILE):
        try:
            os.remove(COROS_TOKENS_FILE)
        except Exception:
            pass

def iniciar_sesion_coros(account: str, password: str, region_key: str = "eu") -> Tuple[bool, str, Dict[str, Any]]:
    """
    Inicia sesión en COROS Training Hub utilizando el endpoint de autenticación.
    Hashea la contraseña con MD5 como requiere la API de COROS.
    """
    account = account.strip()
    if not account or not password:
        return False, "Debes introducir email y contraseña.", {}

    pwd_hash = hashlib.md5(password.encode("utf-8")).hexdigest()
    reg_info = REGIONS.get(region_key, REGIONS["eu"])
    api_base = reg_info["api_base"]
    login_url = f"{api_base}/account/login"

    headers = {
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    payload = json.dumps({
        "account": account,
        "accountType": 2,
        "pwd": pwd_hash
    }).encode("utf-8")

    try:
        req = urllib.request.Request(login_url, data=payload, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=12) as response:
            res_data = json.loads(response.read().decode("utf-8"))

        if str(res_data.get("result")) in ("0000", "0") or ("data" in res_data and "accessToken" in res_data["data"]):
            token_data = res_data["data"]
            access_token = token_data.get("accessToken")
            user_id = token_data.get("userId")
            nick = token_data.get("nickname") or token_data.get("nickName") or account.split("@")[0]

            sesion_info = {
                "account": account,
                "accessToken": access_token,
                "userId": user_id,
                "nickname": nick,
                "region": region_key,
                "api_base": api_base,
                "saved_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            guardar_tokens_coros(sesion_info)
            return True, f"¡Sesión iniciada con éxito! Usuario: {nick}", sesion_info
        else:
            msg = res_data.get("message") or "Credenciales incorrectas o región no coincidente."
            # Si falló en EU, intentar automáticamente en Global
            if region_key == "eu":
                return iniciar_sesion_coros(account, password, region_key="global")
            return False, f"Error al conectar con COROS: {msg}", {}

    except urllib.error.HTTPError as e:
        err_msg = e.read().decode("utf-8", errors="ignore")
        return False, f"Error HTTP {e.code} al conectar con COROS: {err_msg}", {}
    except Exception as e:
        return False, f"Excepción de conexión con COROS: {str(e)}", {}

def consultar_actividades_coros(api_base: str, access_token: str, size: int = 50, page: int = 1) -> List[Dict[str, Any]]:
    """Obtiene la lista de actividades desde el Training Hub de COROS."""
    query_url = f"{api_base}/activity/query"
    headers = {
        "accesstoken": access_token,
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0"
    }
    
    # Rango de fechas amplio
    params = urllib.parse.urlencode({
        "size": size,
        "pageNumber": page,
        "modeList": ""
    })
    full_url = f"{query_url}?{params}"

    req = urllib.request.Request(full_url, headers=headers)
    with urllib.request.urlopen(req, timeout=15) as resp:
        res = json.loads(resp.read().decode("utf-8"))

    if "data" in res and isinstance(res["data"], dict) and "dataList" in res["data"]:
        return res["data"]["dataList"]
    elif "data" in res and isinstance(res["data"], list):
        return res["data"]
    return []

def consultar_detalle_actividad_coros(api_base: str, access_token: str, activity_id: str, sport_type: int = 100) -> Optional[Dict[str, Any]]:
    """Obtiene el detalle y las vueltas (laps) de una actividad COROS específica."""
    detail_url = f"{api_base}/activity/detail/query"
    headers = {
        "accesstoken": access_token,
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0"
    }
    payload = json.dumps({
        "activityId": str(activity_id),
        "sportType": sport_type
    }).encode("utf-8")

    try:
        req = urllib.request.Request(detail_url, data=payload, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return data.get("data")
    except Exception:
        return None

def parsear_actividad_coros(act: Dict[str, Any], detail: Optional[Dict[str, Any]] = None) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """Convierte el formato JSON de COROS a la estructura estándar de SportTracks."""
    act_id = str(act.get("activityId") or act.get("id") or "")
    fit_hash = f"coros_{act_id}"

    # Fecha
    # COROS suele almacenar 'startTime' en epoch milisegundos o string 'date' YYYYMMDD
    start_time = act.get("startTime")
    if start_time and isinstance(start_time, (int, float)):
        fecha_dt = datetime.fromtimestamp(start_time / 1000.0 if start_time > 1e11 else start_time)
        fecha_str = fecha_dt.strftime("%Y-%m-%d %H:%M:%S")
    else:
        date_raw = str(act.get("date") or datetime.now().strftime("%Y%m%d"))
        try:
            fecha_str = f"{date_raw[:4]}-{date_raw[4:6]}-{date_raw[6:8]} 09:00:00"
        except Exception:
            fecha_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    titulo = act.get("name") or act.get("activityName") or "Carrera COROS"
    distancia_m = float(act.get("distance") or 0.0)
    tiempo_total_s = int(act.get("duration") or act.get("totalTime") or 0)
    distancia_km = round(distancia_m / 1000.0, 2)
    tiempo_formateado = segundos_a_formato(tiempo_total_s)
    ritmo_medio = calcular_ritmo(distancia_m, tiempo_total_s)

    fc_media = act.get("avgHeartRate") or act.get("avgHr")
    fc_max = act.get("maxHeartRate") or act.get("maxHr")
    cadencia_media = act.get("avgCadence") or act.get("avgStepCadence")
    calorias = act.get("calorie") or act.get("calories")

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
        "cadencia_media": int(cadencia_media) if cadencia_media else None,
        "calorias": int(calorias) if calorias else None,
        "ubicacion": "COROS",
        "notas_entrenador": "",
        "fit_hash": fit_hash
    }

    # Procesar Laps/Vueltas
    laps_resultado = []
    lap_list = []
    if detail and "lapList" in detail:
        lap_list = detail["lapList"]
    elif "lapList" in act:
        lap_list = act["lapList"]

    if lap_list:
        for idx, lap in enumerate(lap_list):
            lap_dist = float(lap.get("distance") or 0.0)
            lap_time = float(lap.get("duration") or lap.get("totalTime") or 0.0)
            laps_resultado.append({
                "lap_numero": idx + 1,
                "distancia_m": lap_dist,
                "tiempo_s": lap_time,
                "tiempo_formateado": segundos_a_formato(lap_time),
                "ritmo_minkm": calcular_ritmo(lap_dist, lap_time),
                "fc_media": int(lap.get("avgHr") or lap.get("avgHeartRate")) if (lap.get("avgHr") or lap.get("avgHeartRate")) else None,
                "fc_max": int(lap.get("maxHr") or lap.get("maxHeartRate")) if (lap.get("maxHr") or lap.get("maxHeartRate")) else None,
                "cadencia": int(lap.get("avgCadence") or 0),
                "tipo_intervalo": "serie"
            })
    else:
        # Vuelta única por defecto si no hay desglose
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

def sincronizar_actividades_coros(progreso_callback: Optional[Callable[[int, int, str], None]] = None, max_actividades: int = 50) -> Dict[str, Any]:
    """Descarga e importa actividades desde COROS Training Hub."""
    tokens = obtener_tokens_guardados()
    if not tokens or not tokens.get("accessToken"):
        return {"status": "error", "mensaje": "No hay ninguna sesión activa de COROS. Inicia sesión primero.", "nuevos": 0}

    api_base = tokens.get("api_base", REGIONS["eu"]["api_base"])
    token = tokens["accessToken"]

    try:
        actividades = consultar_actividades_coros(api_base, token, size=max_actividades)
    except Exception as e:
        return {"status": "error", "mensaje": f"Error al consultar actividades en COROS: {e}", "nuevos": 0}

    if not actividades:
        return {"status": "ok", "mensaje": "No se encontraron actividades en tu cuenta de COROS.", "nuevos": 0}

    total = len(actividades)
    nuevos_guardados = 0
    ya_existentes = 0

    conn = database.get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT fit_hash FROM entrenamientos WHERE fit_hash IS NOT NULL")
    hashes_existentes = set(r[0] for r in cursor.fetchall())
    conn.close()

    for idx, act in enumerate(actividades):
        act_id = str(act.get("activityId") or act.get("id") or "")
        fit_hash = f"coros_{act_id}"
        nombre_act = act.get("name") or act.get("activityName") or f"Actividad {act_id}"

        if progreso_callback:
            progreso_callback(idx + 1, total, nombre_act)

        if fit_hash in hashes_existentes:
            ya_existentes += 1
            continue

        # Obtener detalle de laps si está disponible
        detail = consultar_detalle_actividad_coros(api_base, token, act_id, act.get("sportType", 100))
        datos_entreno, laps = parsear_actividad_coros(act, detail)

        nuevo_id = database.guardar_entrenamiento(datos_entreno, laps)
        if nuevo_id:
            nuevos_guardados += 1
            hashes_existentes.add(fit_hash)

    # Actualizar fecha de última sincronización
    tokens["last_sync"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    guardar_tokens_coros(tokens)

    return {
        "status": "ok",
        "mensaje": f"Sincronización completada: {nuevos_guardados} nuevos entrenamientos importados ({ya_existentes} ya existían).",
        "nuevos": nuevos_guardados,
        "existentes": ya_existentes,
        "total": total
    }
