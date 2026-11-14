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

# ==================== HELPERS DE ESTILO POWER BI ====================
def aplicar_estilo_powerbi(fig, titulo="", subtitulo="", x_title="", y_title="", mostrar_grid_y=True, altura=380):
    """Estilo limpio, profesional y de alto contraste estilo Power BI moderno con texto negro nítido."""
    fig.update_layout(
        title=dict(
            text=f"<b style='font-size:18px; color:#000000;'>{titulo}</b><br><span style='font-size:13px; color:#334155;'>{subtitulo}</span>" if subtitulo else f"<b style='font-size:18px; color:#000000;'>{titulo}</b>",
            x=0.01,
            y=0.96,
            xanchor="left",
            yanchor="top"
        ),
        plot_bgcolor="rgba(0, 0, 0, 0)",
        paper_bgcolor="rgba(0, 0, 0, 0)",
        height=altura,
        margin=dict(l=20, r=20, t=65 if subtitulo else 45, b=45),
        font=dict(
            family="Segoe UI, -apple-system, BlinkMacSystemFont, Roboto, sans-serif",
            color="#000000",
            size=12
        ),
        xaxis=dict(
            title=dict(text=f"<b>{x_title}</b>" if x_title else "", font=dict(size=13, color="#000000")),
            showgrid=False,
            showline=True,
            linecolor="#000000",
            linewidth=1.5,
            tickfont=dict(size=13, color="#000000", family="Segoe UI"),  # Texto negro puro
            zeroline=False
        ),
        yaxis=dict(
            title=dict(text=f"<b>{y_title}</b>" if y_title else "", font=dict(size=13, color="#000000")),
            showgrid=mostrar_grid_y,
            gridcolor="#E2E8F0",
            gridwidth=1,
            showline=False,
            tickfont=dict(size=12, color="#000000", family="Segoe UI"),  # Texto negro puro
            zeroline=False
        ),
        hoverlabel=dict(
            bgcolor="#0F172A",
            font_size=12,
            font_family="Segoe UI, sans-serif",
            bordercolor="#0078D4"
        ),
        bargap=0.35
    )
    return fig

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
            paleta_pbi = ["#00B4D8", "#0078D4", "#2EC4B6", "#F2C811", "#FF7F50", "#E63946", "#7928CA", "#4361EE"]
            fig_pb = px.bar(
                df_rec_valid,
                x="categoria",
                y="ritmo_seg",
                color="categoria",
                color_discrete_sequence=paleta_pbi,
                text="ritmo"
            )
            fig_pb.update_traces(
                textposition='outside',
                textfont=dict(color="#000000", size=12, family="Segoe UI"),
                marker=dict(line=dict(width=0))
            )
            aplicar_estilo_powerbi(
                fig_pb,
                titulo="Curva de Ritmos en Récords Personales",
                subtitulo="Ritmo oficial (min/km) conseguido en tus mejores marcas",
                x_title="Distancia",
                y_title="Segundos por km"
            )
            st.plotly_chart(fig_pb, use_container_width=True, theme=None)
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
            df_anual_sorted = df_anual.sort_values("anio")
            fig_anual = px.bar(
                df_anual_sorted,
                x="anio",
                y="total_km",
                text=df_anual_sorted["total_km"].apply(lambda v: f"{v:,.0f}k".replace(",", ".")),
                color="total_km",
                color_continuous_scale=[[0.0, "#0078D4"], [0.5, "#00B4D8"], [1.0, "#2EC4B6"]]
            )
            fig_anual.update_traces(
                textposition='outside',
                textfont=dict(color="#000000", size=12, family="Segoe UI"),
                marker=dict(line=dict(width=0))
            )
            fig_anual.update_coloraxes(showscale=False)
            aplicar_estilo_powerbi(
                fig_anual,
                titulo="Volumen Anual Acumulado",
                subtitulo="Kilómetros totales completados por temporada",
                x_title="Año",
                y_title="Kilómetros"
            )
            st.plotly_chart(fig_anual, use_container_width=True, theme=None)

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
            marker=dict(
                color="#00B4D8",
                line=dict(width=0)
            ),
            opacity=0.85
        ))
        fig_sem.add_trace(go.Scatter(
            x=df_sem_filtrado["semana"],
            y=df_sem_filtrado["media_movil_4sem"],
            mode="lines",
            name="Media móvil (4 semanas)",
            line=dict(color="#F2C811", width=3.5)
        ))
        aplicar_estilo_powerbi(
            fig_sem,
            titulo="Carga de Entrenamiento Semanal",
            subtitulo="Volumen semanal (barras) vs. Tendencia de 4 semanas (línea de carga)",
            x_title="Semana",
            y_title="Kilómetros",
            altura=400
        )
        fig_sem.update_layout(
            hovermode="x unified",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, font=dict(color="#000000"))
        )
        st.plotly_chart(fig_sem, use_container_width=True, theme=None)

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
                    laps_clasificados, resumen_series = database.clasificar_vueltas_sesion(laps_sel)
                    df_laps_sel = pd.DataFrame(laps_clasificados)

                    if resumen_series["num_series"] > 1:
                        st.markdown(f"#### ⚡ Análisis de Series: **{resumen_series['num_series']} Series de ~{resumen_series['distancia_aprox']}m**")
                        c_sub1, c_sub2, c_sub3 = st.columns(3)
                        c_sub1.success(f"🎯 **Series reales:** {resumen_series['num_series']} repeticiones")
                        c_sub2.info(f"⏱️ **Recuperaciones:** {resumen_series['num_recuperaciones']} pausas de descanso")
                        c_sub3.caption(f"🏃 **Calentamiento:** {resumen_series['calentamiento_km']} km | **Enfriamiento:** {resumen_series['enfriamiento_km']} km")
                    else:
                        st.markdown(f"#### ⚡ Desglose de Vueltas ({len(laps_sel)} tramos)")

                    # Gráfica de la sesión seleccionada estilo Power BI
                    col_g1, col_g2 = st.columns([1, 1])
                    with col_g1:
                        # Paleta ejecutiva Power BI para los tipos de tramo
                        color_map = {
                            "Calentamiento": "#7928CA",
                            "Recuperación": "#4A5568",
                            "Enfriamiento": "#F77F00"
                        }
                        fig_laps_t = px.bar(
                            df_laps_sel,
                            x="lap_numero",
                            y="distancia_m",
                            color="tipo_clasificado",
                            color_discrete_map=color_map,
                            color_discrete_sequence=["#00B4D8", "#0078D4", "#2EC4B6"]
                        )
                        fig_laps_t.update_traces(marker=dict(line=dict(width=0)))
                        aplicar_estilo_powerbi(
                            fig_laps_t,
                            titulo="Perfil de la Sesión",
                            subtitulo="Metros por tramo (Calentamiento, Series y Descansos)",
                            x_title="Nº Vuelta",
                            y_title="Metros"
                        )
                        fig_laps_t.update_layout(legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, font=dict(color="#000000")))
                        st.plotly_chart(fig_laps_t, use_container_width=True, theme=None)

                    with col_g2:
                        # Filtrar solo series para la gráfica de ritmos/tiempos si hay series
                        df_solo_series = df_laps_sel[df_laps_sel["tipo_clasificado"].str.startswith("Serie")]
                        df_plot_s = df_solo_series if not df_solo_series.empty else df_laps_sel
                        fig_laps_s = px.bar(
                            df_plot_s,
                            x="tipo_clasificado" if not df_solo_series.empty else "lap_numero",
                            y="tiempo_s",
                            color="fc_media",
                            color_continuous_scale=[[0.0, "#0078D4"], [0.5, "#00B4D8"], [1.0, "#FF5A5F"]],
                            text="tiempo_formateado"
                        )
                        fig_laps_s.update_traces(
                            textposition='outside',
                            textfont=dict(color="#000000", size=11, family="Segoe UI"),
                            marker=dict(line=dict(width=0))
                        )
                        fig_laps_s.update_coloraxes(colorbar_title=dict(text="FC Media", font=dict(color="#000000", size=11)))
                        aplicar_estilo_powerbi(
                            fig_laps_s,
                            titulo="Tiempos de las Series Reales",
                            subtitulo="Duración exacta por repetición activa (segundos)",
                            x_title="Serie" if not df_solo_series.empty else "Vuelta",
                            y_title="Segundos"
                        )
                        st.plotly_chart(fig_laps_s, use_container_width=True, theme=None)

                    # Tabla de vueltas
                    columnas_laps = ["lap_numero", "tipo_clasificado", "distancia_m", "tiempo_formateado", "ritmo_minkm", "fc_media", "fc_max"]
                    st.dataframe(
                        df_laps_sel[columnas_laps].rename(columns={
                            "lap_numero": "Vuelta #",
                            "tipo_clasificado": "Tipo de Tramo",
                            "distancia_m": "Metros",
                            "tiempo_formateado": "Tiempo",
                            "ritmo_minkm": "Ritmo",
                            "fc_media": "FC Media",
                            "fc_max": "FC Máx"
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
    st.subheader("⚡ Detalle y Análisis de Series")
    st.caption("Compara los tiempos de cada repetición de forma limpia, separando las recuperaciones.")

    col_s1, col_s2 = st.columns([1, 2])
    with col_s1:
        distancia_opciones = {
            "1000m": (900, 1100),
            "400m (Pista)": (380, 430),
            "2000m": (1900, 2100),
            "5000m": (4800, 5200)
        }
        dist_sel = st.selectbox(
            "Distancia de serie:",
            list(distancia_opciones.keys()),
            index=0
        )
        d_min, d_max = distancia_opciones[dist_sel]

    # Buscar sesiones que tengan series de esa distancia
    query_sesiones = f"""
    SELECT e.id, e.fecha, e.titulo, COUNT(s.id) as num_series,
           ROUND(AVG(s.tiempo_s), 1) as media_seg,
           MIN(s.tiempo_s) as min_seg
    FROM entrenamientos e
    JOIN series_laps s ON s.entrenamiento_id = e.id
    WHERE s.distancia_m BETWEEN {d_min} AND {d_max}
    GROUP BY e.id
    HAVING COUNT(s.id) >= 2
    ORDER BY e.fecha DESC
    """
    sesiones_series = database.ejecutar_consulta_sql(query_sesiones)

    if sesiones_series:
        with col_s2:
            opciones_sesion = [
                f"{s['id']} | {s['fecha'][:10]} · {s['titulo']} ({s['num_series']} series)"
                for s in sesiones_series
            ]
            sel_sesion_str = st.selectbox(
                "Seleccionar sesión de series:",
                opciones_sesion,
                index=0
            )
            sesion_id = int(sel_sesion_str.split(" | ")[0])

        # Cargar los laps exactos de esa sesión
        query_laps = f"""
        SELECT lap_numero, distancia_m, tiempo_s, tiempo_formateado, ritmo_minkm, fc_media, fc_max
        FROM series_laps
        WHERE entrenamiento_id = {sesion_id} AND distancia_m BETWEEN {d_min} AND {d_max}
        ORDER BY lap_numero ASC
        """
        laps_series_raw = database.ejecutar_consulta_sql(query_laps)

        if laps_series_raw:
            df_laps_s = pd.DataFrame(laps_series_raw)
            # Nombrar como Serie 1, Serie 2... en negrita y negro para la gráfica
            df_laps_s["nombre_serie"] = [f"<b>Serie #{i}</b>" for i in range(1, len(df_laps_s) + 1)]
            df_laps_s["nombre_serie_clean"] = [f"Serie #{i}" for i in range(1, len(df_laps_s) + 1)]

            # Métricas resumen de la sesión
            t_seg_lista = df_laps_s["tiempo_s"].tolist()
            min_t = min(t_seg_lista)
            avg_t = sum(t_seg_lista) / len(t_seg_lista)
            mejor_serie_row = df_laps_s.loc[df_laps_s["tiempo_s"].idxmin()]

            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Total Series", f"{len(df_laps_s)} repeticiones")
            m2.metric("Mejor Serie", mejor_serie_row["tiempo_formateado"], f"{mejor_serie_row['ritmo_minkm']} min/km")
            m3.metric("Tiempo Medio", f"{int(avg_t // 60)}:{int(avg_t % 60):02d}", f"{(avg_t / (df_laps_s['distancia_m'].mean() / 1000) / 60):.2f} min/km")
            fc_media_val = df_laps_s["fc_media"].dropna()
            m4.metric("FC Media", f"{int(fc_media_val.mean())} ppm" if not fc_media_val.empty else "No reg.")

            # Gráfica de Barras limpia, ancha y contrastada estilo Power BI
            fig_series = go.Figure()

            # Barras de las series con etiquetas en negro puro y alto contraste
            fig_series.add_trace(go.Bar(
                x=df_laps_s["nombre_serie"],
                y=df_laps_s["tiempo_s"],
                text=df_laps_s["tiempo_formateado"],
                textposition="outside",
                textfont=dict(color="#000000", size=13, family="Segoe UI"),
                marker=dict(
                    color="#0078D4",  # Azul Power BI vibrante
                    line=dict(width=0)
                ),
                name="Tiempo por Serie"
            ))

            # Línea de referencia media
            fig_series.add_hline(
                y=avg_t,
                line_dash="dash",
                line_color="#B45309",
                line_width=2,
                annotation_text=f"Media: {int(avg_t // 60)}:{int(avg_t % 60):02d} min",
                annotation_position="top right",
                annotation_font=dict(color="#B45309", size=12)
            )

            # Margen superior en Y para que el texto de arriba no se corte
            max_y = max(t_seg_lista) * 1.15
            min_y = max(0, min(t_seg_lista) * 0.8)

            aplicar_estilo_powerbi(
                fig_series,
                titulo=f"Tiempos por Serie - {dist_sel}",
                subtitulo=f"Sesión del {sel_sesion_str.split(' | ')[1]}",
                x_title="Repetición",
                y_title="Segundos",
                altura=420
            )
            fig_series.update_layout(
                yaxis=dict(range=[min_y, max_y]),
                xaxis=dict(
                    tickfont=dict(color="#000000", size=13, family="Segoe UI"),
                    tickcolor="#000000",
                    title=dict(font=dict(color="#000000", size=13))
                )
            )
            st.plotly_chart(fig_series, use_container_width=True, theme=None)

            # Tabla con las series
            st.dataframe(
                df_laps_s[["nombre_serie_clean", "distancia_m", "tiempo_formateado", "ritmo_minkm", "fc_media", "fc_max"]].rename(columns={
                    "nombre_serie_clean": "Repetición",
                    "distancia_m": "Metros",
                    "tiempo_formateado": "Tiempo",
                    "ritmo_minkm": "Ritmo",
                    "fc_media": "FC Media",
                    "fc_max": "FC Máx"
                }),
                use_container_width=True,
                hide_index=True
            )
    else:
        st.info(f"No se han encontrado sesiones con series de {dist_sel}.")

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
