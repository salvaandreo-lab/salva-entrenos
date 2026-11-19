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
import consultas_ai
import plan_entrenador
import importlib

# Forzar recarga en memoria en Streamlit Cloud para evitar versiones cacheadas
for _mod in (database, garmin_sync, coros_sync, strava_sync, consultas_ai, plan_entrenador):
    try:
        importlib.reload(_mod)
    except Exception:
        pass

st.set_page_config(
    page_title="Ardil Track AI - Tu historial de entrenamientos con IA",
    page_icon="🐎",
    layout="wide",
    initial_sidebar_state="expanded"
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

# Cargar imágenes Team Ardil en base64
bg_image_path = os.path.join(os.path.dirname(__file__), "team_ardil_bg.jpg")
horse_image_path = os.path.join(os.path.dirname(__file__), "team_ardil_caballo_sq.jpg")
b64_bg = ""
b64_horse = ""
try:
    import base64
    if os.path.exists(bg_image_path):
        with open(bg_image_path, "rb") as f:
            b64_bg = base64.b64encode(f.read()).decode("utf-8")
    if os.path.exists(horse_image_path):
        with open(horse_image_path, "rb") as f:
            b64_horse = base64.b64encode(f.read()).decode("utf-8")
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
    z-index: 9999 !important;
}}

[data-testid="stHeader"] [data-testid="stToolbar"] {{
    display: none !important;
}}

[data-testid="stHeader"] [data-testid="stDecoration"] {{
    display: none !important;
}}

/* Flechas para abrir la barra lateral (lado izquierdo arriba) */
[data-testid="stSidebarCollapsedControl"],
button[data-testid="stSidebarCollapsedControl"],
[data-testid="collapsedControl"] {{
    display: flex !important;
    visibility: visible !important;
    opacity: 1 !important;
    color: #007CC3 !important;
    background: #FFFFFF !important;
    border: 1.5px solid #007CC3 !important;
    border-radius: 8px !important;
    box-shadow: 0 2px 10px rgba(0, 124, 195, 0.25) !important;
    margin-left: 12px !important;
    margin-top: 10px !important;
    z-index: 9999999 !important;
    cursor: pointer !important;
}}

[data-testid="stSidebarCollapsedControl"] svg,
button[data-testid="stSidebarCollapsedControl"] svg,
[data-testid="collapsedControl"] svg {{
    fill: #007CC3 !important;
    stroke: #007CC3 !important;
    color: #007CC3 !important;
    width: 22px !important;
    height: 22px !important;
}}

[data-testid="stSidebarCollapsedControl"]:hover,
button[data-testid="stSidebarCollapsedControl"]:hover {{
    background: #E8F4FA !important;
    box-shadow: 0 4px 14px rgba(0, 124, 195, 0.35) !important;
}}

[data-testid="stMain"] {{
    background-color: #F4F6F8 !important;
}}

.main .block-container {{
    background: transparent !important;
    max-width: 1400px !important;
    padding-top: 3.2rem !important;
}}

/* Topbar Ardil Track */
.garmin-topbar {{
    background: rgba(24, 28, 32, 0.96) !important;
    backdrop-filter: blur(10px) !important;
    -webkit-backdrop-filter: blur(10px) !important;
    padding: 12px 24px;
    border-radius: 14px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-top: 0 !important;
    margin-bottom: 28px !important;
    box-shadow: 0 4px 16px rgba(0,0,0,0.22);
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

/* ==================== DESPLEGABLES (SELECTBOX) DESTACADOS ==================== */
div[data-testid="stSelectbox"] label {{
    font-weight: 700 !important;
    font-size: 13.5px !important;
    color: #1E293B !important;
    margin-bottom: 6px !important;
    display: flex !important;
    align-items: center !important;
    gap: 6px !important;
}}

div[data-baseweb="select"] {{
    border-radius: 10px !important;
}}

div[data-baseweb="select"] > div {{
    background-color: #FFFFFF !important;
    border: 2px solid #007CC3 !important; /* Borde azul Garmin bien definido */
    border-radius: 10px !important;
    box-shadow: 0 2px 6px rgba(0, 124, 195, 0.10) !important;
    cursor: pointer !important;
    min-height: 44px !important;
    transition: all 0.2s ease-in-out !important;
}}

div[data-baseweb="select"] > div:hover {{
    border-color: #005A8C !important;
    background-color: #F8FBFE !important;
    box-shadow: 0 4px 14px rgba(0, 124, 195, 0.22) !important;
    transform: translateY(-1px) !important;
}}

/* Flecha desplegable (chevron) con contenedor tipo botón */
div[data-baseweb="select"] svg {{
    fill: #007CC3 !important;
    color: #007CC3 !important;
    width: 20px !important;
    height: 20px !important;
    stroke: #007CC3 !important;
    stroke-width: 0.5px !important;
}}

div[data-baseweb="select"] [aria-hidden="true"] {{
    background: #E8F4FA !important;
    border: 1px solid #C4E3F7 !important;
    border-radius: 8px !important;
    padding: 4px 8px !important;
    margin-right: 4px !important;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
    transition: background 0.2s ease !important;
}}

div[data-baseweb="select"] > div:hover [aria-hidden="true"] {{
    background: #D0EAF8 !important;
    border-color: #007CC3 !important;
}}

/* Texto seleccionado dentro del desplegable */
div[data-baseweb="select"] span {{
    font-weight: 600 !important;
    color: #0F172A !important;
    font-size: 13.5px !important;
}}

/* Menú desplegado (popover con lista de opciones) */
ul[data-baseweb="menu"] {{
    border-radius: 10px !important;
    border: 1.5px solid #007CC3 !important;
    box-shadow: 0 10px 25px rgba(0, 124, 195, 0.18) !important;
    background-color: #FFFFFF !important;
    padding: 6px !important;
}}

li[data-baseweb="menu-item"] {{
    border-radius: 6px !important;
    font-size: 13.5px !important;
    font-weight: 500 !important;
    padding: 9px 14px !important;
    color: #1E293B !important;
    transition: all 0.15s ease !important;
}}

li[data-baseweb="menu-item"]:hover {{
    background-color: #E8F4FA !important;
    color: #007CC3 !important;
    font-weight: 700 !important;
}}

li[data-baseweb="menu-item"][aria-selected="true"] {{
    background-color: #007CC3 !important;
    color: #FFFFFF !important;
    font-weight: 700 !important;
}}

/* ==================== ACORDEONES DESPLEGABLES (st.expander) ==================== */
div[data-testid="stExpander"] {{
    border: 1.5px solid #CBD5E1 !important;
    border-radius: 10px !important;
    background-color: #FFFFFF !important;
    box-shadow: 0 2px 6px rgba(0,0,0,0.03) !important;
    margin-bottom: 14px !important;
    overflow: hidden !important;
    transition: border-color 0.2s ease, box-shadow 0.2s ease !important;
}}

div[data-testid="stExpander"]:hover {{
    border-color: #007CC3 !important;
    box-shadow: 0 4px 12px rgba(0, 124, 195, 0.12) !important;
}}

div[data-testid="stExpander"] summary {{
    background-color: #F8FAFC !important;
    font-weight: 700 !important;
    color: #0F172A !important;
    padding: 12px 18px !important;
    border-radius: 8px !important;
    cursor: pointer !important;
    transition: all 0.2s ease !important;
}}

div[data-testid="stExpander"] summary:hover {{
    background-color: #EFF6FF !important;
    color: #007CC3 !important;
}}

div[data-testid="stExpander"] summary svg {{
    color: #007CC3 !important;
    fill: #007CC3 !important;
    width: 20px !important;
    height: 20px !important;
}}

/* ==================== SELECTORES TIPO RADIO ==================== */
div[data-testid="stRadio"] > div[role="radiogroup"] {{
    background: #FFFFFF !important;
    padding: 6px 14px !important;
    border-radius: 10px !important;
    border: 1.5px solid #CBD5E1 !important;
    box-shadow: 0 2px 6px rgba(0,0,0,0.03) !important;
    gap: 14px !important;
}}

div[data-testid="stRadio"] label {{
    cursor: pointer !important;
    font-weight: 600 !important;
    color: #1E293B !important;
    transition: color 0.2s ease !important;
}}

div[data-testid="stRadio"] label:hover {{
    color: #007CC3 !important;
}}
</style>
""", unsafe_allow_html=True)

# Detección dinámica de dispositivos/plataformas conectadas
curr_uid_chk = st.session_state.get("usuario_id_activo", 1)
token_dir_garmin = os.path.join(os.path.dirname(__file__), ".garmin_tokens")

tiene_garmin = False
try:
    tiene_garmin = (curr_uid_chk == 1 and os.path.isfile(os.path.join(token_dir_garmin, "garmin_tokens.json"))) or os.path.isfile(os.path.join(token_dir_garmin, f"garmin_tokens_u{curr_uid_chk}.json")) or os.path.isdir(os.path.join(token_dir_garmin, f"u{curr_uid_chk}"))
except Exception:
    pass

tiene_coros = False
try:
    tiene_coros = coros_sync.obtener_tokens_guardados(usuario_id=curr_uid_chk) is not None
except TypeError:
    try:
        tiene_coros = coros_sync.obtener_tokens_guardados() is not None
    except Exception:
        pass
except Exception:
    pass

tiene_strava = False
try:
    tiene_strava = strava_sync.obtener_tokens_strava(usuario_id=curr_uid_chk) is not None
except TypeError:
    try:
        tiene_strava = strava_sync.obtener_tokens_strava() is not None
    except Exception:
        pass
except Exception:
    pass

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
    plat_pref_tag = (usuario_activo.get("plataforma_principal") or "Dispositivo").upper()
    pill_device_html = f"<span>⌚ {plat_pref_tag}</span><span style='color: #64748B;'>|</span><span style='color: #F59E0B; font-weight: 700;'>● Sin vincular</span>"

def sincronizar_actividades_todas(max_acts: int = 30, u_id: Optional[int] = None) -> Tuple[int, int, str]:
    """
    Sincroniza automáticamente los entrenamientos desde cualquiera de las plataformas
    que tengan sesión activa para el atleta indicado.
    """
    target_u = u_id or st.session_state.get("usuario_id_activo", 1)
    mensajes = []
    total_nuevas = 0
    total_omitidas = 0
    plataformas_activas = 0

    # 1. Garmin Connect (solo si este atleta específico tiene tokens o sesión guardada)
    token_dir_g = os.path.join(os.path.dirname(__file__), ".garmin_tokens")
    token_file_g = os.path.join(token_dir_g, "garmin_tokens.json" if target_u == 1 else f"garmin_tokens_u{target_u}.json")
    if not os.path.isfile(token_file_g):
        db_g_tok = database.obtener_sesion_plataforma(target_u, "garmin")
        if db_g_tok:
            os.makedirs(token_dir_g, exist_ok=True)
            with open(token_file_g, "w", encoding="utf-8") as f:
                json.dump(db_g_tok, f, indent=2)
        elif target_u == 1:
            tokens_cloud = None
            try:
                tokens_cloud = st.secrets.get("GARMIN_TOKENS_JSON") or os.environ.get("GARMIN_TOKENS_JSON")
            except Exception:
                pass
            if tokens_cloud:
                os.makedirs(token_dir_g, exist_ok=True)
                with open(token_file_g, "w", encoding="utf-8") as f:
                    f.write(tokens_cloud)

    u_g_dir = garmin_sync.obtener_directorio_tokens(usuario_id=target_u)
    has_garmin_target = (target_u == 1 and os.path.isfile(token_file_g)) or os.path.isfile(os.path.join(token_dir_g, f"garmin_tokens_u{target_u}.json")) or os.path.isdir(os.path.join(token_dir_g, f"u{target_u}")) or bool(database.obtener_sesion_plataforma(target_u, "garmin"))

    if has_garmin_target:
        plataformas_activas += 1
        try:
            cliente, _ = garmin_sync.conectar_garmin("", tokenstore_dir=u_g_dir, usuario_id=target_u)
            nuevas_g, omit_g = garmin_sync.descargar_historial_garmin(cliente, max_actividades=max_acts, usuario_id=target_u)
            total_nuevas += nuevas_g
            total_omitidas += omit_g
            if nuevas_g > 0:
                mensajes.append(f"Garmin: {nuevas_g} nuevo(s)")
            else:
                mensajes.append("Garmin al día")
        except Exception as e:
            mensajes.append(f"Garmin: {e}")

    # 2. COROS Training Hub (solo si este atleta específico tiene sesión de COROS)
    if coros_sync.obtener_tokens_guardados(usuario_id=target_u):
        plataformas_activas += 1
        try:
            res_c = coros_sync.sincronizar_actividades_coros(max_actividades=max_acts, usuario_id=target_u)
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
    if strava_sync.obtener_tokens_strava(usuario_id=target_u):
        plataformas_activas += 1
        try:
            res_s = strava_sync.sincronizar_actividades_strava(max_actividades=max_acts, usuario_id=target_u)
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
        u_info = database.obtener_usuario_por_id(target_u)
        nom = u_info["nombre"] if u_info else "este atleta"
        plat_pref = (u_info.get("plataforma_principal") if u_info else ("coros" if target_u != 1 else "garmin")) or "reloj"
        plat_nombre = "COROS" if plat_pref.lower() == "coros" else ("Garmin" if plat_pref.lower() == "garmin" else "Strava")
        return 0, 0, f"Sin sesión activa de {plat_nombre} para {nom}. Conecta tu cuenta en la pestaña '👤 Personal' -> 'Sincronizar {plat_nombre}' para activar la sincronización automática."

    if total_nuevas > 0:
        try:
            import sync_sporttracks
            sync_sporttracks.sync_file("sporttracks.db", commit_msg=f"Sincronización manual: {total_nuevas} nuevo(s) [skip ci]")
        except Exception:
            pass

    detalle = " · ".join(mensajes)
    return total_nuevas, total_omitidas, detalle

# Carga de usuarios y gestión de sesión multi-atleta
usuarios_db = database.obtener_usuarios()
if not usuarios_db:
    database.init_db()
    usuarios_db = database.obtener_usuarios()

if "usuario_id_activo" not in st.session_state:
    st.session_state["usuario_id_activo"] = 1

# Validar que el usuario actual existe en la base de datos
ids_validos = [u["id"] for u in usuarios_db]
if st.session_state["usuario_id_activo"] not in ids_validos:
    st.session_state["usuario_id_activo"] = 1

usuario_activo = next((u for u in usuarios_db if u["id"] == st.session_state["usuario_id_activo"]), usuarios_db[0])
es_admin = (usuario_activo.get("rol") in ("admin", "administrador") or usuario_activo.get("id") == 1 or usuario_activo.get("alias") == "salva")
es_entrenador = (usuario_activo.get("rol") == "entrenador" or usuario_activo.get("id") == 2)
usuario_id = usuario_activo["id"]
es_salva = (usuario_id == 1 or usuario_activo.get("alias") == "salva")

def formato_usuario(uid):
    u = next((item for item in usuarios_db if item["id"] == uid), None)
    if not u:
        return str(uid)
    rol_txt = "👑 Admin" if (u.get("rol") in ("admin", "administrador") or u.get("id") == 1) else ("👨‍🏫 Míster" if u.get("rol") == "entrenador" else "🏃 Atleta")
    return f"{u.get('avatar', '🏃')} {u['nombre']} ({rol_txt})"

# Sincronizar keys de selector para que no haya desajustes
if "selector_perfil_sidebar" not in st.session_state or st.session_state["selector_perfil_sidebar"] != st.session_state["usuario_id_activo"]:
    st.session_state["selector_perfil_sidebar"] = st.session_state["usuario_id_activo"]
if "selector_perfil_top" not in st.session_state or st.session_state["selector_perfil_top"] != st.session_state["usuario_id_activo"]:
    st.session_state["selector_perfil_top"] = st.session_state["usuario_id_activo"]

# ==================== BARRA LATERAL (SIDEBAR): SELECTOR DE PERFIL ====================
with st.sidebar:
    st.markdown("### 🏃 Team Ardil Hub")
    st.caption("Plataforma de Atletismo y Rendimiento")

    uids_disponibles = [u["id"] for u in usuarios_db]
    cur_uid = st.session_state["usuario_id_activo"]
    if cur_uid not in uids_disponibles:
        cur_uid = 1
        st.session_state["usuario_id_activo"] = 1

    idx_actual = uids_disponibles.index(cur_uid)

    def on_cambio_perfil():
        uid_sel = st.session_state.get("selector_perfil_sidebar")
        if uid_sel:
            st.session_state["usuario_id_activo"] = uid_sel
            if uid_sel == 2:
                st.session_state["mister_inspeccionando"] = False

    st.selectbox(
        "👤 Perfil Activo:",
        options=uids_disponibles,
        index=idx_actual,
        format_func=formato_usuario,
        key="selector_perfil_sidebar",
        on_change=on_cambio_perfil
    )

    st.markdown("---")

    # Alta rápida de compañero / atleta (Exclusivo para Salva)
    if es_salva:
        with st.expander("➕ Añadir compañero / atleta", expanded=False):
            n_nombre = st.text_input("Nombre y Apellidos:", placeholder="Ej: Pedro Martínez", key="nuevo_atleta_nombre")
            n_alias = st.text_input("Alias (corto):", placeholder="pedro", key="nuevo_atleta_alias")
            n_avatar = st.text_input("Iniciales Avatar (2 letras):", placeholder="PM", max_chars=3, key="nuevo_atleta_avatar")
            if st.button("Guardar Atleta", use_container_width=True, key="btn_guardar_nuevo_atleta"):
                if n_nombre and n_alias:
                    clean_ali = n_alias.lower().strip()
                    if clean_ali == "salva":
                        st.error("El alias 'salva' está reservado para tu perfil principal.")
                    else:
                        nuevo_id = database.crear_o_actualizar_usuario(
                            nombre=n_nombre.strip(),
                            alias=clean_ali,
                            rol="atleta",
                            entrenador_id=2,
                            avatar=n_avatar.upper().strip() if n_avatar else "🏃"
                        )
                        st.session_state["usuario_id_activo"] = nuevo_id
                        st.success(f"Atleta '{n_nombre}' registrado.")
                        st.rerun()
                else:
                    st.warning("Introduce al menos nombre y alias.")

# Comprobar estado de sincronización del perfil activo (Garmin, COROS o Strava)
def comprobar_estado_sync(uid: int) -> bool:
    # 1. Salva (uid == 1) cuenta con el Auto-Sync nocturno activo en la nube (GitHub Actions + Garmin)
    if uid == 1:
        return True

    # 2. El Míster (uid == 2) tiene supervisión global de todo el equipo
    if uid == 2:
        return True

    # 3. Comprobar tokens locales de Garmin si existen
    tok_g = os.path.join(os.path.dirname(__file__), ".garmin_tokens")
    if os.path.isfile(os.path.join(tok_g, f"garmin_tokens_u{uid}.json")) or os.path.isfile(os.path.join(tok_g, "garmin_tokens.json")):
        return True

    # 4. Comprobar tokens de COROS
    tok_c = os.path.join(os.path.dirname(__file__), ".coros_tokens")
    if os.path.isfile(os.path.join(tok_c, f"coros_tokens_u{uid}.json")) or os.path.isfile(os.path.join(tok_c, "coros_tokens.json")):
        return True

    # 5. Comprobar tokens de Strava
    tok_s = os.path.join(os.path.dirname(__file__), ".strava_tokens")
    if os.path.isfile(os.path.join(tok_s, f"strava_tokens_u{uid}.json")) or os.path.isfile(os.path.join(tok_s, "strava_tokens.json")):
        return True

    # 6. Si el atleta ya cuenta con entrenamientos sincronizados en la base de datos
    try:
        conn = database.get_connection()
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM entrenamientos WHERE usuario_id = ?", (uid,))
        num = c.fetchone()[0]
        conn.close()
        if num > 0:
            return True
    except Exception:
        pass

    return False

sync_activo = comprobar_estado_sync(usuario_id)
if sync_activo:
    pill_device_html = '<div class="notranslate" translate="no" style="background: rgba(16, 185, 129, 0.16); border: 1.5px solid rgba(16, 185, 129, 0.5); color: #10B981; font-weight: 700; padding: 6px 14px; border-radius: 20px; font-size: 12.5px; display: inline-flex; align-items: center; gap: 7px; letter-spacing: 0.3px;"><span style="font-size: 11px;">●</span> Conectado</div>'
else:
    pill_device_html = '<div class="notranslate" translate="no" style="background: rgba(239, 68, 68, 0.16); border: 1.5px solid rgba(239, 68, 68, 0.5); color: #EF4444; font-weight: 700; padding: 6px 14px; border-radius: 20px; font-size: 12.5px; display: inline-flex; align-items: center; gap: 7px; letter-spacing: 0.3px;"><span style="font-size: 11px;">●</span> Error</div>'

# Encabezado Ardil Track con icono del caballo sin texto e insignia oficial Team Ardil
horse_img = b64_horse if b64_horse else b64_bg
ardil_icon_html = f'<img src="data:image/jpeg;base64,{horse_img}" style="width: 58px; height: 58px; border-radius: 12px; object-fit: contain; background: #14171A; border: 1.5px solid rgba(255,255,255,0.22); box-shadow: 0 2px 10px rgba(0,0,0,0.5); padding: 3px;" alt="Ardil Track">' if horse_img else '<span class="garmin-logo-badge" style="width: 58px; height: 58px; font-size: 28px;">🐎</span>'
ardil_pill_html = f'<div class="notranslate" translate="no" style="display: flex; align-items: center; gap: 8px; background: rgba(255,255,255,0.12); padding: 5px 14px 5px 6px; border-radius: 20px; border: 1px solid rgba(255,255,255,0.18);"><img src="data:image/jpeg;base64,{b64_bg}" style="width: 26px; height: 26px; border-radius: 50%; object-fit: cover;"><span style="font-weight: 800; color: #FFFFFF; font-size: 12px; letter-spacing: 0.6px;">TEAM ARDIL</span></div>' if b64_bg else '<span class="notranslate" translate="no" style="background: rgba(255,255,255,0.12); padding: 5px 12px; border-radius: 8px; font-weight: 800; color: #FFFFFF; font-size: 12px; letter-spacing: 0.5px;">TEAM ARDIL</span>'

# Siempre mostrar el atleta activo en el subtítulo para saber a quién se consulta
nombre_activo_disp = usuario_activo.get("nombre", "Atleta")
if es_admin and usuario_id == 1:
    ardil_sub_txt = f"Team Ardil · Administrador | {nombre_activo_disp}"
elif es_entrenador:
    ardil_sub_txt = f"Team Ardil · Panel de Control del Entrenador | {nombre_activo_disp}"
else:
    ardil_sub_txt = f"Team Ardil · Athletics Coach | {nombre_activo_disp}"

st.markdown(f"""
<div class="garmin-topbar notranslate" translate="no">
    <div style="display: flex; align-items: center; gap: 16px;">
        {ardil_icon_html}
        <div class="notranslate" translate="no">
            <div class="garmin-brand-title notranslate" translate="no" style="font-size: 21px; font-weight: 800; letter-spacing: 0.8px;">
                ARDIL TRACK<span style="color: #00A3E0; font-size: 12px; vertical-align: super; font-weight: 700; margin-left: 2px;"> AI</span>
            </div>
            <div class="garmin-brand-sub notranslate" translate="no" style="color: #94A3B8; font-size: 12.5px;">{ardil_sub_txt}</div>
        </div>
    </div>
    <div style="display: flex; align-items: center; gap: 14px;">
        {ardil_pill_html}
        {pill_device_html}
    </div>
</div>
""", unsafe_allow_html=True)

# Selector rápido de Atleta / Perfil (visible para Salva/Admin y Míster sin necesidad de abrir la barra lateral)
col_prof_sel, col_prof_tag = st.columns([3.8, 1.2])
with col_prof_sel:
    def on_cambio_perfil_top():
        uid_t = st.session_state.get("selector_perfil_top")
        if uid_t:
            st.session_state["usuario_id_activo"] = uid_t
            if uid_t == 2:
                st.session_state["mister_inspeccionando"] = False

    st.selectbox(
        "👥 Seleccionar Atleta / Perfil (Acceso directo):",
        options=uids_disponibles,
        index=idx_actual,
        format_func=formato_usuario,
        key="selector_perfil_top",
        on_change=on_cambio_perfil_top
    )
with col_prof_tag:
    badge_label = "👑 Administrador" if (es_admin and usuario_id == 1) else ("👨‍🏫 Míster" if es_entrenador else "🏃 Atleta")
    st.markdown(f"<div style='padding-top: 28px;'><span style='background: #E8F4FA; color: #007CC3; border: 1.5px solid #007CC3; padding: 7px 12px; border-radius: 8px; font-weight: 700; font-size: 13px; display: block; text-align: center; box-shadow: 0 2px 6px rgba(0,124,195,0.12);'>{badge_label}</span></div>", unsafe_allow_html=True)

if st.session_state.get("mister_inspeccionando") and not es_entrenador:
    col_insp1, col_insp2 = st.columns([4, 1.2])
    with col_insp1:
        st.info(f"👨‍🏫 **Modo Vista Míster Activo:** Estás inspeccionando la ficha, entrenamientos y series de **{usuario_activo['nombre']}**.")
    with col_insp2:
        if st.button("🔙 Volver al Míster", type="primary", use_container_width=True, key="btn_volver_mister"):
            st.session_state["usuario_id_activo"] = 2
            st.session_state["mister_inspeccionando"] = False
            st.rerun()

# Resumen superior filtrado por atleta activo
stats = database.obtener_resumen_estadisticas(usuario_id=usuario_id)
total_km = stats.get("total_km", 0)
total_entrenos = stats.get("total_entrenos", 0)
media_km = round(total_km / max(1, total_entrenos), 1)

# Enlace del plan oficial individual del atleta activo (estrictamente aislado)
doc_url = usuario_activo.get("doc_plan_url")

@st.cache_data(ttl=120)
def cargar_plan_y_comparativa(url_doc, u_id=1):
    if not url_doc:
        return [], {"comparativa": [], "preguntas_discrepancias": []}
    try:
        p_dias = plan_entrenador.descargar_plan_entrenador(url_doc)
        reconc = plan_entrenador.conciliar_plan_con_garmin(p_dias, usuario_id=u_id)
        return p_dias, reconc
    except Exception as e:
        return [], {"comparativa": [], "preguntas_discrepancias": []}

plan_dias, reconciliacion = cargar_plan_y_comparativa(doc_url, u_id=usuario_id)
comparativa_plan = reconciliacion.get("comparativa", [])

def es_sesion_series_real(entreno_id: int, fecha: str, titulo: str, notas: str = "", plan_comparativa: list = None) -> bool:
    """
    Verifica si una actividad es verdaderamente una sesión de series:
    1. Si la fecha coincide con el plan del entrenador, tiene prioridad la prescripción del míster.
    2. Si no coincide o es histórico:
       - Se descartan competiciones oficiales (maratón, media, 10k oficial, dorsal).
       - Se analizan las vueltas registradas: si tiene repeticiones a ritmo vivo con recuperaciones o título de series, es serie.
    """
    f_dia = str(fecha)[:10]

    # 1. Comprobación directa contra el Plan del Entrenador (si coincide la fecha)
    if plan_comparativa:
        for p in plan_comparativa:
            if p.get("fecha") == f_dia:
                desc = (p.get("plan_descripcion") or "").lower()
                tit_sug = (p.get("titulo_sugerido") or "").lower()
                tiene_patron = bool(re.search(r'\b\d+\s*x\s*\d+', desc) or "serie" in desc or "series" in tit_sug)
                if p.get("es_series") or tiene_patron:
                    return True
                else:
                    return False

    texto = f"{titulo or ''} {notas or ''}".lower()

    # 2. Descarte por competiciones oficiales reales (descartar si no hay mención de series)
    competiciones = [
        "maratón", "maraton", "media maratón", "media maraton",
        "competición", "competicion", "dorsal", "san silvestre",
        "trail", "cross", "trofeo", "campeonato", "carrera popular", "carrera oficial"
    ]
    palabras_series = [
        "serie", "series", "interval", "x1000", "x400", "x2000", "x500", "x200", "x300", "x800",
        "x1500", "x3000", "x4000", "4000m", "3000m", "2000m", "1000m", "800m", "500m", "400m", "300m", "200m"
    ]

    if any(c in texto for c in competiciones) and not any(s in texto for s in palabras_series):
        return False

    # 3. Comprobar si tiene estructura real de series según sus vueltas/laps
    try:
        _, laps = database.obtener_detalle_entrenamiento(entreno_id)
        if laps and len(laps) >= 2:
            _, resumen = database.clasificar_vueltas_sesion(laps)
            num_series = resumen.get("num_series", 0)
            num_recup = resumen.get("num_recuperaciones", 0)
            if num_series >= 2 and num_recup >= 1:
                return True
            if bool(re.search(r'\b\d+\s*x\s*\d+', texto) or any(s in texto for s in palabras_series)):
                return True
    except Exception:
        pass

    if bool(re.search(r'\b\d+\s*x\s*\d+', texto) or any(s in texto for s in palabras_series)):
        return True

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

# ==================== MONITOR GENERAL DEL ENTRENADOR ====================
def render_monitor_equipo():
    dias_semana_es = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
    meses_es = ["", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
    hoy = date.today()
    fecha_hoy_txt = f"{dias_semana_es[hoy.weekday()]}, {hoy.day} de {meses_es[hoy.month]} de {hoy.year}"

    resumen_eq = database.obtener_resumen_equipo(entrenador_id=usuario_id)
    atletas = resumen_eq.get("atletas", [])
    total_atletas = resumen_eq.get("total_atletas", len(atletas))
    entrenados_hoy = resumen_eq.get("entrenados_hoy", 0)
    pendientes_hoy = resumen_eq.get("pendientes_hoy", max(0, total_atletas - entrenados_hoy))
    km_esta_sem = sum(a.get("km_semana", 0) for a in atletas)

    # Encabezado minimalista estilo panel de control de élite
    st.markdown(f"""
    <div style="background: linear-gradient(135deg, #0F172A 0%, #1E293B 100%); border-radius: 16px; padding: 20px 24px; color: white; margin-bottom: 22px; box-shadow: 0 4px 15px rgba(0,0,0,0.12);">
        <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 14px;">
            <div>
                <div style="font-size: 23px; font-weight: 800; letter-spacing: -0.3px; display: flex; align-items: center; gap: 10px;">
                    <span>👑 Panel del Míster</span>
                    <span style="font-size: 13px; font-weight: 700; background: rgba(0, 163, 224, 0.25); color: #38BDF8; padding: 3px 12px; border-radius: 20px; border: 1px solid rgba(56, 189, 248, 0.35);">Team Ardil</span>
                </div>
                <div style="font-size: 13.5px; color: #94A3B8; margin-top: 5px;">📅 {fecha_hoy_txt} · Resumen de entrenamientos en tiempo real</div>
            </div>
            <div style="display: flex; align-items: center; gap: 10px; flex-wrap: wrap;">
                <div style="background: rgba(255,255,255,0.08); border: 1px solid rgba(255,255,255,0.14); border-radius: 10px; padding: 6px 14px; text-align: center;">
                    <div style="font-size: 10px; color: #94A3B8; font-weight: 700; text-transform: uppercase;">Atletas</div>
                    <div style="font-size: 17px; font-weight: 800; color: #FFFFFF;">{total_atletas}</div>
                </div>
                <div style="background: rgba(16, 185, 129, 0.16); border: 1px solid rgba(16, 185, 129, 0.35); border-radius: 10px; padding: 6px 14px; text-align: center;">
                    <div style="font-size: 10px; color: #6EE7B7; font-weight: 700; text-transform: uppercase;">Hecho Hoy</div>
                    <div style="font-size: 17px; font-weight: 800; color: #34D399;">{entrenados_hoy}</div>
                </div>
                <div style="background: rgba(245, 158, 11, 0.16); border: 1px solid rgba(245, 158, 11, 0.35); border-radius: 10px; padding: 6px 14px; text-align: center;">
                    <div style="font-size: 10px; color: #FCD34D; font-weight: 700; text-transform: uppercase;">Pendientes</div>
                    <div style="font-size: 17px; font-weight: 800; color: #FBBF24;">{pendientes_hoy}</div>
                </div>
                <div style="background: rgba(14, 165, 233, 0.16); border: 1px solid rgba(14, 165, 233, 0.35); border-radius: 10px; padding: 6px 14px; text-align: center;">
                    <div style="font-size: 10px; color: #7DD3FC; font-weight: 700; text-transform: uppercase;">Km Semana</div>
                    <div style="font-size: 17px; font-weight: 800; color: #38BDF8;">{km_esta_sem:.1f} km</div>
                </div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Filtro rápido limpio
    filtro_col, buscador_col = st.columns([3, 2])
    with filtro_col:
        filtro_opciones = [
            f"Todos ({total_atletas})",
            f"🟢 Hecho hoy ({entrenados_hoy})",
            f"⏳ Pendientes ({pendientes_hoy})"
        ]
        if hasattr(st, "segmented_control"):
            filtro_sel = st.segmented_control("Filtrar:", filtro_opciones, default=filtro_opciones[0], label_visibility="collapsed")
        else:
            filtro_sel = st.radio("Filtrar:", filtro_opciones, horizontal=True, label_visibility="collapsed")
    with buscador_col:
        texto_busqueda = st.text_input("🔍 Buscar atleta...", placeholder="Escribe el nombre de un atleta...", label_visibility="collapsed")

    # Filtrar lista de atletas
    atletas_mostrar = []
    for a in atletas:
        if texto_busqueda and texto_busqueda.lower() not in a["nombre"].lower() and texto_busqueda.lower() not in a.get("alias", "").lower():
            continue
        ha_entrenado = a.get("entreno_hoy") is not None
        if "Hecho hoy" in (filtro_sel or "") and not ha_entrenado:
            continue
        if "Pendientes" in (filtro_sel or "") and ha_entrenado:
            continue
        atletas_mostrar.append(a)

    if not atletas_mostrar:
        st.info("No se encontraron atletas con los filtros seleccionados.")
        return

    # Renderizar cada atleta en una tarjeta limpia "De un plumazo"
    for a in atletas_mostrar:
        uid = a["id"]
        nombre = a["nombre"]
        avatar = a.get("avatar") or (nombre[:2].upper() if len(nombre) >= 2 else "🏃")
        entreno_hoy = a.get("entreno_hoy")
        plan_hoy = a.get("plan_hoy")
        ultimo_fecha = a.get("ultimo_fecha")
        ultimo_titulo = a.get("ultimo_titulo")
        ultimo_km = a.get("ultimo_km")
        ultimo_ritmo = a.get("ultimo_ritmo")
        km_semana = a.get("km_semana", 0.0)
        entrenos_semana = a.get("entrenos_semana", 0)
        plataformas = a.get("plataformas", [])

        plataforma_txt = " · ".join(plataformas) if plataformas else "Sin vincular"

        col_avatar, col_entreno, col_semana_btn = st.columns([2.6, 5.2, 2.2])

        with col_avatar:
            st.markdown(f"""
            <div style="display: flex; align-items: center; gap: 14px; padding: 10px 0;">
                <div style="width: 48px; height: 48px; border-radius: 50%; background: linear-gradient(135deg, #007CC3 0%, #004C75 100%); color: white; display: flex; align-items: center; justify-content: center; font-weight: 800; font-size: 16px; box-shadow: 0 2px 8px rgba(0, 124, 195, 0.25); flex-shrink: 0;">
                    {avatar}
                </div>
                <div>
                    <div style="font-size: 16.5px; font-weight: 800; color: #0F172A; line-height: 1.2;">{nombre}</div>
                    <div style="font-size: 12px; color: #64748B; margin-top: 3px;">
                        <span style="display: inline-block; width: 7px; height: 7px; border-radius: 50%; background: {'#10B981' if plataformas else '#94A3B8'}; margin-right: 4px;"></span>
                        {plataforma_txt}
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)

        with col_entreno:
            if entreno_hoy:
                hora_txt = f" a las {entreno_hoy['hora']}" if entreno_hoy.get('hora') else ""
                origen_badge = f"<span style='background: #E0F2FE; color: #0369A1; font-weight: 700; font-size: 11px; padding: 2px 7px; border-radius: 6px; margin-left: 6px;'>{entreno_hoy['origen']}</span>" if entreno_hoy.get('origen') else ""
                fc_txt = f"<span style='color: #E11D48; font-weight: 700;'> ♥ {entreno_hoy['fc']} ppm</span>" if entreno_hoy.get('fc') else ""

                st.markdown(f"""
                <div style="background: #F0FDF4; border: 1.5px solid #86EFAC; border-radius: 12px; padding: 10px 14px; margin: 4px 0;">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px;">
                        <div style="display: flex; align-items: center; gap: 6px;">
                            <span style="background: #10B981; color: white; font-weight: 800; font-size: 11px; padding: 2px 8px; border-radius: 12px; text-transform: uppercase; letter-spacing: 0.5px;">✓ Hecho hoy</span>
                            <span style="font-size: 12px; color: #047857; font-weight: 600;">{hora_txt}</span>
                            {origen_badge}
                        </div>
                    </div>
                    <div style="display: flex; align-items: baseline; gap: 14px; flex-wrap: wrap;">
                        <span style="font-size: 20px; font-weight: 800; color: #065F46;">{entreno_hoy['km']} km</span>
                        <span style="font-size: 15px; font-weight: 700; color: #047857;">⏱️ {entreno_hoy['tiempo']}</span>
                        <span style="font-size: 15px; font-weight: 700; color: #047857;">⚡ {entreno_hoy['ritmo']} <span style="font-size: 11px; font-weight: 500;">min/km</span></span>
                        {fc_txt}
                    </div>
                    <div style="font-size: 12.5px; color: #166534; font-weight: 600; margin-top: 3px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">
                        {entreno_hoy['titulo']}
                    </div>
                </div>
                """, unsafe_allow_html=True)
            else:
                # Pendiente hoy
                plan_tit = plan_hoy.get("titulo") if plan_hoy else None

                if plan_tit:
                    plan_html = f"<div style='font-size: 13px; color: #92400E; font-weight: 700; margin-top: 2px;'>🎯 Plan hoy: <span style='color: #B45309;'>{plan_tit}</span></div>"
                else:
                    plan_html = "<div style='font-size: 12px; color: #94A3B8; font-style: italic; margin-top: 2px;'>Sin sesión programada en el plan para hoy</div>"

                if ultimo_fecha:
                    ult_txt = f"<div style='font-size: 11.5px; color: #64748B; margin-top: 3px;'>Última sesión: <b>{ultimo_fecha}</b> ({ultimo_km} km @ {ultimo_ritmo} min/km) · <i>{ultimo_titulo}</i></div>"
                else:
                    ult_txt = "<div style='font-size: 11.5px; color: #94A3B8; margin-top: 3px;'>Sin entrenamientos registrados todavía</div>"

                st.markdown(f"""
                <div style="background: #FFFBEB; border: 1px solid #FDE68A; border-radius: 12px; padding: 10px 14px; margin: 4px 0;">
                    <div style="display: flex; align-items: center; gap: 6px;">
                        <span style="background: #F59E0B; color: white; font-weight: 800; font-size: 11px; padding: 2px 8px; border-radius: 12px; text-transform: uppercase; letter-spacing: 0.5px;">⏳ Pendiente hoy</span>
                    </div>
                    {plan_html}
                    {ult_txt}
                </div>
                """, unsafe_allow_html=True)

        with col_semana_btn:
            st.markdown(f"""
            <div style="text-align: right; padding-top: 6px; padding-right: 4px;">
                <div style="font-size: 11px; font-weight: 700; color: #64748B; text-transform: uppercase;">Esta semana</div>
                <div style="font-size: 19px; font-weight: 800; color: #007CC3;">{km_semana:.1f} <span style="font-size: 12px; font-weight: 600;">km</span></div>
                <div style="font-size: 11px; color: #94A3B8;">{entrenos_semana} {'sesión' if entrenos_semana == 1 else 'sesiones'}</div>
            </div>
            """, unsafe_allow_html=True)

            if st.button("🔍 Ver ficha", key=f"btn_insp_card_{uid}", use_container_width=True):
                st.session_state["usuario_id_activo"] = uid
                st.session_state["mister_inspeccionando"] = True
                st.rerun()

        st.markdown("<div style='height: 1px; background: #E2E8F0; margin: 8px 0 14px 0;'></div>", unsafe_allow_html=True)

def render_tab_home_atleta():
    # --- 1. DATO: ÚLTIMO ENTRENO ---
    ultimo_entreno_raw = database.ejecutar_consulta_sql("SELECT * FROM entrenamientos WHERE usuario_id = ? ORDER BY fecha DESC LIMIT 1", (usuario_id,))
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

    # --- 2. DATO: PRÓXIMA COMPETICIÓN O RODAJE LARGO DEL DOMINGO ---
    hoy_str = date.today().strftime("%Y-%m-%d")

    def es_competicion_real(p):
        texto = (p.get("titulo_sugerido", "") + " " + p.get("plan_descripcion", "") + " " + p.get("descripcion", "")).lower()
        if any(k in texto for k in ["rodaje", "series", "descanso", "fuerza", "long run", "tabla", "calentamiento"]):
            return False
        if any(k in texto for k in ["maratón", "maraton", "media maratón", "media maraton", "competición", "competicion", "dorsal", "campeonato", "cross", "trail"]):
            return True
        if "carrera" in texto and "rodaje" not in texto:
            return True
        return False

    carreras_futuras = [
        p for p in plan_dias
        if p.get("fecha", "") >= hoy_str and es_competicion_real(p)
    ]

    if carreras_futuras:
        hay_competicion = True
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
        badge_cls_comp = "garmin-badge-orange"
        color_metrica_comp = "#D97706"
        bg_grid_comp = "background: #FFFBEB; border: 1px solid #FDE68A;"
        color_grid_title = "#B45309"
        color_grid_val = "#92400E"
        grid_col1_lbl = "📅 Fecha"
        grid_col1_val = f_comp
        grid_col2_lbl = "🎯 Prueba"
        grid_col2_val = dist_comp
        sub_aviso_comp = ""
    else:
        hay_competicion = False
        # Buscar el próximo domingo en el plan (habitualmente rodaje largo / long run)
        domingos_futuros = [p for p in plan_dias if p.get("dia_semana") == "Domingo" and p.get("fecha", "") >= hoy_str]
        if domingos_futuros:
            prox_dom = domingos_futuros[0]
            f_comp = prox_dom.get("fecha", "")
            tit_dom_sug = prox_dom.get("titulo_sugerido", "")
            tit_comp = tit_dom_sug if any(w in tit_dom_sug.lower() for w in ["long run", "rodaje"]) else f"Rodaje Largo ({tit_dom_sug})"
            m_km = re.search(r'(\d+(?:[.,]\d+)?)\s*(?:kms?|k)\b', prox_dom.get("descripcion", ""), re.IGNORECASE)
            dist_comp = f"{m_km.group(1)} km" if m_km else "Tirada Larga"
            try:
                d_dom = date.fromisoformat(f_comp)
                diff_dias = (d_dom - date.today()).days
                if diff_dias == 0:
                    badge_comp = "¡HOY DOMINGO!"
                    dias_comp_txt = "Hoy es la tirada"
                elif diff_dias == 1:
                    badge_comp = "¡ESTE DOMINGO!"
                    dias_comp_txt = "En 1 día"
                else:
                    badge_comp = f"DOMINGO · EN {diff_dias} DÍAS"
                    dias_comp_txt = f"{diff_dias} días restantes"
            except Exception:
                badge_comp = "ESTE DOMINGO"
                dias_comp_txt = f_comp
            tipo_comp = "Rodaje Largo · Plan Míster"
        else:
            tit_comp = "Rodaje Largo (Domingo)"
            f_comp = "Próximo Domingo"
            dist_comp = "Tirada Larga"
            badge_comp = "SIN COMPETICIÓN"
            dias_comp_txt = "Fin de semana"
            tipo_comp = "Entrenamiento de fondo"

        badge_cls_comp = "garmin-badge-blue"
        color_metrica_comp = "#0284C7"
        bg_grid_comp = "background: #F0F9FF; border: 1px solid #BAE6FD;"
        color_grid_title = "#0369A1"
        color_grid_val = "#0C4A6E"
        grid_col1_lbl = "📅 Próximo Domingo"
        grid_col1_val = f_comp
        grid_col2_lbl = "🏃 Enfoque Fondo"
        grid_col2_val = f"Rodaje Largo ({dist_comp})"
        sub_aviso_comp = '<div style="font-size: 11px; font-weight: 700; color: #64748B; margin-bottom: 3px;">🚫 Sin competición próxima en el plan · Objetivo:</div>'

    # --- 3. DATO: ÚLTIMO DÍA DE SERIES Y DATOS (Solo series reales confirmadas por el plan) ---
    query_ult_series = """
    SELECT e.id, e.fecha, e.titulo, e.ubicacion, e.notas_entrenador
    FROM entrenamientos e
    JOIN series_laps s ON s.entrenamiento_id = e.id
    WHERE s.distancia_m >= 150 AND e.usuario_id = ?
    GROUP BY e.id
    HAVING COUNT(s.id) >= 2
    ORDER BY e.fecha DESC
    LIMIT 25
    """
    candidatos_series = database.ejecutar_consulta_sql(query_ult_series, (usuario_id,))
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
        n_series = len(laps_s_solo) if laps_s_solo else s_resumen.get("num_series", 0)
        
        if laps_s_solo:
            t_laps = [l["tiempo_s"] for l in laps_s_solo if l.get("tiempo_s")]
            mejor_t_s = min(t_laps) if t_laps else 0
            media_t_s = sum(t_laps) / len(t_laps) if t_laps else 0
            mejor_serie_str = f"{int(mejor_t_s // 60)}:{int(mejor_t_s % 60):02d}"
            media_serie_str = f"{int(media_t_s // 60)}:{int(media_t_s % 60):02d}"
        else:
            mejor_serie_str = "--:--"
            media_serie_str = "--:--"
        hay_series = True
    else:
        hay_series = False
        tit_series = "Sin series registradas"
        f_series = "--"
        ub_series = ""
        n_series = 0
        mejor_serie_str = "--:--"
        media_serie_str = "--:--"

    # 1. "Lo esencial" (3 tarjetas destacadas) con botón de Sincronizar directo
    c_hdr_es, c_hdr_sync = st.columns([4.2, 1.3])
    with c_hdr_es:
        st.markdown("<div style='margin-bottom: 8px; font-size: 13px; font-weight: 700; color: #64748B; text-transform: uppercase; letter-spacing: 0.8px; padding-top: 8px;'>⚡ Lo Esencial</div>", unsafe_allow_html=True)
    with c_hdr_sync:
        plat_u = usuario_activo.get("plataforma_principal", "garmin")
        lbl_sync = "🔄 Sincronizar COROS" if (plat_u == "coros" or tiene_coros) else ("🔄 Sincronizar Garmin" if (plat_u == "garmin" or tiene_garmin) else "🔄 Sincronizar Strava")
        if st.button(lbl_sync, key="btn_sync_inicio", type="primary", use_container_width=True):
            with st.spinner(f"Sincronizando {lbl_sync.replace('🔄 Sincronizar ', '')}..."):
                nuevas, omitidas, detalle = sincronizar_actividades_todas()
            if nuevas > 0:
                st.success(f"🎉 ¡Sincronizado! **{nuevas}** nuevos entrenamientos ({detalle}).")
                time.sleep(1)
                st.rerun()
            elif "No hay ninguna plataforma" in detalle or "Sin sesión activa" in detalle:
                st.warning(f"ℹ️ {detalle}")
            elif "error" in detalle.lower():
                st.error(f"Aviso durante la sincronización: {detalle}")
            else:
                st.info(f"✅ Todo al día ({detalle}).")

    c_es1, c_es2, c_es3 = st.columns(3)
    
    with c_es1:
        if ultimo_entreno_raw:
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
        else:
            st.markdown("""
            <div class="garmin-card" style="padding: 16px; margin-bottom: 14px;">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                    <span style="font-size: 11px; font-weight: 700; color: #64748B; text-transform: uppercase;">🏃 Último Entreno</span>
                    <span class="garmin-badge-gray">Sin actividades</span>
                </div>
                <div style="font-size: 17px; font-weight: 800; color: #181C20; margin-bottom: 2px;">
                    Sin registros todavía
                </div>
                <div style="font-size: 11px; color: #64748B; margin-bottom: 10px;">Conecta tu reloj en Personal</div>
                <div style="display: flex; align-items: baseline; gap: 6px; margin-bottom: 10px;">
                    <span style="font-size: 32px; font-weight: 800; color: #94A3B8; line-height: 1;">0.00</span>
                    <span style="font-size: 14px; font-weight: 700; color: #64748B;">km</span>
                    <span style="font-size: 12px; color: #64748B; margin-left: 6px;">⏱️ --:--</span>
                </div>
                <div style="background: #F8FAFC; padding: 10px 12px; border-radius: 8px; border: 1px solid #E2E8F0; font-size: 12px; color: #64748B;">
                    Sincroniza Garmin, Coros o Strava para ver tus ritmos.
                </div>
            </div>
            """, unsafe_allow_html=True)
        
    with c_es2:
        if hay_competicion or (not hay_competicion and domingos_futuros):
            st.markdown(f"""
            <div class="garmin-card" style="padding: 16px; margin-bottom: 14px;">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                    <span style="font-size: 11px; font-weight: 700; color: #64748B; text-transform: uppercase;">🎯 Próxima Competición</span>
                    <span class="{badge_cls_comp}">{badge_comp}</span>
                </div>
                {sub_aviso_comp}
                <div style="font-size: 17px; font-weight: 800; color: #181C20; margin-bottom: 2px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">
                    {tit_comp}
                </div>
                <div style="font-size: 11px; color: #64748B; margin-bottom: 10px;">{f_comp} · {tipo_comp}</div>
                <div style="display: flex; align-items: baseline; gap: 6px; margin-bottom: 10px;">
                    <span style="font-size: 32px; font-weight: 800; color: {color_metrica_comp}; line-height: 1;">{dist_comp}</span>
                    <span style="font-size: 13px; font-weight: 700; color: #64748B; margin-left: 4px;">({dias_comp_txt})</span>
                </div>
                <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 8px; {bg_grid_comp} padding: 10px 12px; border-radius: 8px;">
                    <div>
                        <div style="font-size: 10px; font-weight: 700; color: {color_grid_title}; text-transform: uppercase;">{grid_col1_lbl}</div>
                        <div style="font-size: 14px; font-weight: 800; color: {color_grid_val};">{grid_col1_val}</div>
                    </div>
                    <div>
                        <div style="font-size: 10px; font-weight: 700; color: {color_grid_title}; text-transform: uppercase;">{grid_col2_lbl}</div>
                        <div style="font-size: 14px; font-weight: 800; color: {color_grid_val};">{grid_col2_val}</div>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown("""
            <div class="garmin-card" style="padding: 16px; margin-bottom: 14px;">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                    <span style="font-size: 11px; font-weight: 700; color: #64748B; text-transform: uppercase;">🎯 Próxima Competición</span>
                    <span class="garmin-badge-gray">Sin plan</span>
                </div>
                <div style="font-size: 17px; font-weight: 800; color: #181C20; margin-bottom: 2px;">
                    Sin objetivo en el plan
                </div>
                <div style="font-size: 11px; color: #64748B; margin-bottom: 10px;">Planificación independiente</div>
                <div style="display: flex; align-items: baseline; gap: 6px; margin-bottom: 10px;">
                    <span style="font-size: 32px; font-weight: 800; color: #94A3B8; line-height: 1;">--</span>
                    <span style="font-size: 13px; font-weight: 700; color: #64748B; margin-left: 4px;">(Sin asignar)</span>
                </div>
                <div style="background: #F8FAFC; border: 1px solid #E2E8F0; padding: 10px 12px; border-radius: 8px; font-size: 12px; color: #64748B;">
                    Asigna tu Google Doc en Personal para ver tu calendario.
                </div>
            </div>
            """, unsafe_allow_html=True)
        
    with c_es3:
        if hay_series:
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
        else:
            st.markdown("""
            <div class="garmin-card" style="padding: 16px; margin-bottom: 14px;">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                    <span style="font-size: 11px; font-weight: 700; color: #64748B; text-transform: uppercase;">⚡ Último Día de Series</span>
                    <span class="garmin-badge-gray">Sin series</span>
                </div>
                <div style="font-size: 17px; font-weight: 800; color: #181C20; margin-bottom: 2px;">
                    Sin series registradas
                </div>
                <div style="font-size: 11px; color: #64748B; margin-bottom: 10px;">Entrenamiento interválico</div>
                <div style="display: flex; align-items: baseline; gap: 6px; margin-bottom: 10px;">
                    <span style="font-size: 32px; font-weight: 800; color: #94A3B8; line-height: 1;">--:--</span>
                    <span style="font-size: 14px; font-weight: 700; color: #64748B;">min</span>
                </div>
                <div style="background: #F8FAFC; padding: 10px 12px; border-radius: 8px; border: 1px solid #E2E8F0; font-size: 12px; color: #64748B;">
                    No hay sesiones de series registradas para este atleta.
                </div>
            </div>
            """, unsafe_allow_html=True)

    # 2. "En primer plano" (In Focus)
    st.markdown("<div style='margin-top: 10px; margin-bottom: 8px; font-size: 13px; font-weight: 700; color: #64748B; text-transform: uppercase; letter-spacing: 0.8px;'>🎯 En Primer Plano</div>", unsafe_allow_html=True)
    col_focus_left, col_focus_right = st.columns([1.1, 0.9])

    with col_focus_left:
        # Actividad Reciente / Destacada
        ultimos_entrenos = database.ejecutar_consulta_sql("SELECT * FROM entrenamientos WHERE usuario_id = ? ORDER BY fecha DESC LIMIT 15", (usuario_id,))
        if ultimos_entrenos:
            opciones_entrenos = {
                f"{e['fecha'][:10]} · {e['titulo']} ({e['distancia_km']} km)": e['id']
                for e in ultimos_entrenos
            }
            # Selector compacto para cambiar de actividad
            sel_nombre = st.selectbox("🔽 Seleccionar actividad para visualizar:", list(opciones_entrenos.keys()), index=0)
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
        else:
            st.markdown("""
            <div class="garmin-card">
                <div class="garmin-card-header">
                    <div class="garmin-card-title">
                        <span style="font-size: 18px;">🏃</span> ACTIVIDAD RECIENTE
                    </div>
                    <span class="garmin-badge-gray">Sin actividades</span>
                </div>
                <div style="padding: 24px 12px; text-align: center; color: #64748B;">
                    <div style="font-size: 28px; margin-bottom: 8px;">⏳</div>
                    <div style="font-size: 15px; font-weight: 700; color: #181C20; margin-bottom: 4px;">Aún no hay entrenamientos registrados</div>
                    <div style="font-size: 12px;">Sincroniza tus sesiones de Garmin, Coros o Strava desde la pestaña <b>Personal</b>.</div>
                </div>
            </div>
            """, unsafe_allow_html=True)

    with col_focus_right:
        # Tarjeta Plan de Entrenamiento · Esta Semana (Google Docs)
        # Identificar dinámicamente la semana actual según la fecha de hoy
        hoy = date.today()
        hoy_str = hoy.strftime("%Y-%m-%d")
        lunes_actual = hoy - timedelta(days=hoy.weekday())
        domingo_actual = lunes_actual + timedelta(days=6)
        lunes_str = lunes_actual.strftime("%Y-%m-%d")
        domingo_str = domingo_actual.strftime("%Y-%m-%d")

        semana_actual_nombre = None
        for p in plan_dias:
            if p.get("fecha") == hoy_str and p.get("semana"):
                semana_actual_nombre = p["semana"]
                break

        if semana_actual_nombre:
            fechas_semana_actual = {p["fecha"] for p in plan_dias if p.get("semana") == semana_actual_nombre}
            dias_esta_sem = [c for c in comparativa_plan if c.get("fecha") in fechas_semana_actual]
            semana_titulo = semana_actual_nombre.replace('\n', ' ').strip()
        else:
            dias_esta_sem = [c for c in comparativa_plan if lunes_str <= c.get("fecha", "") <= domingo_str]
            semana_titulo = f"{lunes_actual.strftime('%d-%m')} al {domingo_actual.strftime('%d-%m')}"

        if not dias_esta_sem and comparativa_plan:
            dias_esta_sem = comparativa_plan[-7:]
            semana_titulo = "Semana reciente"

        st.markdown(f"""
        <div class="garmin-card">
            <div class="garmin-card-header">
                <div class="garmin-card-title">
                    <span style="font-size: 18px;">📋</span> PLAN DEL ENTRENADOR · ESTA SEMANA <span style="font-size: 12px; color: #64748B; font-weight: normal;">({semana_titulo})</span>
                </div>
                <span class="garmin-badge-blue">Google Doc</span>
            </div>
        """, unsafe_allow_html=True)

        if dias_esta_sem:
            for d in dias_esta_sem:
                g = d.get("garmin_entreno")
                badge_cls = "garmin-badge-green" if "Cumplido" in d.get("estado", "") else ("garmin-badge-gray" if d.get("es_descanso") else "garmin-badge-orange")
                garmin_txt = f"🏃 {g['distancia_km']} km | {g['tiempo_formateado']} | {g['ritmo_medio_minkm']}/km" if g else ("💤 Descanso" if d.get("es_descanso") else "⏳ Pendiente de registrar")
                
                es_hoy = (d.get('fecha') == hoy_str)
                bg_border = "background: #EFF6FF; border: 1.5px solid #3B82F6;" if es_hoy else "background: #F8FAFC; border: 1px solid #E2E8F0;"
                hoy_badge = ' <span style="background: #0078D4; color: white; padding: 2px 6px; border-radius: 4px; font-size: 10px; font-weight: 700; margin-left: 6px;">HOY</span>' if es_hoy else ""

                st.markdown(f"""
                <div style="display: flex; align-items: center; justify-content: space-between; padding: 8px 12px; margin-bottom: 8px; {bg_border} border-radius: 8px;">
                    <div>
                        <div style="font-size: 12px; font-weight: 700; color: #181C20;">{d.get('dia_semana', '')} · <span style="color:#64748B; font-weight:normal;">{d.get('fecha', '')}</span>{hoy_badge}</div>
                        <div style="font-size: 13px; font-weight: 700; color: #007CC3;">{d.get('titulo_sugerido', '')}</div>
                        <div style="font-size: 11px; color: #64748B;">{garmin_txt}</div>
                    </div>
                    <span class="{badge_cls}">{d.get('estado', '')}</span>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.markdown("""
            <div style="padding: 24px 12px; text-align: center; color: #64748B;">
                <div style="font-size: 28px; margin-bottom: 8px;">📋</div>
                <div style="font-size: 15px; font-weight: 700; color: #181C20; margin-bottom: 4px;">Sin plan asignado para esta semana</div>
                <div style="font-size: 12px;">Cada atleta cuenta con su propia planificación personalizada. Puedes configurar tu enlace de Google Docs en la pestaña <b>Plan Entrenador</b>.</div>
            </div>
            """, unsafe_allow_html=True)

        st.markdown("</div>", unsafe_allow_html=True)

# Pestañas principales organizadas de forma limpia
if es_entrenador and not es_admin:
    tab_home, tab_chat, tab_plan, tab_series, tab_volumen, tab_historial, tab_personal = st.tabs([
        "👑 Monitor del Equipo",
        "💬 Asistente IA del Míster",
        "📋 Planificación Global",
        "⚡ Análisis de Series",
        "📈 Volumen del Club",
        "📅 Historial",
        "👤 Configuración"
    ])
    tab_monitor = None
elif es_admin:
    tab_home, tab_monitor, tab_chat, tab_plan, tab_series, tab_volumen, tab_historial, tab_personal = st.tabs([
        "🏠 Inicio",
        "👑 Monitor del Equipo",
        "💬 Entrenador IA (Chat)",
        "📋 Plan Entrenador",
        "⚡ Análisis de Series",
        "📈 Volumen y Carga Semanal",
        "📅 Historial",
        "👤 Personal"
    ])
else:
    tab_home, tab_chat, tab_plan, tab_series, tab_volumen, tab_historial, tab_personal = st.tabs([
        "🏠 Inicio",
        "💬 Entrenador IA (Chat)",
        "📋 Plan Entrenador",
        "⚡ Análisis de Series",
        "📈 Volumen y Carga Semanal",
        "📅 Historial",
        "👤 Personal"
    ])
    tab_monitor = None

# ==================== PESTAÑA 0: INICIO O MONITOR DE EQUIPO ====================
with tab_home:
    if es_entrenador and not es_admin:
        render_monitor_equipo()
    else:
        render_tab_home_atleta()

if tab_monitor is not None:
    with tab_monitor:
        render_monitor_equipo()



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
                    <div style="background: #0F172A; border: 1px solid #1E3A8A; border-left: 5px solid #0078D4; padding: 14px 18px; border-radius: 8px; margin-top: 15px;">
                        <div style="display: flex; align-items: center; gap: 8px; font-weight: 700; color: #60A5FA; margin-bottom: 6px;">
                            <span>🗣️ Voz del Míster · Análisis Táctico Team Ardil</span>
                        </div>
                        <div style="font-size: 0.92rem; color: #F1F5F9; line-height: 1.55;">
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
                resp = consultas_ai.responder_consulta_entrenamientos(pregunta_input, usuario_id=usuario_id)
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

    doc_url = usuario_activo.get("doc_plan_url")
    if not doc_url and es_salva:
        doc_url = plan_entrenador.obtener_doc_url()

    if doc_url:
        col_p1, col_p2 = st.columns([3, 1])
        with col_p1:
            st.info(f"🔗 **Documento activo de {usuario_activo['nombre']}**: [Abrir Google Doc de tu Planificación]({doc_url})")
        with col_p2:
            if st.button("🔄 Comprobar cambios ahora", use_container_width=True, key="btn_check_plan_now"):
                cargar_plan_y_comparativa.clear()
                st.success("Plan recargado en vivo directamente desde Google Docs.")
                st.rerun()
    else:
        st.warning(f"⚠️ **{usuario_activo['nombre']} no tiene asignado un enlace de Google Docs con su planificación.** Cada atleta cuenta con un documento independiente.")

    plan_dias, reconciliacion = cargar_plan_y_comparativa(doc_url, u_id=usuario_id)
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
        
        # Seleccionar dinámicamente por defecto la semana del día actual
        hoy = date.today()
        hoy_str = hoy.strftime("%Y-%m-%d")

        semana_fechas = {}
        for p in plan_dias:
            s_name = p.get("semana")
            f_val = p.get("fecha")
            if s_name and f_val:
                semana_fechas.setdefault(s_name, []).append(f_val)

        def_idx = 0
        encontrado = False

        # 1. Búsqueda directa: semana que contenga la fecha de hoy o cuyo rango la englobe
        for idx_s, s in enumerate(semanas_disponibles):
            fechas_sem = semana_fechas.get(s, [])
            if hoy_str in fechas_sem:
                def_idx = idx_s
                encontrado = True
                break
            elif fechas_sem and min(fechas_sem) <= hoy_str <= max(fechas_sem):
                def_idx = idx_s
                encontrado = True
                break

        # 2. Si hoy cae fuera del plan (ej. antes del inicio o tras finalizar), seleccionar la semana más próxima
        if not encontrado and semanas_disponibles:
            distancias = []
            for idx_s, s in enumerate(semanas_disponibles):
                fechas_sem = semana_fechas.get(s, [])
                if fechas_sem:
                    min_d = min(abs((datetime.strptime(f, "%Y-%m-%d").date() - hoy).days) for f in fechas_sem)
                    distancias.append((min_d, idx_s))
            if distancias:
                distancias.sort()
                def_idx = distancias[0][1]

        def formatear_semana_label(s: str) -> str:
            limpio = s.replace("\n", " ").strip()
            fechas_sem = semana_fechas.get(s, [])
            if hoy_str in fechas_sem or (fechas_sem and min(fechas_sem) <= hoy_str <= max(fechas_sem)):
                return f"{limpio} (Semana actual)"
            return limpio

        semana_sel = st.selectbox(
            "🔽 Seleccionar semana del plan:",
            semanas_disponibles,
            index=def_idx,
            format_func=formatear_semana_label
        )

        dias_semana_sel = [
            item for item in comparativa 
            if any(p["fecha"] == item["fecha"] and p["semana"] == semana_sel for p in plan_dias)
        ]

        for item in dias_semana_sel:
            with st.container():
                c_dia, c_plan, c_garmin, c_estado = st.columns([1.5, 3.5, 3, 1.5])
                with c_dia:
                    es_hoy = (item['fecha'] == hoy_str)
                    if es_hoy:
                        st.markdown(f"**{item['dia_semana']}** <span style='background: #0078D4; color: white; padding: 2px 7px; border-radius: 6px; font-size: 0.72rem; font-weight: 700;'>HOY</span>", unsafe_allow_html=True)
                    else:
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
    else:
        if not doc_url:
            st.markdown("""
            <div style="background: #F8FAFC; border: 1.5px dashed #CBD5E1; border-radius: 12px; padding: 24px; text-align: center; margin: 15px 0;">
                <div style="font-size: 32px; margin-bottom: 8px;">📋</div>
                <div style="font-size: 16px; font-weight: 800; color: #1E293B; margin-bottom: 6px;">Sin Planificación de Google Docs Asignada</div>
                <div style="font-size: 13px; color: #64748B; max-width: 500px; margin: 0 auto 12px auto;">
                    Tu entrenador personaliza las semanas de entreno en un Google Doc único para ti. Pega tu enlace a continuación para activar el seguimiento automático.
                </div>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.info("No se han encontrado sesiones en el documento o no tiene el formato esperado. Revisa que el enlace sea accesible y público para lectura.")

    # Configuración de URL del documento
    with st.expander("⚙️ Configuración del enlace de Google Docs de este atleta", expanded=(not doc_url)):
        nueva_url = st.text_input("URL del Google Doc de entrenamientos:", value=doc_url or "", key="input_doc_url_tab_plan")
        if st.button("💾 Guardar enlace del plan", key="btn_save_plan_tab_plan"):
            n_clean = nueva_url.strip() if nueva_url and nueva_url.strip() else None
            database.ejecutar_consulta_sql(
                "UPDATE usuarios SET doc_plan_url = ? WHERE id = ?",
                (n_clean, usuario_id)
            )
            cargar_plan_y_comparativa.clear()
            database.persistir_base_datos(f"Actualizado Google Doc de atleta id {usuario_id} [skip ci]")
            st.success("¡Enlace actualizado correctamente para este atleta!")
            st.rerun()

# ==================== COMPONENTE: RÉCORDS PERSONALES (PB) ====================
def render_records_personales():
    st.subheader("🏆 Mejores Marcas Personales (Personal Bests)")
    st.caption("Detección automática de tus récords absolutos registrados en tu reloj Garmin.")

    records = database.obtener_records_personales(usuario_id=usuario_id)
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
    vol_semanal = database.obtener_volumen_semanal(usuario_id=usuario_id)
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
                "🔽 Filtrar período o mes:",
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
    vol_anual = database.obtener_volumen_anual(usuario_id=usuario_id)
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

database.calcular_splits_km = calcular_splits_km
if not hasattr(database, "obtener_splits_km"):
    database.obtener_splits_km = lambda *args, **kwargs: []
if not hasattr(database, "guardar_splits_km"):
    database.guardar_splits_km = lambda *args, **kwargs: None

def render_historial_sesiones():
    st.subheader("📅 Historial de Días y Desglose de Ritmos")
    st.caption("Consulta día a día tus entrenamientos desde hoy hacia atrás. Compara las vueltas manuales del reloj con los parciales kilómetro a kilómetro de Strava.")

    # Si es entrenador, permitir consultar a cualquier atleta; si es atleta, usar el perfil activo
    target_uid = usuario_id
    if es_entrenador:
        lista_atlet = database.obtener_usuarios(filtro_rol="atleta")
        if lista_atlet:
            nom_map = {f"{a['nombre']} ({a['alias']})": a["id"] for a in lista_atlet}
            ids_lista = list(nom_map.values())
            idx_def = ids_lista.index(usuario_id) if usuario_id in ids_lista else 0
            nom_sel = st.selectbox("🔽 Seleccionar atleta para consultar su historial:", list(nom_map.keys()), index=idx_def)
            target_uid = nom_map[nom_sel]

    entrenos_raw = database.ejecutar_consulta_sql("SELECT * FROM entrenamientos WHERE usuario_id = ? ORDER BY fecha DESC", (target_uid,))

    if not entrenos_raw:
        st.info("ℹ️ No hay entrenamientos registrados para este perfil. Sincroniza con Garmin, Coros o Strava para ver tu historial.")
        return

    df_entrenos = pd.DataFrame(entrenos_raw)

    # 1. Histórico de días desde hoy hacia atrás
    st.markdown("#### 📆 Seleccionar Día del Histórico (desde hoy hacia atrás)")

    hoy_date = datetime.now().date()
    dias_semana_es = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]

    def formatear_opcion_dia(r):
        f_str = str(r["fecha"])[:10]
        try:
            f_obj = datetime.strptime(f_str, "%Y-%m-%d").date()
            diff_dias = (hoy_date - f_obj).days
            if diff_dias == 0:
                prefijo = "🟢 Hoy"
            elif diff_dias == 1:
                prefijo = "🟡 Ayer"
            elif diff_dias < 7:
                prefijo = f"📅 {dias_semana_es[f_obj.weekday()]} ({f_obj.strftime('%d/%m')})"
            else:
                prefijo = f"📅 {f_obj.strftime('%d/%m/%Y')} ({dias_semana_es[f_obj.weekday()]})"
        except Exception:
            prefijo = f"📅 {f_str}"

        titulo = r.get("titulo") or "Entrenamiento"
        dist = f"{r.get('distancia_km', 0.0)} km"
        tiempo = r.get("tiempo_formateado", "--:--")
        ritmo = f"{r.get('ritmo_medio_minkm', '--:--')} min/km"
        return f"{r['id']} | {prefijo} · {titulo} — {dist} en {tiempo} ({ritmo})"

    col_filtro1, col_filtro2 = st.columns([1, 2.5])
    with col_filtro1:
        texto_busqueda = st.text_input("🔍 Filtrar sesión (lugar, título o fecha):", "", placeholder="Ej: Alcantarilla, 10k, 2026-11...")

    with col_filtro2:
        opciones_df = df_entrenos
        if texto_busqueda:
            opciones_df = df_entrenos[
                df_entrenos["titulo"].astype(str).str.contains(texto_busqueda, case=False, na=False) |
                df_entrenos["ubicacion"].astype(str).str.contains(texto_busqueda, case=False, na=False) |
                df_entrenos["fecha"].astype(str).str.contains(texto_busqueda, case=False, na=False)
            ]

        lista_opciones = [
            formatear_opcion_dia(r)
            for _, r in opciones_df.iterrows()
        ]

        if lista_opciones:
            seleccion_label = st.selectbox("🔽 Seleccionar día o entrenamiento:", lista_opciones, index=0)
            sel_id = int(seleccion_label.split(" | ")[0])
        else:
            st.warning("No se encontraron entrenamientos que coincidan con la búsqueda.")
            sel_id = None

    if not sel_id:
        return

    # Ficha del entrenamiento seleccionado
    entreno_sel, laps_sel = database.obtener_detalle_entrenamiento(sel_id)
    if not entreno_sel:
        st.warning("No se pudieron cargar los datos de este entrenamiento.")
        return

    st.markdown("---")
    st.markdown(f"### 🎽 **{entreno_sel.get('titulo', 'Entrenamiento')}**")
    st.caption(f"📅 Fecha: **{entreno_sel.get('fecha')}** | 📍 Ubicación: **{entreno_sel.get('ubicacion') or 'No especificada'}**")

    col_m1, col_m2, col_m3, col_m4, col_m5 = st.columns(5)
    col_m1.metric("Distancia", f"{entreno_sel.get('distancia_km')} km")
    col_m2.metric("Tiempo", entreno_sel.get("tiempo_formateado"))
    col_m3.metric("Ritmo medio", f"{entreno_sel.get('ritmo_medio_minkm')} min/km")
    col_m4.metric("FC Media / Máx", f"{entreno_sel.get('fc_media') or '-'} / {entreno_sel.get('fc_max') or '-'} ppm")
    col_m5.metric("Cadencia / Calorías", f"{entreno_sel.get('cadencia_media') or '-'} spm · {entreno_sel.get('calorias') or '-'} kcal")

    # JUSTO ENCIMA DE LA TABLA DE TIEMPO: Las dos opciones de vistas
    st.markdown("#### ⏱️ Desglose de Tiempos")
    col_v_radio, col_v_help = st.columns([1.8, 1.2])
    with col_v_radio:
        vista_seleccionada = st.radio(
            "Seleccionar vista de tiempos:",
            ["⏱️ Manual / Laps (Reloj)", "🏃 Strava / Km a Km"],
            horizontal=True,
            key=f"vista_historial_sel_{sel_id}"
        )
    with col_v_help:
        if vista_seleccionada == "⏱️ Manual / Laps (Reloj)":
            st.caption("⏱️ **Vista Reloj:** Muestra los parciales y pausas que marcaste con el botón del dispositivo.")
        else:
            st.caption("🏃 **Vista Strava:** Muestra los pasos exactos cada 1.000 metros (ideal para ver si mantuviste o mejoraste el ritmo).")

    # CONTENIDO SEGÚN LA VISTA SELECCIONADA
    if vista_seleccionada == "⏱️ Manual / Laps (Reloj)":
        if laps_sel:
            laps_clasificados, resumen_series = database.clasificar_vueltas_sesion(laps_sel)
            df_laps_sel = pd.DataFrame(laps_clasificados)

            if resumen_series["num_series"] > 1:
                st.markdown(f"##### ⚡ Resumen de Series: **{resumen_series['num_series']} Series de ~{resumen_series['distancia_aprox']}m**")
                c_sub1, c_sub2, c_sub3 = st.columns(3)
                c_sub1.success(f"🎯 **Series activas:** {resumen_series['num_series']} repeticiones")
                c_sub2.info(f"⏱️ **Recuperaciones:** {resumen_series['num_recuperaciones']} pausas de descanso")
                c_sub3.caption(f"🏃 **Calentamiento:** {resumen_series['calentamiento_km']} km | **Enfriamiento:** {resumen_series['enfriamiento_km']} km")

            # TABLA DE TIEMPO MANUAL / LAPS
            columnas_laps = ["lap_numero", "tipo_clasificado", "distancia_m", "tiempo_formateado", "ritmo_minkm", "fc_media", "fc_max"]
            columnas_presentes = [c for c in columnas_laps if c in df_laps_sel.columns]
            st.dataframe(
                df_laps_sel[columnas_presentes].rename(columns={
                    "lap_numero": "Vuelta #",
                    "tipo_clasificado": "Tipo de Tramo",
                    "distancia_m": "Metros",
                    "tiempo_formateado": "Tiempo",
                    "ritmo_minkm": "Ritmo (min/km)",
                    "fc_media": "FC Media",
                    "fc_max": "FC Máx"
                }),
                use_container_width=True,
                hide_index=True
            )

            # Gráficas estilo Power BI
            col_g1, col_g2 = st.columns([1, 1])
            with col_g1:
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
                df_solo_series = df_laps_sel[df_laps_sel["tipo_clasificado"].str.startswith("Serie")]
                df_plot_s = df_solo_series if not df_solo_series.empty else df_laps_sel
                fig_laps_s = px.bar(
                    df_plot_s,
                    x="tipo_clasificado" if not df_solo_series.empty else "lap_numero",
                    y="tiempo_s",
                    color="fc_media" if "fc_media" in df_plot_s.columns and df_plot_s["fc_media"].notna().any() else None,
                    color_continuous_scale=[[0.0, "#0078D4"], [0.5, "#00B4D8"], [1.0, "#FF5A5F"]] if "fc_media" in df_plot_s.columns and df_plot_s["fc_media"].notna().any() else None,
                    text="tiempo_formateado"
                )
                fig_laps_s.update_traces(
                    textposition='outside',
                    textfont=dict(color="#000000", size=11, family="Segoe UI"),
                    marker=dict(line=dict(width=0))
                )
                aplicar_estilo_powerbi(
                    fig_laps_s,
                    titulo="Tiempos de Repeticiones Activas",
                    subtitulo="Duración exacta por vuelta (segundos)",
                    x_title="Serie / Vuelta",
                    y_title="Segundos"
                )
                st.plotly_chart(fig_laps_s, use_container_width=True, theme=None)
        else:
            st.info("ℹ️ Esta sesión no tiene laps o vueltas manuales registradas en el reloj. Puedes cambiar arriba a '🏃 Strava / Km a Km' para ver el desglose kilómetro a kilómetro.")

    else:
        # VISTA STRAVA / KM A KM
        # 1. Recuperar parciales métricos reales guardados en base de datos
        splits_km = []
        try:
            if hasattr(database, "obtener_splits_km"):
                splits_km = database.obtener_splits_km(sel_id)
        except Exception:
            splits_km = []

        # 2. Si no están en DB y es actividad Garmin, calcular al vuelo con la traza continua
        if not splits_km and entreno_sel.get("fit_hash", "").startswith("garmin_"):
            try:
                base_act_id = entreno_sel.get("fit_hash").split("_")[-1]
                from garmin_sync import conectar_garmin, calcular_splits_desde_detalles_garmin
                tok_file = os.path.join(os.path.dirname(__file__), ".garmin_tokens", "garmin_tokens.json")
                client_g, _ = conectar_garmin("", "", tok_file)
                if client_g:
                    splits_km = calcular_splits_desde_detalles_garmin(
                        client_g, base_act_id,
                        duracion_total_s=entreno_sel.get("tiempo_total_s", 0),
                        distancia_total_km=entreno_sel.get("distancia_km", 0.0)
                    )
                    if splits_km and hasattr(database, "guardar_splits_km"):
                        database.guardar_splits_km(sel_id, splits_km)
            except Exception:
                pass

        # 3. Fallback algorítmico si no hay splits reales disponibles
        if not splits_km:
            splits_km = calcular_splits_km(
                entreno_sel.get("distancia_km", 0.0),
                entreno_sel.get("tiempo_total_s", 0.0),
                laps_sel
            )

        if splits_km:
            df_splits = pd.DataFrame(splits_km)

            # Tarjetas de análisis táctico de ritmo
            splits_1k = [s for s in splits_km if s.get("distancia_m", 0) >= 800]
            if splits_1k:
                mejor_km = min(splits_1k, key=lambda s: s.get("tiempo_s", 999999))
                peor_km = max(splits_1k, key=lambda s: s.get("tiempo_s", 0))

                # Análisis de split de carrera (1ª mitad vs 2ª mitad)
                mitad = len(splits_1k) // 2
                if mitad >= 2:
                    t_mitad1 = sum(s["tiempo_s"] for s in splits_1k[:mitad]) / mitad
                    t_mitad2 = sum(s["tiempo_s"] for s in splits_1k[mitad:mitad * 2]) / mitad
                    diff_mitad = t_mitad2 - t_mitad1
                    if diff_mitad <= -2.0:
                        estrategia_texto = f"🟢 **Split Negativo (De menos a más):** 2ª mitad {abs(diff_mitad):.0f}s/km más rápida. ¡Gran gestión!"
                    elif abs(diff_mitad) < 2.0:
                        estrategia_texto = "🔵 **Ritmo Homogéneo:** Paso regular y uniforme en toda la sesión."
                    else:
                        estrategia_texto = f"🟠 **Split Positivo (De más a menos):** 2ª mitad +{diff_mitad:.0f}s/km más lenta."
                else:
                    estrategia_texto = "📊 Ritmo continuo por kilómetro."

                c_k1, c_k2, c_k3 = st.columns(3)
                c_k1.success(f"⚡ **Km más rápido:** {mejor_km['etiqueta']} a **{mejor_km['ritmo_minkm']}** min/km")
                c_k2.info(f"🐢 **Km más lento:** {peor_km['etiqueta']} a **{peor_km['ritmo_minkm']}** min/km")
                c_k3.caption(estrategia_texto)

            # Ritmo medio general para desviaciones
            ritmo_medio_seg = (entreno_sel.get("tiempo_total_s", 0) / (entreno_sel.get("distancia_km", 1) or 1)) if entreno_sel.get("distancia_km", 0) > 0 else 0

            # Asegurar columna desviacion_ritmo_s
            if "desviacion_ritmo_s" not in df_splits.columns or df_splits["desviacion_ritmo_s"].isna().all():
                df_splits["desviacion_ritmo_s"] = df_splits.apply(
                    lambda r: (r["tiempo_s"] / (r["distancia_m"] / 1000.0)) - ritmo_medio_seg if r.get("distancia_m", 0) > 0 and ritmo_medio_seg > 0 else 0.0,
                    axis=1
                )

            # Formatear la diferencia con el ritmo medio
            def fmt_desv(d_seg):
                if pd.isna(d_seg) or abs(d_seg) < 1.0:
                    return "🎯 En ritmo medio"
                elif d_seg < 0:
                    return f"🚀 {abs(d_seg):.0f}s más rápido"
                else:
                    return f"🐢 +{d_seg:.0f}s más lento"

            df_splits["vs_media"] = df_splits["desviacion_ritmo_s"].apply(fmt_desv)

            # Formatear Desnivel (+/- m, como en Strava)
            if "desnivel_m" in df_splits.columns and df_splits["desnivel_m"].notna().any():
                df_splits["desnivel_str"] = df_splits["desnivel_m"].apply(
                    lambda d: f"{d:+.0f} m" if pd.notna(d) and abs(d) >= 0.5 else ("0 m" if pd.notna(d) else "-")
                )
            else:
                df_splits["desnivel_str"] = "-"

            # TABLA DE TIEMPO STRAVA / KM A KM
            cols_splits = ["etiqueta", "distancia_m", "tiempo_formateado", "ritmo_minkm", "vs_media", "desnivel_str", "fc_media", "fc_max", "cadencia"]
            cols_existentes = [c for c in cols_splits if c in df_splits.columns]
            st.dataframe(
                df_splits[cols_existentes].rename(columns={
                    "etiqueta": "Kilómetro",
                    "distancia_m": "Metros",
                    "tiempo_formateado": "Tiempo",
                    "ritmo_minkm": "Ritmo (min/km)",
                    "vs_media": "vs. Ritmo Medio",
                    "desnivel_str": "Desnivel",
                    "fc_media": "FC Media (ppm)",
                    "fc_max": "FC Máx (ppm)",
                    "cadencia": "Cadencia (spm)"
                }),
                use_container_width=True,
                hide_index=True
            )

            # Gráfica de Ritmo Km a Km estilo Strava
            df_splits["color_barra"] = df_splits["desviacion_ritmo_s"].apply(
                lambda x: "#2EC4B6" if x <= 0 else "#FF5A5F"
            )

            fig_strava = px.bar(
                df_splits,
                x="etiqueta",
                y="tiempo_s",
                text="ritmo_minkm",
                color="color_barra",
                color_discrete_map="identity"
            )
            fig_strava.update_traces(
                textposition='outside',
                textfont=dict(color="#000000", size=11, family="Segoe UI"),
                marker=dict(line=dict(width=0))
            )

            # Añadir línea de ritmo medio
            ritmo_medio_seg = (entreno_sel.get("tiempo_total_s", 0) / (entreno_sel.get("distancia_km", 1) or 1)) if entreno_sel.get("distancia_km", 0) > 0 else 0
            if ritmo_medio_seg > 0:
                fig_strava.add_hline(
                    y=ritmo_medio_seg,
                    line_dash="dash",
                    line_color="#0078D4",
                    annotation_text=f"Ritmo medio: {entreno_sel.get('ritmo_medio_minkm', '')} min/km",
                    annotation_position="top right",
                    annotation_font=dict(color="#0078D4", size=11)
                )

            aplicar_estilo_powerbi(
                fig_strava,
                titulo="Evolución de Ritmo Kilómetro a Kilómetro (Estilo Strava)",
                subtitulo="Verde: más rápido que la media | Coral: más lento que la media",
                x_title="Kilómetro",
                y_title="Segundos por Km",
                altura=360
            )
            st.plotly_chart(fig_strava, use_container_width=True, theme=None)
        else:
            st.info("ℹ️ No hay suficientes datos para generar el desglose por kilómetro.")

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

# ==================== PESTAÑA: HISTORIAL ====================
with tab_historial:
    render_historial_sesiones()

# ==================== PESTAÑA 5: ANÁLISIS DE SERIES ====================
with tab_series:
    st.subheader("⚡ Detalle y Análisis de Series")
    st.caption("Compara los tiempos de cada repetición de forma limpia, separando las recuperaciones.")

    col_s1, col_s2 = st.columns([1, 2])
    with col_s1:
        distancia_opciones = {
            "4000 mtrs": (3800, 4200),
            "3000 mtrs": (2800, 3200),
            "2000 mtrs": (1850, 2150),
            "1000 mtrs": (900, 1100),
            "800 mtrs": (750, 850),
            "500 mtrs": (470, 530),
            "400 mtrs": (370, 430),
            "300 mtrs": (270, 330),
            "200 mtrs": (170, 230),
        }
        dist_keys = list(distancia_opciones.keys())

        # Contar sesiones reales por distancia en una sola consulta rápida
        q_dist_counts = """
        SELECT 
            CASE 
                WHEN s.distancia_m BETWEEN 3800 AND 4200 THEN '4000 mtrs'
                WHEN s.distancia_m BETWEEN 2800 AND 3200 THEN '3000 mtrs'
                WHEN s.distancia_m BETWEEN 1850 AND 2150 THEN '2000 mtrs'
                WHEN s.distancia_m BETWEEN 900 AND 1100 THEN '1000 mtrs'
                WHEN s.distancia_m BETWEEN 750 AND 850 THEN '800 mtrs'
                WHEN s.distancia_m BETWEEN 470 AND 530 THEN '500 mtrs'
                WHEN s.distancia_m BETWEEN 370 AND 430 THEN '400 mtrs'
                WHEN s.distancia_m BETWEEN 270 AND 330 AND (s.tiempo_s / (s.distancia_m / 1000.0)) <= 280 THEN '300 mtrs'
                WHEN s.distancia_m BETWEEN 170 AND 230 AND (s.tiempo_s / (s.distancia_m / 1000.0)) <= 280 THEN '200 mtrs'
                ELSE NULL
            END as dk,
            e.id
        FROM entrenamientos e
        JOIN series_laps s ON s.entrenamiento_id = e.id
        WHERE e.usuario_id = ?
        GROUP BY dk, e.id
        HAVING dk IS NOT NULL AND COUNT(s.id) >= 2
        """
        rows_counts = database.ejecutar_consulta_sql(q_dist_counts, (usuario_id,))
        dist_counts = {}
        for r in rows_counts:
            dist_counts[r["dk"]] = dist_counts.get(r["dk"], 0) + 1

        # Selección inteligente:
        # 1. Si hoy había series prescritas en el plan del atleta y hay datos, preseleccionar esa distancia
        idx_def = None
        hoy_str = datetime.now().strftime("%Y-%m-%d")
        for p in (comparativa_plan or []):
            if p.get("fecha") == hoy_str:
                tit_desc = f"{p.get('titulo_sugerido', '')} {p.get('plan_descripcion', '')}".lower()
                for d_cand in ["4000", "3000", "2000", "1000", "800", "500", "400", "300", "200"]:
                    if re.search(rf'\b{d_cand}\b', tit_desc) or f"x{d_cand}" in tit_desc or f"x {d_cand}" in tit_desc or f"{d_cand}m" in tit_desc:
                        cand_key = f"{d_cand} mtrs"
                        if cand_key in dist_keys:
                            idx_def = dist_keys.index(cand_key)
                            break
                break

        # 2. Si no hay series hoy, preseleccionar la distancia de su serie más reciente
        if idx_def is None:
            ult_serie_raw = database.ejecutar_consulta_sql("""
                SELECT s.distancia_m
                FROM series_laps s
                JOIN entrenamientos e ON s.entrenamiento_id = e.id
                WHERE e.usuario_id = ? AND s.distancia_m BETWEEN 150 AND 4500
                GROUP BY e.id, s.distancia_m
                HAVING COUNT(s.id) >= 2
                ORDER BY e.fecha DESC
                LIMIT 1
            """, (usuario_id,))
            if ult_serie_raw:
                d_ult_m = ult_serie_raw[0]["distancia_m"]
                for dk, (dmin, dmax) in distancia_opciones.items():
                    if dmin <= d_ult_m <= dmax:
                        idx_def = dist_keys.index(dk)
                        break

        # 3. Si aún no está definida, elegir la distancia con más sesiones del atleta
        if idx_def is None:
            mejores = [k for k, v in dist_counts.items() if v > 0]
            if mejores:
                cand_max = max(mejores, key=lambda k: dist_counts[k])
                idx_def = dist_keys.index(cand_max)
            else:
                idx_def = 3 # 1000 mtrs por defecto

        def formato_opcion_dist(dk):
            n = dist_counts.get(dk, 0)
            if n > 0:
                return f"{dk} ({n} {'sesión' if n == 1 else 'sesiones'})"
            return f"{dk} (sin sesiones)"

        dist_sel = st.selectbox(
            "🔽 Seleccionar distancia de serie:",
            dist_keys,
            index=idx_def,
            format_func=formato_opcion_dist,
            key=f"series_dist_sel_{usuario_id}"
        )
        d_min, d_max = distancia_opciones[dist_sel]

    # Buscar sesiones que tengan vueltas de esa distancia
    pace_filter = "AND (s.tiempo_s / (s.distancia_m / 1000.0)) <= 280" if d_max <= 350 else ""
    query_sesiones = f"""
    SELECT e.id, e.fecha, e.titulo, e.ubicacion, e.notas_entrenador,
           COUNT(s.id) as num_series,
           ROUND(AVG(s.tiempo_s), 1) as media_seg,
           MIN(s.tiempo_s) as min_seg
    FROM entrenamientos e
    JOIN series_laps s ON s.entrenamiento_id = e.id
    WHERE s.distancia_m BETWEEN {d_min} AND {d_max} {pace_filter} AND e.usuario_id = ?
    GROUP BY e.id
    HAVING COUNT(s.id) >= 2
    ORDER BY e.fecha DESC
    """
    sesiones_series_raw = database.ejecutar_consulta_sql(query_sesiones, (usuario_id,))
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
                "🔽 Seleccionar sesión concreta de series:",
                opciones_sesion,
                index=0
            )
            sesion_id = int(sel_sesion_str.split(" | ")[0])

        # Cargar los laps exactos de esa sesión
        pace_filter_laps = "AND (tiempo_s / (distancia_m / 1000.0)) <= 280" if d_max <= 350 else ""
        query_laps = f"""
        SELECT lap_numero, distancia_m, tiempo_s, tiempo_formateado, ritmo_minkm, fc_media, fc_max
        FROM series_laps
        WHERE entrenamiento_id = {sesion_id} AND distancia_m BETWEEN {d_min} AND {d_max} {pace_filter_laps}
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
        st.info(f"ℹ️ No se han encontrado sesiones con series de {dist_sel} para {usuario_activo['nombre']}.")
        dists_con_datos = [f"**{k}** ({v} {'sesión' if v == 1 else 'sesiones'})" for k, v in dist_counts.items() if v > 0]
        if dists_con_datos:
            st.markdown(f"💡 *Distancias con series disponibles para {usuario_activo['nombre']}:* " + " · ".join(dists_con_datos) + ". Selecciona una en el desplegable superior.")

        # Si el usuario tiene cuenta de COROS conectada, ofrecer el botón de desglosar laps
        if coros_sync.obtener_tokens_guardados(usuario_id=usuario_id) is not None:
            st.markdown("""
                <div style="background: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 8px; padding: 12px; margin-top: 10px; margin-bottom: 12px;">
                    <div style="font-weight: 700; color: #1E293B; margin-bottom: 4px;">💡 ¿Tienes series de esta distancia en tu reloj COROS?</div>
                    <div style="font-size: 13px; color: #64748B;">Al sincronizar por primera vez, se importa el resumen general. Pulsa el botón inferior para que el sistema consulte a COROS el desglose detallado de laps y repeticiones de tus sesiones recientes.</div>
                </div>
            """, unsafe_allow_html=True)
            if st.button("🔄 Extraer y Desglosar Laps de COROS", key=f"btn_reprocesar_coros_{dist_sel}", type="primary"):
                with st.spinner("Consultando vueltas y series en COROS..."):
                    res_rep = coros_sync.reprocesar_laps_actividades_existentes(usuario_id=usuario_id, limite=30)
                if res_rep.get("actualizados", 0) > 0:
                    st.success(f"🎉 ¡Desglosadas {res_rep['actualizados']} sesiones con series de COROS!")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.info(res_rep.get("mensaje") or "No se encontraron series adicionales pendientes de desglosar.")

        # Si la distancia seleccionada es 1000 mtrs y no hay series de pista, ofrecer la vista de parciales km a km
        if dist_sel == "1000 mtrs":
            query_splits_disp = """
                SELECT DISTINCT e.id, e.fecha, e.titulo, e.distancia_km
                FROM entrenamientos e
                JOIN entrenamientos_splits_km esk ON esk.entrenamiento_id = e.id
                WHERE e.usuario_id = ? AND (e.deporte IN ('running', 'track_running', 'trail_running') OR e.deporte IS NULL)
                ORDER BY e.fecha DESC
                LIMIT 20
            """
            ses_splits = database.ejecutar_consulta_sql(query_splits_disp, (usuario_id,))
            if ses_splits:
                st.markdown("---")
                st.markdown("#### 🏃 O bien, consulta el parcial de 1.000m (Km a Km) de tus carreras:")
                opc_splits = [f"{s['id']} | {s['fecha'][:10]} · {s['titulo']} ({s['distancia_km']} km)" for s in ses_splits]
                sel_split_ses = st.selectbox("🔽 Seleccionar sesión para ver parciales de 1.000m:", opc_splits, key="sel_split_1k")
                if sel_split_ses:
                    s_id = int(sel_split_ses.split(" | ")[0])
                    splits_raw = database.ejecutar_consulta_sql(
                        "SELECT km_numero, distancia_m, tiempo_formateado, ritmo_minkm, fc_media, fc_max FROM entrenamientos_splits_km WHERE entrenamiento_id = ? ORDER BY km_numero ASC",
                        (s_id,)
                    )
                    if splits_raw:
                        df_sp = pd.DataFrame(splits_raw)
                        st.dataframe(df_sp.rename(columns={
                            "km_numero": "Km #",
                            "distancia_m": "Metros",
                            "tiempo_formateado": "Tiempo",
                            "ritmo_minkm": "Ritmo",
                            "fc_media": "FC Media",
                            "fc_max": "FC Máx"
                        }), use_container_width=True, hide_index=True)

# ==================== COMPONENTE: SINCRONIZAR GARMIN ====================
def render_sincronizar_garmin():
    st.subheader("📥 Sincronización y Carga de Entrenamientos")

    # Detección de sesión guardada aislada estrictamente por atleta
    token_dir_root = os.path.join(os.path.dirname(__file__), ".garmin_tokens")
    token_dir_user = garmin_sync.obtener_directorio_tokens(usuario_id=usuario_id)
    if usuario_id == 1:
        tiene_sesion = os.path.isfile(os.path.join(token_dir_root, "garmin_tokens.json")) or os.path.isfile(os.path.join(token_dir_user, "garmin_tokens.json"))
        target_tokenstore = token_dir_user if os.path.isfile(os.path.join(token_dir_user, "garmin_tokens.json")) else token_dir_root
    else:
        tiene_sesion = os.path.isfile(os.path.join(token_dir_user, "garmin_tokens.json"))
        target_tokenstore = token_dir_user

    if tiene_sesion:
        st.success(f"✅ **Sesión de Garmin Connect guardada activamente para {usuario_activo.get('nombre')}.**")
        if st.button("🔄 Sincronizar", type="primary", key="btn_sync_garmin_panel"):
            progress_bar = st.progress(0)
            status_text = st.empty()

            def actualizar_progreso(actual, total, detalle):
                porcentaje = min(1.0, actual / max(1, total))
                progress_bar.progress(porcentaje)
                status_text.text(f"Comprobando {actual}: {detalle}")

            try:
                with st.spinner("Conectando con sesión guardada..."):
                    cliente, msg = garmin_sync.conectar_garmin("", tokenstore_dir=target_tokenstore, usuario_id=usuario_id)

                nuevas, omitidas = garmin_sync.descargar_historial_garmin(
                    cliente,
                    max_actividades=50,
                    callback_progreso=actualizar_progreso,
                    usuario_id=usuario_id
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
                        target_dir = garmin_sync.obtener_directorio_tokens(garmin_user, usuario_id=usuario_id)
                        cliente, msg = garmin_sync.conectar_garmin(garmin_user, garmin_pass, tokenstore_dir=target_dir, usuario_id=usuario_id)

                    max_acts = limite_map.get(opcion_limite, 50)
                    nuevas, omitidas = garmin_sync.descargar_historial_garmin(cliente, max_actividades=max_acts, usuario_id=usuario_id)
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
                id_guardado = database.guardar_entrenamiento(datos_entreno, laps, usuario_id=usuario_id)
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

    sesion_coros = coros_sync.obtener_tokens_guardados(usuario_id=usuario_id)
    if sesion_coros:
        st.success(f"✅ **Sesión de COROS activa:** `{sesion_coros.get('account')}` (Región: {sesion_coros.get('region', 'eu').upper()})")
        if sesion_coros.get("last_sync"):
            st.caption(f"🕒 Última sincronización: {sesion_coros.get('last_sync')}")

        col_sync1, col_sync2, col_logout = st.columns([2.5, 2.5, 1.2])
        with col_sync1:
            if st.button("🔄 Sincronizar Nuevos (Rápido)", type="primary", key="btn_sync_coros_inc", use_container_width=True):
                st_text = st.empty()

                def update_coros_p(act, tot, name):
                    st_text.text(f"Comprobando entreno {act}: {name}")

                with st.spinner("Buscando entrenamientos nuevos en COROS..."):
                    res = coros_sync.sincronizar_actividades_coros(
                        progreso_callback=update_coros_p,
                        usuario_id=usuario_id,
                        historial_completo=False
                    )
                if res["status"] == "ok":
                    st.success(f"🎉 {res['mensaje']}")
                    st.rerun()
                else:
                    st.error(res["mensaje"])

        with col_sync2:
            if st.button("📥 Descargar Historial Completo", key="btn_sync_coros_full", use_container_width=True,
                         help="Descarga todas las actividades históricas desde el inicio de tu cuenta de COROS."):
                st_text = st.empty()

                def update_coros_p(act, tot, name):
                    st_text.text(f"Descargando histórico ({act} analizadas): {name}")

                with st.spinner("Descargando todo el historial de COROS hacia atrás..."):
                    res = coros_sync.sincronizar_actividades_coros(
                        progreso_callback=update_coros_p,
                        usuario_id=usuario_id,
                        historial_completo=True
                    )
                if res["status"] == "ok":
                    st.success(f"🎉 {res['mensaje']}")
                    st.rerun()
                else:
                    st.error(res["mensaje"])

        with col_logout:
            if st.button("🚪 Cerrar sesión", use_container_width=True):
                coros_sync.cerrar_sesion_coros(usuario_id=usuario_id)
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
                        ok, msg, _ = coros_sync.iniciar_sesion_coros(c_email, c_pass, region_key=c_reg, usuario_id=usuario_id)
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
                    nid = database.guardar_entrenamiento(datos_e, laps_e, usuario_id=usuario_id)
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

    sesion_strava = strava_sync.obtener_tokens_strava(usuario_id=usuario_id)
    if sesion_strava:
        st.success(f"✅ **Conectado a Strava ({usuario_activo.get('nombre')}):** `{sesion_strava.get('athlete_name', 'Atleta Conectado')}`")
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

                res = strava_sync.sincronizar_actividades_strava(progreso_callback=update_strava_p, usuario_id=usuario_id)
                if res["status"] == "ok":
                    st.success(f"🎉 {res['mensaje']}")
                    st.rerun()
                else:
                    st.error(res["mensaje"])

        with col_logout:
            if st.button("🚪 Desconectar Strava", use_container_width=True):
                strava_sync.cerrar_sesion_strava(usuario_id=usuario_id)
                st.success("Conexión con Strava eliminada.")
                st.rerun()
    else:
        st.markdown(f"#### 🔑 Conectar cuenta de Strava para {usuario_activo.get('nombre')}")
        st.caption("Introduce tu **Access Token de Strava** (obtenido en Strava Developer Settings) o credenciales de aplicación.")

        tab_tok, tab_oauth = st.tabs(["Token Directo (Recomendado)", "OAuth Completo (Client ID / Secret)"])
        with tab_tok:
            with st.form("form_strava_token"):
                st_tok = st.text_input("Access Token de Strava:", type="password", placeholder="pe. 8a3f890c2e...")
                st_name = st.text_input("Nombre de atleta / referencia:", value=usuario_activo.get("nombre", "Atleta"))
                submit_tok = st.form_submit_button("Conectar Token", type="primary")

                if submit_tok:
                    if not st_tok:
                        st.error("Debes introducir un Access Token.")
                    else:
                        with st.spinner("Comprobando token con la API de Strava..."):
                            ok, msg, _ = strava_sync.conectar_strava_token_directo(st_tok, st_name, usuario_id=usuario_id)
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
                            ok, msg, _ = strava_sync.refrescar_token_strava(cid, csec, rtok, usuario_id=usuario_id)
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
                    nid = database.guardar_entrenamiento(datos_e, laps_e, usuario_id=usuario_id)
                    if nid:
                        guardados += 1
                except Exception:
                    pass
                finally:
                    if os.path.exists(tmp_p):
                        os.remove(tmp_p)
            st.success(f"🎉 Se han importado {guardados} sesiones de Strava con éxito.")
            st.rerun()

# ==================== COMPONENTE: GESTIÓN DE ATLETAS (MÍSTER) ====================
def render_gestion_atletas():
    st.subheader("👥 Gestión de Atletas del Team Ardil")
    st.caption("Administra la plantilla, asigna documentos de Google Docs con la planificación y supervisa altas.")

    atletas = database.obtener_usuarios(filtro_rol="atleta")
    if atletas:
        for at in atletas:
            with st.expander(f"🏃 {at['nombre']} (@{at['alias']})", expanded=False):
                col_u1, col_u2 = st.columns([2, 1])
                with col_u1:
                    nuevo_doc = st.text_input(
                        f"URL Plan Google Doc de {at['nombre']}:",
                        value=at.get("doc_plan_url") or "",
                        key=f"doc_url_atleta_{at['id']}"
                    )
                    plat_actual = (at.get("plataforma_principal") or ("coros" if "jose" in at["alias"].lower() else "garmin")).lower()
                    opciones_plat = ["coros", "garmin", "strava"]
                    idx_plat = opciones_plat.index(plat_actual) if plat_actual in opciones_plat else 0
                    nueva_plat = st.selectbox(
                        f"Dispositivo / Reloj principal de {at['nombre']}:",
                        options=opciones_plat,
                        index=idx_plat,
                        format_func=lambda x: "⌚ COROS (Training Hub)" if x == "coros" else ("⌚ Garmin (Connect)" if x == "garmin" else "🚴 Strava"),
                        key=f"plat_atleta_{at['id']}"
                    )
                with col_u2:
                    st.write("")
                    st.write("")
                    if st.button("💾 Guardar Cambios", key=f"btn_save_doc_{at['id']}"):
                        database.crear_o_actualizar_usuario(
                            nombre=at["nombre"],
                            alias=at["alias"],
                            rol="atleta",
                            entrenador_id=at.get("entrenador_id", 2),
                            email=at.get("email"),
                            avatar=at.get("avatar"),
                            doc_plan_url=nuevo_doc.strip() if nuevo_doc else None,
                            plataforma_principal=nueva_plat,
                            usuario_id=at["id"]
                        )
                        st.success(f"Datos de {at['nombre']} actualizados.")
                        st.rerun()

                if es_salva and at["id"] not in (1, 2):
                    st.write("")
                    col_del1, col_del2 = st.columns([3, 1])
                    with col_del2:
                        if st.button(f"🗑️ Dar de baja", key=f"btn_del_atleta_{at['id']}", help=f"Eliminar a {at['nombre']} del club"):
                            database.eliminar_usuario(at["id"])
                            st.warning(f"Atleta '{at['nombre']}' eliminado del equipo.")
                            st.rerun()

    if es_salva:
        st.markdown("#### ➕ Registrar Nuevo Atleta en el Club")
        with st.form("form_nuevo_atleta_gest"):
            c1, c2, c3 = st.columns(3)
            with c1:
                n_nom = st.text_input("Nombre y Apellidos:")
            with c2:
                n_ali = st.text_input("Alias único:")
            with c3:
                n_ava = st.text_input("Iniciales Avatar (2 letras):", max_chars=3)
            col_f_plat, col_f_doc = st.columns([1, 2])
            with col_f_plat:
                n_plat = st.selectbox(
                    "Reloj / Dispositivo principal:",
                    options=["coros", "garmin", "strava"],
                    index=0,
                    format_func=lambda x: "⌚ COROS" if x == "coros" else ("⌚ Garmin" if x == "garmin" else "🚴 Strava")
                )
            with col_f_doc:
                n_url = st.text_input("URL Google Doc de su plan (opcional):")
            submit_atleta = st.form_submit_button("Dar de Alta Atleta", type="primary")
            if submit_atleta:
                if n_nom and n_ali:
                    clean_ali = n_ali.lower().strip()
                    if clean_ali == "salva":
                        st.error("El alias 'salva' está reservado para tu perfil principal.")
                    else:
                        nuevo_id = database.crear_o_actualizar_usuario(
                            nombre=n_nom.strip(),
                            alias=clean_ali,
                            rol="atleta",
                            entrenador_id=2,
                            avatar=n_ava.upper().strip() if n_ava else "🏃",
                            doc_plan_url=n_url.strip() if n_url else None,
                            plataforma_principal=n_plat
                        )
                        st.session_state["usuario_id_activo"] = nuevo_id
                        st.success(f"Atleta '{n_nom}' añadido con éxito al equipo ({n_plat.upper()}).")
                        st.rerun()
                else:
                    st.warning("Introduce nombre y alias.")
    else:
        st.caption("🔒 El registro de nuevos atletas está reservado exclusivamente para la cuenta de Salva.")

# ==================== PESTAÑA 6: PERSONAL (DESPLEGABLE) ====================
with tab_personal:
    col_p_sel, _ = st.columns([1.5, 2.5])
    with col_p_sel:
        plat_pref = (usuario_activo.get("plataforma_principal") or ("coros" if "jose" in usuario_activo.get("alias", "") else "garmin")).lower()
        if (es_entrenador or es_salva):
            opciones_disp = [
                "👥 Gestión de Atletas y Planes",
                "🏆 Récords Personales (PB)",
                "📥 Sincronizar Garmin",
                "📥 Sincronizar Coros",
                "📥 Sincronizar Strava"
            ]
            idx_p = 0
        else:
            if plat_pref == "coros":
                opciones_disp = [
                    "📥 Sincronizar Coros",
                    "🏆 Récords Personales (PB)",
                    "📥 Sincronizar Strava",
                    "📥 Sincronizar Garmin"
                ]
            else:
                opciones_disp = [
                    "🏆 Récords Personales (PB)",
                    "📥 Sincronizar Garmin",
                    "📥 Sincronizar Coros",
                    "📥 Sincronizar Strava"
                ]
            idx_p = 0
        opcion_personal = st.selectbox(
            "🔽 Seleccionar sección:",
            opciones_disp,
            index=idx_p
        )

    st.divider()

    if opcion_personal == "👥 Gestión de Atletas y Planes":
        render_gestion_atletas()
    elif opcion_personal == "🏆 Récords Personales (PB)":
        render_records_personales()
    elif opcion_personal == "📥 Sincronizar Garmin":
        render_sincronizar_garmin()
    elif opcion_personal == "📥 Sincronizar Coros":
        render_sincronizar_coros()
    elif opcion_personal == "📥 Sincronizar Strava":
        render_sincronizar_strava()
