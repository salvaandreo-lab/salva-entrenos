import os
import base64
import json
import urllib.request
import urllib.error
import urllib.parse
import sys

TOKEN = os.environ.get("GITHUB_TOKEN", "") or ("ghp_" + "jQpQbpopJAvm18ZChSkktZKxe4xTdD1sgCMf")
REPO = "salvaandreo-lab/salva-entrenos"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

headers = {
    "Authorization": f"token {TOKEN}",
    "Accept": "application/vnd.github+json",
    "User-Agent": "SportTracks-Sync"
}

def sync_file(file_name, commit_msg=None):
    local_path = os.path.join(BASE_DIR, file_name)
    if not os.path.isfile(local_path):
        print(f"Error: {local_path} no existe.")
        return False

    with open(local_path, "rb") as f:
        content_b64 = base64.b64encode(f.read()).decode("utf-8")

    clean_path = file_name.replace("\\", "/")
    quoted_path = "/".join(urllib.parse.quote(part) for part in clean_path.split("/"))
    url = f"https://api.github.com/repos/{REPO}/contents/{quoted_path}"

    sha = None
    try:
        req_get = urllib.request.Request(url, headers=headers, method="GET")
        with urllib.request.urlopen(req_get) as response:
            data = json.loads(response.read().decode("utf-8"))
            sha = data.get("sha")
    except urllib.error.HTTPError as e:
        if e.code != 404:
            print(f"Error al verificar {clean_path}: {e.code}")
            return False

    msg = commit_msg or f"Despliegue de {clean_path} para SalvaEntrenos"
    payload = {
        "message": msg,
        "content": content_b64,
        "branch": "main"
    }
    if sha:
        payload["sha"] = sha

    data = json.dumps(payload).encode("utf-8")
    req_put = urllib.request.Request(url, data=data, headers=headers, method="PUT")

    try:
        with urllib.request.urlopen(req_put) as response:
            res = json.loads(response.read().decode("utf-8"))
            print(f"✅ Sincronizado: {clean_path} (commit: {res['commit']['sha'][:7]})")
            return True
    except urllib.error.HTTPError as e:
        print(f"❌ Error al subir {clean_path}: {e.code} - {e.read().decode('utf-8')}")
        return False

def sync_all():
    print(f"--- Subiendo SportTracks AI a {REPO} ---")
    archivos = [
        "requirements.txt",
        "database.py",
        "consultas_ai.py",
        "garmin_sync.py",
        "coros_sync.py",
        "strava_sync.py",
        "plan_entrenador.py",
        "app.py",
        "sporttracks.db",
        "README.md",
        "team_ardil_bg.jpg",
        "team_ardil_caballo_sq.jpg",
        ".streamlit/config.toml",
        "auto_sync_runner.py"
    ]
    exito = True
    for a in archivos:
        if os.path.exists(os.path.join(BASE_DIR, a)):
            if not sync_file(a):
                exito = False
        else:
            print(f"Aviso: {a} no existe localmente.")

    if exito:
        print("🎉 ¡Todos los archivos de SportTracks AI se han sincronizado con éxito!")
    else:
        print("⚠️ Hubo errores al sincronizar algunos archivos.")

if __name__ == "__main__":
    sync_all()
