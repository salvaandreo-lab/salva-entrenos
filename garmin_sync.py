import os
import re
import hashlib
import time
from datetime import datetime, timedelta
from typing import List, Dict, Any, Tuple, Optional, Callable
import json
import database

def segundos_a_formato(segundos: float) -> str:
    """Convierte segundos a HH:MM:SS o MM:SS."""
    if not segundos or segundos <= 0:
        return "00:00"
    total_seconds = int(segundos)
    horas = total_seconds // 3600
    minutos = (total_seconds % 3600) // 60
    segs = total_seconds % 60
    if horas > 0:
        return f"{horas:02d}:{minutos:02d}:{segs:02d}"
    return f"{minutos:02d}:{segs:02d}"

def calcular_ritmo(distancia_m: float, tiempo_s: float) -> str:
    """Calcula el ritmo en min/km a partir de metros y segundos."""
    if not distancia_m or distancia_m <= 0 or not tiempo_s or tiempo_s <= 0:
        return "--:--"
    distancia_km = distancia_m / 1000.0
    segundos_por_km = tiempo_s / distancia_km
    minutos = int(segundos_por_km // 60)
    segs = int(segundos_por_km % 60)
    return f"{minutos}:{segs:02d}"

# ==================== PARSER DE ARCHIVOS .FIT ====================

def parsear_archivo_fit(fit_file_path: str) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """
    Parsea un archivo binario .FIT de Garmin usando fitparse.
    Extrae la sesión general y cada vuelta/intervalo.
    """
    try:
        from fitparse import FitFile
    except ImportError:
        raise ImportError("Se requiere la librería 'fitparse'. Instálala con: pip install fitparse")

    fitfile = FitFile(fit_file_path)

    with open(fit_file_path, "rb") as f:
        file_hash = hashlib.sha256(f.read()).hexdigest()

    datos_entreno = {
        "fecha": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "titulo": os.path.splitext(os.path.basename(fit_file_path))[0],
        "deporte": "running",
        "distancia_km": 0.0,
        "tiempo_total_s": 0,
        "tiempo_formateado": "00:00",
        "ritmo_medio_minkm": "--:--",
        "fc_media": None,
        "fc_max": None,
        "cadencia_media": None,
        "calorias": None,
        "ubicacion": "",
        "notas_entrenador": "",
        "fit_hash": file_hash
    }

    for record in fitfile.get_messages('session'):
        for data in record:
            if data.name == 'start_time' and data.value:
                datos_entreno["fecha"] = data.value.strftime("%Y-%m-%d %H:%M:%S")
            elif data.name == 'total_distance' and data.value is not None:
                datos_entreno["distancia_km"] = round(data.value / 1000.0, 2)
            elif data.name == 'total_elapsed_time' and data.value is not None:
                datos_entreno["tiempo_total_s"] = int(data.value)
                datos_entreno["tiempo_formateado"] = segundos_a_formato(data.value)
            elif data.name == 'avg_heart_rate' and data.value is not None:
                datos_entreno["fc_media"] = int(data.value)
            elif data.name == 'max_heart_rate' and data.value is not None:
                datos_entreno["fc_max"] = int(data.value)
            elif data.name == 'avg_cadence' and data.value is not None:
                datos_entreno["cadencia_media"] = int(data.value)
            elif data.name == 'total_calories' and data.value is not None:
                datos_entreno["calorias"] = int(data.value)
            elif data.name == 'sport' and data.value is not None:
                datos_entreno["deporte"] = str(data.value)

    if datos_entreno["distancia_km"] > 0 and datos_entreno["tiempo_total_s"] > 0:
        datos_entreno["ritmo_medio_minkm"] = calcular_ritmo(
            datos_entreno["distancia_km"] * 1000.0,
            datos_entreno["tiempo_total_s"]
        )

    laps = []
    lap_num = 1
    for record in fitfile.get_messages('lap'):
        lap_data = {
            "lap_numero": lap_num,
            "distancia_m": 0.0,
            "tiempo_s": 0.0,
            "tiempo_formateado": "00:00",
            "ritmo_minkm": "--:--",
            "fc_media": None,
            "fc_max": None,
            "cadencia": None,
            "tipo_intervalo": "serie"
        }
        for data in record:
            if data.name == 'total_distance' and data.value is not None:
                lap_data["distancia_m"] = round(float(data.value), 1)
            elif data.name == 'total_elapsed_time' and data.value is not None:
                lap_data["tiempo_s"] = round(float(data.value), 1)
                lap_data["tiempo_formateado"] = segundos_a_formato(lap_data["tiempo_s"])
            elif data.name == 'avg_heart_rate' and data.value is not None:
                lap_data["fc_media"] = int(data.value)
            elif data.name == 'max_heart_rate' and data.value is not None:
                lap_data["fc_max"] = int(data.value)
            elif data.name == 'avg_cadence' and data.value is not None:
                lap_data["cadencia"] = int(data.value)

        if lap_data["distancia_m"] > 0:
            lap_data["ritmo_minkm"] = calcular_ritmo(lap_data["distancia_m"], lap_data["tiempo_s"])
            if 350 <= lap_data["distancia_m"] <= 450:
                lap_data["tipo_intervalo"] = "serie_400m"
            elif 900 <= lap_data["distancia_m"] <= 1100:
                lap_data["tipo_intervalo"] = "serie_1000m"
            elif 1500 <= lap_data["distancia_m"] <= 1700:
                lap_data["tipo_intervalo"] = "serie_1600m"
            elif 1800 <= lap_data["distancia_m"] <= 2200:
                lap_data["tipo_intervalo"] = "serie_2000m"

            laps.append(lap_data)
            lap_num += 1

    return datos_entreno, laps

# ==================== CONEXIÓN ONLINE GARMIN CONNECT ====================

def obtener_directorio_tokens(email: str = "", usuario_id: Optional[int] = None) -> str:
    """Devuelve la ruta del directorio de tokens para un atleta o email específico."""
    base_dir = os.path.join(os.path.dirname(__file__), ".garmin_tokens")
    if usuario_id and usuario_id != 1:
        token_dir = os.path.join(base_dir, f"u{usuario_id}")
    elif email:
        safe_name = re.sub(r'[^a-zA-Z0-9_.-]', '_', email.lower().strip())
        token_dir = os.path.join(base_dir, safe_name)
    else:
        token_dir = base_dir
    os.makedirs(token_dir, exist_ok=True)
    return token_dir

def conectar_garmin(email: str, password: str = "", tokenstore_dir: Optional[str] = None, usuario_id: Optional[int] = None):
    """
    Inicia sesión en Garmin Connect.
    Soporta múltiples cuentas almacenando tokens estrictamente separados por atleta o email.
    """
    from garminconnect import Garmin, GarminConnectAuthenticationError

    if not tokenstore_dir:
        tokenstore_dir = obtener_directorio_tokens(email, usuario_id=usuario_id)

    target_uid = usuario_id if usuario_id is not None else 1
    token_json_file = os.path.join(tokenstore_dir, "garmin_tokens.json")
    if not os.path.isfile(token_json_file):
        try:
            db_tok = database.obtener_sesion_plataforma(target_uid, "garmin")
            if db_tok:
                os.makedirs(tokenstore_dir, exist_ok=True)
                with open(token_json_file, "w", encoding="utf-8") as f:
                    json.dump(db_tok, f, indent=2)
        except Exception:
            pass

    client = Garmin(email, password)
    # Intentar login usando tokens guardados si existen
    try:
        client.login(tokenstore=tokenstore_dir)
        try:
            if os.path.isfile(token_json_file):
                with open(token_json_file, "r", encoding="utf-8") as f:
                    updated_tokens = json.load(f)
                database.guardar_sesion_plataforma(target_uid, "garmin", updated_tokens)
        except Exception as e_tok:
            print(f"Aviso guardando tokens Garmin en DB: {e_tok}")
        return client, "Conexión exitosa"
    except Exception as e:
        if not password:
            raise Exception(f"Se requiere contraseña para iniciar sesión por primera vez con {email or 'este atleta'}: {e}")
        raise Exception(f"No se pudo conectar a Garmin Connect ({email or 'este atleta'}): {e}")

def calcular_splits_desde_detalles_garmin(
    client,
    act_id: str,
    duracion_total_s: float = 0.0,
    distancia_total_km: float = 0.0
) -> List[Dict[str, Any]]:
    """
    Calcula los parciales métricos exactos de 1 km (estilo Strava) a partir de la traza continua
    de puntos GPS, elevación y tiempo de Garmin Connect.
    """
    try:
        det = client.get_activity_details(act_id)
        if not det or not det.get("metricDescriptors") or not det.get("activityDetailMetrics"):
            return []

        desc_map = {d["key"]: d["metricsIndex"] for d in det["metricDescriptors"] if "key" in d and "metricsIndex" in d}
        dist_idx = desc_map.get("sumDistance")
        time_idx = desc_map.get("sumMovingDuration") or desc_map.get("sumDuration")
        elev_idx = desc_map.get("directElevation") or desc_map.get("directCorrectedElevation")
        cad_idx = desc_map.get("directDoubleCadence") or desc_map.get("directRunCadence")

        if dist_idx is None or time_idx is None:
            return []

        pts = []
        for m in det.get("activityDetailMetrics", []):
            vals = m.get("metrics", [])
            if len(vals) <= max(dist_idx, time_idx):
                continue
            d = vals[dist_idx]
            t = vals[time_idx]
            if d is not None and t is not None:
                e = vals[elev_idx] if elev_idx is not None and elev_idx < len(vals) and vals[elev_idx] is not None else 0.0
                c = vals[cad_idx] if cad_idx is not None and cad_idx < len(vals) and vals[cad_idx] is not None else 0.0
                pts.append((float(d), float(t), float(e), float(c)))

        if len(pts) < 5:
            return []

        def interp_at(target_d):
            for i in range(1, len(pts)):
                d0, t0, e0, c0 = pts[i-1]
                d1, t1, e1, c1 = pts[i]
                if d0 <= target_d <= d1:
                    frac = (target_d - d0) / (d1 - d0) if d1 > d0 else 0
                    return t0 + frac * (t1 - t0), e0 + frac * (e1 - e0), c1
            return pts[-1][1], pts[-1][2], pts[-1][3]

        max_d = pts[-1][0]
        if max_d <= 200:
            return []

        # Ritmo medio para comparar desviaciones
        ritmo_medio_seg = 0.0
        if distancia_total_km > 0 and duracion_total_s > 0:
            ritmo_medio_seg = duracion_total_s / distancia_total_km
        elif max_d > 0 and pts[-1][1] > 0:
            ritmo_medio_seg = pts[-1][1] / (max_d / 1000.0)

        prev_d = 0.0
        prev_t = 0.0
        prev_e = pts[0][2]

        splits = []
        km = 1
        while prev_d < max_d:
            target_d = min(km * 1000.0, max_d)
            t, e, cad = interp_at(target_d)
            split_dist = target_d - prev_d
            split_time = t - prev_t
            split_elev = e - prev_e

            if split_dist <= 0:
                break

            pace_s = split_time / (split_dist / 1000.0)
            mins = int(pace_s // 60)
            secs = int(round(pace_s % 60))
            if secs == 60:
                mins += 1
                secs = 0
            pace_str = f"{mins}:{secs:02d}"

            diff_s = pace_s - ritmo_medio_seg if ritmo_medio_seg > 0 else 0.0
            label = f"Km {km}" if split_dist >= 800 else f"{split_dist/1000.0:.1f} km"
            cad_norm = int(round(cad * 2)) if 30 < cad < 110 else int(round(cad)) if cad >= 110 else None

            splits.append({
                "km_numero": km,
                "split_numero": km,
                "etiqueta": label,
                "distancia_m": round(split_dist, 1),
                "tiempo_s": round(split_time, 1),
                "tiempo_formateado": segundos_a_formato(split_time),
                "ritmo_minkm": pace_str,
                "desnivel_m": round(split_elev, 1),
                "desviacion_ritmo_s": round(diff_s, 1),
                "fc_media": None,
                "fc_max": None,
                "cadencia": cad_norm
            })

            prev_d = target_d
            prev_t = t
            prev_e = e
            if target_d >= max_d:
                break
            km += 1

        return splits
    except Exception as e:
        print(f"Aviso: No se pudieron calcular splits detallados para Garmin {act_id}: {e}")
        return []

def descargar_historial_garmin(
    client,
    max_actividades: int = 100,
    callback_progreso: Optional[Callable[[int, int, str], None]] = None,
    usuario_id: int = 1
) -> Tuple[int, int]:
    """
    Descarga el historial de Garmin Connect de forma paginada para un atleta específico.
    Retorna (guardadas_nuevas, total_omitidas_duplicadas).
    """
    batch_size = 50
    start = 0
    guardadas = 0
    omitidas = 0

    total_objetivo = max_actividades if max_actividades > 0 else 10000

    while start < total_objetivo:
        limite_lote = min(batch_size, total_objetivo - start)
        try:
            actividades = client.get_activities(start, limite_lote)
        except Exception as e:
            print(f"Error al obtener lote desde {start}: {e}")
            break

        if not actividades:
            break

        for act in actividades:
            act_id = str(act.get("activityId", ""))
            titulo = act.get("activityName", "Entrenamiento Garmin")
            fecha_str = act.get("startTimeLocal", "")
            tipo_sport = act.get("activityType", {}).get("typeKey", "running")
            distancia_m = float(act.get("distance", 0.0))
            duracion_s = int(act.get("duration", 0))

            if callback_progreso:
                callback_progreso(guardadas + omitidas + 1, total_objetivo, f"{fecha_str[:10]} - {titulo}")

            # Identificador único para evitar duplicar por usuario
            fit_hash = f"garmin_u{usuario_id}_{act_id}"

            datos_entreno = {
                "fecha": fecha_str,
                "titulo": titulo,
                "deporte": tipo_sport,
                "distancia_km": round(distancia_m / 1000.0, 2),
                "tiempo_total_s": duracion_s,
                "tiempo_formateado": segundos_a_formato(duracion_s),
                "ritmo_medio_minkm": calcular_ritmo(distancia_m, duracion_s),
                "fc_media": act.get("averageHR"),
                "fc_max": act.get("maxHR"),
                "cadencia_media": act.get("averageRunningCadenceInStepsPerMinute"),
                "calorias": act.get("calories"),
                "ubicacion": act.get("locationName", ""),
                "notas_entrenador": "",
                "fit_hash": fit_hash
            }

            # Obtener splits/laps de la actividad
            laps = []
            try:
                splits_data = client.get_activity_splits(act_id)
                lap_dtos = splits_data.get("lapDTOs", [])
                for i, lap in enumerate(lap_dtos, start=1):
                    lap_dist_m = float(lap.get("distance", 0.0))
                    lap_dur_s = float(lap.get("duration", 0.0))
                    if lap_dist_m > 0:
                        laps.append({
                            "lap_numero": i,
                            "distancia_m": round(lap_dist_m, 1),
                            "tiempo_s": round(lap_dur_s, 1),
                            "tiempo_formateado": segundos_a_formato(lap_dur_s),
                            "ritmo_minkm": calcular_ritmo(lap_dist_m, lap_dur_s),
                            "fc_media": lap.get("averageHR"),
                            "fc_max": lap.get("maxHR"),
                            "cadencia": lap.get("averageRunCadence"),
                            "tipo_intervalo": "serie" if (160 <= lap_dist_m <= 4500 and (lap_dur_s / (lap_dist_m / 1000.0) <= 280 if lap_dist_m <= 350 else lap_dur_s / (lap_dist_m / 1000.0) <= 330)) else "tramo"
                        })
            except Exception:
                # Si no tiene splits detallados, se guarda la sesión general
                pass

            id_creado = database.guardar_entrenamiento(datos_entreno, laps, usuario_id=usuario_id)
            if id_creado:
                guardadas += 1
                try:
                    splits_km = calcular_splits_desde_detalles_garmin(
                        client, act_id,
                        duracion_total_s=duracion_s,
                        distancia_total_km=datos_entreno.get("distancia_km", 0.0)
                    )
                    if splits_km:
                        database.guardar_splits_km(id_creado, splits_km)
                except Exception as e_spl:
                    print(f"Aviso al guardar splits km de Garmin ({act_id}): {e_spl}")
            else:
                omitidas += 1

        start += len(actividades)
        # Breve pausa para respetar las políticas de API de Garmin
        time.sleep(0.5)

    return guardadas, omitidas

# ==================== DATOS DE EJEMPLO ====================

def cargar_datos_ejemplo():
    """Genera datos de demostración para poder probar el asistente de inmediato."""
    database.init_db()

    ejemplos = [
        {
            "entreno": {
                "fecha": "2026-10-28 19:30:00",
                "titulo": "Series de 400m en Pista de Atletismo",
                "deporte": "running",
                "distancia_km": 8.5,
                "tiempo_total_s": 2700,
                "tiempo_formateado": "45:00",
                "ritmo_medio_minkm": "5:17",
                "fc_media": 162,
                "fc_max": 182,
                "cadencia_media": 178,
                "calorias": 650,
                "ubicacion": "Pista Municipal",
                "notas_entrenador": "Objetivo: 8x400 a 1:18 recuperando 1:15 al trote",
                "fit_hash": "demo_hash_series_400_oct2026"
            },
            "laps": [
                {"lap_numero": 1, "distancia_m": 2000.0, "tiempo_s": 600.0, "tiempo_formateado": "10:00", "ritmo_minkm": "5:00", "fc_media": 140, "fc_max": 150, "cadencia": 165, "tipo_intervalo": "calentamiento"},
                {"lap_numero": 2, "distancia_m": 400.0, "tiempo_s": 78.5, "tiempo_formateado": "01:18", "ritmo_minkm": "3:16", "fc_media": 165, "fc_max": 174, "cadencia": 185, "tipo_intervalo": "serie_400m"},
                {"lap_numero": 3, "distancia_m": 400.0, "tiempo_s": 77.8, "tiempo_formateado": "01:17", "ritmo_minkm": "3:14", "fc_media": 168, "fc_max": 176, "cadencia": 186, "tipo_intervalo": "serie_400m"},
                {"lap_numero": 4, "distancia_m": 400.0, "tiempo_s": 79.1, "tiempo_formateado": "01:19", "ritmo_minkm": "3:17", "fc_media": 170, "fc_max": 178, "cadencia": 184, "tipo_intervalo": "serie_400m"},
                {"lap_numero": 5, "distancia_m": 400.0, "tiempo_s": 76.2, "tiempo_formateado": "01:16", "ritmo_minkm": "3:10", "fc_media": 172, "fc_max": 180, "cadencia": 188, "tipo_intervalo": "serie_400m"},
                {"lap_numero": 6, "distancia_m": 400.0, "tiempo_s": 75.0, "tiempo_formateado": "01:15", "ritmo_minkm": "3:07", "fc_media": 175, "fc_max": 182, "cadencia": 190, "tipo_intervalo": "serie_400m"},
                {"lap_numero": 7, "distancia_m": 1500.0, "tiempo_s": 540.0, "tiempo_formateado": "09:00", "ritmo_minkm": "6:00", "fc_media": 135, "fc_max": 145, "cadencia": 160, "tipo_intervalo": "enfriamiento"}
            ]
        },
        {
            "entreno": {
                "fecha": "2026-02-15 10:00:00",
                "titulo": "Media Maratón de Orihuela 2026",
                "deporte": "running",
                "distancia_km": 21.1,
                "tiempo_total_s": 5340,
                "tiempo_formateado": "01:29:00",
                "ritmo_medio_minkm": "4:13",
                "fc_media": 170,
                "fc_max": 184,
                "cadencia_media": 182,
                "calorias": 1520,
                "ubicacion": "Orihuela",
                "notas_entrenador": "Objetivo sub 1h30 logrado con soltura",
                "fit_hash": "demo_hash_orihuela_2026"
            },
            "laps": [
                {"lap_numero": 1, "distancia_m": 5000.0, "tiempo_s": 1260.0, "tiempo_formateado": "21:00", "ritmo_minkm": "4:12", "fc_media": 165, "fc_max": 172, "cadencia": 180, "tipo_intervalo": "bloque_5k"},
                {"lap_numero": 2, "distancia_m": 5000.0, "tiempo_s": 1265.0, "tiempo_formateado": "21:05", "ritmo_minkm": "4:13", "fc_media": 169, "fc_max": 175, "cadencia": 181, "tipo_intervalo": "bloque_5k"},
                {"lap_numero": 3, "distancia_m": 5000.0, "tiempo_s": 1270.0, "tiempo_formateado": "21:10", "ritmo_minkm": "4:14", "fc_media": 172, "fc_max": 178, "cadencia": 182, "tipo_intervalo": "bloque_5k"},
                {"lap_numero": 4, "distancia_m": 6100.0, "tiempo_s": 1545.0, "tiempo_formateado": "25:45", "ritmo_minkm": "4:13", "fc_media": 176, "fc_max": 184, "cadencia": 184, "tipo_intervalo": "bloque_final"}
            ]
        },
        {
            "entreno": {
                "fecha": "2025-02-16 10:00:00",
                "titulo": "Media Maratón de Orihuela 2025",
                "deporte": "running",
                "distancia_km": 21.1,
                "tiempo_total_s": 5580,
                "tiempo_formateado": "01:33:00",
                "ritmo_medio_minkm": "4:24",
                "fc_media": 168,
                "fc_max": 181,
                "cadencia_media": 180,
                "calorias": 1550,
                "ubicacion": "Orihuela",
                "notas_entrenador": "Buen ritmo constante",
                "fit_hash": "demo_hash_orihuela_2025"
            },
            "laps": []
        }
    ]

    for item in ejemplos:
        database.guardar_entrenamiento(item["entreno"], item["laps"])
    print("Datos de ejemplo cargados con éxito.")

if __name__ == "__main__":
    cargar_datos_ejemplo()
