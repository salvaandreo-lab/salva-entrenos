import os
import sys
import json
import sqlite3
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)
os.chdir(BASE_DIR)

import database
import garmin_sync
import coros_sync

def ejecutar_auto_sync():
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Iniciando Auto-Sync de Entrenamientos...")
    nuevos_totales = 0

    # 1. Configurar tokens de Garmin desde variable de entorno o disco local
    tokens_env = os.environ.get("GARMIN_TOKENS_JSON")
    token_dir = os.path.join(BASE_DIR, ".garmin_tokens")
    token_file = os.path.join(token_dir, "garmin_tokens.json")

    if tokens_env:
        os.makedirs(token_dir, exist_ok=True)
        with open(token_file, "w", encoding="utf-8") as f:
            f.write(tokens_env)
        print("✅ Tokens de Garmin cargados desde GitHub Secrets.")

    if os.path.isfile(token_file):
        try:
            print("Conectando con Garmin Connect...")
            cliente, msg = garmin_sync.conectar_garmin("", tokenstore_dir=token_dir)
            print("Estado Garmin:", msg)

            def cb(actual, total, detalle):
                print(f"  [{actual}/{total}] {detalle}")

            nuevas_g, omitidas_g = garmin_sync.descargar_historial_garmin(
                cliente,
                max_actividades=25,
                callback_progreso=cb
            )
            print(f"Resultado Garmin: {nuevas_g} nuevas guardadas, {omitidas_g} ya existían.")
            nuevos_totales += nuevas_g
        except Exception as e:
            print(f"❌ Error durante la descarga de Garmin: {e}")
    else:
        print("⚠️ No se encontraron tokens de sesión de Garmin.")

    # 2. Configurar y sincronizar COROS
    tok_dir_c = os.path.join(BASE_DIR, ".coros_tokens")
    coros_env = os.environ.get("COROS_TOKENS_JSON")
    if coros_env:
        os.makedirs(tok_dir_c, exist_ok=True)
        with open(os.path.join(tok_dir_c, "coros_tokens.json"), "w", encoding="utf-8") as f:
            f.write(coros_env)
        with open(os.path.join(tok_dir_c, "coros_tokens_u8.json"), "w", encoding="utf-8") as f:
            f.write(coros_env)
        print("✅ Tokens de COROS cargados desde GitHub Secrets.")

    if os.path.exists(tok_dir_c):
        for f in os.listdir(tok_dir_c):
            if f.endswith(".json"):
                uid = 8 if "u8" in f else 1
                try:
                    res_c = coros_sync.sincronizar_actividades_coros(usuario_id=uid, historial_completo=False)
                    print(f"Resultado COROS (atleta {uid}): {res_c.get('mensaje')}")
                    nuevos_totales += res_c.get("nuevos", 0)
                except Exception as e_c:
                    print(f"❌ Error en auto-sync COROS (atleta {uid}): {e_c}")

    return nuevos_totales

if __name__ == "__main__":
    nuevos = ejecutar_auto_sync()
    # Escribir código de salida para que GitHub Actions sepa si hubo cambios
    with open(os.path.join(BASE_DIR, "sync_status.txt"), "w", encoding="utf-8") as f:
        f.write(f"NUEVOS={nuevos}\n")
    print(f"Auto-Sync finalizado. Nuevos entrenos: {nuevos}")
