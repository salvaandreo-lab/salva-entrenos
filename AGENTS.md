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
* **Almacenamiento en SQLite (`sesiones_plataformas`):** Todo inicio de sesión o refresco de tokens en `garmin_sync.py`, `coros_sync.py` y `strava_sync.py` debe persistirse en `sesiones_plataformas`. Prohibido `import json` local dentro de `conectar_garmin()`.
* **Aislamiento en splits y detección de Garmin:** El cálculo al vuelo de splits en `app.py` debe usar `obtener_directorio_tokens(usuario_id=uid_split)` como `tokenstore_dir` (nunca un archivo `.json` ni la sesión raíz). La detección de Garmin en `app.py` y `database.py` debe verificar `garmin_tokens.json` o `sesiones_plataformas`, nunca `os.path.isdir(.../u{uid})`.
* **Errores de sincronización:** Cualquier fallo en `sincronizar_actividades_todas()` debe contener `"error"` para mostrarse como alerta y nunca como `Todo al día`.

---

## 7. Conciliación del Planning en Dos Pasadas y Tests en Series
* **Dos pasadas obligatorias:** `plan_entrenador.conciliar_plan_con_garmin()` empareja primero fechas exactas y después desplazamientos solo sobre entrenos huérfanos; `aplicar_etiquetas_entrenador()` nunca renombra un entreno real a `"Descanso"`.
* **Tests, COROS laps, 1600m y clasificación de vueltas:** `TEST 2 KMS` / `Control` entran en *Análisis de Series* (`2k` → `2000 mtrs`), el desplegable incluye `1600 mtrs` (`1500–1700 m`) y `clasificar_vueltas_sesion()` separa calentamiento inicial suave ($\ge 800\,\text{m}$), enfriamiento y recuperaciones de ~400 m ($\le 450\,\text{m}$) si son $\ge 25\,\text{s/km}$ más lentos que la serie rápida. `generar_titulo_amigable()` preserva `5x1.000m` → `Series 5x1000m`. En `coros_sync.py`, descomprimir respuestas `gzip`, priorizar `lapList` `type == 2` sobre `type == -1` y convertir cm/cs (`/ 100.0`).

---

## 8. Auto-Sync Multi-Atleta (21:05 + Apertura App) y Guardián Obligatorio
* `auto_sync_runner.py` descarga primero `sporttracks.db` con `pull_file`, recorre dinámicamente `database.obtener_usuarios()` para todas las plataformas y concilia planes con una sola subida atómica (`AUTO_SYNC_BATCH=1`). En modo incremental, COROS limita el reprocesamiento a `limite=5` recientes; `app.py` ejecuta `_ejecutar_auto_sync_apertura()` con cooldown de 2h para todos los atletas.
* **Obligatorio antes de desplegar:** Ejecutar `python tests_sporttracks.py` y verificar que pasen **todas** las pruebas.
