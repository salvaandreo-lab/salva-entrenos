# SportTracks AI 🏃‍♂️⏱️

Asistente inteligente de entrenamientos y análisis de series para Garmin.

## Objetivo del proyecto
1. **Historial de Garmin:** Almacenar entrenamientos, carreras y series/intervalos detallados (ritmo, pulsaciones, tiempo, distancia).
2. **Consultas en lenguaje natural con IA:** Preguntar al asistente cosas como:
   - *"¿Cuándo fue la última vez que hice series de 400m?"*
   - *"¿Cuál fue mi serie más rápida de 1000m este mes?"*
   - *"Dime todas las veces que corrí la carrera de Orihuela y mis tiempos."*
3. **Sincronización con el entrenador:** Planificación vs. entrenamientos realizados.

## Estructura del proyecto
- `app.py`: Panel visual en Streamlit con visor de entrenamientos y chat interactivo.
- `database.py`: Base de datos SQLite para almacenar sesiones y vueltas/series.
- `garmin_sync.py`: Procesador de archivos `.FIT` y conexión con Garmin.
- `consultas_ai.py`: Motor de consultas con IA para responder preguntas sobre tu historial.
- `requirements.txt`: Librerías necesarias.
- `Arrancar_SportTracks.bat`: Acceso directo para ejecutar la app.
