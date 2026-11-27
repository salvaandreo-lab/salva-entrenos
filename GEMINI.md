# Reglas de Desarrollo y Arquitectura - SportTracks AI (Team Ardil)

Este documento define las reglas estrictas de arquitectura, buenas prácticas y lecciones aprendidas para garantizar la estabilidad de la plataforma y evitar regresiones.

---

## 1. Aislamiento Estricto de Atletas y Planificaciones (CRÍTICO)
* **Independencia absoluta:** Cada atleta es 100% autónomo. Sus entrenamientos, series, marcas personales, métricas y planificación pertenecen única y exclusivamente a su perfil (`usuario_id`).
* **Plannings independientes:** Cada atleta tiene su propio planning individual en Google Docs configurado en la columna `usuarios.doc_plan_url`. 
  * **PROHIBIDO** reutilizar o asignar por defecto el documento de Salva a ningún otro atleta (e.g., Jose Ángel).
  * **PROHIBIDO** borrar o sobreescribir la URL de Google Docs de un atleta al actualizar sus datos personales o al realizar modificaciones en la base de datos.
* **Dispositivo y plataforma por atleta:** Cada atleta utiliza su propio ecosistema (e.g., Salva con Garmin, Jose Ángel con COROS). La plataforma preferida se almacena en `usuarios.plataforma_principal` y las sesiones activas en la tabla `sesiones_plataformas`.

---

## 2. Orden de Inicialización y Alcance en `app.py`
* **Definición de `usuario_activo`:** La variable global `usuario_activo` se inicializa y resuelve en las líneas centrales del script (tras cargar `usuarios_db`).
* **PROHIBIDO** acceder a `usuario_activo` en las cabeceras o utilidades previas (líneas 1 a 650). Si se requiere información del usuario en esa sección, utilizar siempre `database.obtener_usuario_por_id(curr_uid_chk)`.
* **Prueba obligatoria:** Toda modificación de variables de ámbito global debe verificarse con `python -m py_compile app.py`.

---

## 3. Manejo de Widgets y Estado en Streamlit (`StreamlitWidgetAlreadyInstantiatedError`)
* **Regla de oro de Streamlit:** NUNCA modificar una clave de widget en `st.session_state` (por ejemplo, `st.session_state["selector_perfil_sidebar"] = uid`) si dicho widget ya se ha instanciado y dibujado previamente en la ejecución actual.
* **Patrón correcto de navegación:**
  1. Al hacer clic en un botón de acción (como "🔍 Ver ficha"), actualizar únicamente la clave de estado lógico: `st.session_state["usuario_id_activo"] = uid` y `st.session_state["mister_inspeccionando"] = True`.
  2. Llamar inmediatamente a `st.rerun()`.
  3. En la nueva pasada de ejecución, sincronizar los selectores en la cabecera del script **ANTES** de que los widgets `st.selectbox` sean instanciados.

---

## 4. Reglas de Renderizado HTML en `st.markdown`
* **Peligro de sangría Markdown:** CommonMark interpreta cualquier línea con 4 o más espacios de sangría dentro de un bloque HTML como un bloque de código indentado (`<pre><code>`).
* **PROHIBIDO:** Dejar sangrías o saltos de línea con espacios dentro de cadenas multilínea con variables de texto (por ejemplo, `{entreno_hoy['titulo']}`).
* **Patrón correcto:**
  * Generar HTML en cadenas contiguas compactas:
    ```python
    st.markdown(
        f'<div style="...">{variable}</div>',
        unsafe_allow_html=True
    )
    ```
  * O bien aplicar siempre `textwrap.dedent(f"""...""").strip()` asegurando que ninguna línea interior tenga más de 0 espacios relativos.

---

## 5. Detección y Sincronización de Series
* **Clasificación de series y laps:**
  * Mantener soporte completo para series puras y mixtas/combinadas (e.g., `8x300 + 1000`).
  * En la pestaña de series, filtrar siempre agrupaciones válidas mediante `HAVING COUNT >= 1` para permitir series aisladas finales (como un 1000m de remate tras series cortas).
* **Despliegue y persistencia:**
  * Toda modificación que deba verse en Streamlit Cloud debe sincronizarse a GitHub usando `sync_sporttracks.sync_file()`.
  * Si se modifican datos en la base de datos local, sincronizar `sporttracks.db`.

---

## 6. Persistencia de Sesiones y Tokens (Garmin / COROS / Strava)
* **Almacenamiento en SQLite (`sesiones_plataformas`):** La nube de Streamlit es efímera; todo inicio de sesión o refresco de tokens en `garmin_sync.py`, `coros_sync.py` y `strava_sync.py` **debe** guardarse en `sesiones_plataformas` mediante `database.guardar_sesion_plataforma()`.
* **Aislamiento en cálculo al vuelo y detección de Garmin:** En `app.py`, el cálculo al vuelo de splits km a km debe resolver el **directorio** de tokens del atleta (`obtener_directorio_tokens(usuario_id=uid_split)`) y pasarlo como `tokenstore_dir` junto a `usuario_id=uid_split` (nunca pasar la ruta de un `.json` ni usar el token raíz de Salva). Además, ni `app.py` ni `database.py` deben detectar Garmin mediante `os.path.isdir(.../u{uid})` (los directorios vacíos provocan falsos positivos); deben exigir `garmin_tokens.json` o sesión en `sesiones_plataformas`.
* **`import json` a nivel de módulo:** Prohibido hacer `import json` local dentro de un `if` en `garmin_sync.conectar_garmin()`, ya que provoca `UnboundLocalError` al persistir tokens actualizados.
* **Errores de sincronización visibles:** En `sincronizar_actividades_todas()` (`app.py`), cualquier excepción debe incluir la palabra `"error"` en el detalle para no caer en el mensaje engañoso `Todo al día`.

---

## 7. Conciliación del Planning en Dos Pasadas y Días de Descanso
* **Prioridad de fecha exacta:** `plan_entrenador.conciliar_plan_con_garmin()` debe ejecutarse en **dos pasadas** (Paso 1: fechas exactas; Paso 2: desplazamientos $\pm 1/\pm 2$ días únicamente usando entrenamientos huérfanos). Un día pasado sin entreno (ej. sábado) **nunca** puede robar el entreno de otro día con su propia pauta (ej. lunes).
* **Respeto de descansos:** `aplicar_etiquetas_entrenador()` nunca debe renombrar un entrenamiento real realizado en día de descanso al título `"Descanso"`, ni comparar contra diccionarios en memoria desactualizados en lugar del estado real en SQLite.

---

## 8. Tests, Controles, COROS Laps y Clasificación de Sesiones
* **Tests como sesiones analizables:** Palabras clave como `Test` y `Control` (ej. `TEST 2 KMS` → `Test 2k`) deben reconocerse con `es_series = True` en `plan_entrenador.py` y ser aceptadas por `es_sesion_series_real()` en `app.py`, además de preseleccionar su distancia (`2k` → `2000 mtrs`).
* **Distancias soportadas en Análisis de Series:** El desplegable de `app.py` incluye `4000`, `3000`, `2000`, `1600` (`1500–1700 m`), `1000`, `800`, `500`, `400`, `300` y `200 mtrs`.
* **Separadores de miles en series (`5x1.000m`, `5x1k`):** `plan_entrenador.generar_titulo_amigable()` debe preservar el separador de miles (`.000`) y el sufijo `k`/`km` para no truncar `5x1.000m` a `Series 5x1`.
* **COROS Training Hub (`gzip`, `lapList` y unidades):** `coros_sync._decodificar_respuesta_json()` debe descomprimir respuestas `gzip` (en especial `/activity/detail/query`). En `parsear_actividad_coros()`, se debe priorizar el grupo `type == 2` (vueltas reales del entrenamiento) sobre `type == -1` (resumen único) y convertir distancias/tiempos de `lapItemList` desde **cm/cs** (`/ 100.0`) validando la escala contra el total de la actividad.
* **Calentamiento/Enfriamiento en 3 tramos:** `database.clasificar_vueltas_sesion()` debe separar Calentamiento (lap 1 ≥ 1200 m) y Enfriamiento (último lap ≥ 1000 m) también cuando `total == 3` siempre que su ritmo sea notablemente más suave ($\ge 25\,\text{s/km}$) que el tramo rápido central (sin degradar series puras tipo `3x2000m`).

---

## 9. Auto-Sync Diario (21:05) Multi-Atleta, Apertura en App y Orden Nube ↔ Local
* **Descarga previa obligatoria (`pull_file`):** En ejecución local (Tarea Programada de Windows `SportTracks_AutoSync_2105`), `auto_sync_runner.py` debe descargar primero `sporttracks.db` desde GitHub antes de ejecutar ninguna sincronización, evitando sobrescribir nuevos atletas o sesiones creadas desde Streamlit Cloud.
* **Bucle dinámico y rapidez:** `auto_sync_runner.py` recorre dinámicamente todos los atletas activos en `database.obtener_usuarios()`, sincroniza todas sus plataformas activas y aplica la conciliación del plan del míster usando un único volcado atómico (`AUTO_SYNC_BATCH=1`). En modo incremental (`not es_modo_historial`), `coros_sync.sincronizar_actividades_coros()` limita `reprocesar_laps_actividades_existentes()` a `limite=5` y `solo_recientes=True`.
* **Auto-sync al abrir la app:** `app.py` ejecuta `_ejecutar_auto_sync_apertura()` con enfriamiento de 2 horas (`AUTO_SYNC_COOLDOWN_S = 7200`) para todos los atletas activos (Garmin, COROS o Strava) y para el equipo completo en la vista del Míster.

---

## 10. Verificación Obligatoria Antes de Terminar (Guardián)
Siempre que edites cualquier archivo `.py` o el workflow en `SportTracks_AI`:
1. Ejecuta `python tests_sporttracks.py` y asegúrate de que pasen **todas** las pruebas.
2. Si has corregido un error nuevo, añade su prueba en modo solo lectura en `tests_sporttracks.py` y documéntalo en este archivo.
3. No sincronices a GitHub (`sync_sporttracks.py`) si `tests_sporttracks.py` falla.
