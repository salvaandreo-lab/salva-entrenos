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

def pull_file(file_name, branch="main"):
    """Descarga la versión más reciente de un archivo desde GitHub sin caché CDN (vía Git Trees + Blobs API)."""
    clean_path = file_name.replace("\\", "/")
    tree_url = f"https://api.github.com/repos/{REPO}/git/trees/{urllib.parse.quote(branch)}"
    try:
        req_tree = urllib.request.Request(tree_url, headers=headers, method="GET")
        with urllib.request.urlopen(req_tree, timeout=15) as resp:
            tree_data = json.loads(resp.read().decode("utf-8"))
        blob_sha = None
        for item in tree_data.get("tree", []):
            if item.get("path") == clean_path:
                blob_sha = item.get("sha")
                break
        if not blob_sha:
            print(f"Aviso pull_file: {clean_path} no encontrado en el árbol remoto.")
            return False

        blob_url = f"https://api.github.com/repos/{REPO}/git/blobs/{blob_sha}"
        req_blob = urllib.request.Request(blob_url, headers=headers, method="GET")
        with urllib.request.urlopen(req_blob, timeout=30) as resp:
            blob_data = json.loads(resp.read().decode("utf-8"))

        raw_bytes = base64.b64decode(blob_data["content"])
        local_path = os.path.join(BASE_DIR, file_name)
        tmp_path = local_path + ".tmp"
        with open(tmp_path, "wb") as f:
            f.write(raw_bytes)
        os.replace(tmp_path, local_path)
        print(f"📥 Descargada última versión remota de {clean_path} (blob: {blob_sha[:7]})")
        return True
    except Exception as e:
        print(f"⚠️ No se pudo descargar {clean_path} de GitHub: {e}")
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
        "team_ardil_intro.mp4",
        "team_ardil_intro_v2.mp4",
        "team_ardil_intro_v3.mp4",
        "team_ardil_intro_v4.mp4",
        "AGENTS.md",
        "GEMINI.md",
        ".streamlit/config.toml",
        "auto_sync_runner.py",
        "tests_sporttracks.py"
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
