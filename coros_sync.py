import os
import json
import hashlib
import time
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

def obtener_tokens_guardados(usuario_id: Optional[int] = None, *args, **kwargs) -> Optional[Dict[str, Any]]:
    """Devuelve los datos de sesión de COROS para el atleta correspondiente, consultando disco y base de datos persistente."""
    uid = usuario_id if usuario_id is not None else kwargs.get("usuario_id")
    if uid is None and len(args) > 0 and isinstance(args[0], int):
        uid = args[0]
    target_uid = uid if uid is not None else 1

    os.makedirs(COROS_TOKENS_DIR, exist_ok=True)
    f_user = os.path.join(COROS_TOKENS_DIR, f"coros_tokens_u{target_uid}.json")

    # 1. Comprobar archivo específico en disco
    if os.path.isfile(f_user):
        try:
            with open(f_user, "r", encoding="utf-8") as f:
                d = json.load(f)
                if d.get("accessToken"):
                    return d
        except Exception:
            pass

    # 2. Si no está en disco (reinicio de Streamlit Cloud), recuperar de SQLite permanente
    try:
        db_tokens = database.obtener_sesion_plataforma(target_uid, "coros")
        if db_tokens and db_tokens.get("accessToken"):
            # Restaurar el archivo en disco para operaciones subsiguientes
            with open(f_user, "w", encoding="utf-8") as f:
                json.dump(db_tokens, f, indent=2)
            return db_tokens
    except Exception:
        pass

    # 3. Comprobar si coros_tokens.json es de este usuario o es usuario 1
    if os.path.isfile(COROS_TOKENS_FILE):
        try:
            with open(COROS_TOKENS_FILE, "r", encoding="utf-8") as f:
                d = json.load(f)
                if d.get("usuario_id") == target_uid or (target_uid == 1 and d.get("accessToken")):
                    return d
        except Exception:
            pass

    return None

def guardar_tokens_coros(data: Dict[str, Any], usuario_id: Optional[int] = None):
    """Guarda los tokens de sesión de COROS en disco y en SQLite de forma estrictamente aislada por atleta."""
    os.makedirs(COROS_TOKENS_DIR, exist_ok=True)
    uid = usuario_id if usuario_id is not None else 1
    data["usuario_id"] = uid

    f_user = os.path.join(COROS_TOKENS_DIR, f"coros_tokens_u{uid}.json")
    with open(f_user, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    if uid == 1:
        with open(COROS_TOKENS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    # Persistir en la base de datos sporttracks.db para sobrevivir a reinicios de contenedor en Streamlit Cloud
    try:
        database.guardar_sesion_plataforma(uid, "coros", data)
    except Exception as e:
        print(f"Aviso al guardar sesión COROS en SQLite: {e}")

def cerrar_sesion_coros(usuario_id: Optional[int] = None):
    """Elimina la sesión guardada de COROS en disco y en SQLite para el atleta correspondiente."""
    uid = usuario_id if usuario_id is not None else 1
    f_user = os.path.join(COROS_TOKENS_DIR, f"coros_tokens_u{uid}.json")
    if os.path.isfile(f_user):
        try:
            os.remove(f_user)
        except Exception:
            pass

    try:
        database.eliminar_sesion_plataforma(uid, "coros")
    except Exception:
        pass

    if uid == 1 and os.path.isfile(COROS_TOKENS_FILE):
        try:
            os.remove(COROS_TOKENS_FILE)
        except Exception:
            pass

def iniciar_sesion_coros(account: str, password: str, region_key: str = "eu", usuario_id: Optional[int] = None) -> Tuple[bool, str, Dict[str, Any]]:
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
                "usuario_id": usuario_id,
                "saved_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            guardar_tokens_coros(sesion_info, usuario_id=usuario_id)
            return True, f"¡Sesión iniciada con éxito! Usuario: {nick}", sesion_info
        else:
            msg = res_data.get("message") or "Credenciales incorrectas o región no coincidente."
            # Si falló en EU, intentar automáticamente en Global
            if region_key == "eu":
                return iniciar_sesion_coros(account, password, region_key="global", usuario_id=usuario_id)
            return False, f"Error al conectar con COROS: {msg}", {}

    except urllib.error.HTTPError as e:
        err_msg = e.read().decode("utf-8", errors="ignore")
        return False, f"Error HTTP {e.code} al conectar con COROS: {err_msg}", {}
    except Exception as e:
        return False, f"Excepción de conexión con COROS: {str(e)}", {}

def consultar_actividades_coros(
    api_base: str,
    access_token: str,
    size: int = 50,
    page: int = 1,
    start_day: Optional[str] = None,
    end_day: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Obtiene una página de actividades desde el Training Hub de COROS con rango de fechas."""
    query_url = f"{api_base}/activity/query"
    headers = {
        "accesstoken": access_token,
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0"
    }

    if not start_day:
        start_day = "20150101"
    if not end_day:
        end_day = datetime.now().strftime("%Y%m%d")

    params = urllib.parse.urlencode({
        "size": size,
        "pageNumber": page,
        "modeList": "",
        "startDay": start_day,
        "endDay": end_day
    })
    full_url = f"{query_url}?{params}"

    req = urllib.request.Request(full_url, headers=headers)
    with urllib.request.urlopen(req, timeout=15) as resp:
        res = json.loads(resp.read().decode("utf-8"))

    if "data" in res and isinstance(res["data"], dict) and "dataList" in res["data"]:
        return res["data"]["dataList"] or []
    elif "data" in res and isinstance(res["data"], list):
        return res["data"] or []
    return []

def extraer_coros_act_id(act: Dict[str, Any]) -> str:
    """Extrae el identificador único de la actividad de COROS soportando labelId, sportDataId, activityId, id, etc."""
    for k in ("labelId", "sportDataId", "activityId", "id", "hId", "workoutId", "fileId"):
        val = act.get(k)
        if val is not None and str(val).strip() != "":
            return str(val).strip()

    st = act.get("startTime")
    if st is not None and str(st).strip() != "":
        return str(st).strip()

    date_val = act.get("date")
    if date_val is not None and str(date_val).strip() != "":
        dist = int(float(act.get("distance") or 0))
        dur = int(float(act.get("duration") or act.get("totalTime") or 0))
        return f"{date_val}_{dist}_{dur}"

    return ""

SPORT_TYPE_MAP = {
    100: "running",
    101: "running",
    102: "trail_running",
    103: "track_running",
    200: "cycling",
    201: "indoor_cycling",
    300: "swimming",
    301: "open_water_swimming",
    400: "walking"
}

def consultar_detalle_actividad_coros(
    api_base: str,
    access_token: str,
    activity_id: str,
    sport_type: int = 100,
    user_id: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """
    Obtiene el detalle y las vueltas (laps) de una actividad COROS específica.
    Implementa application/x-www-form-urlencoded (requerido por COROS Training Hub API)
    con fallbacks robustos a GET y JSON.
    """
    if not activity_id:
        return None

    detail_url = f"{api_base}/activity/detail/query"
    headers_base = {
        "accesstoken": access_token,
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    form_data = {
        "labelId": str(activity_id),
        "sportType": str(sport_type)
    }
    if user_id:
        form_data["userId"] = str(user_id)

    # 1. Intento POST application/x-www-form-urlencoded (método oficial COROS Training Hub)
    try:
        body_encoded = urllib.parse.urlencode(form_data).encode("utf-8")
        h_post = {**headers_base, "Content-Type": "application/x-www-form-urlencoded"}
        req = urllib.request.Request(detail_url, data=body_encoded, headers=h_post, method="POST")
        with urllib.request.urlopen(req, timeout=12) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if data and data.get("data"):
                return data.get("data")
    except Exception:
        pass

    # 2. Intento GET /activity/detail?labelId=...&sportType=...
    try:
        q_params = urllib.parse.urlencode(form_data)
        get_url = f"{detail_url}?{q_params}"
        req_get = urllib.request.Request(get_url, headers=headers_base, method="GET")
        with urllib.request.urlopen(req_get, timeout=12) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if data and data.get("data"):
                return data.get("data")
    except Exception:
        pass

    # 3. Intento POST JSON
    try:
        json_payload = json.dumps({
            "activityId": str(activity_id),
            "labelId": str(activity_id),
            "sportType": int(sport_type),
            **({"userId": str(user_id)} if user_id else {})
        }).encode("utf-8")
        h_json = {**headers_base, "Content-Type": "application/json"}
        req_json = urllib.request.Request(detail_url, data=json_payload, headers=h_json, method="POST")
        with urllib.request.urlopen(req_json, timeout=12) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if data and data.get("data"):
                return data.get("data")
    except Exception:
        pass

    return None

def parsear_actividad_coros(
    act: Dict[str, Any],
    detail: Optional[Dict[str, Any]] = None,
    usuario_id: int = 1
) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """Convierte el formato JSON de COROS a la estructura estándar de SportTracks."""
    act_id = extraer_coros_act_id(act)
    if not act_id:
        dist_m = int(float(act.get("distance") or 0.0))
        dur_s = int(float(act.get("duration") or act.get("totalTime") or 0.0))
        st_val = act.get("startTime") or act.get("date") or "0"
        act_id = f"act_{st_val}_{dist_m}_{dur_s}"
    fit_hash = f"coros_u{usuario_id}_{act_id}"

    # Fecha
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

    # Mapeo de deporte para no contaminar atletismo con piscina o ciclismo
    sport_num = act.get("sportType")
    deporte = SPORT_TYPE_MAP.get(sport_num, "running")
    tit_low = titulo.lower()
    if any(k in tit_low for k in ["ciclismo", "bici", "bike"]):
        deporte = "cycling"
    elif any(k in tit_low for k in ["piscina", "natación", "natacion", "swim"]):
        deporte = "swimming"
    elif any(k in tit_low for k in ["caminata", "andar", "walk"]):
        deporte = "walking"

    datos_entreno = {
        "fecha": fecha_str,
        "titulo": titulo,
        "deporte": deporte,
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

    # Procesar Laps/Vueltas reales de COROS
    laps_resultado = []
    lap_items_extraidos = []

    if detail:
        # Estructura oficial COROS Training Hub: lapList contiene grupos. El grupo con type == -1 son las vueltas reales del atleta
        raw_lap_list = detail.get("lapList") or []
        for group in raw_lap_list:
            if isinstance(group, dict):
                items = group.get("lapItemList")
                if items and isinstance(items, list):
                    # Priorizar type == -1 (vueltas del atleta) o el grupo con más vueltas
                    if group.get("type") == -1 or not lap_items_extraidos:
                        lap_items_extraidos = items
                elif "distance" in group or "totalTime" in group or "duration" in group or "time" in group:
                    lap_items_extraidos.append(group)
            elif isinstance(group, list):
                lap_items_extraidos.extend(group)

        if not lap_items_extraidos:
            lap_items_extraidos = detail.get("laps") or detail.get("splits") or []

    if not lap_items_extraidos and "lapList" in act:
        act_laps = act.get("lapList")
        if isinstance(act_laps, list):
            for item in act_laps:
                if isinstance(item, dict) and "lapItemList" in item:
                    lap_items_extraidos.extend(item["lapItemList"])
                else:
                    lap_items_extraidos.append(item)

    if lap_items_extraidos:
        for idx, lap in enumerate(lap_items_extraidos):
            # En COROS Training Hub, distancia viene en milímetros (si > 50000 mm = 50 m)
            raw_dist = float(lap.get("distance") or 0.0)
            if raw_dist > 50000:
                lap_dist = round(raw_dist / 1000.0, 2)
            else:
                lap_dist = round(raw_dist, 2)

            # Duración puede venir en milisegundos (si > 100000 ms = 100 s)
            raw_time = float(lap.get("time") or lap.get("duration") or lap.get("totalTime") or 0.0)
            if raw_time > 100000:
                lap_time = round(raw_time / 1000.0, 1)
            else:
                lap_time = round(raw_time, 1)

            if lap_dist <= 0 and lap_time <= 0:
                continue

            ritmo_str = calcular_ritmo(lap_dist, lap_time)
            fc_med = lap.get("avgHr") or lap.get("avgHeartRate")
            fc_mx = lap.get("maxHr") or lap.get("maxHeartRate")
            cad = lap.get("avgCadence") or lap.get("cadence") or 0

            # Clasificación de tipo de intervalo
            tipo_int = "serie" if 150 <= lap_dist <= 3500 else "tramo"

            laps_resultado.append({
                "lap_numero": int(lap.get("lapIndex") or (idx + 1)),
                "distancia_m": lap_dist,
                "tiempo_s": lap_time,
                "tiempo_formateado": segundos_a_formato(int(lap_time)),
                "ritmo_minkm": ritmo_str,
                "fc_media": int(fc_med) if fc_med else None,
                "fc_max": int(fc_mx) if fc_mx else None,
                "cadencia": int(cad),
                "tipo_intervalo": tipo_int
            })

    if not laps_resultado:
        # Vuelta única por defecto solo si no se obtuvo ningún desglose
        laps_resultado.append({
            "lap_numero": 1,
            "distancia_m": distancia_m,
            "tiempo_s": tiempo_total_s,
            "tiempo_formateado": tiempo_formateado,
            "ritmo_minkm": ritmo_medio,
            "fc_media": datos_entreno["fc_media"],
            "fc_max": datos_entreno["fc_max"],
            "cadencia": datos_entreno["cadencia_media"] or 0,
            "tipo_intervalo": "serie" if 350 <= distancia_m <= 1100 else "tramo"
        })

    return datos_entreno, laps_resultado

def sincronizar_actividades_coros(
    progreso_callback: Optional[Callable[[int, int, str], None]] = None,
    max_actividades: int = 0,
    usuario_id: int = 1,
    historial_completo: Optional[bool] = None
) -> Dict[str, Any]:
    """
    Descarga e importa actividades desde COROS Training Hub para un atleta específico.
    - Primera vez: descarga todo el historial de forma paginada hacia atrás.
    - Sincronizaciones posteriores: descarga solo las actividades nuevas que no estén en la app.
    """
    tokens = obtener_tokens_guardados(usuario_id=usuario_id)
    if not tokens or not tokens.get("accessToken"):
        return {"status": "error", "mensaje": "No hay ninguna sesión activa de COROS. Inicia sesión primero.", "nuevos": 0}

    api_base = tokens.get("api_base", REGIONS["eu"]["api_base"])
    token = tokens["accessToken"]

    conn = database.get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT fit_hash FROM entrenamientos WHERE usuario_id = ? AND fit_hash IS NOT NULL", (usuario_id,))
    hashes_existentes = set(r[0] for r in cursor.fetchall())
    conn.close()

    tiene_entrenos_previos = len(hashes_existentes) > 0

    # Si historial_completo no se especifica, se activa automáticamente si no tiene entrenos previos
    if historial_completo is None:
        es_modo_historial = not tiene_entrenos_previos
    else:
        es_modo_historial = historial_completo

    page = 1
    page_size = 50
    nuevos_guardados = 0
    ya_existentes = 0
    consecutivos_existentes = 0
    total_analizadas = 0

    end_day = datetime.now().strftime("%Y%m%d")
    start_day = "20150101"

    while True:
        try:
            lote = consultar_actividades_coros(
                api_base, token,
                size=page_size,
                page=page,
                start_day=start_day,
                end_day=end_day
            )
        except Exception as e:
            if page == 1:
                return {"status": "error", "mensaje": f"Error al consultar actividades en COROS: {e}", "nuevos": 0}
            break

        if not lote:
            break

        for act in lote:
            total_analizadas += 1
            act_id = extraer_coros_act_id(act)
            if not act_id:
                dist_m = int(float(act.get("distance") or 0.0))
                dur_s = int(float(act.get("duration") or act.get("totalTime") or 0.0))
                st_val = act.get("startTime") or act.get("date") or total_analizadas
                act_id = f"act_{st_val}_{dist_m}_{dur_s}"

            fit_hash = f"coros_u{usuario_id}_{act_id}"
            nombre_act = act.get("name") or act.get("activityName") or f"Actividad {act_id}"

            if progreso_callback:
                progreso_callback(total_analizadas, total_analizadas + 1, nombre_act)

            # Comprobar si ya existe en la base de datos (tanto formato con uX como sin uX)
            ya_esta = (fit_hash in hashes_existentes) or (act_id and f"coros_{act_id}" in hashes_existentes)
            if ya_esta:
                ya_existentes += 1
                consecutivos_existentes += 1

                # Comprobación de enriquecimiento: si ya existe pero solo tiene 1 vuelta dummy en la base de datos,
                # intentar consultar el detalle de laps para que las series se desglosen correctamente
                if consecutivos_existentes <= 20:
                    try:
                        conn_chk = database.get_connection()
                        c_chk = conn_chk.cursor()
                        c_chk.execute(
                            "SELECT id FROM entrenamientos WHERE (fit_hash = ? OR fit_hash = ?) AND usuario_id = ?",
                            (fit_hash, f"coros_{act_id}", usuario_id)
                        )
                        row_e = c_chk.fetchone()
                        if row_e:
                            entreno_id_existente = row_e[0]
                            c_chk.execute(
                                "SELECT COUNT(*) FROM series_laps WHERE entrenamiento_id = ?",
                                (entreno_id_existente,)
                            )
                            cnt_laps = c_chk.fetchone()[0]
                            if cnt_laps <= 1:
                                user_id_coros = tokens.get("userId") or act.get("userId")
                                detail = consultar_detalle_actividad_coros(
                                    api_base, token, act_id, act.get("sportType", 100), user_id=user_id_coros
                                )
                                if detail:
                                    _, nuevas_vueltas = parsear_actividad_coros(act, detail, usuario_id=usuario_id)
                                    if len(nuevas_vueltas) > 1:
                                        c_chk.execute("DELETE FROM series_laps WHERE entrenamiento_id = ?", (entreno_id_existente,))
                                        for nl in nuevas_vueltas:
                                            c_chk.execute("""
                                                INSERT INTO series_laps (
                                                    entrenamiento_id, lap_numero, distancia_m, tiempo_s,
                                                    tiempo_formateado, ritmo_minkm, fc_media, fc_max, cadencia, tipo_intervalo
                                                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                                            """, (
                                                entreno_id_existente, nl["lap_numero"], nl["distancia_m"], nl["tiempo_s"],
                                                nl["tiempo_formateado"], nl["ritmo_minkm"], nl["fc_media"], nl["fc_max"],
                                                nl["cadencia"], nl["tipo_intervalo"]
                                            ))
                                        conn_chk.commit()
                        conn_chk.close()
                    except Exception:
                        pass

                # En sincronización incremental normal, si encontramos 5 entrenamientos consecutivos ya guardados,
                # significa que ya hemos alcanzado el último entreno conocido.
                if not es_modo_historial and tiene_entrenos_previos and consecutivos_existentes >= 5:
                    break
                continue

            consecutivos_existentes = 0

            # Obtener detalle de laps si está disponible
            detail = None
            try:
                user_id_coros = tokens.get("userId") or act.get("userId")
                detail = consultar_detalle_actividad_coros(
                    api_base, token, act_id, act.get("sportType", 100), user_id=user_id_coros
                )
            except Exception:
                pass

            datos_entreno, laps = parsear_actividad_coros(act, detail, usuario_id=usuario_id)
            nuevo_id = database.guardar_entrenamiento(datos_entreno, laps, usuario_id=usuario_id)

            if nuevo_id:
                nuevos_guardados += 1
                hashes_existentes.add(fit_hash)

                # Calcular y guardar splits de 1 km
                try:
                    splits_km = database.calcular_splits_km(
                        datos_entreno.get("distancia_km", 0.0),
                        datos_entreno.get("tiempo_total_s", 0.0),
                        laps
                    )
                    if splits_km:
                        database.guardar_splits_km(nuevo_id, splits_km)
                except Exception:
                    pass

            if max_actividades > 0 and nuevos_guardados >= max_actividades:
                break

        # Condición de parada temprana en modo incremental
        if not es_modo_historial and tiene_entrenos_previos and consecutivos_existentes >= 5:
            break

        if len(lote) < page_size:
            # Fin del historial disponible en COROS
            break

        if max_actividades > 0 and nuevos_guardados >= max_actividades:
            break

        page += 1
        time.sleep(0.3)

    # Actualizar fecha de última sincronización
    tokens["last_sync"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    guardar_tokens_coros(tokens, usuario_id=usuario_id)

    # Persistencia permanente en GitHub
    if nuevos_guardados > 0:
        try:
            database.persistir_base_datos(f"Sincronizados {nuevos_guardados} entrenos de COROS (atleta id {usuario_id}) [skip ci]")
        except Exception:
            pass

    # Auto-reprocesar laps de actividades recientes o históricas que solo tengan 1 vuelta
    try:
        reprocesar_laps_actividades_existentes(usuario_id=usuario_id, limite=50)
    except Exception:
        pass

    modo_txt = "historial completo" if es_modo_historial else "sincronización incremental"
    return {
        "status": "ok",
        "mensaje": f"Sincronización COROS completada ({modo_txt}): {nuevos_guardados} nuevos entrenamientos importados ({ya_existentes} ya existían).",
        "nuevos": nuevos_guardados,
        "existentes": ya_existentes,
        "total": total_analizadas
    }

def reprocesar_laps_actividades_existentes(usuario_id: int = 8, limite: int = 30) -> Dict[str, Any]:
    """
    Recorre las actividades de un usuario que solo tienen 1 vuelta dummy y consulta
    a COROS para descargar el desglose real de laps y repeticiones de series.
    """
    tokens = obtener_tokens_guardados(usuario_id=usuario_id)
    if not tokens or not tokens.get("accessToken"):
        return {"status": "error", "mensaje": "No hay sesión activa de COROS para este usuario."}

    api_base = tokens.get("api_base", REGIONS["eu"]["api_base"])
    token = tokens["accessToken"]
    user_id_coros = tokens.get("userId")

    conn = database.get_connection()
    cursor = conn.cursor()

    # Buscar entrenamientos con fit_hash de COROS y que solo tengan 1 vuelta
    query = """
    SELECT e.id, e.fit_hash, e.titulo, e.distancia_km, e.tiempo_total_s, e.fecha
    FROM entrenamientos e
    JOIN series_laps s ON s.entrenamiento_id = e.id
    WHERE e.usuario_id = ? AND e.fit_hash LIKE 'coros_%'
    GROUP BY e.id
    HAVING COUNT(s.id) <= 1
    ORDER BY e.fecha DESC
    LIMIT ?
    """
    cursor.execute(query, (usuario_id, limite))
    candidatos = cursor.fetchall()

    actualizados = 0
    for entreno in candidatos:
        entreno_id, fit_hash, tit, dist_km, dur_s, fecha_s = entreno
        partes = fit_hash.split("_")
        act_id = partes[-1]
        if not act_id or not act_id.isdigit():
            continue

        try:
            detail = consultar_detalle_actividad_coros(
                api_base, token, act_id, sport_type=100, user_id=user_id_coros
            )
            if detail:
                dummy_act = {
                    "distance": dist_km * 1000.0,
                    "duration": dur_s,
                    "name": tit,
                    "startTime": fecha_s
                }
                _, laps = parsear_actividad_coros(dummy_act, detail, usuario_id=usuario_id)
                if len(laps) > 1:
                    cursor.execute("DELETE FROM series_laps WHERE entrenamiento_id = ?", (entreno_id,))
                    for l in laps:
                        cursor.execute("""
                            INSERT INTO series_laps (
                                entrenamiento_id, lap_numero, distancia_m, tiempo_s,
                                tiempo_formateado, ritmo_minkm, fc_media, fc_max, cadencia, tipo_intervalo
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            entreno_id, l["lap_numero"], l["distancia_m"], l["tiempo_s"],
                            l["tiempo_formateado"], l["ritmo_minkm"], l["fc_media"], l["fc_max"],
                            l["cadencia"], l["tipo_intervalo"]
                        ))
                    actualizados += 1
                    conn.commit()
        except Exception:
            pass

    conn.close()
    if actualizados > 0:
        try:
            database.persistir_base_datos(f"Actualizados laps de {actualizados} sesiones de COROS (usuario {usuario_id}) [skip ci]")
        except Exception:
            pass

    return {
        "status": "ok",
        "mensaje": f"Se han desglosado y actualizado las series de {actualizados} sesiones.",
        "actualizados": actualizados
    }
