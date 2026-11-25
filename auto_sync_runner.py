import os
import sys
import json
import re
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)
os.chdir(BASE_DIR)

import database
import garmin_sync
import coros_sync
import strava_sync

def ejecutar_auto_sync():
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Iniciando Auto-Sync Multi-Atleta de Entrenamientos...")
    nuevos_totales = 0

    # ==================== 1. GARMIN CONNECT ====================
    # Salva (id 1): tokens desde secreto, base de datos o disco
    tokens_env_g = os.environ.get("GARMIN_TOKENS_JSON")
    token_dir_g = os.path.join(BASE_DIR, ".garmin_tokens")
    token_file_g1 = os.path.join(token_dir_g, "garmin_tokens.json")

    if tokens_env_g:
        os.makedirs(token_dir_g, exist_ok=True)
        with open(token_file_g1, "w", encoding="utf-8") as f:
            f.write(tokens_env_g)
        print("✅ Tokens de Garmin para Salva (id 1) cargados desde GitHub Secrets.")
    elif not os.path.isfile(token_file_g1):
        db_tok = database.obtener_sesion_plataforma(1, "garmin")
        if db_tok:
            os.makedirs(token_dir_g, exist_ok=True)
            with open(token_file_g1, "w", encoding="utf-8") as f:
                json.dump(db_tok, f, indent=2)
            print("✅ Tokens de Garmin para Salva (id 1) restaurados desde la base de datos.")

    # Sincronizar Garmin para Salva (u1) si existen tokens
    if os.path.isfile(token_file_g1):
        try:
            print("Sincronizando Garmin para Salva (u1)...")
            cliente, msg = garmin_sync.conectar_garmin("", tokenstore_dir=token_dir_g, usuario_id=1)
            nuevas_g, omit_g = garmin_sync.descargar_historial_garmin(cliente, max_actividades=25, usuario_id=1)
            print(f"Resultado Garmin (Salva u1): {nuevas_g} nuevas, {omit_g} ya existían.")
            nuevos_totales += nuevas_g
        except Exception as e:
            print(f"❌ Error en Garmin (Salva u1): {e}")

    # Restaurar tokens de Garmin para otros atletas si existen en DB
    try:
        usuarios = database.obtener_usuarios()
        for u in usuarios:
            uid = u["id"]
            if uid != 1:
                db_tok_g = database.obtener_sesion_plataforma(uid, "garmin")
                if db_tok_g:
                    u_g_dir = os.path.join(token_dir_g, f"u{uid}")
                    os.makedirs(u_g_dir, exist_ok=True)
                    with open(os.path.join(u_g_dir, "garmin_tokens.json"), "w", encoding="utf-8") as f:
                        json.dump(db_tok_g, f, indent=2)
    except Exception as e_tg:
        print(f"Aviso restaurando sesiones Garmin desde DB: {e_tg}")

    # Sincronizar Garmin para otros atletas si tienen subdirectorio u{id}
    if os.path.isdir(token_dir_g):
        for entry in os.listdir(token_dir_g):
            m_u = re.match(r"^u(\d+)$", entry)
            if m_u:
                uid = int(m_u.group(1))
                if uid != 1:
                    u_dir = os.path.join(token_dir_g, entry)
                    try:
                        print(f"Sincronizando Garmin para atleta {uid}...")
                        cliente, msg = garmin_sync.conectar_garmin("", tokenstore_dir=u_dir, usuario_id=uid)
                        ng, og = garmin_sync.descargar_historial_garmin(cliente, max_actividades=25, usuario_id=uid)
                        print(f"Resultado Garmin (atleta {uid}): {ng} nuevas, {og} ya existían.")
                        nuevos_totales += ng
                    except Exception as e:
                        print(f"❌ Error en Garmin (atleta {uid}): {e}")

    # ==================== 2. COROS TRAINING HUB ====================
    tok_dir_c = os.path.join(BASE_DIR, ".coros_tokens")
    os.makedirs(tok_dir_c, exist_ok=True)
    coros_env = os.environ.get("COROS_TOKENS_JSON")

    if coros_env:
        # Los tokens de COROS de Jose Ángel se guardan estrictamente bajo coros_tokens_u8.json
        with open(os.path.join(tok_dir_c, "coros_tokens_u8.json"), "w", encoding="utf-8") as f:
            f.write(coros_env)
        print("✅ Tokens de COROS para Jose Ángel (id 8) cargados desde GitHub Secrets.")

    # Restaurar sesiones COROS desde SQLite para todos los atletas registrados
    try:
        usuarios = database.obtener_usuarios()
        for u in usuarios:
            uid = u["id"]
            db_tok_c = database.obtener_sesion_plataforma(uid, "coros")
            if db_tok_c and db_tok_c.get("accessToken"):
                f_u_coros = os.path.join(tok_dir_c, f"coros_tokens_u{uid}.json")
                with open(f_u_coros, "w", encoding="utf-8") as f:
                    json.dump(db_tok_c, f, indent=2)
                print(f"✅ Tokens de COROS para {u.get('nombre', f'atleta {uid}')} restaurados desde DB.")
    except Exception as e_tok_c:
        print(f"Aviso restaurando sesiones COROS desde DB: {e_tok_c}")

    if os.path.isdir(tok_dir_c):
        for f in os.listdir(tok_dir_c):
            m_coros = re.match(r"^coros_tokens_u(\d+)\.json$", f)
            if m_coros:
                uid = int(m_coros.group(1))
                try:
                    res_c = coros_sync.sincronizar_actividades_coros(usuario_id=uid, historial_completo=False)
                    print(f"Resultado COROS (atleta {uid}): {res_c.get('mensaje')}")
                    nuevos_totales += res_c.get("nuevos", 0)
                except Exception as e_c:
                    print(f"❌ Error en COROS (atleta {uid}): {e_c}")

    # ==================== 3. STRAVA ====================
    tok_dir_s = os.path.join(BASE_DIR, ".strava_tokens")
    os.makedirs(tok_dir_s, exist_ok=True)
    # Restaurar sesiones Strava desde SQLite
    try:
        usuarios = database.obtener_usuarios()
        for u in usuarios:
            uid = u["id"]
            db_tok_s = database.obtener_sesion_plataforma(uid, "strava")
            if db_tok_s and db_tok_s.get("access_token"):
                f_u_strava = os.path.join(tok_dir_s, f"strava_tokens_u{uid}.json")
                with open(f_u_strava, "w", encoding="utf-8") as f:
                    json.dump(db_tok_s, f, indent=2)
    except Exception as e_tok_s:
        print(f"Aviso restaurando sesiones Strava desde DB: {e_tok_s}")
    if os.path.isdir(tok_dir_s):
        for f in os.listdir(tok_dir_s):
            m_strava = re.match(r"^strava_tokens_u(\d+)\.json$", f)
            if m_strava:
                uid = int(m_strava.group(1))
                try:
                    res_s = strava_sync.sincronizar_actividades_strava(max_actividades=25, usuario_id=uid)
                    print(f"Resultado Strava (atleta {uid}): {res_s.get('mensaje')}")
                    nuevos_totales += res_s.get("nuevos", 0)
                except Exception as e_s:
                    print(f"❌ Error en Strava (atleta {uid}): {e_s}")

    # ==================== 4. RECONCILIACIÓN CON EL PLAN DEL MÍSTER ====================
    try:
        import plan_entrenador
        usuarios = database.obtener_usuarios()
        for u in usuarios:
            u_id = u["id"]
            doc_url = plan_entrenador.obtener_doc_url(u_id)
            if doc_url:
                dias = plan_entrenador.descargar_plan_entrenador(doc_url)
                if dias:
                    res_plan = plan_entrenador.conciliar_plan_con_garmin(dias, usuario_id=u_id)
                    actualizados = plan_entrenador.aplicar_etiquetas_entrenador(res_plan.get("comparativa", []))
                    if actualizados > 0:
                        print(f"✅ Plan del míster aplicado para {u.get('nombre', f'atleta {u_id}')}: {actualizados} entrenos etiquetados.")
    except Exception as e_p:
        print(f"Aviso al conciliar plan del míster en auto-sync: {e_p}")

    return nuevos_totales

if __name__ == "__main__":
    nuevos = ejecutar_auto_sync()
    with open(os.path.join(BASE_DIR, "sync_status.txt"), "w", encoding="utf-8") as f:
        f.write(f"NUEVOS={nuevos}\n")
    print(f"Auto-Sync Multi-Atleta finalizado. Nuevos entrenos: {nuevos}")
