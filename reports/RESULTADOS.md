# Resultados de los objetivos 7 y 9

Este es el índice consolidado de resultados. Todo se generó en la rama
`feature/objetivos-7-9-dl-evaluacion`.

## 1. Clasificador de publicaciones críticas (objetivo 7)

### Métrica principal (validación cruzada fuera de muestra)

| Métrica | Modelo TextCNN | Baseline por reglas |
|---|---:|---:|
| Accuracy | **0.86** | 0.73 |
| Precision | **0.8462** | 0.5472 |
| Recall | 0.6875 | **0.9062** |
| F1 | **0.7586** | 0.6824 |
| ROC-AUC | **0.938** | 0.7767 |

**Matriz de confusión (OOF, umbral 0.5):**

```text
[[64, 4],
 [10, 22]]
```

**F1 por fold:**

| Fold | n test | F1 | Accuracy |
|---:|---:|---:|---:|
| 1 | 20 | 0.4444 | 0.75 |
| 2 | 20 | 0.6667 | 0.85 |
| 3 | 20 | 0.9091 | 0.95 |
| 4 | 20 | 0.80 | 0.85 |
| 5 | 20 | 0.8571 | 0.90 |

> **Importante:** el F1 in-sample del modelo final es 1.0 porque se entrenó con
> todo el piloto. La métrica honesta de generalización es **F1 0.7586** (OOF).

### Dónde verlo

| Archivo | Contenido |
|---|---|
| `reports/clasificador_reporte.md` | Reporte legible con tablas, matriz y folds |
| `reports/clasificador_metricas.json` | Métricas completas en JSON |
| `reports/evaluacion_clasificador.json` | Evaluación del modelo final + OOF |
| `docs/modelo_criticidad.md` | Ficha del modelo, arquitectura y limitaciones |

### Cómo regenerarlo

```bash
cd ingestion/X
python entrenar_clasificador.py
cd ../../tests
python evaluar_clasificador.py
```

### Vista rápida en terminal

```bash
cd reports
cat clasificador_reporte.md
python -m json.tool clasificador_metricas.json
```

---

## 2. Evaluación técnica y tests (objetivo 9)

| Runner | Resultado |
|---|---|
| `tests/run_golden.py` | **32/32** |
| `tests/run_conversacion.py` | **11/11** |
| `tests/run_interprete.py` | **14/14** |
| `tests/run_clasificador.py` | **7/7** |

### Dónde verlo

Los resultados se imprimen en la terminal al ejecutar cada runner. Los casos
están en:

```text
tests/golden_set.jsonl
tests/golden_conversacion.jsonl
tests/golden_interprete.jsonl
```

### Cómo regenerarlo

```bash
cd tests
python run_golden.py
python run_conversacion.py
python run_interprete.py
python run_clasificador.py
```

---

## 3. Usabilidad (objetivo 9)

### Validación funcional de las 5 tareas

| Tarea | Pregunta | Resultado | Tiempo |
|---|---|---|---:|
| T1 | promedio de ENDIREH para Jalisco en 2021 | OK | 5.28 s |
| T2 | compara la violencia de pareja entre Jalisco y Puebla en 2021 | OK | 11.88 s |
| T3 | publicaciones críticas de Jalisco | OK | 5.02 s |
| T4 | estoy sufriendo violencia, ¿dónde puedo pedir ayuda? | OK | 4.30 s |
| T5 | muéstrame los indicadores de Puebla | OK | 19.25 s |

**Resultado: 5/5.**

### Análisis de usabilidad con datos de ejemplo

| Métrica | Valor |
|---|---:|
| Participantes (ficticios) | 5 |
| Tasa de éxito | 92% |
| Tiempo promedio | 37 s |
| SUS promedio | 85 |

> Estos datos son de ejemplo y están marcados como tales en el reporte. **No
> sustituyen** las sesiones con personas reales.

### Dónde verlo

| Archivo | Contenido |
|---|---|
| `reports/validacion_funcional_tareas.md` | Validación funcional 5/5 |
| `reports/validacion_funcional_tareas.json` | Resultados en JSON |
| `reports/usabilidad_reporte.md` | Reporte de usabilidad (ejemplo) |
| `reports/usabilidad_metricas.json` | Métricas de usabilidad (ejemplo) |
| `tests/usabilidad/protocolo.md` | Protocolo para sesiones reales |
| `tests/usabilidad/evaluacion_heuristica.md` | Evaluación heurística |

### Cómo regenerarlo

```bash
cd tests/usabilidad
python validar_tareas_funcional.py
python analizar_usabilidad.py \
  --tareas resultados_tareas.csv \
  --sus resultados_sus.csv
```

---

## 4. Estado de la base de datos

Después de la migración y el ETL:

| Elemento | Cantidad |
|---|---:|
| Indicadores | 329 |
| Hechos | 17,648 |
| Publicaciones de X | 2,319 |
| Publicaciones críticas | 261 |

Consulta rápida:

```sql
SELECT es_critica, COUNT(*) FROM fact_publicacion GROUP BY es_critica;
```

---

## 5. Resumen para la tesis

- **Objetivo 7:** modelo TextCNN entrenado y validado; F1 0.7586, accuracy 0.86,
  ROC-AUC 0.938; integrado al ETL y al chat.
- **Objetivo 9:** evaluación técnica completa, tests 32/32, 11/11, 14/14 y 7/7,
  validación funcional 5/5 y kit de usabilidad listo. Las sesiones con personas
  reales quedan pendientes.

Documento de cierre detallado:

```text
docs/implementacion_objetivos_7_9.md
```
