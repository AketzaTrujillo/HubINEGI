# Kit de pruebas de usabilidad — MHub (objetivo 9)

Este kit permite ejecutar y analizar pruebas de usabilidad del Asistente MHub y
del Panel sin modificar el código de la aplicación.

## Archivos

| Archivo | Para qué sirve |
|---|---|
| `protocolo.md` | Objetivo, perfil de participantes, tareas, métricas y consentimiento. |
| `tareas.csv` | Lista de tareas y criterios de éxito. |
| `sus.csv` | Cuestionario System Usability Scale (10 reactivos). |
| `resultados_tareas_ejemplo.csv` | Ejemplo de captura de resultados por tarea. |
| `resultados_sus_ejemplo.csv` | Ejemplo de respuestas SUS. |
| `analizar_usabilidad.py` | Calcula éxito, tiempos y SUS; genera reporte. |

## Cómo ejecutar una sesión

1. Arranca backend y frontend (ver README principal).
2. Lee el consentimiento del `protocolo.md` y pide aceptación verbal.
3. Pide a la persona que realice las tareas de `tareas.csv` sin ayuda.
4. Registra en `resultados_tareas.csv`:
   - `usuario`, `tarea`, `exito` (1/0), `tiempo_segundos`, `errores`, `comentarios`.
5. Al terminar, aplica `sus.csv` y registra en `resultados_sus.csv`.
6. Ejecuta:

```bash
python analizar_usabilidad.py \
  --tareas resultados_tareas.csv \
  --sus resultados_sus.csv
```

El reporte se guarda en `reports/usabilidad_reporte.md`.

## Ejemplo

Para ver el formato y validar el script sin participantes:

```bash
python analizar_usabilidad.py \
  --tareas resultados_tareas_ejemplo.csv \
  --sus resultados_sus_ejemplo.csv
```

> Los archivos de ejemplo contienen datos ficticios; no deben presentarse como
> resultados reales.
