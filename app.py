import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import os
import tempfile
import time
import re
from typing import Tuple, List, Dict, Any, Optional
from datetime import datetime, date, timedelta

import database
import garmin_sync
import coros_sync
import strava_sync
import importlib
import consultas_ai
importlib.reload(consultas_ai)
import plan_entrenador

st.set_page_config(
    page_title="SportTracks AI - Tu historial de entrenamientos con IA",
    page_icon="🏃",
    layout="wide"
)

# Keepalive automático y prevención de traducción automática del navegador
components.html(
    """
    <script>
    try {
        const doc = window.parent.document;
        if (doc) {
            doc.documentElement.setAttribute('translate', 'no');
            doc.documentElement.classList.add('notranslate');
        }
    } catch (e) {}

    if (!window.keepAliveSet) {
        window.keepAliveSet = true;
        setInterval(function() {
            try {
                window.parent.postMessage({type: 'streamlit:ping'}, '*');
            } catch (e) {}
        }, 25000);
    }
    </script>
    """,
    height=0,
    width=0
)

# Inicializar Base de Datos una única vez por sesión
if "db_initialized" not in st.session_state:
    database.init_db()
    st.session_state.db_initialized = True

# Cargar imagen de fondo Team Ardil en base64
bg_image_path = os.path.join(os.path.dirname(__file__), "team_ardil_bg.jpg")
b64_bg = ""
if os.path.exists(bg_image_path):
    try:
        import base64
        with open(bg_image_path, "rb") as f:
            b64_bg = base64.b64encode(f.read()).decode("utf-8")
    except Exception:
        pass

# ==================== CSS GLOBAL ESTILO GARMIN CONNECT WEB (FONDO LISO ELEGANTE) ====================
st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Open+Sans:wght@400;600;700;800&display=swap');

html, body, [data-testid="stAppViewContainer"] {{
    font-family: 'Open Sans', 'Segoe UI', -apple-system, BlinkMacSystemFont, Roboto, sans-serif !important;
    background-color: #F4F6F8 !important;
    background-image: none !important;
    color: #181C20 !important;
}}

[data-testid="stHeader"] {{
    background-color: transparent !important;
}}

[data-testid="stMain"] {{
    background-color: #F4F6F8 !important;
}}

.main .block-container {{
    background: transparent !important;
    max-width: 1400px !important;
    padding-top: 1.2rem !important;
}}

/* Topbar Garmin Connect */
.garmin-topbar {{
    background: rgba(24, 28, 32, 0.96) !important;
    backdrop-filter: blur(10px) !important;
    -webkit-backdrop-filter: blur(10px) !important;
    padding: 14px 24px;
    border-radius: 12px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 20px;
    box-shadow: 0 4px 14px rgba(0,0,0,0.18);
    border: 1px solid rgba(255, 255, 255, 0.1);
}}

.garmin-logo-badge {{
    background: #007CC3;
    width: 42px;
    height: 42px;
    border-radius: 10px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 24px;
}}

.garmin-brand-title {{
    color: #FFFFFF;
    font-weight: 800;
    font-size: 19px;
    letter-spacing: 0.8px;
    font-family: 'Open Sans', 'Segoe UI', sans-serif;
    margin: 0;
    line-height: 1.1;
}}

.garmin-brand-sub {{
    color: #94A3B8;
    font-size: 12px;
    margin: 0;
}}

.garmin-device-pill {{
    background: rgba(255, 255, 255, 0.08);
    border: 1px solid rgba(255, 255, 255, 0.15);
    padding: 6px 14px;
    border-radius: 20px;
    color: #E2E8F0;
    font-size: 12px;
    display: flex;
    align-items: center;
    gap: 8px;
}}

.garmin-avatar {{
    background: linear-gradient(135deg, #007CC3, #00A3E0);
    color: #FFFFFF;
    width: 38px;
    height: 38px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-weight: 800;
    font-size: 14px;
    box-shadow: 0 2px 6px rgba(0, 124, 195, 0.4);
}}

/* Tabs estilo Garmin Connect */
div[data-baseweb="tab-list"] {{
    background-color: #FFFFFF !important;
    padding: 6px 12px !important;
    border-radius: 12px !important;
    border: 1px solid #E2E8F0 !important;
    box-shadow: 0 2px 6px rgba(0,0,0,0.04) !important;
    gap: 6px !important;
    margin-bottom: 20px !important;
}}

button[data-baseweb="tab"] {{
    font-family: 'Open Sans', 'Segoe UI', sans-serif !important;
    font-size: 13.5px !important;
    font-weight: 600 !important;
    color: #475569 !important;
    border-radius: 8px !important;
    padding: 8px 16px !important;
    transition: all 0.2s ease !important;
    border: none !important;
}}

button[data-baseweb="tab"]:hover {{
    color: #007CC3 !important;
    background-color: #F1F5F9 !important;
}}

button[data-baseweb="tab"][aria-selected="true"] {{
    color: #007CC3 !important;
    background-color: #E8F4FA !important;
    font-weight: 700 !important;
    border-bottom: 3px solid #007CC3 !important;
}}

/* Tarjetas y Contenedores Garmin */
.garmin-card {{
    background: #FFFFFF !important;
    border: 1px solid #E2E8F0 !important;
    border-radius: 12px;
    padding: 20px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.04);
    margin-bottom: 16px;
}}

.garmin-card-header {{
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 14px;
    padding-bottom: 10px;
    border-bottom: 1px solid #F1F5F9;
}}

.garmin-card-title {{
    font-size: 13px;
    font-weight: 700;
    color: #181C20;
    text-transform: uppercase;
    letter-spacing: 0.6px;
    display: flex;
    align-items: center;
    gap: 8px;
}}

.garmin-badge-green {{
    background: #E8F8F0;
    color: #008744;
    border: 1px solid #A3E4BE;
    padding: 4px 10px;
    border-radius: 12px;
    font-size: 11px;
    font-weight: 700;
}}

.garmin-badge-blue {{
    background: #EBF5FB;
    color: #007CC3;
    border: 1px solid #A3D4F7;
    padding: 4px 10px;
    border-radius: 12px;
    font-size: 11px;
    font-weight: 700;
}}

.garmin-badge-orange {{
    background: #FFF7ED;
    color: #C2410C;
    border: 1px solid #FDBA74;
    padding: 4px 10px;
    border-radius: 12px;
    font-size: 11px;
    font-weight: 700;
}}

.garmin-badge-gray {{
    background: #F1F5F9;
    color: #64748B;
    border: 1px solid #CBD5E1;
    padding: 4px 10px;
    border-radius: 12px;
    font-size: 11px;
    font-weight: 700;
}}

/* Botones estilo Garmin */
div.stButton > button:first-child {{
    background-color: #007CC3 !important;
    color: #FFFFFF !important;
    font-weight: 600 !important;
    border-radius: 8px !important;
    border: none !important;
    padding: 8px 18px !important;
    transition: all 0.2s ease !important;
}}

div.stButton > button:first-child:hover {{
    background-color: #0066A2 !important;
    color: #FFFFFF !important;
}}
</style>
""", unsafe_allow_html=True)

# Detección dinámica de dispositivos/plataformas conectadas
token_dir_garmin = os.path.join(os.path.dirname(__file__), ".garmin_tokens")
tiene_garmin = os.path.isfile(os.path.join(token_dir_garmin, "garmin_tokens.json"))
tiene_coros = coros_sync.obtener_tokens_guardados() is not None
tiene_strava = strava_sync.obtener_tokens_strava() is not None

marcas_conectadas = []
if tiene_garmin:
    marcas_conectadas.append("Garmin")
if tiene_coros:
    marcas_conectadas.append("COROS")
if tiene_strava:
    marcas_conectadas.append("Strava")

if marcas_conectadas:
    dispositivo_txt = " · ".join(marcas_conectadas)
    pill_device_html = f"<span>⌚ {dispositivo_txt}</span><span style='color: #64748B;'>|</span><span style='color: #10B981; font-weight: 700;'>● Conectado</span>"
else:
    pill_device_html = "<span>⌚ Dispositivo</span><span style='color: #64748B;'>|</span><span style='color: #F59E0B; font-weight: 700;'>● Sin vincular</span>"

def sincronizar_actividades_todas(max_acts: int = 30) -> Tuple[int, int, str]:
    """
    Sincroniza automáticamente los entrenamientos desde cualquiera de las plataformas
    que tengan sesión activa (Garmin Connect, COROS Training Hub o Strava).
    """
    mensajes = []
    total_nuevas = 0
    total_omitidas = 0
    plataformas_activas = 0

    # 1. Garmin Connect
    token_dir_g = os.path.join(os.path.dirname(__file__), ".garmin_tokens")
    token_file_g = os.path.join(token_dir_g, "garmin_tokens.json")
    if not os.path.isfile(token_file_g):
        tokens_cloud = None
        try:
            tokens_cloud = st.secrets.get("GARMIN_TOKENS_JSON") or os.environ.get("GARMIN_TOKENS_JSON")
        except Exception:
            pass
        if tokens_cloud:
            os.makedirs(token_dir_g, exist_ok=True)
            with open(token_file_g, "w", encoding="utf-8") as f:
                f.write(tokens_cloud)

    if os.path.isfile(token_file_g):
        plataformas_activas += 1
        try:
            cliente, _ = garmin_sync.conectar_garmin("", tokenstore_dir=token_dir_g)
            nuevas_g, omit_g = garmin_sync.descargar_historial_garmin(cliente, max_actividades=max_acts)
            total_nuevas += nuevas_g
            total_omitidas += omit_g
            if nuevas_g > 0:
                mensajes.append(f"Garmin: {nuevas_g} nuevo(s)")
            else:
                mensajes.append("Garmin al día")
        except Exception as e:
            mensajes.append(f"Garmin: {e}")

    # 2. COROS Training Hub
    if coros_sync.obtener_tokens_guardados():
        plataformas_activas += 1
        try:
            res_c = coros_sync.sincronizar_actividades_coros(max_actividades=max_acts)
            if res_c.get("status") == "ok":
                n_c = res_c.get("nuevos", 0)
                o_c = res_c.get("existentes", 0)
                total_nuevas += n_c
                total_omitidas += o_c
                if n_c > 0:
                    mensajes.append(f"COROS: {n_c} nuevo(s)")
                else:
                    mensajes.append("COROS al día")
            else:
                mensajes.append(f"COROS: {res_c.get('mensaje')}")
        except Exception as e:
            mensajes.append(f"COROS: {e}")

    # 3. Strava
    if strava_sync.obtener_tokens_strava():
        plataformas_activas += 1
        try:
            res_s = strava_sync.sincronizar_actividades_strava(max_actividades=max_acts)
            if res_s.get("status") == "ok":
                n_s = res_s.get("nuevos", 0)
                o_s = res_s.get("existentes", 0)
                total_nuevas += n_s
                total_omitidas += o_s
                if n_s > 0:
                    mensajes.append(f"Strava: {n_s} nuevo(s)")
                else:
                    mensajes.append("Strava al día")
            else:
                mensajes.append(f"Strava: {res_s.get('mensaje')}")
        except Exception as e:
            mensajes.append(f"Strava: {e}")

    if plataformas_activas == 0:
        return 0, 0, "No hay ninguna plataforma vinculada todavía. Puedes conectar tu cuenta de Garmin, COROS o Strava en la pestaña '👤 Personal'."

    if total_nuevas > 0:
        try:
            import sync_sporttracks
            sync_sporttracks.sync_file("sporttracks.db", commit_msg=f"Sincronización manual: {total_nuevas} nuevo(s) [skip ci]")
        except Exception:
            pass

    detalle = " · ".join(mensajes)
    return total_nuevas, total_omitidas, detalle

# Encabezado SportTracks AI con icono e insignia oficial Team Ardil
ardil_icon_html = f'<img src="data:image/jpeg;base64,{b64_bg}" style="width: 46px; height: 46px; border-radius: 10px; object-fit: cover; border: 1.5px solid rgba(255,255,255,0.3); box-shadow: 0 2px 8px rgba(0,0,0,0.4);" alt="Team Ardil">' if b64_bg else '<span class="garmin-logo-badge">🏃</span>'
ardil_pill_html = f'<div class="notranslate" translate="no" style="display: flex; align-items: center; gap: 8px; background: rgba(255,255,255,0.12); padding: 4px 14px 4px 6px; border-radius: 20px; border: 1px solid rgba(255,255,255,0.18);"><img src="data:image/jpeg;base64,{b64_bg}" style="width: 26px; height: 26px; border-radius: 50%; object-fit: cover;"><span style="font-weight: 800; color: #FFFFFF; font-size: 12px; letter-spacing: 0.6px;">TEAM ARDIL</span></div>' if b64_bg else '<span class="notranslate" translate="no" style="background: rgba(255,255,255,0.12); padding: 5px 12px; border-radius: 8px; font-weight: 800; color: #FFFFFF; font-size: 12px; letter-spacing: 0.5px;">TEAM ARDIL</span>'

st.markdown(f"""
<div class="garmin-topbar notranslate" translate="no">
    <div style="display: flex; align-items: center; gap: 14px;">
        {ardil_icon_html}
        <div class="notranslate" translate="no">
            <div class="garmin-brand-title notranslate" translate="no">
                SPORTTRACKS<span style="color: #00A3E0; font-size: 13px; vertical-align: super;"> AI</span>
            </div>
            <div class="garmin-brand-sub notranslate" translate="no">Team Ardil · Athletics Coach | Salva Andreo</div>
        </div>
    </div>
    <div style="display: flex; align-items: center; gap: 16px;">
        {ardil_pill_html}
        <div class="garmin-device-pill notranslate" translate="no">
            {pill_device_html}
        </div>
        <div class="garmin-avatar notranslate" translate="no">SA</div>
    </div>
</div>
""", unsafe_allow_html=True)

# Resumen superior
stats = database.obtener_resumen_estadisticas()
total_km = stats.get("total_km", 0)
total_entrenos = stats.get("total_entrenos", 0)
media_km = round(total_km / max(1, total_entrenos), 1)

doc_url = plan_entrenador.obtener_doc_url()

@st.cache_data(ttl=120)
def cargar_plan_y_comparativa(url_doc):
    try:
        p_dias = plan_entrenador.descargar_plan_entrenador(url_doc)
        reconc = plan_entrenador.conciliar_plan_con_garmin(p_dias)
        return p_dias, reconc
    except Exception as e:
        return [], {"comparativa": [], "preguntas_discrepancias": []}

plan_dias, reconciliacion = cargar_plan_y_comparativa(doc_url)
comparativa_plan = reconciliacion.get("comparativa", [])

def es_sesion_series_real(entreno_id: int, fecha: str, titulo: str, notas: str = "", plan_comparativa: list = None) -> bool:
    """
    Verifica de forma estricta si una actividad es verdaderamente una sesión de series.
    Regla del entrenador:
    1. Si la fecha está en el plan del entrenador, SOLO es serie si el entrenador indicó series explícitamente.
       Si en el plan pone carrera, rodaje, descanso, tirada o fuerza sin series, NUNCA es serie.
    2. Si es una fecha fuera del plan (histórico):
       - Se descartan carreras, competiciones y rodajes continuos.
       - Se verifica si existen pausas/recuperaciones intermedias entre vueltas o título explícito.
    """
    f_dia = str(fecha)[:10]

    # 1. Comprobación contra el Plan del Entrenador (Prioridad absoluta)
    if plan_comparativa:
        for p in plan_comparativa:
            if p.get("fecha") == f_dia:
                desc = (p.get("plan_descripcion") or "").lower()
                tit_sug = (p.get("titulo_sugerido") or "").lower()
                tiene_patron = bool(re.search(r'\b\d+\s*x\s*\d+', desc) or "serie" in desc or "series" in tit_sug)
                if p.get("es_series") or tiene_patron:
                    return True
                return False

    # 2. Descarte por palabras clave excluyentes (carreras, competiciones, rodajes continuos)
    texto = f"{titulo or ''} {notas or ''}".lower()
    palabras_excluidas = [
        "maratón", "maraton", "media maratón", "media maraton", "carrera",
        "competición", "competicion", "dorsal", "10k", "5k", "san silvestre",
        "trail", "cross", "trofeo", "campeonato", "rodaje", "tirada",
        "long run", "suave", "regenerativo", "recuperación", "recuperacion", "caco"
    ]
    palabras_series = ["serie", "series", "interval", "x1000", "x400", "x2000", "x500", "x200", "x800", "x1500"]

    if any(p in texto for p in palabras_excluidas) and not any(s in texto for s in palabras_series):
        return False

    # 3. Comprobar si tiene estructura de series con recuperaciones entre repeticiones
    try:
        _, laps = database.obtener_detalle_entrenamiento(entreno_id)
        if laps:
            _, resumen = database.clasificar_vueltas_sesion(laps)
            if resumen.get("num_recuperaciones", 0) >= 1:
                return True
            if bool(re.search(r'\b\d+\s*x\s*\d+', texto) or any(s in texto for s in palabras_series)):
                return True
    except Exception:
        pass

    return False

# ==================== HELPERS DE ESTILO POWER BI / GARMIN ====================
def aplicar_estilo_powerbi(fig, titulo="", subtitulo="", x_title="", y_title="", mostrar_grid_y=True, altura=380):
    """Estilo limpio, profesional y de alto contraste estilo Garmin Connect moderno con texto negro nítido."""
    fig.update_layout(
        title=dict(
            text=f"<b style='font-size:17px; color:#181C20; font-family:Open Sans, Segoe UI, sans-serif;'>{titulo}</b><br><span style='font-size:12px; color:#64748B;'>{subtitulo}</span>" if subtitulo else f"<b style='font-size:17px; color:#181C20; font-family:Open Sans, Segoe UI, sans-serif;'>{titulo}</b>",
            x=0.01,
            y=0.96,
            xanchor="left",
            yanchor="top"
        ),
        plot_bgcolor="rgba(0, 0, 0, 0)",
        paper_bgcolor="rgba(0, 0, 0, 0)",
        height=altura,
        margin=dict(l=20, r=20, t=65 if subtitulo else 45, b=45),
        font=dict(
            family="Open Sans, Segoe UI, -apple-system, Roboto, sans-serif",
            color="#181C20",
            size=12
        ),
        xaxis=dict(
            title=dict(text=f"<b>{x_title}</b>" if x_title else "", font=dict(size=12, color="#181C20")),
            showgrid=False,
            showline=True,
            linecolor="#000000",
            linewidth=1.5,
            tickfont=dict(size=12, color="#000000", family="Open Sans, Segoe UI"),
            zeroline=False
        ),
        yaxis=dict(
            title=dict(text=f"<b>{y_title}</b>" if y_title else "", font=dict(size=12, color="#181C20")),
            showgrid=mostrar_grid_y,
            gridcolor="#E2E8F0",
            gridwidth=1,
            showline=False,
            tickfont=dict(size=11, color="#000000", family="Open Sans, Segoe UI"),
            zeroline=False
        ),
        hoverlabel=dict(
            bgcolor="#181C20",
            font_size=12,
            font_family="Open Sans, Segoe UI, sans-serif",
            bordercolor="#007CC3"
        ),
        bargap=0.35
    )
    return fig

# Pestañas principales organizadas de forma limpia
tab_home, tab_chat, tab_plan, tab_series, tab_volumen, tab_personal = st.tabs([
    "🏠 Inicio",
    "💬 Entrenador IA (Chat)",
    "📋 Plan Entrenador",
    "⚡ Análisis de Series",
    "📈 Volumen y Carga Semanal",
    "👤 Personal"
])

# ==================== PESTAÑA 0: INICIO (GARMIN CONNECT) ====================
with tab_home:
    # --- 1. DATO: ÚLTIMO ENTRENO ---
    ultimo_entreno_raw = database.ejecutar_consulta_sql("SELECT * FROM entrenamientos ORDER BY fecha DESC LIMIT 1")
    if ultimo_entreno_raw:
        ult_entreno = ultimo_entreno_raw[0]
        f_ult_full = ult_entreno['fecha']
        f_ult = f_ult_full[:10]
        p_match = [p for p in comparativa_plan if p.get("fecha") == f_ult]
        tit_ult = p_match[0]["titulo_sugerido"] if p_match else (ult_entreno.get("titulo") or "Carrera")
        km_ult = f"{ult_entreno.get('distancia_km', 0):.2f}"
        t_ult = ult_entreno.get("tiempo_formateado", "--")
        r_ult = ult_entreno.get("ritmo_medio_minkm", "--")
        cal_ult = ult_entreno.get("calorias") or "--"
        ub_ult = ult_entreno.get("ubicacion") or "Murcia"
    else:
        tit_ult, km_ult, t_ult, r_ult, cal_ult, f_ult, ub_ult = "Sin registros", "0.00", "--", "--", "--", "--", ""

    # --- 2. DATO: PRÓXIMA COMPETICIÓN ---
    hoy_str = date.today().strftime("%Y-%m-%d")
    carreras_futuras = [
        p for p in plan_dias
        if p.get("fecha", "") >= hoy_str and (
            p.get("es_carrera") or any(k in (p.get("titulo_sugerido", "") + " " + p.get("plan_descripcion", "")).lower() for k in ["marat", "media", "competi", "carrera", "10k", "5k", "campeonato", "cross", "trail"])
        )
    ]

    if carreras_futuras:
        prox_carrera = carreras_futuras[0]
        tit_comp = prox_carrera.get("titulo_sugerido") or "Competición"
        f_comp = prox_carrera.get("fecha", "")
        try:
            d_comp = date.fromisoformat(f_comp)
            diff_dias = (d_comp - date.today()).days
            if diff_dias == 0:
                badge_comp = "¡HOY!"
                dias_comp_txt = "¡Hoy es la prueba!"
            elif diff_dias == 1:
                badge_comp = "¡MAÑANA!"
                dias_comp_txt = "En 1 día"
            else:
                badge_comp = f"EN {diff_dias} DÍAS"
                dias_comp_txt = f"{diff_dias} días restantes"
        except Exception:
            badge_comp = "PROGRAMADA"
            dias_comp_txt = f_comp

        dist_comp = "21.097 km" if "media" in tit_comp.lower() else ("42.195 km" if "marat" in tit_comp.lower() else ("10.0 km" if "10k" in tit_comp.lower() else "Oficial"))
        tipo_comp = "Asfalto Oficial"
    else:
        tit_comp = "MEDIA MARATÓN ORIHUELA"
        f_comp = "2026-11-15"
        badge_comp = "¡MAÑANA!"
        dias_comp_txt = "En 1 día"
        dist_comp = "21.097 km"
        tipo_comp = "Asfalto Oficial"

    # --- 3. DATO: ÚLTIMO DÍA DE SERIES Y DATOS (Solo series reales confirmadas por el plan) ---
    query_ult_series = """
    SELECT e.id, e.fecha, e.titulo, e.ubicacion, e.notas_entrenador
    FROM entrenamientos e
    JOIN series_laps s ON s.entrenamiento_id = e.id
    WHERE s.distancia_m >= 350
    GROUP BY e.id
    HAVING COUNT(s.id) >= 2
    ORDER BY e.fecha DESC
    LIMIT 25
    """
    candidatos_series = database.ejecutar_consulta_sql(query_ult_series)
    ult_sesion_series = [
        s for s in candidatos_series
        if es_sesion_series_real(s["id"], s["fecha"], s["titulo"], s.get("notas_entrenador", ""), comparativa_plan)
    ]
    if ult_sesion_series:
        s_id = ult_sesion_series[0]["id"]
        s_act, s_laps = database.obtener_detalle_entrenamiento(s_id)
        s_clasif, s_resumen = database.clasificar_vueltas_sesion(s_laps) if s_laps else ([], {})
        laps_s_solo = [l for l in s_clasif if str(l.get("tipo_clasificado", "")).startswith("Serie")]
        
        p_match_s = [p for p in comparativa_plan if p.get("fecha") == ult_sesion_series[0]["fecha"][:10]]
        tit_series = p_match_s[0]["titulo_sugerido"] if p_match_s else f"Series {len(laps_s_solo)}x{s_resumen.get('distancia_aprox', 1000)}m"
        f_series = ult_sesion_series[0]["fecha"][:10]
        ub_series = ult_sesion_series[0].get("ubicacion") or "Alcantarilla"
        n_series = len(laps_s_solo) if laps_s_solo else s_resumen.get("num_series", 8)
        
        if laps_s_solo:
            t_laps = [l["tiempo_s"] for l in laps_s_solo if l.get("tiempo_s")]
            mejor_t_s = min(t_laps) if t_laps else 206
            media_t_s = sum(t_laps) / len(t_laps) if t_laps else 213
            mejor_serie_str = f"{int(mejor_t_s // 60)}:{int(mejor_t_s % 60):02d}"
            media_serie_str = f"{int(media_t_s // 60)}:{int(media_t_s % 60):02d}"
        else:
            mejor_serie_str = "3:26"
            media_serie_str = "3:33"
    else:
        tit_series = "Series 8x1000 (Rec 1')"
        f_series = "2026-11-10"
        ub_series = "Alcantarilla"
        n_series = 8
        mejor_serie_str = "3:26"
        media_serie_str = "3:33"

    # 1. "Lo esencial" (3 tarjetas destacadas) con botón de Sincronizar directo
    c_hdr_es, c_hdr_sync = st.columns([4.2, 1.3])
    with c_hdr_es:
        st.markdown("<div style='margin-bottom: 8px; font-size: 13px; font-weight: 700; color: #64748B; text-transform: uppercase; letter-spacing: 0.8px; padding-top: 8px;'>⚡ Lo Esencial</div>", unsafe_allow_html=True)
    with c_hdr_sync:
        if st.button("🔄 Sincronizar", key="btn_sync_inicio", type="primary", use_container_width=True):
            with st.spinner("Sincronizando entrenamientos..."):
                nuevas, omitidas, detalle = sincronizar_actividades_todas()
            if nuevas > 0:
                st.success(f"🎉 ¡Sincronizado! **{nuevas}** nuevos entrenamientos ({detalle}).")
                time.sleep(1)
                st.rerun()
            elif "No hay ninguna plataforma" in detalle:
                st.warning(detalle)
            elif "error" in detalle.lower():
                st.error(f"Aviso durante la sincronización: {detalle}")
            else:
                st.info(f"✅ Todo al día ({detalle}).")

    c_es1, c_es2, c_es3 = st.columns(3)
    
    with c_es1:
        st.markdown(f"""
        <div class="garmin-card" style="padding: 16px; margin-bottom: 14px;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                <span style="font-size: 11px; font-weight: 700; color: #64748B; text-transform: uppercase;">🏃 Último Entreno</span>
                <span class="garmin-badge-green">Completado</span>
            </div>
            <div style="font-size: 17px; font-weight: 800; color: #181C20; margin-bottom: 2px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">
                {tit_ult}
            </div>
            <div style="font-size: 11px; color: #64748B; margin-bottom: 10px;">{f_ult} · {ub_ult}</div>
            <div style="display: flex; align-items: baseline; gap: 6px; margin-bottom: 10px;">
                <span style="font-size: 32px; font-weight: 800; color: #007CC3; line-height: 1;">{km_ult}</span>
                <span style="font-size: 14px; font-weight: 700; color: #64748B;">km</span>
                <span style="font-size: 12px; color: #64748B; margin-left: 6px;">⏱️ {t_ult}</span>
            </div>
            <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 8px; background: #F8FAFC; padding: 10px 12px; border-radius: 8px; border: 1px solid #E2E8F0;">
                <div>
                    <div style="font-size: 10px; font-weight: 700; color: #64748B; text-transform: uppercase;">⚡ Ritmo Medio</div>
                    <div style="font-size: 15px; font-weight: 800; color: #181C20;">{r_ult} <span style="font-size: 10px; font-weight: normal; color: #64748B;">/km</span></div>
                </div>
                <div>
                    <div style="font-size: 10px; font-weight: 700; color: #64748B; text-transform: uppercase;">🔥 Calorías</div>
                    <div style="font-size: 15px; font-weight: 800; color: #181C20;">{cal_ult} <span style="font-size: 10px; font-weight: normal; color: #64748B;">kcal</span></div>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
    with c_es2:
        st.markdown(f"""
        <div class="garmin-card" style="padding: 16px; margin-bottom: 14px;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                <span style="font-size: 11px; font-weight: 700; color: #64748B; text-transform: uppercase;">🎯 Próxima Competición</span>
                <span class="garmin-badge-orange">{badge_comp}</span>
            </div>
            <div style="font-size: 17px; font-weight: 800; color: #181C20; margin-bottom: 2px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">
                {tit_comp}
            </div>
            <div style="font-size: 11px; color: #64748B; margin-bottom: 10px;">{f_comp} · {tipo_comp}</div>
            <div style="display: flex; align-items: baseline; gap: 6px; margin-bottom: 10px;">
                <span style="font-size: 32px; font-weight: 800; color: #D97706; line-height: 1;">{dist_comp}</span>
                <span style="font-size: 13px; font-weight: 700; color: #64748B; margin-left: 4px;">({dias_comp_txt})</span>
            </div>
            <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 8px; background: #FFFBEB; padding: 10px 12px; border-radius: 8px; border: 1px solid #FDE68A;">
                <div>
                    <div style="font-size: 10px; font-weight: 700; color: #B45309; text-transform: uppercase;">📅 Fecha</div>
                    <div style="font-size: 14px; font-weight: 800; color: #92400E;">{f_comp}</div>
                </div>
                <div>
                    <div style="font-size: 10px; font-weight: 700; color: #B45309; text-transform: uppercase;">🎯 Prueba</div>
                    <div style="font-size: 14px; font-weight: 800; color: #92400E;">{dist_comp}</div>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
    with c_es3:
        st.markdown(f"""
        <div class="garmin-card" style="padding: 16px; margin-bottom: 14px;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                <span style="font-size: 11px; font-weight: 700; color: #64748B; text-transform: uppercase;">⚡ Último Día de Series</span>
                <span class="garmin-badge-blue">{n_series} series</span>
            </div>
            <div style="font-size: 17px; font-weight: 800; color: #181C20; margin-bottom: 2px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">
                {tit_series}
            </div>
            <div style="font-size: 11px; color: #64748B; margin-bottom: 10px;">{f_series} · {ub_series}</div>
            <div style="display: flex; align-items: baseline; gap: 6px; margin-bottom: 10px;">
                <span style="font-size: 32px; font-weight: 800; color: #007CC3; line-height: 1;">{mejor_serie_str}</span>
                <span style="font-size: 14px; font-weight: 700; color: #64748B;">min</span>
                <span style="font-size: 12px; color: #64748B; margin-left: 6px;">(Mejor Serie)</span>
            </div>
            <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 8px; background: #F8FAFC; padding: 10px 12px; border-radius: 8px; border: 1px solid #E2E8F0;">
                <div>
                    <div style="font-size: 10px; font-weight: 700; color: #64748B; text-transform: uppercase;">⚡ Media Series</div>
                    <div style="font-size: 15px; font-weight: 800; color: #181C20;">{media_serie_str} <span style="font-size: 10px; font-weight: normal; color: #64748B;">min</span></div>
                </div>
                <div>
                    <div style="font-size: 10px; font-weight: 700; color: #64748B; text-transform: uppercase;">⏱️ Recuperación</div>
                    <div style="font-size: 15px; font-weight: 800; color: #181C20;">1' <span style="font-size: 10px; font-weight: normal; color: #64748B;">pausa</span></div>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

    # 2. "En primer plano" (In Focus)
    st.markdown("<div style='margin-top: 10px; margin-bottom: 8px; font-size: 13px; font-weight: 700; color: #64748B; text-transform: uppercase; letter-spacing: 0.8px;'>🎯 En Primer Plano</div>", unsafe_allow_html=True)
    col_focus_left, col_focus_right = st.columns([1.1, 0.9])

    with col_focus_left:
        # Actividad Reciente / Destacada
        ultimos_entrenos = database.ejecutar_consulta_sql("SELECT * FROM entrenamientos ORDER BY fecha DESC LIMIT 15")
        if ultimos_entrenos:
            opciones_entrenos = {
                f"{e['fecha'][:10]} · {e['titulo']} ({e['distancia_km']} km)": e['id']
                for e in ultimos_entrenos
            }
            # Selector compacto para cambiar de actividad
            sel_nombre = st.selectbox("Seleccionar actividad para visualizar:", list(opciones_entrenos.keys()), index=0)
            act_id = opciones_entrenos[sel_nombre]
            act_sel, laps_act = database.obtener_detalle_entrenamiento(act_id)

            if act_sel:
                fecha_act = act_sel['fecha'][:10]
                plan_match = [p for p in comparativa_plan if p.get("fecha") == fecha_act]
                titulo_plan = plan_match[0]["titulo_sugerido"] if plan_match else ""

                laps_clasificados, resumen_laps = database.clasificar_vueltas_sesion(laps_act) if laps_act else ([], {})
                es_sesion_series = resumen_laps.get("num_series", 0) > 0

                st.markdown(f"""
                <div class="garmin-card">
                    <div class="garmin-card-header">
                        <div class="garmin-card-title">
                            <span style="font-size: 18px;">🏃</span> CARRERA · {act_sel['fecha'][:10]} {act_sel['fecha'][11:16]}
                        </div>
                        <span class="garmin-badge-green">{'✅ Plan: ' + titulo_plan if titulo_plan else '🟢 Actividad Garmin'}</span>
                    </div>
                    <div style="font-size: 20px; font-weight: 800; color: #181C20; margin-bottom: 12px;">
                        {titulo_plan if titulo_plan else act_sel['titulo']}
                        <span style="font-size: 12px; font-weight: 600; color: #64748B; margin-left: 8px;">📍 {act_sel.get('ubicacion') or 'Murcia'}</span>
                    </div>
                    <div style="display: flex; align-items: baseline; gap: 8px; margin-bottom: 16px;">
                        <span style="font-size: 42px; font-weight: 800; color: #007CC3; line-height: 1;">{act_sel['distancia_km']}</span>
                        <span style="font-size: 18px; font-weight: 700; color: #64748B;">km</span>
                    </div>
                    <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; background: #F8FAFC; padding: 14px; border-radius: 10px; border: 1px solid #E2E8F0;">
                        <div>
                            <div style="font-size: 11px; font-weight: 700; color: #64748B; text-transform: uppercase;">⏱️ Tiempo</div>
                            <div style="font-size: 18px; font-weight: 800; color: #181C20;">{act_sel['tiempo_formateado']}</div>
                        </div>
                        <div>
                            <div style="font-size: 11px; font-weight: 700; color: #64748B; text-transform: uppercase;">⚡ Ritmo Medio</div>
                            <div style="font-size: 18px; font-weight: 800; color: #181C20;">{act_sel['ritmo_medio_minkm']} <span style="font-size: 11px; font-weight: normal; color: #64748B;">/km</span></div>
                        </div>
                        <div>
                            <div style="font-size: 11px; font-weight: 700; color: #64748B; text-transform: uppercase;">🔥 Calorías</div>
                            <div style="font-size: 18px; font-weight: 800; color: #181C20;">{act_sel.get('calorias') or '--'} <span style="font-size: 11px; font-weight: normal; color: #64748B;">kcal</span></div>
                        </div>
                    </div>
                </div>
                """, unsafe_allow_html=True)



    with col_focus_right:
        # Tarjeta Plan de Entrenamiento · Esta Semana (Google Docs)
        st.markdown("""
        <div class="garmin-card">
            <div class="garmin-card-header">
                <div class="garmin-card-title">
                    <span style="font-size: 18px;">📋</span> PLAN DEL ENTRENADOR · ESTA SEMANA
                </div>
                <span class="garmin-badge-blue">Google Doc</span>
            </div>
        """, unsafe_allow_html=True)

        # Mostrar los días de la semana actual
        dias_esta_sem = [
            c for c in comparativa_plan
            if "09-11" in c.get("semana", "") or "15-11" in c.get("semana", "") or any(d in c.get("fecha", "") for d in ["2026-11-09", "2026-11-10", "2026-11-11", "2026-11-12", "2026-11-13", "2026-11-14", "2026-11-15"])
        ]
        if not dias_esta_sem:
            dias_esta_sem = comparativa_plan[-7:] if comparativa_plan else []

        for d in dias_esta_sem:
            g = d.get("garmin_entreno")
            badge_cls = "garmin-badge-green" if "Cumplido" in d.get("estado", "") else ("garmin-badge-gray" if d.get("es_descanso") else "garmin-badge-orange")
            garmin_txt = f"🏃 {g['distancia_km']} km | {g['tiempo_formateado']} | {g['ritmo_medio_minkm']}/km" if g else ("💤 Descanso" if d.get("es_descanso") else "⏳ Pendiente de registrar")
            
            st.markdown(f"""
            <div style="display: flex; align-items: center; justify-content: space-between; padding: 8px 12px; margin-bottom: 8px; background: #F8FAFC; border-radius: 8px; border: 1px solid #E2E8F0;">
                <div>
                    <div style="font-size: 12px; font-weight: 700; color: #181C20;">{d.get('dia_semana', '')} · <span style="color:#64748B; font-weight:normal;">{d.get('fecha', '')}</span></div>
                    <div style="font-size: 13px; font-weight: 700; color: #007CC3;">{d.get('titulo_sugerido', '')}</div>
                    <div style="font-size: 11px; color: #64748B;">{garmin_txt}</div>
                </div>
                <span class="{badge_cls}">{d.get('estado', '')}</span>
            </div>
            """, unsafe_allow_html=True)

        st.markdown("</div>", unsafe_allow_html=True)



# ==================== PESTAÑA 1: CHAT IA CON MEMORIA ====================
with tab_chat:
    col_t1, col_t2 = st.columns([4, 1])
    with col_t1:
        st.subheader("🤖 Pregúntale a tu historial de entrenamientos")
    with col_t2:
        if st.button("🗑️ Limpiar chat", use_container_width=True):
            st.session_state.chat_history = []
            st.rerun()

    has_api = bool(consultas_ai.obtener_gemini_api_key())
    if has_api:
        st.success("🟢 **Cerebro IA Activo (Text-to-SQL con Gemini)**: Pregúntale lo que quieras sobre tus ritmos, competiciones, series o evolución.")
    else:
        st.info("ℹ️ Clave API no detectada: funcionando con el motor de reglas básicas.")

    # Inicializar memoria de chat
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []

    # Renderizar historial de mensajes
    for idx, msg in enumerate(st.session_state.chat_history):
        with st.chat_message(msg["role"]):
            # Detección retroactiva para mensajes antiguos en memoria
            faf = msg.get("frente_a_frente")
            if not faf and "### 🏅 Historial encontrado para" in msg.get("content", ""):
                m_lugar = re.search(r"Historial encontrado para '([^']+)'", msg.get("content", ""))
                if m_lugar:
                    lugar_nombre = m_lugar.group(1).lower()
                    faf = consultas_ai.obtener_datos_frente_a_frente(lugar_nombre)
                    if faf and faf.get("total_sesiones", 0) > 0:
                        msg["frente_a_frente"] = faf
                        # Reconstruir la tabla limpia sin sesiones demo antiguas
                        filas = faf["todas_filas"]
                        respuesta_md = f"### 🏅 Historial encontrado para '{lugar_nombre.capitalize()}':\n\n"
                        respuesta_md += f"Se han registrado **{len(filas)}** participaciones/sesiones:\n\n"
                        respuesta_md += "| Fecha | Título / Evento | Distancia | Tiempo | Ritmo Medio | FC Media |\n"
                        respuesta_md += "|---|---|---|---|---|---|\n"
                        for f in filas:
                            titulo_display = f["titulo"]
                            if f.get("es_calentamiento"):
                                titulo_display += " *(Calentamiento)*"
                            elif faf.get("pb") and f["fecha"][:10] == faf["pb"]["fecha"]:
                                titulo_display += " *(PB 🥇)*"
                            fc_str = f"{f['fc_media']} ppm" if f.get("fc_media") else "- ppm"
                            respuesta_md += f"| {f['fecha'][:10]} | {titulo_display} | {f['distancia_km']} km | {f['tiempo_formateado']} | {f['ritmo_medio_minkm']} min/km | {fc_str} |\n"
                        msg["content"] = respuesta_md

            st.markdown(msg["content"])
            
            # Módulo Frente a Frente si está presente en el mensaje
            if faf:
                lugar = faf["lugar"]
                n_ed = faf.get("num_ediciones", 0)
                cat_principal = faf.get("categoria_seleccionada", "Competición")
                
                # Fila de acción con botón destacado en grande a la derecha
                st.markdown("<div style='margin-top: 14px; margin-bottom: 8px;'></div>", unsafe_allow_html=True)
                col_faf_info, col_faf_btn = st.columns([2.4, 1.6])
                with col_faf_info:
                    st.markdown(f"**⚔️ Comparativa 'Frente a Frente' disponible**")
                    st.caption(f"Enfrenta tus {n_ed} ediciones de {cat_principal} en {lugar} cara a cara.")
                with col_faf_btn:
                    faf_key = f"faf_open_{idx}"
                    is_open = st.session_state.get(faf_key, False)
                    btn_text = "🔽 Ocultar Comparativa" if is_open else "⚔️ FRENTE A FRENTE"
                    if st.button(btn_text, key=f"btn_{faf_key}", type="primary", use_container_width=True):
                        st.session_state[faf_key] = not is_open
                        st.rerun()
                        
                # Si está abierto, desplegar el cuadro de mandos Frente a Frente
                if is_open:
                    # Selector de categoría si hay más de una en ese lugar
                    cats = list(faf.get("categorias", {}).keys())
                    if len(cats) > 1:
                        cat_sel = st.radio(
                            "Selecciona distancia / modalidad a comparar:",
                            cats,
                            index=cats.index(cat_principal) if cat_principal in cats else 0,
                            horizontal=True,
                            key=f"cat_rad_{idx}"
                        )
                        datos_cat = consultas_ai.generar_datos_categoria(faf["categorias"][cat_sel])
                    else:
                        cat_sel = cat_principal
                        datos_cat = faf

                    # Tarjetas KPI de Comparativa
                    pb = datos_cat.get("pb", {})
                    ultima = datos_cat.get("ultima", {})
                    promedio = datos_cat.get("promedio", {})
                    
                    st.markdown("<div style='margin-top: 10px; margin-bottom: 10px;'></div>", unsafe_allow_html=True)
                    k1, k2, k3, k4 = st.columns(4)
                    with k1:
                        st.markdown(f"""
                        <div class="metric-card" style="border-left: 4px solid #F59E0B; text-align: center; padding: 12px;">
                            <div style="font-size: 0.78rem; color: #F59E0B; font-weight: 700;">🥇 MEJOR MARCA (PB)</div>
                            <div style="font-size: 1.35rem; font-weight: 700; color: #FFFFFF; margin: 4px 0;">{pb.get('tiempo_formateado', '-')}</div>
                            <div style="font-size: 0.78rem; color: #94A3B8;">{pb.get('ritmo_minkm', '-')} min/km · Ed. {pb.get('año', '-')}</div>
                        </div>
                        """, unsafe_allow_html=True)
                    with k2:
                        st.markdown(f"""
                        <div class="metric-card" style="border-left: 4px solid #60A5FA; text-align: center; padding: 12px;">
                            <div style="font-size: 0.78rem; color: #60A5FA; font-weight: 700;">🏃 ÚLTIMA EDICIÓN</div>
                            <div style="font-size: 1.35rem; font-weight: 700; color: #FFFFFF; margin: 4px 0;">{ultima.get('tiempo_formateado', '-')}</div>
                            <div style="font-size: 0.78rem; color: #94A3B8;">{ultima.get('ritmo_minkm', '-')} min/km · Ed. {ultima.get('año', '-')}</div>
                        </div>
                        """, unsafe_allow_html=True)
                    with k3:
                        st.markdown(f"""
                        <div class="metric-card" style="border-left: 4px solid #EC4899; text-align: center; padding: 12px;">
                            <div style="font-size: 0.78rem; color: #EC4899; font-weight: 700;">⏱️ DIFERENCIA VS PB</div>
                            <div style="font-size: 1.35rem; font-weight: 700; color: #FFFFFF; margin: 4px 0;">{ultima.get('diferencia_vs_pb', '-')}</div>
                            <div style="font-size: 0.78rem; color: #94A3B8;">vs récord de {pb.get('año', '-')}</div>
                        </div>
                        """, unsafe_allow_html=True)
                    with k4:
                        st.markdown(f"""
                        <div class="metric-card" style="border-left: 4px solid #00D26A; text-align: center; padding: 12px;">
                            <div style="font-size: 0.78rem; color: #00D26A; font-weight: 700;">📊 PROMEDIO CIRCUITO</div>
                            <div style="font-size: 1.35rem; font-weight: 700; color: #FFFFFF; margin: 4px 0;">{promedio.get('tiempo_formateado', '-')}</div>
                            <div style="font-size: 0.78rem; color: #94A3B8;">Ritmo: {promedio.get('ritmo_minkm', '-')} min/km</div>
                        </div>
                        """, unsafe_allow_html=True)

                    # Gráfico Plotly
                    st.markdown("<div style='height: 8px;'></div>", unsafe_allow_html=True)
                    fig_faf = consultas_ai.generar_grafico_frente_a_frente(datos_cat.get("ediciones_cron", []), lugar, cat_sel)
                    st.plotly_chart(fig_faf, use_container_width=True)

                    # Tabla comparativa Frente a Frente
                    st.markdown("##### 📋 Cara a Cara: Desglose Edición por Edición")
                    t_md = "| Edición | Fecha | Distancia | Tiempo | Ritmo Medio | FC Media | Dif. vs PB | Estado |\n"
                    t_md += "| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :--- |\n"
                    for ed in datos_cat.get("ediciones", []):
                        fc_val = f"{ed['fc_media']} ppm" if ed.get("fc_media") else "- ppm"
                        badge_pb = "🥇 **PB (Récord)**" if ed.get("es_pb") else f"`{ed.get('diferencia_vs_pb', '-')}`"
                        año_txt = f"**{ed.get('año', '-')}**" if ed.get("es_pb") else ed.get("año", "-")
                        t_md += f"| {año_txt} | {ed.get('fecha', '-')} | {ed.get('distancia_km', '-')} km | **{ed.get('tiempo_formateado', '-')}** | {ed.get('ritmo_minkm', '-')} min/km | {fc_val} | {badge_pb} | {ed.get('estado', '-')} |\n"
                    st.markdown(t_md)

                    # Análisis Táctico Team Ardil
                    analisis_texto = faf.get("analisis_coach") or consultas_ai.generar_analisis_tactico_coach(lugar, cat_sel, datos_cat.get("ediciones_cron", []), pb, ultima)
                    st.markdown(f"""
                    <div style="background: rgba(0, 120, 212, 0.12); border-left: 4px solid #0078D4; padding: 14px 18px; border-radius: 8px; margin-top: 15px;">
                        <div style="display: flex; align-items: center; gap: 8px; font-weight: 700; color: #60A5FA; margin-bottom: 6px;">
                            <span>🗣️ Voz del Míster · Análisis Táctico Team Ardil</span>
                        </div>
                        <div style="font-size: 0.92rem; color: #E2E8F0; line-height: 1.5;">
                            {analisis_texto}
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

    # Entrada de texto del usuario
    pregunta_input = st.chat_input("Escribe tu pregunta al entrenador IA...")
    if pregunta_input:
        st.session_state.chat_history.append({"role": "user", "content": pregunta_input})
        with st.chat_message("user"):
            st.markdown(pregunta_input)

        with st.chat_message("assistant"):
            with st.spinner("El entrenador está consultando tu historial en Garmin..."):
                resp = consultas_ai.responder_consulta_entrenamientos(pregunta_input)
                if isinstance(resp, dict):
                    msg_content = resp.get("texto", "")
                    faf_data = resp.get("frente_a_frente")
                else:
                    msg_content = str(resp)
                    faf_data = None
                st.markdown(msg_content)
                
        assistant_msg = {"role": "assistant", "content": msg_content}
        if faf_data:
            assistant_msg["frente_a_frente"] = faf_data
            if "frente a frente" in pregunta_input.lower() or "comparativa" in pregunta_input.lower():
                st.session_state[f"faf_open_{len(st.session_state.chat_history)}"] = True
        st.session_state.chat_history.append(assistant_msg)
        st.rerun()

# ==================== PESTAÑA 2: PLAN DEL ENTRENADOR VS. GARMIN ====================
with tab_plan:
    st.subheader("📋 Planificación del Entrenador vs. Entrenamientos Garmin")
    st.caption("Vinculado en tiempo real con el Google Doc de tu entrenador. Detecta cambios automáticos, etiquetas de series y discrepancias de fechas.")

    doc_url = plan_entrenador.obtener_doc_url()

    col_p1, col_p2 = st.columns([3, 1])
    with col_p1:
        st.info(f"🔗 **Documento activo del míster**: [Abrir Google Doc del Entrenador]({doc_url})")
    with col_p2:
        if st.button("🔄 Comprobar cambios ahora", use_container_width=True):
            cargar_plan_y_comparativa.clear()
            st.success("Plan recargado en vivo directamente desde Google Docs.")
            st.rerun()

    plan_dias, reconciliacion = cargar_plan_y_comparativa(doc_url)
    comparativa = reconciliacion.get("comparativa", [])
    preguntas = reconciliacion.get("preguntas_discrepancias", [])

    if comparativa:
        # 1. Alertas y discrepancias detectadas (preguntas al atleta)
        if preguntas:
            with st.expander(f"💬 **Preguntas del Asistente ({len(preguntas)} discrepancias detectadas)**", expanded=True):
                st.markdown("El asistente ha detectado diferencias entre lo programado y lo registrado en Garmin. Confirma para ajustar tu historial:")
                for idx, preg in enumerate(preguntas):
                    col_pr1, col_pr2 = st.columns([4, 1])
                    with col_pr1:
                        st.markdown(f"**{idx+1}.** {preg['mensaje']}")
                    with col_pr2:
                        if preg.get("entreno_id"):
                            if st.button("✅ Asignar", key=f"btn_preg_{idx}", use_container_width=True):
                                nuevo_tit = preg.get("plan_desc", "Entrenamiento del Plan")
                                database.ejecutar_consulta_sql(
                                    "UPDATE entrenamientos SET titulo = ? WHERE id = ?",
                                    (nuevo_tit, preg["entreno_id"])
                                )
                                st.success("¡Asignado y renombrado!")
                                st.rerun()

        # 2. Botón de etiquetado masivo
        st.markdown("#### 🏷️ Renombrado y Etiquetado Automático")
        col_et1, col_et2 = st.columns([3, 1])
        with col_et1:
            st.caption("Actualiza los nombres genéricos de Garmin ('Murcia Carrera', 'Alcantarilla Carrera') con los títulos reales prescritos por el entrenador ('Series 8x1000m', 'Series 5x2000m', 'Long Run 20k', etc.) y añade la prescripción completa en notas.")
        with col_et2:
            if st.button("🏷️ Etiquetar con el Plan", type="primary", use_container_width=True):
                num_act = plan_entrenador.aplicar_etiquetas_entrenador(comparativa)
                st.success(f"🎉 ¡Se han etiquetado y actualizado {num_act} entrenamientos con los nombres oficiales del míster!")
                st.rerun()

        st.divider()

        # 3. Visor Semanal
        st.markdown("#### 📅 Desglose Semanal: Plan vs. Garmin")
        semanas_disponibles = list(dict.fromkeys(p["semana"] for p in plan_dias if p.get("semana")))
        
        # Seleccionar por defecto la semana actual (09-11 al 15-11)
        def_idx = 0
        for idx_s, s in enumerate(semanas_disponibles):
            if "09-11" in s or "15-11" in s:
                def_idx = idx_s
                break

        semana_sel = st.selectbox("Seleccionar semana del plan:", semanas_disponibles, index=def_idx)

        dias_semana_sel = [
            item for item in comparativa 
            if any(p["fecha"] == item["fecha"] and p["semana"] == semana_sel for p in plan_dias)
        ]

        for item in dias_semana_sel:
            with st.container():
                c_dia, c_plan, c_garmin, c_estado = st.columns([1.5, 3.5, 3, 1.5])
                with c_dia:
                    st.markdown(f"**{item['dia_semana']}**")
                    st.caption(f"📅 {item['fecha']}")
                with c_plan:
                    st.markdown(f"**{item['titulo_sugerido']}**")
                    st.caption(item['plan_descripcion'].replace('\n', ' · '))
                with c_garmin:
                    g = item.get("garmin_entreno")
                    if g:
                        st.markdown(f"🏃 **{g['titulo']}**")
                        st.caption(f"{g['distancia_km']} km | {g['tiempo_formateado']} | {g['ritmo_medio_minkm']} min/km")
                    else:
                        if item["es_descanso"]:
                            st.markdown("💤 *Descanso*")
                        else:
                            st.markdown("⏳ *Sin registrar aún*")
                with c_estado:
                    st.markdown(f"**{item['estado']}**")
                st.divider()

    # Configuración de URL del documento
    with st.expander("⚙️ Configuración del enlace de Google Docs"):
        nueva_url = st.text_input("URL del Google Doc de entrenamientos:", value=doc_url)
        if st.button("Guardar nuevo enlace"):
            plan_entrenador.guardar_doc_url(nueva_url)
            st.success("Enlace actualizado correctamente.")
            st.rerun()

# ==================== COMPONENTE: RÉCORDS PERSONALES (PB) ====================
def render_records_personales():
    st.subheader("🏆 Mejores Marcas Personales (Personal Bests)")
    st.caption("Detección automática de tus récords absolutos registrados en tu reloj Garmin.")

    records = database.obtener_records_personales()
    if records:
        # Tarjetas de héroe en columnas
        num_cols = min(4, len(records))
        cols = st.columns(num_cols)
        for idx, rec in enumerate(records[:4]):
            with cols[idx]:
                st.metric(
                    label=f"🥇 {rec['categoria']}",
                    value=rec["marca"],
                    delta=f"{rec['ritmo']} min/km"
                )
                st.caption(f"📅 {rec['fecha'][:10]} · *{rec['titulo']}*")

        if len(records) > 4:
            cols2 = st.columns(len(records) - 4)
            for idx, rec in enumerate(records[4:]):
                with cols2[idx]:
                    st.metric(
                        label=f"🥇 {rec['categoria']}",
                        value=rec["marca"],
                        delta=f"{rec['ritmo']} min/km"
                    )
                    st.caption(f"📅 {rec['fecha'][:10]} · *{rec['titulo']}*")

        st.divider()

        # Tabla comparativa completa
        st.markdown("#### 📋 Desglose detallado de récords")
        df_rec = pd.DataFrame(records)
        columnas_rec = ["categoria", "marca", "ritmo", "fecha", "titulo", "fc_media"]
        df_rec_display = df_rec[columnas_rec].rename(columns={
            "categoria": "Distancia / Modalidad",
            "marca": "Tiempo Oficial",
            "ritmo": "Ritmo (min/km)",
            "fecha": "Fecha",
            "titulo": "Sesión / Competición",
            "fc_media": "FC Media"
        })
        st.dataframe(df_rec_display, use_container_width=True, hide_index=True)

        # Gráfica de curva de ritmos
        # Convertir ritmos a segundos por km para poder graficarlos
        def ritmo_a_segundos(r_str):
            try:
                parts = str(r_str).split(":")
                return int(parts[0]) * 60 + int(parts[1])
            except Exception:
                return None

        df_rec["ritmo_seg"] = df_rec["ritmo"].apply(ritmo_a_segundos)
        df_rec_valid = df_rec.dropna(subset=["ritmo_seg"])

        if not df_rec_valid.empty:
            paleta_pbi = ["#00B4D8", "#0078D4", "#2EC4B6", "#F2C811", "#FF7F50", "#E63946", "#7928CA", "#4361EE"]
            fig_pb = px.bar(
                df_rec_valid,
                x="categoria",
                y="ritmo_seg",
                color="categoria",
                color_discrete_sequence=paleta_pbi,
                text="ritmo"
            )
            fig_pb.update_traces(
                textposition='outside',
                textfont=dict(color="#000000", size=12, family="Segoe UI"),
                marker=dict(line=dict(width=0))
            )
            aplicar_estilo_powerbi(
                fig_pb,
                titulo="Curva de Ritmos en Récords Personales",
                subtitulo="Ritmo oficial (min/km) conseguido en tus mejores marcas",
                x_title="Distancia",
                y_title="Segundos por km"
            )
            st.plotly_chart(fig_pb, use_container_width=True, theme=None)
    else:
        st.info("No se han podido calcular los récords con los datos actuales.")

# ==================== PESTAÑA 3: VOLUMEN Y CARGA SEMANAL ====================
with tab_volumen:
    st.subheader("📈 Carga y Volumen de Entrenamiento")
    st.caption("Evolución de kilómetros semanales, mensuales y anuales para control de picos de forma y descanso.")

    # 1. Volumen Semanal con media móvil y filtros por mes / 12 semanas (Destacado arriba)
    vol_semanal = database.obtener_volumen_semanal()
    if vol_semanal:
        df_sem = pd.DataFrame(vol_semanal)
        df_sem["media_movil_4sem"] = df_sem["total_km"].rolling(window=4, min_periods=1).mean().round(1)

        meses_es = {
            1: "ene", 2: "feb", 3: "mar", 4: "abr", 5: "may", 6: "jun",
            7: "jul", 8: "ago", 9: "sep", 10: "oct", 11: "nov", 12: "dic"
        }

        # Calcular fechas y nombres de meses en español
        meses_list = []
        rangos_list = []
        for s in df_sem["semana"]:
            try:
                d_l = datetime.strptime(s + "-1", "%Y-W%W-%w")
                d_d = d_l + timedelta(days=6)
                m_nom = f"{meses_es.get(d_l.month, 'mes')}-{d_l.year}"
                r_nom = f"{d_l.strftime('%d/%m')} - {d_d.strftime('%d/%m')}"
            except Exception:
                m_nom = s
                r_nom = s
            meses_list.append(m_nom)
            rangos_list.append(r_nom)

        df_sem["mes_nombre"] = meses_list
        df_sem["rango_semana"] = rangos_list
        df_sem["etiqueta_x"] = [f"{r} (S{s.split('-W')[-1]})" for r, s in zip(rangos_list, df_sem["semana"])]

        # Lista de meses disponibles de más reciente a más antiguo
        meses_unicos = list(dict.fromkeys(reversed(df_sem["mes_nombre"].tolist())))

        # Desplegable de filtros: 12 semanas por defecto + opciones mensuales (ej. ene-2026, feb-2026)
        col_filtro_v, _ = st.columns([1.2, 2.8])
        with col_filtro_v:
            opciones_periodo = [
                "⚡ Últimas 12 Semanas (Por defecto)",
                "⚡ Últimas 4 Semanas (Último mes)",
                "⚡ Últimas 24 Semanas (Semestre)",
                "⚡ Todo 2026 (Año actual)",
                "⚡ Todo 2025"
            ] + meses_unicos

            periodo_sel = st.selectbox(
                "Filtrar período o mes:",
                opciones_periodo,
                index=0
            )

        # Aplicar el filtro seleccionado
        if periodo_sel == "⚡ Últimas 12 Semanas (Por defecto)":
            df_sem_filtrado = df_sem.tail(12)
            subtitulo_graf = "Últimas 12 semanas automáticas desde la fecha actual"
        elif periodo_sel == "⚡ Últimas 4 Semanas (Último mes)":
            df_sem_filtrado = df_sem.tail(4)
            subtitulo_graf = "Últimas 4 semanas de entrenamiento"
        elif periodo_sel == "⚡ Últimas 24 Semanas (Semestre)":
            df_sem_filtrado = df_sem.tail(24)
            subtitulo_graf = "Últimas 24 semanas (medio año de progresión)"
        elif periodo_sel == "⚡ Todo 2026 (Año actual)":
            df_sem_filtrado = df_sem[df_sem["semana"].str.startswith("2026")]
            subtitulo_graf = "Temporada 2026 completa"
        elif periodo_sel == "⚡ Todo 2025":
            df_sem_filtrado = df_sem[df_sem["semana"].str.startswith("2025")]
            subtitulo_graf = "Temporada 2025 completa"
        else:
            # Mes específico seleccionado directamente (ej. nov-2026, oct-2026, etc.)
            df_sem_filtrado = df_sem[df_sem["mes_nombre"] == periodo_sel]
            subtitulo_graf = f"Volumen semanal en {periodo_sel}"

        if not df_sem_filtrado.empty:
            # Métricas resumen del período seleccionado
            k_km_tot = df_sem_filtrado["total_km"].sum()
            k_km_med = df_sem_filtrado["total_km"].mean()
            k_km_max = df_sem_filtrado["total_km"].max()
            k_ses_tot = df_sem_filtrado["sesiones"].sum()

            c_vk1, c_vk2, c_vk3, c_vk4 = st.columns(4)
            c_vk1.metric("Kms en el Período", f"{k_km_tot:.1f} km")
            c_vk2.metric("Media Semanal", f"{k_km_med:.1f} km/sem")
            c_vk3.metric("Semana Pico", f"{k_km_max:.1f} km")
            c_vk4.metric("Sesiones Totales", f"{k_ses_tot} entrenos")

            # Gráfica de barras
            fig_sem = go.Figure()

            # Usar etiquetas detalladas si son pocas semanas (<= 16), o código ISO si son muchas
            x_labels = df_sem_filtrado["rango_semana"] if len(df_sem_filtrado) <= 16 else df_sem_filtrado["semana"]
            text_labels = df_sem_filtrado["total_km"].apply(lambda v: f"{v:.0f}k" if v >= 100 else f"{v:.1f}")

            fig_sem.add_trace(go.Bar(
                x=x_labels,
                y=df_sem_filtrado["total_km"],
                text=text_labels,
                textposition="outside",
                textfont=dict(color="#000000", size=12, family="Open Sans, Segoe UI"),
                name="Km Semanales",
                marker=dict(
                    color="#007CC3",
                    line=dict(width=0)
                ),
                opacity=0.9
            ))
            fig_sem.add_trace(go.Scatter(
                x=x_labels,
                y=df_sem_filtrado["media_movil_4sem"],
                mode="lines+markers",
                name="Media móvil (4 semanas)",
                line=dict(color="#B45309", width=3),
                marker=dict(size=6, color="#B45309")
            ))

            max_y_val = max(df_sem_filtrado["total_km"].max(), 50) * 1.18

            aplicar_estilo_powerbi(
                fig_sem,
                titulo="Carga de Entrenamiento Semanal",
                subtitulo=subtitulo_graf,
                x_title="Semana",
                y_title="Kilómetros",
                altura=420
            )
            fig_sem.update_layout(
                yaxis=dict(range=[0, max_y_val]),
                hovermode="x unified",
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, font=dict(color="#000000", size=12))
            )
            st.plotly_chart(fig_sem, use_container_width=True, theme=None)
        else:
            st.info("No hay datos de entrenamientos para el período o mes seleccionado.")

    st.divider()

    # 2. Resumen Anual Histórico (Debajo)
    vol_anual = database.obtener_volumen_anual()
    if vol_anual:
        st.markdown("#### 📅 Historial y Resumen por Temporada (Años)")
        df_anual = pd.DataFrame(vol_anual)
        col_va1, col_va2 = st.columns([1, 2])
        with col_va1:
            st.markdown("**Kilómetros por Año**")
            st.dataframe(
                df_anual.rename(columns={
                    "anio": "Año",
                    "sesiones": "Sesiones",
                    "total_km": "Kms Totales",
                    "media_km": "Media km/sesión"
                }),
                use_container_width=True,
                hide_index=True
            )
        with col_va2:
            df_anual_sorted = df_anual.sort_values("anio")
            fig_anual = px.bar(
                df_anual_sorted,
                x="anio",
                y="total_km",
                text=df_anual_sorted["total_km"].apply(lambda v: f"{v:,.0f}k".replace(",", ".")),
                color="total_km",
                color_continuous_scale=[[0.0, "#0078D4"], [0.5, "#00B4D8"], [1.0, "#2EC4B6"]]
            )
            fig_anual.update_traces(
                textposition='outside',
                textfont=dict(color="#000000", size=12, family="Segoe UI"),
                marker=dict(line=dict(width=0))
            )
            fig_anual.update_coloraxes(showscale=False)
            aplicar_estilo_powerbi(
                fig_anual,
                titulo="Volumen Anual Acumulado",
                subtitulo="Kilómetros totales completados por temporada",
                x_title="Año",
                y_title="Kilómetros"
            )
            st.plotly_chart(fig_anual, use_container_width=True, theme=None)

# ==================== COMPONENTE: HISTORIAL Y FICHA DETALLADA ====================
def render_historial_sesiones():
    st.subheader("📋 Historial y Ficha Detallada de Entrenamiento")

    entrenos_raw = database.ejecutar_consulta_sql("SELECT * FROM entrenamientos ORDER BY fecha DESC")

    if entrenos_raw:
        df_entrenos = pd.DataFrame(entrenos_raw)

        # Buscador y selector de sesión para ver su ficha
        st.markdown("#### 🔍 Inspeccionar Sesión en Detalle")
        col_filtro1, col_filtro2 = st.columns([1, 2])
        with col_filtro1:
            texto_busqueda = st.text_input("Filtrar por texto (ej. 'Santa Pola', 'Maratón', '400m', 'Valencia'):", "")
        with col_filtro2:
            opciones_df = df_entrenos
            if texto_busqueda:
                opciones_df = df_entrenos[
                    df_entrenos["titulo"].astype(str).str.contains(texto_busqueda, case=False, na=False) |
                    df_entrenos["ubicacion"].astype(str).str.contains(texto_busqueda, case=False, na=False)
                ]

            lista_opciones = [
                f"{r['id']} | {r['fecha'][:10]} · {r['titulo']} ({r['distancia_km']} km, {r['tiempo_formateado']})"
                for _, r in opciones_df.head(100).iterrows()
            ]

            if lista_opciones:
                seleccion_label = st.selectbox("Selecciona un entrenamiento para ver su ficha completa:", lista_opciones)
                sel_id = int(seleccion_label.split(" | ")[0])
            else:
                st.warning("No se encontraron entrenamientos con ese texto.")
                sel_id = None

        # Mostrar ficha del entrenamiento seleccionado
        if sel_id:
            entreno_sel, laps_sel = database.obtener_detalle_entrenamiento(sel_id)
            if entreno_sel:
                st.markdown(f"### 🎽 Ficha: **{entreno_sel.get('titulo', 'Entrenamiento')}**")
                st.caption(f"📅 Fecha: **{entreno_sel.get('fecha')}** | 📍 Ubicación: **{entreno_sel.get('ubicacion') or 'No especificada'}**")

                col_m1, col_m2, col_m3, col_m4, col_m5 = st.columns(5)
                col_m1.metric("Distancia", f"{entreno_sel.get('distancia_km')} km")
                col_m2.metric("Tiempo", entreno_sel.get("tiempo_formateado"))
                col_m3.metric("Ritmo medio", f"{entreno_sel.get('ritmo_medio_minkm')} min/km")
                col_m4.metric("FC Media / Máx", f"{entreno_sel.get('fc_media') or '-'} / {entreno_sel.get('fc_max') or '-'} ppm")
                col_m5.metric("Cadencia / Calorías", f"{entreno_sel.get('cadencia_media') or '-'} spm · {entreno_sel.get('calorias') or '-'} kcal")

                if laps_sel:
                    laps_clasificados, resumen_series = database.clasificar_vueltas_sesion(laps_sel)
                    df_laps_sel = pd.DataFrame(laps_clasificados)

                    if resumen_series["num_series"] > 1:
                        st.markdown(f"#### ⚡ Análisis de Series: **{resumen_series['num_series']} Series de ~{resumen_series['distancia_aprox']}m**")
                        c_sub1, c_sub2, c_sub3 = st.columns(3)
                        c_sub1.success(f"🎯 **Series reales:** {resumen_series['num_series']} repeticiones")
                        c_sub2.info(f"⏱️ **Recuperaciones:** {resumen_series['num_recuperaciones']} pausas de descanso")
                        c_sub3.caption(f"🏃 **Calentamiento:** {resumen_series['calentamiento_km']} km | **Enfriamiento:** {resumen_series['enfriamiento_km']} km")
                    else:
                        st.markdown(f"#### ⚡ Desglose de Vueltas ({len(laps_sel)} tramos)")

                    # Gráfica de la sesión seleccionada estilo Power BI
                    col_g1, col_g2 = st.columns([1, 1])
                    with col_g1:
                        # Paleta ejecutiva Power BI para los tipos de tramo
                        color_map = {
                            "Calentamiento": "#7928CA",
                            "Recuperación": "#4A5568",
                            "Enfriamiento": "#F77F00"
                        }
                        fig_laps_t = px.bar(
                            df_laps_sel,
                            x="lap_numero",
                            y="distancia_m",
                            color="tipo_clasificado",
                            color_discrete_map=color_map,
                            color_discrete_sequence=["#00B4D8", "#0078D4", "#2EC4B6"]
                        )
                        fig_laps_t.update_traces(marker=dict(line=dict(width=0)))
                        aplicar_estilo_powerbi(
                            fig_laps_t,
                            titulo="Perfil de la Sesión",
                            subtitulo="Metros por tramo (Calentamiento, Series y Descansos)",
                            x_title="Nº Vuelta",
                            y_title="Metros"
                        )
                        fig_laps_t.update_layout(legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, font=dict(color="#000000")))
                        st.plotly_chart(fig_laps_t, use_container_width=True, theme=None)

                    with col_g2:
                        # Filtrar solo series para la gráfica de ritmos/tiempos si hay series
                        df_solo_series = df_laps_sel[df_laps_sel["tipo_clasificado"].str.startswith("Serie")]
                        df_plot_s = df_solo_series if not df_solo_series.empty else df_laps_sel
                        fig_laps_s = px.bar(
                            df_plot_s,
                            x="tipo_clasificado" if not df_solo_series.empty else "lap_numero",
                            y="tiempo_s",
                            color="fc_media",
                            color_continuous_scale=[[0.0, "#0078D4"], [0.5, "#00B4D8"], [1.0, "#FF5A5F"]],
                            text="tiempo_formateado"
                        )
                        fig_laps_s.update_traces(
                            textposition='outside',
                            textfont=dict(color="#000000", size=11, family="Segoe UI"),
                            marker=dict(line=dict(width=0))
                        )
                        fig_laps_s.update_coloraxes(colorbar_title=dict(text="FC Media", font=dict(color="#000000", size=11)))
                        aplicar_estilo_powerbi(
                            fig_laps_s,
                            titulo="Tiempos de las Series Reales",
                            subtitulo="Duración exacta por repetición activa (segundos)",
                            x_title="Serie" if not df_solo_series.empty else "Vuelta",
                            y_title="Segundos"
                        )
                        st.plotly_chart(fig_laps_s, use_container_width=True, theme=None)

                    # Tabla de vueltas
                    columnas_laps = ["lap_numero", "tipo_clasificado", "distancia_m", "tiempo_formateado", "ritmo_minkm", "fc_media", "fc_max"]
                    st.dataframe(
                        df_laps_sel[columnas_laps].rename(columns={
                            "lap_numero": "Vuelta #",
                            "tipo_clasificado": "Tipo de Tramo",
                            "distancia_m": "Metros",
                            "tiempo_formateado": "Tiempo",
                            "ritmo_minkm": "Ritmo",
                            "fc_media": "FC Media",
                            "fc_max": "FC Máx"
                        }),
                        use_container_width=True,
                        hide_index=True
                    )
                else:
                    st.info("Esta sesión no tiene registros de vueltas o series intermedias.")

        st.divider()

        # Tabla general completa abajo
        st.markdown("#### 📜 Registro General Completo")
        columnas_mostrar = ["fecha", "titulo", "distancia_km", "tiempo_formateado", "ritmo_medio_minkm", "fc_media", "ubicacion"]
        st.dataframe(
            df_entrenos[columnas_mostrar].rename(columns={
                "fecha": "Fecha",
                "titulo": "Título",
                "distancia_km": "Distancia (km)",
                "tiempo_formateado": "Tiempo",
                "ritmo_medio_minkm": "Ritmo medio",
                "fc_media": "FC Media",
                "ubicacion": "Ubicación"
            }),
            use_container_width=True,
            hide_index=True
        )

# ==================== PESTAÑA 5: ANÁLISIS DE SERIES ====================
with tab_series:
    st.subheader("⚡ Detalle y Análisis de Series")
    st.caption("Compara los tiempos de cada repetición de forma limpia, separando las recuperaciones.")

    col_s1, col_s2 = st.columns([1, 2])
    with col_s1:
        distancia_opciones = {
            "1000m": (900, 1100),
            "400m (Pista)": (380, 430),
            "2000m": (1900, 2100),
            "5000m": (4800, 5200)
        }
        dist_sel = st.selectbox(
            "Distancia de serie:",
            list(distancia_opciones.keys()),
            index=0
        )
        d_min, d_max = distancia_opciones[dist_sel]

    # Buscar sesiones que tengan vueltas de esa distancia
    query_sesiones = f"""
    SELECT e.id, e.fecha, e.titulo, e.ubicacion, e.notas_entrenador,
           COUNT(s.id) as num_series,
           ROUND(AVG(s.tiempo_s), 1) as media_seg,
           MIN(s.tiempo_s) as min_seg
    FROM entrenamientos e
    JOIN series_laps s ON s.entrenamiento_id = e.id
    WHERE s.distancia_m BETWEEN {d_min} AND {d_max}
    GROUP BY e.id
    HAVING COUNT(s.id) >= 2
    ORDER BY e.fecha DESC
    """
    sesiones_series_raw = database.ejecutar_consulta_sql(query_sesiones)
    # Filtrar estrictamente solo sesiones de series reales (respetando la regla del entrenador y descartando carreras/rodajes)
    sesiones_series = [
        s for s in sesiones_series_raw
        if es_sesion_series_real(s["id"], s["fecha"], s["titulo"], s.get("notas_entrenador", ""), comparativa_plan)
    ]

    if sesiones_series:
        with col_s2:
            opciones_sesion = []
            for s in sesiones_series:
                p_match = [p for p in comparativa_plan if p.get("fecha") == s["fecha"][:10]]
                tit_amigable = p_match[0]["titulo_sugerido"] if p_match else s["titulo"]
                opciones_sesion.append(f"{s['id']} | {s['fecha'][:10]} · {tit_amigable} ({s['num_series']} series)")

            sel_sesion_str = st.selectbox(
                "Seleccionar sesión de series:",
                opciones_sesion,
                index=0
            )
            sesion_id = int(sel_sesion_str.split(" | ")[0])

        # Cargar los laps exactos de esa sesión
        query_laps = f"""
        SELECT lap_numero, distancia_m, tiempo_s, tiempo_formateado, ritmo_minkm, fc_media, fc_max
        FROM series_laps
        WHERE entrenamiento_id = {sesion_id} AND distancia_m BETWEEN {d_min} AND {d_max}
        ORDER BY lap_numero ASC
        """
        laps_series_raw = database.ejecutar_consulta_sql(query_laps)

        if laps_series_raw:
            df_laps_s = pd.DataFrame(laps_series_raw)
            # Nombrar como Serie 1, Serie 2... en negrita y negro para la gráfica
            df_laps_s["nombre_serie"] = [f"<b>Serie #{i}</b>" for i in range(1, len(df_laps_s) + 1)]
            df_laps_s["nombre_serie_clean"] = [f"Serie #{i}" for i in range(1, len(df_laps_s) + 1)]

            # Métricas resumen de la sesión
            t_seg_lista = df_laps_s["tiempo_s"].tolist()
            min_t = min(t_seg_lista)
            avg_t = sum(t_seg_lista) / len(t_seg_lista)
            mejor_serie_row = df_laps_s.loc[df_laps_s["tiempo_s"].idxmin()]

            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Total Series", f"{len(df_laps_s)} repeticiones")
            m2.metric("Mejor Serie", mejor_serie_row["tiempo_formateado"], f"{mejor_serie_row['ritmo_minkm']} min/km")
            m3.metric("Tiempo Promedio", f"{int(avg_t // 60)}:{int(avg_t % 60):02d}", f"{(avg_t / (df_laps_s['distancia_m'].mean() / 1000) / 60):.2f} min/km")
            fc_media_val = df_laps_s["fc_media"].dropna()
            m4.metric("FC Promedio", f"{int(fc_media_val.mean())} ppm" if not fc_media_val.empty else "Sin datos")

            # Gráfica de Barras limpia, ancha y contrastada estilo Power BI
            fig_series = go.Figure()

            # Barras de las series con etiquetas en negro puro y alto contraste
            fig_series.add_trace(go.Bar(
                x=df_laps_s["nombre_serie"],
                y=df_laps_s["tiempo_s"],
                text=df_laps_s["tiempo_formateado"],
                textposition="outside",
                textfont=dict(color="#000000", size=13, family="Segoe UI"),
                marker=dict(
                    color="#0078D4",  # Azul Power BI vibrante
                    line=dict(width=0)
                ),
                name="Tiempo por Serie"
            ))

            # Línea de referencia media
            fig_series.add_hline(
                y=avg_t,
                line_dash="dash",
                line_color="#B45309",
                line_width=2,
                annotation_text=f"Media: {int(avg_t // 60)}:{int(avg_t % 60):02d} min",
                annotation_position="top right",
                annotation_font=dict(color="#B45309", size=12)
            )

            # Margen superior en Y para que el texto de arriba no se corte
            max_y = max(t_seg_lista) * 1.15
            min_y = max(0, min(t_seg_lista) * 0.8)

            aplicar_estilo_powerbi(
                fig_series,
                titulo=f"Tiempos por Serie - {dist_sel}",
                subtitulo=f"Sesión del {sel_sesion_str.split(' | ')[1]}",
                x_title="Repetición",
                y_title="Segundos",
                altura=420
            )
            fig_series.update_layout(
                yaxis=dict(range=[min_y, max_y]),
                xaxis=dict(
                    tickfont=dict(color="#000000", size=13, family="Segoe UI"),
                    tickcolor="#000000",
                    title=dict(font=dict(color="#000000", size=13))
                )
            )
            st.plotly_chart(fig_series, use_container_width=True, theme=None)

            # Tabla con las series
            st.dataframe(
                df_laps_s[["nombre_serie_clean", "distancia_m", "tiempo_formateado", "ritmo_minkm", "fc_media", "fc_max"]].rename(columns={
                    "nombre_serie_clean": "Repetición",
                    "distancia_m": "Metros",
                    "tiempo_formateado": "Tiempo",
                    "ritmo_minkm": "Ritmo",
                    "fc_media": "FC Media",
                    "fc_max": "FC Máx"
                }),
                use_container_width=True,
                hide_index=True
            )
    else:
        st.info(f"No se han encontrado sesiones con series de {dist_sel}.")

# ==================== COMPONENTE: SINCRONIZAR GARMIN ====================
def render_sincronizar_garmin():
    st.subheader("📥 Sincronización y Carga de Entrenamientos")

    # Detección de sesión guardada
    token_dir = os.path.join(os.path.dirname(__file__), ".garmin_tokens")
    token_file = os.path.join(token_dir, "garmin_tokens.json")
    tiene_sesion = os.path.isfile(token_file)

    if tiene_sesion:
        st.success("✅ **Sesión de Garmin Connect guardada activamente en este ordenador.**")
        if st.button("🔄 Sincronizar", type="primary", key="btn_sync_garmin_panel"):
            progress_bar = st.progress(0)
            status_text = st.empty()

            def actualizar_progreso(actual, total, detalle):
                porcentaje = min(1.0, actual / max(1, total))
                progress_bar.progress(porcentaje)
                status_text.text(f"Comprobando {actual}: {detalle}")

            try:
                with st.spinner("Conectando con sesión guardada..."):
                    cliente, msg = garmin_sync.conectar_garmin("", tokenstore_dir=token_dir)

                nuevas, omitidas = garmin_sync.descargar_historial_garmin(
                    cliente,
                    max_actividades=50,
                    callback_progreso=actualizar_progreso
                )
                progress_bar.progress(1.0)
                status_text.empty()
                st.success(f"🎉 Sincronización finalizada: **{nuevas}** nuevos entrenos añadidos ({omitidas} ya existían).")
                st.rerun()
            except Exception as e:
                st.error(f"Error al sincronizar: {e}")

    st.divider()

    with st.expander("🌐 Iniciar sesión con otra cuenta de Garmin Connect"):
        col_g1, col_g2 = st.columns(2)
        with col_g1:
            garmin_user = st.text_input("Correo de Garmin Connect", placeholder="tu_correo@gmail.com")
            garmin_pass = st.text_input("Contraseña", type="password")

        with col_g2:
            opcion_limite = st.selectbox(
                "Cantidad de entrenamientos a sincronizar:",
                [
                    "Últimos 25 entrenamientos (Rápido)",
                    "Últimos 100 entrenamientos",
                    "Últimos 500 entrenamientos",
                    "Todo mi historial completo"
                ]
            )

        limite_map = {
            "Últimos 25 entrenamientos (Rápido)": 25,
            "Últimos 100 entrenamientos": 100,
            "Últimos 500 entrenamientos": 500,
            "Todo mi historial completo": 10000
        }

        if st.button("🚀 Sincronizar cuenta nueva"):
            if not garmin_user or not garmin_pass:
                st.error("Por favor, introduce tu correo y contraseña.")
            else:
                try:
                    with st.spinner(f"Conectando a {garmin_user}..."):
                        cliente, msg = garmin_sync.conectar_garmin(garmin_user, garmin_pass)

                    max_acts = limite_map.get(opcion_limite, 50)
                    nuevas, omitidas = garmin_sync.descargar_historial_garmin(cliente, max_actividades=max_acts)
                    st.success(f"🎉 Sincronizados **{nuevas}** nuevos entrenamientos de {garmin_user}.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")

    # Subida de archivo .FIT manual
    with st.expander("📁 Subir archivo binario `.FIT` suelto"):
        archivo_fit = st.file_uploader("Seleccionar archivo .fit", type=["fit"])
        if archivo_fit is not None:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".fit") as tmp:
                tmp.write(archivo_fit.read())
                tmp_path = tmp.name
            try:
                datos_entreno, laps = garmin_sync.parsear_archivo_fit(tmp_path)
                id_guardado = database.guardar_entrenamiento(datos_entreno, laps)
                if id_guardado:
                    st.success(f"✅ ¡Entrenamiento '{datos_entreno['titulo']}' importado con éxito!")
                else:
                    st.warning("Este entrenamiento ya existía en la base de datos.")
            except Exception as e:
                st.error(f"Error: {e}")
            finally:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)

# ==================== COMPONENTE: SINCRONIZAR COROS ====================
def render_sincronizar_coros():
    st.subheader("📥 Sincronización con COROS Training Hub")
    st.caption("Conexión con los servidores de COROS (relojes Pace, Apex, Vertix) para descargar tus entrenamientos y series o importar archivos.")

    col_c1, col_c2 = st.columns([2, 1])
    with col_c1:
        st.info("🔗 **Plataforma web oficial**: [COROS Training Hub Europa](https://trainingeu.coros.com/login)")
    with col_c2:
        st.caption("Compatible con COROS Training Hub Europa y Global.")

    sesion_coros = coros_sync.obtener_tokens_guardados()
    if sesion_coros:
        st.success(f"✅ **Sesión de COROS activa:** `{sesion_coros.get('account')}` (Región: {sesion_coros.get('region', 'eu').upper()})")
        if sesion_coros.get("last_sync"):
            st.caption(f"🕒 Última sincronización: {sesion_coros.get('last_sync')}")

        col_sync, col_logout = st.columns([3, 1])
        with col_sync:
            if st.button("🔄 Sincronizar", type="primary", key="btn_sync_coros_panel", use_container_width=True):
                p_bar = st.progress(0)
                st_text = st.empty()

                def update_coros_p(act, tot, name):
                    pct = min(1.0, act / max(1, tot))
                    p_bar.progress(pct)
                    st_text.text(f"Importando {act}/{tot}: {name}")

                res = coros_sync.sincronizar_actividades_coros(progreso_callback=update_coros_p)
                if res["status"] == "ok":
                    st.success(f"🎉 {res['mensaje']}")
                    st.rerun()
                else:
                    st.error(res["mensaje"])

        with col_logout:
            if st.button("🚪 Cerrar sesión COROS", use_container_width=True):
                coros_sync.cerrar_sesion_coros()
                st.success("Sesión cerrada correctamente.")
                st.rerun()
    else:
        st.markdown("#### 🔑 Iniciar Sesión en COROS Training Hub")
        with st.form("form_coros_login"):
            c_email = st.text_input("Email / Cuenta COROS:", placeholder="ejemplo@email.com")
            c_pass = st.text_input("Contraseña COROS:", type="password")
            c_reg = st.selectbox(
                "Servidor / Región:",
                options=["eu", "global"],
                format_func=lambda x: "Europa (trainingeu.coros.com)" if x == "eu" else "Global / América (training.coros.com)"
            )
            submit_coros = st.form_submit_button("Conectar con COROS", type="primary")

            if submit_coros:
                if not c_email or not c_pass:
                    st.error("Por favor, introduce tu email y contraseña de COROS.")
                else:
                    with st.spinner("Conectando y autenticando con COROS Training Hub..."):
                        ok, msg, _ = coros_sync.iniciar_sesion_coros(c_email, c_pass, region_key=c_reg)
                        if ok:
                            st.success(msg)
                            st.rerun()
                        else:
                            st.error(msg)

    st.divider()

    # Importador manual de archivos de COROS
    st.markdown("#### 📁 Importar Archivos de COROS (.FIT o .ZIP)")
    st.caption("También puedes arrastrar archivos FIT descargados individualmente o en lote desde el Training Hub o la app de COROS.")

    archivos_coros = st.file_uploader(
        "Arrastra tus archivos de COROS aquí:",
        type=["fit", "zip"],
        accept_multiple_files=True,
        key="uploader_coros"
    )
    if archivos_coros:
        if st.button(f"📥 Procesar {len(archivos_coros)} archivo(s) de COROS", type="primary"):
            p_bar_f = st.progress(0)
            guardados = 0
            for idx_f, arch in enumerate(archivos_coros):
                p_bar_f.progress((idx_f + 1) / len(archivos_coros))
                with tempfile.NamedTemporaryFile(delete=False, suffix=".fit") as tmp:
                    tmp.write(arch.read())
                    tmp_p = tmp.name
                try:
                    datos_e, laps_e = garmin_sync.parsear_archivo_fit(tmp_p)
                    nid = database.guardar_entrenamiento(datos_e, laps_e)
                    if nid:
                        guardados += 1
                except Exception:
                    pass
                finally:
                    if os.path.exists(tmp_p):
                        os.remove(tmp_p)
            st.success(f"🎉 Se han importado {guardados} sesiones de COROS con éxito.")
            st.rerun()

# ==================== COMPONENTE: SINCRONIZAR STRAVA ====================
def render_sincronizar_strava():
    st.subheader("📥 Sincronización con Strava")
    st.caption("Conecta tu cuenta de Strava para descargar actividades y series automáticamente o importa exportaciones de Strava.")

    col_s1, col_s2 = st.columns([2, 1])
    with col_s1:
        st.info("🔗 **Configuración API oficial**: [Strava API Settings](https://www.strava.com/settings/api)")
    with col_s2:
        st.caption("Compatible con Tokens Personales y OAuth 2.0 de Strava.")

    sesion_strava = strava_sync.obtener_tokens_strava()
    if sesion_strava:
        st.success(f"✅ **Conectado a Strava:** `{sesion_strava.get('athlete_name', 'Atleta Conectado')}`")
        if sesion_strava.get("last_sync"):
            st.caption(f"🕒 Última sincronización: {sesion_strava.get('last_sync')}")

        col_sync, col_logout = st.columns([3, 1])
        with col_sync:
            if st.button("🔄 Sincronizar", type="primary", key="btn_sync_strava_panel", use_container_width=True):
                p_bar = st.progress(0)
                st_text = st.empty()

                def update_strava_p(act, tot, name):
                    pct = min(1.0, act / max(1, tot))
                    p_bar.progress(pct)
                    st_text.text(f"Importando {act}/{tot}: {name}")

                res = strava_sync.sincronizar_actividades_strava(progreso_callback=update_strava_p)
                if res["status"] == "ok":
                    st.success(f"🎉 {res['mensaje']}")
                    st.rerun()
                else:
                    st.error(res["mensaje"])

        with col_logout:
            if st.button("🚪 Desconectar Strava", use_container_width=True):
                strava_sync.cerrar_sesion_strava()
                st.success("Conexión con Strava eliminada.")
                st.rerun()
    else:
        st.markdown("#### 🔑 Conectar cuenta de Strava")
        st.caption("Introduce tu **Access Token de Strava** (obtenido en Strava Developer Settings) o credenciales de aplicación.")

        tab_tok, tab_oauth = st.tabs(["Token Directo (Recomendado)", "OAuth Completo (Client ID / Secret)"])
        with tab_tok:
            with st.form("form_strava_token"):
                st_tok = st.text_input("Access Token de Strava:", type="password", placeholder="pe. 8a3f890c2e...")
                st_name = st.text_input("Nombre de atleta / referencia:", value="Salva Andreo")
                submit_tok = st.form_submit_button("Conectar Token", type="primary")

                if submit_tok:
                    if not st_tok:
                        st.error("Debes introducir un Access Token.")
                    else:
                        with st.spinner("Comprobando token con la API de Strava..."):
                            ok, msg, _ = strava_sync.conectar_strava_token_directo(st_tok, st_name)
                            if ok:
                                st.success(msg)
                                st.rerun()
                            else:
                                st.error(msg)

        with tab_oauth:
            with st.form("form_strava_oauth"):
                cid = st.text_input("Client ID:")
                csec = st.text_input("Client Secret:", type="password")
                rtok = st.text_input("Refresh Token:", type="password")
                submit_oauth = st.form_submit_button("Conectar OAuth")

                if submit_oauth:
                    if not cid or not csec or not rtok:
                        st.error("Introduce todos los campos OAuth.")
                    else:
                        with st.spinner("Solicitando token de acceso a Strava..."):
                            ok, msg, _ = strava_sync.refrescar_token_strava(cid, csec, rtok)
                            if ok:
                                st.success(msg)
                                st.rerun()
                            else:
                                st.error(msg)

    st.divider()

    # Importador manual de archivos de Strava
    st.markdown("#### 📁 Importar Archivos de Strava (.FIT o .ZIP)")
    st.caption("Arrastra cualquier archivo FIT o exportación comprimida de Strava.")

    archivos_strava = st.file_uploader(
        "Arrastra tus archivos de Strava aquí:",
        type=["fit", "zip"],
        accept_multiple_files=True,
        key="uploader_strava"
    )
    if archivos_strava:
        if st.button(f"📥 Procesar {len(archivos_strava)} archivo(s) de Strava", type="primary"):
            p_bar_s = st.progress(0)
            guardados = 0
            for idx_f, arch in enumerate(archivos_strava):
                p_bar_s.progress((idx_f + 1) / len(archivos_strava))
                with tempfile.NamedTemporaryFile(delete=False, suffix=".fit") as tmp:
                    tmp.write(arch.read())
                    tmp_p = tmp.name
                try:
                    datos_e, laps_e = garmin_sync.parsear_archivo_fit(tmp_p)
                    nid = database.guardar_entrenamiento(datos_e, laps_e)
                    if nid:
                        guardados += 1
                except Exception:
                    pass
                finally:
                    if os.path.exists(tmp_p):
                        os.remove(tmp_p)
            st.success(f"🎉 Se han importado {guardados} sesiones de Strava con éxito.")
            st.rerun()

# ==================== PESTAÑA 6: PERSONAL (DESPLEGABLE) ====================
with tab_personal:
    col_p_sel, _ = st.columns([1.5, 2.5])
    with col_p_sel:
        opcion_personal = st.selectbox(
            "Seleccionar sección personal:",
            [
                "🏆 Récords Personales (PB)",
                "🎽 Ficha de Sesión e Historial",
                "📥 Sincronizar Garmin",
                "📥 Sincronizar Coros",
                "📥 Sincronizar Strava"
            ],
            index=0
        )

    st.divider()

    if opcion_personal == "🏆 Récords Personales (PB)":
        render_records_personales()
    elif opcion_personal == "🎽 Ficha de Sesión e Historial":
        render_historial_sesiones()
    elif opcion_personal == "📥 Sincronizar Garmin":
        render_sincronizar_garmin()
    elif opcion_personal == "📥 Sincronizar Coros":
        render_sincronizar_coros()
    elif opcion_personal == "📥 Sincronizar Strava":
        render_sincronizar_strava()
