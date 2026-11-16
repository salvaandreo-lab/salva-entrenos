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

def ejecutar_auto_sync():
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Iniciando Auto-Sync de Entrenamientos...")

    # 1. Configurar tokens de Garmin desde variable de entorno o disco local
    tokens_env = os.environ.get("GARMIN_TOKENS_JSON")
    token_dir = os.path.join(BASE_DIR, ".garmin_tokens")
    token_file = os.path.join(token_dir, "garmin_tokens.json")

    if tokens_env:
        os.makedirs(token_dir, exist_ok=True)
        with open(token_file, "w", encoding="utf-8") as f:
            f.write(tokens_env)
        print("✅ Tokens de Garmin cargados desde GitHub Secrets.")

    if not os.path.isfile(token_file):
        print("⚠️ No se encontraron tokens de sesión de Garmin. Omitiendo sincronización.")
        return 0

    # 2. Conectar y descargar
    try:
        print("Conectando con Garmin Connect...")
        cliente, msg = garmin_sync.conectar_garmin("", tokenstore_dir=token_dir)
        print("Estado:", msg)

        def cb(actual, total, detalle):
            print(f"  [{actual}/{total}] {detalle}")

        nuevas, omitidas = garmin_sync.descargar_historial_garmin(
            cliente,
            max_actividades=25,
            callback_progreso=cb
        )
        print(f"Resultado Garmin: {nuevas} nuevas guardadas, {omitidas} ya existían.")
        return nuevas
    except Exception as e:
        print(f"❌ Error durante la descarga de Garmin: {e}")
        return 0

if __name__ == "__main__":
    nuevos = ejecutar_auto_sync()
    # Escribir código de salida para que GitHub Actions sepa si hubo cambios
    with open(os.path.join(BASE_DIR, "sync_status.txt"), "w", encoding="utf-8") as f:
        f.write(f"NUEVOS={nuevos}\n")
    print(f"Auto-Sync finalizado. Nuevos entrenos: {nuevos}")
