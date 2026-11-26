import os
import re
import json
import urllib.request
from datetime import datetime, timedelta
from html.parser import HTMLParser
from typing import List, Dict, Any, Tuple, Optional
import database

CONFIG_FILE = os.path.join(os.path.dirname(__file__), "config_entrenador.json")

def obtener_doc_url(usuario_id: Optional[int] = None) -> Optional[str]:
    """
    Devuelve la URL del documento de Google Docs del atleta correspondiente.
    Cada atleta es 100% independiente y nunca se devuelve el plan de otro atleta.
    """
    if usuario_id is not None:
        try:
            u = database.obtener_usuario_por_id(usuario_id)
            if u and u.get("doc_plan_url"):
                return u["doc_plan_url"]
        except Exception:
            pass

    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("doc_url")
        except Exception:
            pass
    return None

def guardar_doc_url(url: str):
    """Guarda la URL del documento."""
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump({"doc_url": url.strip()}, f, indent=2)

def extraer_id_documento(url: str) -> Optional[str]:
    """Extrae el identificador único del Google Doc a partir de su enlace."""
    if not url:
        return None
    match = re.search(r'/document/d/([a-zA-Z0-9-_]+)', url)
    return match.group(1) if match else None

class GoogleDocTableParser(HTMLParser):
    """Parsea el HTML exportado de Google Docs para extraer tablas de entrenamiento."""
    def __init__(self):
        super().__init__()
        self.in_cell = False
        self.cell_data = []
        self.rows = []
        self.curr_row = []

    def handle_starttag(self, tag, attrs):
        if tag == 'tr':
            self.curr_row = []
        elif tag in ('td', 'th'):
            self.in_cell = True
            self.cell_data = []
        elif tag in ('p', 'div', 'br', 'li') and self.in_cell:
            self.cell_data.append('\n')

    def handle_endtag(self, tag):
        if tag == 'tr':
            if any(self.curr_row):
                self.rows.append(self.curr_row)
        elif tag in ('td', 'th'):
            self.in_cell = False
            texto = ''.join(self.cell_data).strip()
            # Limpiar espacios repetidos en la misma línea pero conservar saltos
            lineas = [re.sub(r'[ \t]+', ' ', l).strip() for l in texto.split('\n')]
            self.curr_row.append('\n'.join(l for l in lineas if l))
        elif tag in ('p', 'div') and self.in_cell:
            self.cell_data.append('\n')

    def handle_data(self, data):
        if self.in_cell:
            self.cell_data.append(data)

def generar_titulo_amigable(texto_plan: str) -> str:
    """Genera un título corto y representativo a partir de la descripción del entrenador."""
    t = texto_plan.strip()
    # Separar con espacios zonas como @z1, @z2 para evitar que se peguen a números
    t = re.sub(r'(@z\d+)', r'\1 ', t)
    t = re.sub(r'([A-Za-z]+)(\d+x\d+)', r'\1 \2', t)

    # Caso competición
    if "MEDIA MARATÓN" in t.upper() or "MARATÓN" in t.upper() or "CARRERA" in t.upper():
        match_carrera = re.search(r'“?([A-ZÁÉÍÓÚ\s]+MARATÓN[A-ZÁÉÍÓÚ\s]*)”?|“([^”]+)”', t, re.IGNORECASE)
        if match_carrera:
            return (match_carrera.group(1) or match_carrera.group(2)).strip().strip('“”"')
        return "Competición"

    # Caso Series (ej: 8x1000, 15x400, 5x2000, 8x300 + 1000m, 5x1.000m, 5x1k) usando límites de palabra
    match_series = re.search(r'\b(\d+\s*x\s*\d+(?:\.\d{3})*(?:km?|m)?)\b\s*(?:Rec\s*([0-9’"”\s]+))?', t, re.IGNORECASE)
    if match_series:
        serie_name = re.sub(r'\s+', '', match_series.group(1))
        serie_name = re.sub(r'(\d+)\.(\d{3})', r'\1\2', serie_name)
        m_km_rep = re.match(r'^(\d+x)(\d+)km?$', serie_name, re.IGNORECASE)
        if m_km_rep:
            serie_name = f"{m_km_rep.group(1)}{int(m_km_rep.group(2)) * 1000}m"
        rec = match_series.group(2).strip() if match_series.group(2) else ""

        # Comprobar si hay una serie o bloque adicional posterior (ej: 1000m @ 3.30, + 1x1000, + 1000m)
        pos_fin = match_series.end()
        resto = t[pos_fin:]
        m_extra = re.search(r'(?:[\+\n\r]+|\brec\s+[^\n\r]+[\n\r]+)\s*(?:(\d+\s*x\s*\d+m?)|(\b\d{3,4}\s*m?\b))\s*(?:@\s*([0-9\.:]+))?', resto, re.IGNORECASE)
        extra = ""
        if m_extra:
            cand = m_extra.group(1) or m_extra.group(2)
            if cand and not any(cand.strip().lower().startswith(x) for x in ['km', 'kms', 'min', 'seg', 'z']):
                cd = cand.strip()
                if not cd.endswith('m') and 'x' not in cd:
                    cd += 'm'
                extra = f" + {cd}"
                if m_extra.group(3):
                    extra += f" @{m_extra.group(3)}"

        base = f"Series {serie_name}"
        if rec and not extra:
            return f"{base} (Rec {rec})"
        elif extra:
            return f"{base}{extra}"
        return base

    # Caso Long Run / Tirada Larga
    if "LONG RUN" in t.upper() or "TIRADA" in t.upper():
        match_km = re.search(r'\b(\d+)\s*kms?', t, re.IGNORECASE)
        km_str = f" {match_km.group(1)}k" if match_km else ""
        return f"Long Run{km_str} @z1/z2"

    # Caso Test / Control
    if "test" in t.lower() or "control" in t.lower():
        match_km = re.search(r'\b(\d+)\s*kms?', t, re.IGNORECASE)
        km_str = f" {match_km.group(1)}k" if match_km else ""
        return f"Test{km_str}"

    # Caso Rodaje estándar
    match_rodaje = re.search(r'\b(\d+)\s*kms?', t, re.IGNORECASE)
    if match_rodaje:
        km = match_rodaje.group(1)
        if "fuerza" in t.lower():
            return f"Rodaje {km}k + Fuerza"
        elif "progresivo" in t.lower() or "4x100" in t:
            return f"Activación {km}k + 4x100m"
        return f"Rodaje {km} kms"

    if "descanso" in t.lower():
        return "Descanso"

    t_clean = re.sub(r'[\n\r]+', ' ', t)
    return t_clean[:35]

def descargar_plan_entrenador(doc_url: Optional[str] = None, anio_defecto: int = 2026) -> List[Dict[str, Any]]:
    """
    Descarga el documento de Google Docs en tiempo real y parsea los días de entrenamiento.
    PRINCIPIO DE INDEPENDENCIA TOTAL: Cada atleta tiene su propio documento. Si un atleta
    no tiene URL asignada, se devuelve lista vacía y NUNCA se recurre al plan de otro atleta.
    """
    if not doc_url or not doc_url.strip():
        return []

    doc_id = extraer_id_documento(doc_url)
    if not doc_id:
        return []

    cache_file = os.path.join(os.path.dirname(__file__), f".cache_plan_{doc_id}.json")

    export_url = f"https://docs.google.com/document/d/{doc_id}/export?format=html"
    req = urllib.request.Request(export_url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})

    try:
        with urllib.request.urlopen(req, timeout=12) as resp:
            html_content = resp.read().decode("utf-8")
    except Exception as e:
        # Si falla la descarga en vivo (timeout de red, sin conexión), recuperar del caché local si existe
        if os.path.exists(cache_file):
            try:
                with open(cache_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        raise e

    parser = GoogleDocTableParser()
    parser.feed(html_content)

    dias_nombre = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
    plan_dias = []

    for fila in parser.rows:
        if len(fila) < 8:
            continue
        col_semana = fila[0].strip()

        # Buscar formato tipo '09-11 al 15-11' o '02-11 a 08-11'
        match_semana = re.search(r'(\d{1,2})-(\d{1,2})\s*(?:al?|a)\s*(\d{1,2})-(\d{1,2})', col_semana)
        if not match_semana:
            continue

        d_ini, m_ini = int(match_semana.group(1)), int(match_semana.group(2))
        try:
            fecha_lunes = datetime(anio_defecto, m_ini, d_ini)
        except ValueError:
            continue

        for i, dia_nombre in enumerate(dias_nombre):
            indice_col = i + 1
            if indice_col < len(fila):
                texto_entreno = fila[indice_col].strip()
                if not texto_entreno:
                    continue

                fecha_dia = fecha_lunes + timedelta(days=i)
                fecha_str = fecha_dia.strftime("%Y-%m-%d")

                es_descanso = "descanso" in texto_entreno.lower()
                es_series = bool(
                    re.search(r'\d+\s*x\s*\d+', texto_entreno, re.IGNORECASE)
                    or "test" in texto_entreno.lower()
                    or "control" in texto_entreno.lower()
                )
                es_carrera = "maratón" in texto_entreno.lower() or "carrera" in texto_entreno.lower()

                plan_dias.append({
                    "fecha": fecha_str,
                    "dia_semana": dia_nombre,
                    "semana": col_semana,
                    "descripcion": texto_entreno,
                    "titulo_sugerido": generar_titulo_amigable(texto_entreno),
                    "es_descanso": es_descanso,
                    "es_series": es_series,
                    "es_carrera": es_carrera
                })

    if plan_dias:
        try:
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(plan_dias, f, ensure_ascii=False)
        except Exception:
            pass

    return plan_dias

def conciliar_plan_con_garmin(plan_dias: List[Dict[str, Any]], usuario_id: int = 1) -> Dict[str, Any]:
    """
    Compara el plan del entrenador contra los entrenamientos reales en la base de datos de Garmin para un atleta específico.
    Detecta:
    - Entrenamientos cumplidos en el mismo día.
    - Entrenamientos desplazados de día (ej: tocaba el día 12 pero se hizo el día 13).
    - Entrenamientos pendientes o futuros.
    - Preguntas de confirmación para el usuario.
    """
    conn = database.get_connection()
    cursor = conn.cursor()

    # Obtener entrenamientos reales desde la fecha inicial del plan
    if not plan_dias:
        conn.close()
        return {"comparativa": [], "preguntas_discrepancias": []}

    fecha_min = min(p["fecha"] for p in plan_dias)
    fecha_max = max(p["fecha"] for p in plan_dias)
    # Extender 3 días por posibles desplazamientos
    fecha_min_ext = (datetime.strptime(fecha_min, "%Y-%m-%d") - timedelta(days=2)).strftime("%Y-%m-%d")
    fecha_max_ext = (datetime.strptime(fecha_max, "%Y-%m-%d") + timedelta(days=2)).strftime("%Y-%m-%d")

    cursor.execute("""
        SELECT id, fecha, titulo, distancia_km, tiempo_formateado, ritmo_medio_minkm, notas_entrenador
        FROM entrenamientos
        WHERE usuario_id = ? AND fecha >= ? AND fecha <= ? || ' 23:59:59'
        ORDER BY fecha ASC
    """, (usuario_id, fecha_min_ext, fecha_max_ext))
    entrenos_reales = [dict(r) for r in cursor.fetchall()]
    conn.close()

    # Mapear entrenos por fecha (YYYY-MM-DD)
    mapa_reales = {}
    for e in entrenos_reales:
        f_dia = e["fecha"][:10]
        if f_dia not in mapa_reales:
            mapa_reales[f_dia] = []
        mapa_reales[f_dia].append(e)

    hoy_str = datetime.now().strftime("%Y-%m-%d")
    ids_reales_asignados = set()
    items_map = {}
    preguntas_discrepancias = []

    # ==================== PASO 1: EMPAREJAMIENTO EXACTO POR FECHA ====================
    for p in plan_dias:
        f_plan = p["fecha"]
        plan_desc = p["descripcion"]
        es_descanso = p["es_descanso"]

        item = {
            "fecha": f_plan,
            "dia_semana": p["dia_semana"],
            "plan_descripcion": plan_desc,
            "titulo_sugerido": p["titulo_sugerido"],
            "es_series": p["es_series"],
            "es_descanso": es_descanso,
            "estado": "Pendiente",
            "garmin_entreno": None,
            "diferencia_dias": 0
        }

        # Comprobar si hay entreno en la fecha exacta
        if f_plan in mapa_reales and mapa_reales[f_plan]:
            candidatos_dia = mapa_reales[f_plan]
            e_real = max(candidatos_dia, key=lambda x: x["distancia_km"])
            item["garmin_entreno"] = e_real

            # Registrar todos los entrenos de ese día como asignados a su fecha exacta
            for cand in candidatos_dia:
                ids_reales_asignados.add(cand["id"])

            if es_descanso:
                item["estado"] = "⚠️ Entreno en día de descanso"
                preguntas_discrepancias.append({
                    "tipo": "descanso_con_entreno",
                    "plan_fecha": f_plan,
                    "entreno_id": e_real["id"],
                    "mensaje": f"El {p['dia_semana']} {f_plan} estaba planificado como Descanso, pero registraste un entreno de {e_real['distancia_km']} km en Garmin (*{e_real['titulo']}*)."
                })
            else:
                item["estado"] = "✅ Cumplido (Mismo día)"

        elif es_descanso:
            if f_plan <= hoy_str:
                item["estado"] = "💤 Descanso respetado"
            else:
                item["estado"] = "📅 Futuro"
        else:
            if f_plan == hoy_str:
                item["estado"] = "⏳ Programado para hoy"
            elif f_plan > hoy_str:
                item["estado"] = "📅 Futuro"
            # Si f_plan < hoy_str se evaluará en el Paso 2 si hubo desplazamiento

        items_map[f_plan] = item

    # ==================== PASO 2: BUSCAR DESPLAZAMIENTOS SOLO EN ENTRENOS LIBRES ====================
    for p in plan_dias:
        f_plan = p["fecha"]
        item = items_map[f_plan]

        # Solo buscar desplazados si era entreno planificado en el pasado que no tuvo sesión exacta
        if not p["es_descanso"] and item["garmin_entreno"] is None and f_plan < hoy_str:
            f_dt = datetime.strptime(f_plan, "%Y-%m-%d")
            desplazado_encontrado = None

            for offset in [1, -1, 2, -2]:
                f_cand = (f_dt + timedelta(days=offset)).strftime("%Y-%m-%d")
                if f_cand in mapa_reales:
                    for cand in mapa_reales[f_cand]:
                        # CRÍTICO: Nunca robar un entreno que ya corresponde a su propio día exacto
                        if cand["id"] not in ids_reales_asignados:
                            desplazado_encontrado = (cand, offset, f_cand)
                            break
                if desplazado_encontrado:
                    break

            if desplazado_encontrado:
                e_mov, offset, f_mov = desplazado_encontrado
                item["garmin_entreno"] = e_mov
                item["diferencia_dias"] = offset
                item["estado"] = f"🔄 Movido ({'+' if offset > 0 else ''}{offset} días)"
                ids_reales_asignados.add(e_mov["id"])

                preguntas_discrepancias.append({
                    "tipo": "entreno_movido",
                    "plan_fecha": f_plan,
                    "real_fecha": f_mov,
                    "entreno_id": e_mov["id"],
                    "plan_desc": p["titulo_sugerido"],
                    "mensaje": f"¿El entrenamiento del {p['dia_semana']} {f_plan} (*{p['titulo_sugerido']}*) lo realizaste el día {f_mov}? En tu Garmin aparece ese día una sesión de {e_mov['distancia_km']} km (*{e_mov['titulo']}*)."
                })
            else:
                item["estado"] = "❌ No registrado en Garmin"
                preguntas_discrepancias.append({
                    "tipo": "no_realizado",
                    "plan_fecha": f_plan,
                    "plan_desc": p["titulo_sugerido"],
                    "mensaje": f"El entrenamiento del {p['dia_semana']} {f_plan} (*{p['titulo_sugerido']}*) no aparece registrado en tu Garmin. ¿Fue día de descanso imprevisto o cambiaste de día?"
                })

    comparativa = [items_map[p["fecha"]] for p in plan_dias]

    return {
        "comparativa": comparativa,
        "preguntas_discrepancias": preguntas_discrepancias
    }

def aplicar_etiquetas_entrenador(comparativa: List[Dict[str, Any]]) -> int:
    """
    Renombra los entrenamientos genéricos de Garmin con el título del míster
    y guarda la prescripción en notas_entrenador.
    Prioriza estrictamente los emparejamientos de fecha exacta sobre los desplazados.
    """
    conn = database.get_connection()
    cursor = conn.cursor()
    actualizados = 0
    ids_procesados = set()

    # Priorizar emparejamientos exactos ("✅ Cumplido (Mismo día)") sobre desplazados
    items_ordenados = sorted(
        comparativa,
        key=lambda x: 0 if "Mismo día" in x.get("estado", "") else 1
    )

    for item in items_ordenados:
        e = item.get("garmin_entreno")
        if not e or not item.get("titulo_sugerido"):
            continue

        if item.get("es_descanso"):
            # No sobreescribir el título de un entreno real con "Descanso"
            continue

        e_id = e["id"]
        if e_id in ids_procesados:
            continue

        nuevo_titulo = item["titulo_sugerido"]
        notas = item.get("plan_descripcion", "")

        cursor.execute("SELECT titulo, notas_entrenador FROM entrenamientos WHERE id = ?", (e_id,))
        row_actual = cursor.fetchone()
        if row_actual:
            tit_db, notas_db = row_actual[0], row_actual[1]
            if tit_db != nuevo_titulo or notas_db != notas:
                cursor.execute("""
                    UPDATE entrenamientos
                    SET titulo = ?, notas_entrenador = ?
                    WHERE id = ?
                """, (nuevo_titulo, notas, e_id))
                actualizados += 1

        ids_procesados.add(e_id)

    conn.commit()
    conn.close()
    return actualizados

if __name__ == "__main__":
    plan = descargar_plan_entrenador()
    print(f"Total sesiones planificadas: {len(plan)}")
    res = conciliar_plan_con_garmin(plan)
    print(f"Comparativas generadas: {len(res['comparativa'])}")
    print(f"Discrepancias detectadas: {len(res['preguntas_discrepancias'])}")
    for p in res['preguntas_discrepancias']:
        print(" ->", p["mensaje"])
