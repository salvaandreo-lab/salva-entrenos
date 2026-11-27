import os
import sys
import json
import re
import hashlib
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)
os.chdir(BASE_DIR)

# Evitar subidas intermedias por cada token/entreno; se sincroniza una sola vez al final
os.environ["AUTO_SYNC_BATCH"] = "1"

import database
import garmin_sync
import coros_sync
import strava_sync
import sync_sporttracks


def _hash_archivo(path: str) -> str:
    if not os.path.isfile(path):
        return ""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _sincronizar_garmin_atleta(uid: int, nombre: str) -> int:
    """Sincroniza Garmin Connect para un atleta si posee tokens en DB, disco o secreto."""
    u_g_dir = garmin_sync.obtener_directorio_tokens(usuario_id=uid)
    token_file = os.path.join(u_g_dir, "garmin_tokens.json")

    # 1. Priorizar token guardado en SQLite (siempre contiene el refresh más reciente)
    db_tok = database.obtener_sesion_plataforma(uid, "garmin")
    if db_tok:
        os.makedirs(u_g_dir, exist_ok=True)
        with open(token_file, "w", encoding="utf-8") as f:
            json.dump(db_tok, f, indent=2)
    elif uid == 1 and not os.path.isfile(token_file):
        tokens_env = os.environ.get("GARMIN_TOKENS_JSON")
        if tokens_env:
            os.makedirs(u_g_dir, exist_ok=True)
            with open(token_file, "w", encoding="utf-8") as f:
                f.write(tokens_env)

    # Si tampoco hay archivo local tras revisar DB/env, el atleta no usa Garmin
    if not os.path.isfile(token_file):
        return 0

    try:
        print(f"⌚ Sincronizando Garmin para {nombre} (u{uid})...")
        cliente, _ = garmin_sync.conectar_garmin("", tokenstore_dir=u_g_dir, usuario_id=uid)
        nuevas_g, omit_g = garmin_sync.descargar_historial_garmin(cliente, max_actividades=25, usuario_id=uid)
        print(f"   Resultado Garmin ({nombre}): {nuevas_g} nuevas, {omit_g} ya existían.")
        return nuevas_g
    except Exception as e:
        print(f"❌ Error en Garmin ({nombre} u{uid}): {e}")
        return 0


def _sincronizar_coros_atleta(uid: int, nombre: str) -> int:
    """Sincroniza COROS Training Hub para un atleta si posee tokens en DB, disco o secreto."""
    tok_dir_c = os.path.join(BASE_DIR, ".coros_tokens")
    f_user = os.path.join(tok_dir_c, f"coros_tokens_u{uid}.json")

    if uid == 8 and not database.obtener_sesion_plataforma(uid, "coros") and not os.path.isfile(f_user):
        coros_env = os.environ.get("COROS_TOKENS_JSON")
        if coros_env:
            os.makedirs(tok_dir_c, exist_ok=True)
            with open(f_user, "w", encoding="utf-8") as f:
                f.write(coros_env)

    toks = coros_sync.obtener_tokens_guardados(usuario_id=uid)
    if not toks or not toks.get("accessToken"):
        return 0

    try:
        print(f"⌚ Sincronizando COROS para {nombre} (u{uid})...")
        res_c = coros_sync.sincronizar_actividades_coros(usuario_id=uid, historial_completo=False)
        print(f"   Resultado COROS ({nombre}): {res_c.get('mensaje')}")
        return res_c.get("nuevos", 0)
    except Exception as e_c:
        print(f"❌ Error en COROS ({nombre} u{uid}): {e_c}")
        return 0


def _sincronizar_strava_atleta(uid: int, nombre: str) -> int:
    """Sincroniza Strava para un atleta si posee tokens en DB o disco."""
    toks = strava_sync.obtener_tokens_strava(usuario_id=uid)
    if not toks or not (toks.get("access_token") or toks.get("accessToken")):
        return 0

    try:
        print(f"🚴 Sincronizando Strava para {nombre} (u{uid})...")
        res_s = strava_sync.sincronizar_actividades_strava(max_actividades=25, usuario_id=uid)
        print(f"   Resultado Strava ({nombre}): {res_s.get('mensaje')}")
        return res_s.get("nuevos", 0)
    except Exception as e_s:
        print(f"❌ Error en Strava ({nombre} u{uid}): {e_s}")
        return 0


def ejecutar_auto_sync():
    en_github_actions = os.environ.get("GITHUB_ACTIONS") == "true"
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Iniciando Auto-Sync Multi-Atleta de Entrenamientos...")

    db_path = database.DB_PATH

    # 1. En ejecución local (Windows 21:05), descargar primero la última DB de GitHub
    #    para incorporar nuevos atletas, tokens o ediciones hechas desde la web durante el día.
    if not en_github_actions:
        sync_sporttracks.pull_file("sporttracks.db")

    hash_inicial = _hash_archivo(db_path)
    nuevos_totales = 0
    etiquetados_totales = 0

    # 2. Recorrer dinámicamente TODOS los atletas activos registrados en la base de datos
    usuarios = database.obtener_usuarios()
    ids_procesados = set()

    for u in usuarios:
        uid = u["id"]
        rol = (u.get("rol") or "").lower()
        if rol == "entrenador":
            continue
        ids_procesados.add(uid)
        nombre = u.get("nombre") or f"Atleta {uid}"

        # Sincronizar cada plataforma que tenga sesión activa para este atleta (Garmin, COROS y/o Strava)
        nuevos_totales += _sincronizar_garmin_atleta(uid, nombre)
        nuevos_totales += _sincronizar_coros_atleta(uid, nombre)
        nuevos_totales += _sincronizar_strava_atleta(uid, nombre)

    # 3. Reconciliar con el plan de Google Docs de cada atleta que tenga URL configurada
    try:
        import plan_entrenador
        for u in usuarios:
            u_id = u["id"]
            if (u.get("rol") or "").lower() == "entrenador":
                continue
            doc_url = plan_entrenador.obtener_doc_url(u_id)
            if doc_url:
                dias = plan_entrenador.descargar_plan_entrenador(doc_url)
                if dias:
                    res_plan = plan_entrenador.conciliar_plan_con_garmin(dias, usuario_id=u_id)
                    actualizados = plan_entrenador.aplicar_etiquetas_entrenador(res_plan.get("comparativa", []))
                    if actualizados > 0:
                        etiquetados_totales += actualizados
                        print(f"✅ Plan del míster aplicado para {u.get('nombre', f'atleta {u_id}')}: {actualizados} entreno(s).")
    except Exception as e_p:
        print(f"Aviso al conciliar plan del míster en auto-sync: {e_p}")

    # 4. Persistencia única atómica en GitHub si hubo cualquier cambio en sporttracks.db
    os.environ.pop("AUTO_SYNC_BATCH", None)
    hash_final = _hash_archivo(db_path)
    if not en_github_actions and hash_final != hash_inicial:
        sync_sporttracks.sync_file(
            "sporttracks.db",
            commit_msg=f"🔄 Auto-sync multi-atleta ({nuevos_totales} nuevos, {etiquetados_totales} etiquetados) [skip ci]"
        )

    return nuevos_totales


if __name__ == "__main__":
    log_path = os.path.join(BASE_DIR, "auto_sync.log")
    # Duplicar salida a consola y a auto_sync.log para trazabilidad en Windows Task Scheduler
    class _Tee:
        def __init__(self, *streams):
            self.streams = streams
        def write(self, data):
            for s in self.streams:
                try:
                    s.write(data)
                    s.flush()
                except Exception:
                    pass
        def flush(self):
            for s in self.streams:
                try:
                    s.flush()
                except Exception:
                    pass

    with open(log_path, "a", encoding="utf-8", buffering=1) as log_f:
        orig_out, orig_err = sys.stdout, sys.stderr
        sys.stdout = _Tee(orig_out, log_f)
        sys.stderr = _Tee(orig_err, log_f)
        try:
            nuevos = ejecutar_auto_sync()
            with open(os.path.join(BASE_DIR, "sync_status.txt"), "w", encoding="utf-8") as f:
                f.write(f"NUEVOS={nuevos}\n")
            print(f"Auto-Sync Multi-Atleta finalizado. Nuevos entrenos: {nuevos}\n")
        finally:
            sys.stdout = orig_out
            sys.stderr = orig_err
