"""
Batería de pruebas anti-regresiones en modo SOLO LECTURA para SportTracks AI (Team Ardil).
Verifica que ningún error ya solucionado vuelva a producirse, sin modificar sporttracks.db,
sin realizar peticiones de red a Garmin/COROS/Strava y sin ejecutar la interfaz de Streamlit.
"""
import ast
import os
import py_compile
import re
import sqlite3
import tempfile
from datetime import datetime, timedelta

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
APP_PATH = os.path.join(BASE_DIR, "app.py")


def _leer_archivo(nombre: str) -> str:
    ruta = os.path.join(BASE_DIR, nombre)
    with open(ruta, "r", encoding="utf-8") as f:
        return f.read()


def _extraer_funcion_app(nombre_func: str, extras_ns: dict = None):
    """Extrae una función pura de app.py via AST sin ejecutar Streamlit."""
    src = _leer_archivo("app.py")
    tree = ast.parse(src, filename=APP_PATH)
    nodos = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == nombre_func]
    assert len(nodos) == 1, f"No se encontró la función '{nombre_func}' en app.py"
    ns = {"re": re, "os": os, "datetime": datetime, "timedelta": timedelta}
    if extras_ns:
        ns.update(extras_ns)
    mod = ast.Module(body=nodos, type_ignores=[])
    ast.fix_missing_locations(mod)
    exec(compile(mod, APP_PATH, "exec"), ns)
    return ns[nombre_func], src, tree


def test_01_sintaxis_modulos():
    criticos = [
        "app.py",
        "database.py",
        "garmin_sync.py",
        "coros_sync.py",
        "strava_sync.py",
        "plan_entrenador.py",
        "auto_sync_runner.py",
        "consultas_ai.py",
        "sync_sporttracks.py",
    ]
    for nombre in criticos:
        ruta = os.path.join(BASE_DIR, nombre)
        assert os.path.isfile(ruta), f"Falta archivo crítico: {nombre}"
        py_compile.compile(ruta, doraise=True)


def test_02_aislamiento_atletas_y_alcance_usuario_activo():
    import database
    import plan_entrenador

    # 1. Nunca devolver el plan de otro atleta para un usuario inexistente/sin plan
    assert plan_entrenador.obtener_doc_url(usuario_id=999999) is None, (
        "REGRESIÓN: obtener_doc_url(999999) devolvió un plan ajeno."
    )

    # 2. Verificar que en BD Salva (1) y Jose Ángel (8) mantienen plataformas y planes aislados
    u1 = database.obtener_usuario_por_id(1)
    u8 = database.obtener_usuario_por_id(8)
    assert u1 and u8, "Faltan usuarios principales (1 y 8) en sporttracks.db"
    assert u1.get("doc_plan_url") != u8.get("doc_plan_url"), (
        "REGRESIÓN: Salva y Jose Ángel comparten la misma URL de planning."
    )
    assert (u1.get("plataforma_principal") or "").lower() == "garmin"
    assert (u8.get("plataforma_principal") or "").lower() == "coros"

    # 3. En app.py, comprobar_estado_sync no debe comprobar el garmin_tokens.json de Salva para otros uids
    src_app = _leer_archivo("app.py")
    tree_app = ast.parse(src_app, filename=APP_PATH)
    fn_sync = [n for n in tree_app.body if isinstance(n, ast.FunctionDef) and n.name == "comprobar_estado_sync"]
    assert fn_sync, "Falta comprobar_estado_sync en app.py"
    src_fn = ast.get_source_segment(src_app, fn_sync[0]) or ""
    assert 'os.path.join(tok_g, "garmin_tokens.json")' not in src_fn, (
        "REGRESIÓN: comprobar_estado_sync() consulta garmin_tokens.json raíz (de Salva) para otros atletas."
    )
    assert 'f"u{uid}", "garmin_tokens.json"' in src_fn
    assert "obtener_sesion_plataforma" in src_fn, (
        "REGRESIÓN: comprobar_estado_sync() no consulta sesiones_plataformas en SQLite."
    )

    # 4. Prohibido acceder a usuario_activo antes de su definición en app.py
    lineas = src_app.splitlines()
    linea_def = next((i for i, l in enumerate(lineas) if l.startswith("usuario_activo =")), None)
    assert linea_def is not None, "No se encontró definición global de usuario_activo"
    # En la cabecera (de línea 1 a linea_def), fuera de funciones que se llamen después, no usar usuario_activo
    for idx in range(linea_def):
        l = lineas[idx]
        if l.startswith(" ") or l.strip().startswith("#"):
            continue
        assert not re.search(r'\busuario_activo\b', l), (
            f"REGRESIÓN NameError en app.py:{idx+1}: uso de usuario_activo antes de definirse."
        )

    # 5. Splits km a km al vuelo en app.py deben aislar tokens Garmin por atleta (y pasar directorio, no .json)
    assert 'conectar_garmin("", "", tok_file)' not in src_app, (
        "REGRESIÓN: splits km a km pasan un archivo .json y la sesión raíz de Salva a conectar_garmin()."
    )
    assert "obtener_directorio_tokens(usuario_id=uid_split)" in src_app
    assert "tokenstore_dir=tok_dir, usuario_id=uid_split" in src_app

    # 6. Detección de Garmin conectado no debe dar falsos positivos por directorios u{uid} vacíos
    src_db = _leer_archivo("database.py")
    assert 'os.path.isdir(os.path.join(token_dir_garmin, f"u{curr_uid_chk}"))' not in src_app, (
        "REGRESIÓN: app.py detecta Garmin por carpeta vacía u{uid} sin comprobar garmin_tokens.json."
    )
    assert 'os.path.isdir(os.path.join(token_dir_g, f"u{uid}"))' not in src_db, (
        "REGRESIÓN: database.py detecta Garmin por carpeta vacía u{uid} sin comprobar garmin_tokens.json."
    )


def test_03_widgets_streamlit_y_html_seguro():
    src_app = _leer_archivo("app.py")
    lineas = src_app.splitlines()
    linea_inst = next((i for i, l in enumerate(lineas) if 'key="selector_perfil_sidebar"' in l), None)
    assert linea_inst is not None, "Falta widget selector_perfil_sidebar"
    for idx in range(linea_inst + 1, len(lineas)):
        l = lineas[idx]
        if l.strip().startswith("#"):
            continue
        assert 'st.session_state["selector_perfil_sidebar"] =' not in l, (
            f"REGRESIÓN StreamlitWidgetAlreadyInstantiatedError en app.py:{idx+1}."
        )


def test_04_conciliacion_dos_pasadas_y_no_descanso():
    import database
    import plan_entrenador

    # Crear BD temporal aislada para probar sin tocar sporttracks.db real
    fd, tmp_db = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    orig_get_conn = database.get_connection

    try:
        conn = sqlite3.connect(tmp_db)
        conn.row_factory = sqlite3.Row
        conn.execute("""
            CREATE TABLE entrenamientos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                usuario_id INTEGER,
                fecha TEXT,
                titulo TEXT,
                distancia_km REAL,
                tiempo_formateado TEXT,
                ritmo_medio_minkm TEXT,
                notas_entrenador TEXT
            )
        """)
        # Simular escenario real del 21-23 nov: entreno el lunes 23, descanso sin entreno el sábado 21,
        # más un entreno el viernes 20 que era día de Descanso.
        conn.execute(
            "INSERT INTO entrenamientos (id, usuario_id, fecha, titulo, distancia_km, tiempo_formateado, ritmo_medio_minkm, notas_entrenador) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (101, 1, "2026-11-20 11:55:08", "Murcia Carrera", 12.0, "58:56", "4:54", ""),
        )
        conn.execute(
            "INSERT INTO entrenamientos (id, usuario_id, fecha, titulo, distancia_km, tiempo_formateado, ritmo_medio_minkm, notas_entrenador) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (102, 1, "2026-11-23 18:54:48", "Murcia Carrera", 10.21, "50:47", "4:58", ""),
        )
        conn.commit()
        conn.close()

        def _fake_conn():
            c = sqlite3.connect(tmp_db)
            c.row_factory = sqlite3.Row
            return c

        database.get_connection = _fake_conn

        plan_dias = [
            {"fecha": "2026-11-20", "dia_semana": "Viernes", "descripcion": "Descanso", "titulo_sugerido": "Descanso", "es_series": False, "es_descanso": True},
            {"fecha": "2026-11-21", "dia_semana": "Sábado", "descripcion": "6 kms @z0\nProgresivos\n4x100m", "titulo_sugerido": "Series 4x100m", "es_series": True, "es_descanso": False},
            {"fecha": "2026-11-23", "dia_semana": "Lunes", "descripcion": "10kms\n@z1\nTabla de Fuerza", "titulo_sugerido": "Rodaje 10k + Fuerza", "es_series": False, "es_descanso": False},
        ]

        res = plan_entrenador.conciliar_plan_con_garmin(plan_dias, usuario_id=1)
        mapa_comp = {c["fecha"]: c for c in res["comparativa"]}

        # El sábado 21 NO debe robar el entreno del lunes 23
        assert mapa_comp["2026-11-21"]["garmin_entreno"] is None, (
            "REGRESIÓN: El sábado 21 robó el entrenamiento del lunes 23."
        )
        assert mapa_comp["2026-11-23"]["garmin_entreno"]["id"] == 102
        assert "Mismo día" in mapa_comp["2026-11-23"]["estado"]

        # Aplicar etiquetas en la BD temporal
        plan_entrenador.aplicar_etiquetas_entrenador(res["comparativa"])
        c_chk = _fake_conn()
        tit_20 = c_chk.execute("SELECT titulo FROM entrenamientos WHERE id = 101").fetchone()[0]
        tit_23 = c_chk.execute("SELECT titulo FROM entrenamientos WHERE id = 102").fetchone()[0]
        c_chk.close()

        assert tit_20 == "Murcia Carrera", (
            f"REGRESIÓN: Un entreno hecho en día de descanso se renombró a '{tit_20}'."
        )
        assert tit_23 == "Rodaje 10k + Fuerza", (
            f"REGRESIÓN: El entreno del lunes 23 quedó como '{tit_23}' en vez de 'Rodaje 10k + Fuerza'."
        )
    finally:
        database.get_connection = orig_get_conn
        if os.path.exists(tmp_db):
            os.remove(tmp_db)


def test_05_tests_controles_y_clasificacion_3_vueltas():
    import database
    import plan_entrenador

    # 1. TEST 2 KMS debe titularse Test 2k y marcarse como es_series = True
    assert plan_entrenador.generar_titulo_amigable("TEST 2 KMS") == "Test 2k"
    src_plan = _leer_archivo("plan_entrenador.py")
    assert '"test" in texto_entreno.lower()' in src_plan

    # 2. es_sesion_series_real debe aceptar Test 2k en el plan y rechazar maratones sin series
    import database as db_mod
    es_serie_fn, src_app, _ = _extraer_funcion_app("es_sesion_series_real", {"database": db_mod})
    comp_mock = [
        {"fecha": "2026-11-25", "plan_descripcion": "TEST 2 KMS", "titulo_sugerido": "Test 2k", "es_series": True},
        {"fecha": "2026-11-15", "plan_descripcion": "MEDIA MARATÓN ORIHUELA", "titulo_sugerido": "MEDIA MARATÓN ORIHUELA", "es_series": False},
    ]
    assert es_serie_fn(2397, "2026-11-25 19:01:16", "Test 2k", "TEST 2 KMS", comp_mock) is True, (
        "REGRESIÓN: es_sesion_series_real() oculta el Test 2k."
    )
    assert es_serie_fn(1298, "2026-11-15 10:00:25", "MEDIA MARATÓN ORIHUELA", "", comp_mock) is False

    # 3. Preselección en app.py debe mapear 2k/2 kms -> 2000 mtrs
    assert 'km_aliases' in src_app and '"2000": "2"' in src_app

    # 4. clasificar_vueltas_sesion con 3 tramos: Calentamiento + Test 2k + Enfriamiento
    laps_test = [
        {"lap_numero": 1, "distancia_m": 5042.0, "tiempo_s": 1488.4, "ritmo_minkm": "4:55"},
        {"lap_numero": 2, "distancia_m": 2024.6, "tiempo_s": 426.1, "ritmo_minkm": "3:30"},
        {"lap_numero": 3, "distancia_m": 3129.9, "tiempo_s": 944.2, "ritmo_minkm": "5:01"},
    ]
    clasif, resumen = database.clasificar_vueltas_sesion(laps_test)
    assert clasif[0]["tipo_clasificado"] == "Calentamiento", f"Fallo warmup: {clasif[0]}"
    assert clasif[1]["tipo_clasificado"] == "Serie #1", f"Fallo test rep: {clasif[1]}"
    assert clasif[2]["tipo_clasificado"] == "Enfriamiento", f"Fallo cooldown: {clasif[2]}"
    assert resumen["num_series"] == 1

    # 5. Sesión pura 3x2000m (todas rápidas): ninguna debe degradarse a calentamiento/enfriamiento
    laps_3x2k = [
        {"lap_numero": 1, "distancia_m": 2000.0, "tiempo_s": 440.0, "ritmo_minkm": "3:40"},
        {"lap_numero": 2, "distancia_m": 2000.0, "tiempo_s": 438.0, "ritmo_minkm": "3:39"},
        {"lap_numero": 3, "distancia_m": 2000.0, "tiempo_s": 436.0, "ritmo_minkm": "3:38"},
    ]
    clasif_3, res_3 = database.clasificar_vueltas_sesion(laps_3x2k)
    assert res_3["num_series"] == 3, f"REGRESIÓN en 3x2000m: {res_3}"

    # 6. 5x1600m con calentamiento partido (auto-lap 1km + 3.97km) y recuperaciones de 400m al trote (~5:00/km)
    laps_5x1600 = [
        {"lap_numero": 1, "distancia_m": 1002.4, "tiempo_s": 324.9, "ritmo_minkm": "5:24"},
        {"lap_numero": 2, "distancia_m": 3973.9, "tiempo_s": 1152.8, "ritmo_minkm": "4:50"},
        {"lap_numero": 3, "distancia_m": 1602.8, "tiempo_s": 399.9, "ritmo_minkm": "4:09"},
        {"lap_numero": 4, "distancia_m": 408.6, "tiempo_s": 121.6, "ritmo_minkm": "4:57"},
        {"lap_numero": 5, "distancia_m": 1605.3, "tiempo_s": 401.5, "ritmo_minkm": "4:10"},
        {"lap_numero": 6, "distancia_m": 408.9, "tiempo_s": 141.5, "ritmo_minkm": "5:46"},
        {"lap_numero": 7, "distancia_m": 1621.5, "tiempo_s": 393.2, "ritmo_minkm": "4:02"},
        {"lap_numero": 8, "distancia_m": 2410.8, "tiempo_s": 676.6, "ritmo_minkm": "4:40"},
    ]
    clasif_16, res_16 = database.clasificar_vueltas_sesion(laps_5x1600)
    assert res_16["num_series"] == 3, f"REGRESIÓN 1600m clasificó rec/warmup como serie: {res_16}"
    assert res_16["num_recuperaciones"] == 2
    assert clasif_16[0]["tipo_clasificado"] == "Calentamiento" and clasif_16[1]["tipo_clasificado"] == "Calentamiento"
    assert clasif_16[3]["tipo_clasificado"] == "Recuperación" and clasif_16[5]["tipo_clasificado"] == "Recuperación"


def test_06_persistencia_tokens_y_nube():
    src_g = _leer_archivo("garmin_sync.py")
    # import json debe estar a nivel de módulo, NO dentro de conectar_garmin (causaba UnboundLocalError)
    assert re.search(r'^import json\b', src_g, re.MULTILINE), "Falta 'import json' global en garmin_sync.py"
    assert "import json, database" not in src_g, (
        "REGRESIÓN UnboundLocalError: 'import json' local dentro de conectar_garmin."
    )
    assert "database.guardar_sesion_plataforma" in src_g

    src_c = _leer_archivo("coros_sync.py")
    src_s = _leer_archivo("strava_sync.py")
    assert "database.guardar_sesion_plataforma" in src_c and "obtener_sesion_plataforma" in src_c
    assert "database.guardar_sesion_plataforma" in src_s and "obtener_sesion_plataforma" in src_s

    src_app = _leer_archivo("app.py")
    assert 'mensajes.append(f"Garmin error: {e}")' in src_app, (
        "REGRESIÓN UI: los fallos de Garmin deben etiquetarse con 'error' para no mostrar 'Todo al día'."
    )
    assert 'database.persistir_base_datos(' in src_app


def test_07_auto_sync_multiatleta_y_cron():
    src_auto = _leer_archivo("auto_sync_runner.py")
    for marcador in [
        'AUTO_SYNC_BATCH',
        'sync_sporttracks.pull_file("sporttracks.db")',
        'database.obtener_usuarios()',
        '_sincronizar_garmin_atleta',
        '_sincronizar_coros_atleta',
        '_sincronizar_strava_atleta',
        'plan_entrenador',
    ]:
        assert marcador in src_auto, f"REGRESIÓN en auto_sync_runner.py: falta '{marcador}'"

    src_db = _leer_archivo("database.py")
    assert 'AUTO_SYNC_BATCH' in src_db and 'GITHUB_ACTIONS' in src_db

    yml_path = os.path.join(BASE_DIR, ".github", "workflows", "auto_sync.yml")
    assert os.path.isfile(yml_path), "Falta .github/workflows/auto_sync.yml"
    with open(yml_path, "r", encoding="utf-8") as f:
        yml = f.read()
    assert "5 20 * * *" in yml, "REGRESIÓN: se alteró el cron '5 20 * * *' en auto_sync.yml"


def test_08_coros_gzip_laps_y_series_miles():
    import gzip
    import json
    import coros_sync
    import database
    import plan_entrenador

    # 1. Títulos con separador de miles (5x1.000m) o sufijo k (5x1k) no deben truncarse a 5x1
    assert plan_entrenador.generar_titulo_amigable(
        '2,5 km Z1 + 5x1.000m Pista Rec 90" @3\'48"-3\'52"/km + 1,5 km Z1'
    ) == "Series 5x1000m"
    assert plan_entrenador.generar_titulo_amigable("5x1k Rec 90") == "Series 5x1000m (Rec 90)"

    # 2. _decodificar_respuesta_json debe descomprimir respuestas gzip de COROS
    class _FakeGzipResp:
        headers = {"Content-Encoding": "gzip"}
        def read(self):
            return gzip.compress(json.dumps({"result": "0000", "data": {"ok": True}}).encode("utf-8"))

    assert coros_sync._decodificar_respuesta_json(_FakeGzipResp())["data"]["ok"] is True

    # 3. parsear_actividad_coros debe priorizar type==2 sobre type==-1 y convertir cm/cs a m/s
    act_mock = {"labelId": "999", "distance": 10029.43, "totalTime": 2957, "name": "Carrera", "sportType": 100}
    detail_mock = {
        "lapList": [
            {"type": 10, "lapItemList": [{"lapIndex": 1, "distance": 100000, "time": 32000}]},
            {"type": 2, "lapItemList": [
                {"lapIndex": 1, "distance": 251579, "time": 79465},
                {"lapIndex": 2, "distance": 100374, "time": 22968},
                {"lapIndex": 3, "distance": 12637, "time": 8834},
                {"lapIndex": 4, "distance": 100089, "time": 23037},
                {"lapIndex": 5, "distance": 12271, "time": 8970},
                {"lapIndex": 6, "distance": 100423, "time": 22758},
                {"lapIndex": 7, "distance": 15050, "time": 9084},
                {"lapIndex": 8, "distance": 100651, "time": 22603},
                {"lapIndex": 9, "distance": 12210, "time": 8847},
                {"lapIndex": 10, "distance": 101778, "time": 22219},
                {"lapIndex": 11, "distance": 151895, "time": 44798},
            ]},
            {"type": -1, "lapItemList": [{"lapIndex": 1, "distance": 1002943, "time": 295618}]},
        ]
    }
    _, laps = coros_sync.parsear_actividad_coros(act_mock, detail_mock, usuario_id=8)
    assert len(laps) == 11, f"REGRESIÓN COROS lapList: esperaba 11 laps (type==2), obtuvo {len(laps)}"
    assert 990 <= laps[1]["distancia_m"] <= 1020, f"REGRESIÓN unidades cm->m COROS: {laps[1]}"
    assert 220 <= laps[1]["tiempo_s"] <= 235, f"REGRESIÓN unidades cs->s COROS: {laps[1]}"
    _, res = database.clasificar_vueltas_sesion(laps)
    assert res["num_series"] == 5, f"REGRESIÓN clasificación 5x1000m COROS: {res}"

    # 4. Desplegable de Análisis de Series debe incluir 1600 mtrs y auto-sync en apertura para todos los atletas
    src_app = _leer_archivo("app.py")
    for marcador in ['"1600 mtrs": (1500, 1700)', "BETWEEN 1500 AND 1700 THEN '1600 mtrs'", '"1600"', "_ejecutar_auto_sync_apertura"]:
        assert marcador in src_app, f"Falta '{marcador}' en app.py"
    src_coros = _leer_archivo("coros_sync.py")
    assert "solo_recientes=(not es_modo_historial)" in src_coros


def main():
    tests = [
        ("01. Sintaxis de todos los módulos", test_01_sintaxis_modulos),
        ("02. Aislamiento de atletas, planes y alcance", test_02_aislamiento_atletas_y_alcance_usuario_activo),
        ("03. Widgets de Streamlit y estado", test_03_widgets_streamlit_y_html_seguro),
        ("04. Conciliación en 2 pasadas y días de descanso", test_04_conciliacion_dos_pasadas_y_no_descanso),
        ("05. Tests/Controles y clasificación de 3 tramos", test_05_tests_controles_y_clasificacion_3_vueltas),
        ("06. Persistencia de tokens Garmin/COROS/Strava", test_06_persistencia_tokens_y_nube),
        ("07. Auto-Sync multi-atleta, pull previo y cron", test_07_auto_sync_multiatleta_y_cron),
        ("08. COROS gzip, laps type==2 (cm/cs) y 5x1.000m", test_08_coros_gzip_laps_y_series_miles),
    ]
    for titulo, fn in tests:
        fn()
        print(f"[OK] {titulo}")
    print("\nTODAS LAS PRUEBAS DE GUARDIAN SPORTTRACKS PASARON CON EXITO.")


if __name__ == "__main__":
    main()
