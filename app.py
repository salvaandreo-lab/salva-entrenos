import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import os
import tempfile
from datetime import datetime

import database
import garmin_sync
import consultas_ai
import plan_entrenador

st.set_page_config(
    page_title="SportTracks AI - Tu historial de Garmin con IA",
    page_icon="🏃",
    layout="wide"
)

# Inicializar Base de Datos
database.init_db()

# Título y encabezado principal
st.title("🏃 SportTracks AI")
st.caption("Análisis avanzado de entrenamientos de atletismo, cargas de trabajo y asistente inteligente con IA.")

# Resumen superior
stats = database.obtener_resumen_estadisticas()
total_km = stats.get("total_km", 0)
total_entrenos = stats.get("total_entrenos", 0)
media_km = round(total_km / max(1, total_entrenos), 1)

col1, col2, col3, col4 = st.columns(4)
col1.metric("Sesiones registradas", total_entrenos)
col2.metric("Kilómetros totales", f"{total_km:,} km".replace(",", "."))
col3.metric("Media por sesión", f"{media_km} km")
col4.metric("Series e intervalos", stats.get("total_series", 0))

st.divider()

# Pestañas principales
tab_chat, tab_plan, tab_records, tab_volumen, tab_historial, tab_series, tab_importar = st.tabs([
    "💬 Entrenador IA (Chat)",
    "📋 Plan Entrenador vs. Garmin",
    "🏆 Récords Personales (PB)",
    "📈 Volumen y Carga Semanal",
    "🎽 Ficha de Sesión e Historial",
    "⚡ Análisis de Series",
    "📥 Sincronizar Garmin"
])

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

    # Mostrar sugerencias rápidas si el chat está vacío
    if not st.session_state.chat_history:
        st.markdown("**Consultas rápidas sugeridas:**")
        col_sug1, col_sug2, col_sug3, col_sug4 = st.columns(4)
        pregunta_click = None

        if col_sug1.button("⚡ Mi mejor serie de 400m", use_container_width=True):
            pregunta_click = "¿Cuál fue mi serie de 400 metros más rápida de toda mi historia y qué día fue?"
        if col_sug2.button("🏆 Mis marcas en Santa Pola", use_container_width=True):
            pregunta_click = "Dime todas las veces que corrí la Media Maratón de Santa Pola y mis tiempos"
        if col_sug3.button("📅 Mi semana con más kms", use_container_width=True):
            pregunta_click = "¿Cuál fue la semana en la que corrí más kilómetros y cuántos hice?"
        if col_sug4.button("🏃 ¿Cuándo corrí mi Maratón?", use_container_width=True):
            pregunta_click = "Cuéntame los detalles de mi mejor maratón: fecha, ritmo, tiempo y pulso"

        if pregunta_click:
            st.session_state.chat_history.append({"role": "user", "content": pregunta_click})
            with st.spinner("Analizando tus 1.296 entrenamientos con Gemini..."):
                resp = consultas_ai.responder_consulta_entrenamientos(pregunta_click)
                st.session_state.chat_history.append({"role": "assistant", "content": resp})
            st.rerun()

    # Renderizar historial de mensajes
    for msg in st.session_state.chat_history:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # Entrada de texto del usuario
    pregunta_input = st.chat_input("Escribe tu pregunta al entrenador IA...")
    if pregunta_input:
        st.session_state.chat_history.append({"role": "user", "content": pregunta_input})
        with st.chat_message("user"):
            st.markdown(pregunta_input)

        with st.chat_message("assistant"):
            with st.spinner("El entrenador está consultando tu historial en Garmin..."):
                resp = consultas_ai.responder_consulta_entrenamientos(pregunta_input)
                st.markdown(resp)
        st.session_state.chat_history.append({"role": "assistant", "content": resp})
        st.rerun()

# ==================== PESTAÑA 2: PLAN DEL ENTRENADOR VS. GARMIN ====================
with tab_plan:
    st.subheader("📋 Planificación del Entrenador vs. Entrenamientos Garmin")
    st.caption("Vinculado en tiempo real con el Google Doc de tu entrenador. Detecta cambios automáticos, etiquetas de series y discrepancias de fechas.")

    doc_url = plan_entrenador.obtener_doc_url()

    col_p1, col_p2 = st.columns([3, 1])
    with col_p1:
        st.info(f"🔗 **Documento activo del míster**: [Abrir Google Doc del Entrenador]({doc_url})")
    with col_p2:
        if st.button("🔄 Comprobar cambios ahora", use_container_width=True):
            st.success("Plan recargado en vivo directamente desde Google Docs.")
            st.rerun()

    # Descargar y conciliar en vivo
    try:
        plan_dias = plan_entrenador.descargar_plan_entrenador(doc_url)
        reconciliacion = plan_entrenador.conciliar_plan_con_garmin(plan_dias)
        comparativa = reconciliacion["comparativa"]
        preguntas = reconciliacion["preguntas_discrepancias"]
    except Exception as e:
        st.error(f"Error al sincronizar con el Google Doc del entrenador: {e}")
        plan_dias = []
        comparativa = []
        preguntas = []

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
        
        # Seleccionar por defecto la semana actual (09-11 al 15-11)
        def_idx = 0
        for idx_s, s in enumerate(semanas_disponibles):
            if "09-11" in s or "15-11" in s:
                def_idx = idx_s
                break

        semana_sel = st.selectbox("Seleccionar semana del plan:", semanas_disponibles, index=def_idx)

        dias_semana_sel = [
            item for item in comparativa 
            if any(p["fecha"] == item["fecha"] and p["semana"] == semana_sel for p in plan_dias)
        ]

        for item in dias_semana_sel:
            with st.container():
                c_dia, c_plan, c_garmin, c_estado = st.columns([1.5, 3.5, 3, 1.5])
                with c_dia:
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

    # Configuración de URL del documento
    with st.expander("⚙️ Configuración del enlace de Google Docs"):
        nueva_url = st.text_input("URL del Google Doc de entrenamientos:", value=doc_url)
        if st.button("Guardar nuevo enlace"):
            plan_entrenador.guardar_doc_url(nueva_url)
            st.success("Enlace actualizado correctamente.")
            st.rerun()

# ==================== PESTAÑA 3: RÉCORDS PERSONALES (PB) ====================
with tab_records:
    st.subheader("🏆 Mejores Marcas Personales (Personal Bests)")
    st.caption("Detección automática de tus récords absolutos registrados en tu reloj Garmin.")

    records = database.obtener_records_personales()
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
            fig_pb = px.bar(
                df_rec_valid,
                x="categoria",
                y="ritmo_seg",
                color="categoria",
                title="Curva de Ritmos en tus Récords Personales (segundos / km)",
                labels={"categoria": "Distancia", "ritmo_seg": "Segundos por km"},
                text="ritmo"
            )
            fig_pb.update_traces(textposition='outside')
            st.plotly_chart(fig_pb, use_container_width=True)
    else:
        st.info("No se han podido calcular los récords con los datos actuales.")

# ==================== PESTAÑA 3: VOLUMEN Y CARGA SEMANAL ====================
with tab_volumen:
    st.subheader("📈 Carga y Volumen de Entrenamiento")
    st.caption("Evolución de kilómetros semanales, mensuales y anuales para control de picos de forma y descanso.")

    # 1. Resumen Anual
    vol_anual = database.obtener_volumen_anual()
    if vol_anual:
        df_anual = pd.DataFrame(vol_anual)
        col_va1, col_va2 = st.columns([1, 2])
        with col_va1:
            st.markdown("#### 📅 Kilómetros por Año")
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
            fig_anual = px.bar(
                df_anual.sort_values("anio"),
                x="anio",
                y="total_km",
                text="total_km",
                title="Volumen Anual Acumulado (km)",
                color="total_km",
                color_continuous_scale="Blues"
            )
            fig_anual.update_traces(textposition='outside')
            st.plotly_chart(fig_anual, use_container_width=True)

    st.divider()

    # 2. Volumen Semanal con media móvil
    st.markdown("#### 🏃 Kilómetros Semanales (Carga Aguda vs. Crónica)")
    vol_semanal = database.obtener_volumen_semanal()
    if vol_semanal:
        df_sem = pd.DataFrame(vol_semanal)
        df_sem["media_movil_4sem"] = df_sem["total_km"].rolling(window=4, min_periods=1).mean().round(1)

        # Filtro de años para no saturar la vista semanal
        anios_disponibles = sorted(list(set(s[:4] for s in df_sem["semana"])), reverse=True)
        anios_sel = st.multiselect("Filtrar por año(s):", anios_disponibles, default=anios_disponibles[:3])

        df_sem_filtrado = df_sem[df_sem["semana"].str[:4].isin(anios_sel)]

        fig_sem = go.Figure()
        fig_sem.add_trace(go.Bar(
            x=df_sem_filtrado["semana"],
            y=df_sem_filtrado["total_km"],
            name="Km Semanales",
            marker_color="#1f77b4",
            opacity=0.75
        ))
        fig_sem.add_trace(go.Scatter(
            x=df_sem_filtrado["semana"],
            y=df_sem_filtrado["media_movil_4sem"],
            mode="lines",
            name="Media móvil (4 semanas)",
            line=dict(color="#ff7f0e", width=3)
        ))
        fig_sem.update_layout(
            title="Volumen Semanal con Tendencia (Media 4 Semanas)",
            xaxis_title="Semana",
            yaxis_title="Kilómetros",
            hovermode="x unified",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        st.plotly_chart(fig_sem, use_container_width=True)

# ==================== PESTAÑA 4: FICHA DE SESIÓN E HISTORIAL ====================
with tab_historial:
    st.subheader("📋 Historial y Ficha Detallada de Entrenamiento")

    entrenos_raw = database.ejecutar_consulta_sql("SELECT * FROM entrenamientos ORDER BY fecha DESC")

    if entrenos_raw:
        df_entrenos = pd.DataFrame(entrenos_raw)

        # Buscador y selector de sesión para ver su ficha
        st.markdown("#### 🔍 Inspeccionar Sesión en Detalle")
        col_filtro1, col_filtro2 = st.columns([1, 2])
        with col_filtro1:
            texto_busqueda = st.text_input("Filtrar por texto (ej. 'Santa Pola', 'Maratón', '400m', 'Valencia'):", "")
        with col_filtro2:
            opciones_df = df_entrenos
            if texto_busqueda:
                opciones_df = df_entrenos[
                    df_entrenos["titulo"].astype(str).str.contains(texto_busqueda, case=False, na=False) |
                    df_entrenos["ubicacion"].astype(str).str.contains(texto_busqueda, case=False, na=False)
                ]

            lista_opciones = [
                f"{r['id']} | {r['fecha'][:10]} · {r['titulo']} ({r['distancia_km']} km, {r['tiempo_formateado']})"
                for _, r in opciones_df.head(100).iterrows()
            ]

            if lista_opciones:
                seleccion_label = st.selectbox("Selecciona un entrenamiento para ver su ficha completa:", lista_opciones)
                sel_id = int(seleccion_label.split(" | ")[0])
            else:
                st.warning("No se encontraron entrenamientos con ese texto.")
                sel_id = None

        # Mostrar ficha del entrenamiento seleccionado
        if sel_id:
            entreno_sel, laps_sel = database.obtener_detalle_entrenamiento(sel_id)
            if entreno_sel:
                st.markdown(f"### 🎽 Ficha: **{entreno_sel.get('titulo', 'Entrenamiento')}**")
                st.caption(f"📅 Fecha: **{entreno_sel.get('fecha')}** | 📍 Ubicación: **{entreno_sel.get('ubicacion') or 'No especificada'}**")

                col_m1, col_m2, col_m3, col_m4, col_m5 = st.columns(5)
                col_m1.metric("Distancia", f"{entreno_sel.get('distancia_km')} km")
                col_m2.metric("Tiempo", entreno_sel.get("tiempo_formateado"))
                col_m3.metric("Ritmo medio", f"{entreno_sel.get('ritmo_medio_minkm')} min/km")
                col_m4.metric("FC Media / Máx", f"{entreno_sel.get('fc_media') or '-'} / {entreno_sel.get('fc_max') or '-'} ppm")
                col_m5.metric("Cadencia / Calorías", f"{entreno_sel.get('cadencia_media') or '-'} spm · {entreno_sel.get('calorias') or '-'} kcal")

                if laps_sel:
                    df_laps_sel = pd.DataFrame(laps_sel)
                    st.markdown(f"#### ⚡ Desglose de Vueltas / Series ({len(laps_sel)} intervalos)")

                    # Gráfica de la sesión seleccionada
                    col_g1, col_g2 = st.columns([1, 1])
                    with col_g1:
                        fig_laps_t = px.bar(
                            df_laps_sel,
                            x="lap_numero",
                            y="distancia_m",
                            color="fc_media",
                            title="Distancia y Pulso por Vuelta",
                            labels={"lap_numero": "Nº Vuelta", "distancia_m": "Metros", "fc_media": "FC Media"},
                            color_continuous_scale="Reds"
                        )
                        st.plotly_chart(fig_laps_t, use_container_width=True)

                    with col_g2:
                        fig_laps_s = px.line(
                            df_laps_sel,
                            x="lap_numero",
                            y="tiempo_s",
                            markers=True,
                            title="Tiempo por Vuelta (segundos)",
                            labels={"lap_numero": "Nº Vuelta", "tiempo_s": "Segundos"}
                        )
                        st.plotly_chart(fig_laps_s, use_container_width=True)

                    # Tabla de vueltas
                    columnas_laps = ["lap_numero", "distancia_m", "tiempo_formateado", "ritmo_minkm", "fc_media", "fc_max", "cadencia"]
                    st.dataframe(
                        df_laps_sel[columnas_laps].rename(columns={
                            "lap_numero": "Vuelta #",
                            "distancia_m": "Metros",
                            "tiempo_formateado": "Tiempo",
                            "ritmo_minkm": "Ritmo",
                            "fc_media": "FC Media",
                            "fc_max": "FC Máx",
                            "cadencia": "Cadencia"
                        }),
                        use_container_width=True,
                        hide_index=True
                    )
                else:
                    st.info("Esta sesión no tiene registros de vueltas o series intermedias.")

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

# ==================== PESTAÑA 5: ANÁLISIS DE SERIES ====================
with tab_series:
    st.subheader("⚡ Detalle de Series e Intervalos")
    distancia_filtro = st.selectbox(
        "Seleccionar distancia de serie a analizar:",
        ["Todas", "400m (Pista)", "1000m", "2000m", "5000m"]
    )

    query_series = """
    SELECT e.fecha, e.titulo, s.lap_numero, s.distancia_m, s.tiempo_s,
           s.tiempo_formateado, s.ritmo_minkm, s.fc_media, s.fc_max, s.cadencia
    FROM series_laps s
    JOIN entrenamientos e ON s.entrenamiento_id = e.id
    """
    if distancia_filtro == "400m (Pista)":
        query_series += " WHERE s.distancia_m BETWEEN 380 AND 420 "
    elif distancia_filtro == "1000m":
        query_series += " WHERE s.distancia_m BETWEEN 950 AND 1050 "
    elif distancia_filtro == "2000m":
        query_series += " WHERE s.distancia_m BETWEEN 1900 AND 2100 "
    elif distancia_filtro == "5000m":
        query_series += " WHERE s.distancia_m BETWEEN 4800 AND 5200 "

    query_series += " ORDER BY e.fecha DESC, s.lap_numero ASC"

    series_data = database.ejecutar_consulta_sql(query_series)

    if series_data:
        df_series = pd.DataFrame(series_data)
        st.dataframe(
            df_series[["fecha", "titulo", "lap_numero", "distancia_m", "tiempo_formateado", "ritmo_minkm", "fc_media", "fc_max"]].rename(columns={
                "fecha": "Fecha",
                "titulo": "Sesión",
                "lap_numero": "Nº Serie",
                "distancia_m": "Metros",
                "tiempo_formateado": "Tiempo",
                "ritmo_minkm": "Ritmo",
                "fc_media": "FC Media",
                "fc_max": "FC Máx"
            }),
            use_container_width=True,
            hide_index=True
        )

        fig = px.bar(
            df_series.head(100),
            x="fecha",
            y="tiempo_s",
            color="fc_media",
            title="Evolución de tiempos de serie en el tiempo",
            labels={"fecha": "Fecha", "tiempo_s": "Segundos", "fc_media": "FC Media"},
            color_continuous_scale="Viridis"
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No hay series registradas para el filtro seleccionado.")

# ==================== PESTAÑA 6: CONECTAR GARMIN ====================
with tab_importar:
    st.subheader("📥 Sincronización y Carga de Entrenamientos")

    # Detección de sesión guardada
    token_dir = os.path.join(os.path.dirname(__file__), ".garmin_tokens")
    token_file = os.path.join(token_dir, "garmin_tokens.json")
    tiene_sesion = os.path.isfile(token_file)

    if tiene_sesion:
        st.success("✅ **Sesión de Garmin Connect guardada activamente en este ordenador.**")
        if st.button("⚡ Sincronización Rápida a 1 Clic (Descargar nuevos entrenos)", type="primary"):
            progress_bar = st.progress(0)
            status_text = st.empty()

            def actualizar_progreso(actual, total, detalle):
                porcentaje = min(1.0, actual / max(1, total))
                progress_bar.progress(porcentaje)
                status_text.text(f"Comprobando {actual}: {detalle}")

            try:
                with st.spinner("Conectando con sesión guardada..."):
                    cliente, msg = garmin_sync.conectar_garmin("", tokenstore_dir=token_dir)

                nuevas, omitidas = garmin_sync.descargar_historial_garmin(
                    cliente,
                    max_actividades=50,
                    callback_progreso=actualizar_progreso
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
                        cliente, msg = garmin_sync.conectar_garmin(garmin_user, garmin_pass)

                    max_acts = limite_map.get(opcion_limite, 50)
                    nuevas, omitidas = garmin_sync.descargar_historial_garmin(cliente, max_actividades=max_acts)
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
                id_guardado = database.guardar_entrenamiento(datos_entreno, laps)
                if id_guardado:
                    st.success(f"✅ ¡Entrenamiento '{datos_entreno['titulo']}' importado con éxito!")
                else:
                    st.warning("Este entrenamiento ya existía en la base de datos.")
            except Exception as e:
                st.error(f"Error: {e}")
            finally:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
