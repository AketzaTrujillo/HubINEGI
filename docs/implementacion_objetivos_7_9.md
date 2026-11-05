# Implementación de los objetivos 7 y 9 — MHub

## 1. Resumen ejecutivo

Este documento describe los cambios realizados para cumplir los objetivos
específicos **7** y **9** del proyecto MHub:

- **Objetivo 7:** entrenar y validar un modelo de clasificación de aprendizaje
  profundo para identificar publicaciones críticas en fuentes complementarias
  (X), mitigando el sesgo de subregistro institucional.
- **Objetivo 9:** evaluar el desempeño del sistema con métricas de precisión
  técnica (F1-score, exactitud) y pruebas de usabilidad.

Los cambios se desarrollaron en la rama:

```text
feature/objetivos-7-9-dl-evaluacion
```

Y se publicaron en el PR:

```text
https://github.com/AketzaTrujillo/HubINEGI/pull/1
```

Commits principales:

```text
940e430 Objetivos 7 y 9: clasificador TextCNN y evaluacion F1/usabilidad
324c020 Documenta modelo de criticidad y aviso de respaldo (opcion B)
e9c4b11 Objetivo 9: validacion funcional de tareas y fallback del interprete
```

**Resultado general:** el objetivo 7 queda implementado de extremo a extremo
(modelo, entrenamiento, validación, base de datos, ETL, chat y reportes). El
objetivo 9 queda cubierto en su parte técnica (F1, exactitud, pruebas
deterministas y validación funcional) y con el kit de usabilidad listo; las
sesiones con personas reales quedan pendientes de ejecución por el equipo.

---

## 2. Punto de partida

Antes de estos cambios, el sistema ya integraba ENDIREH, SIESVIM, INMUJERES,
SESNSP y publicaciones de X. Sin embargo:

- La clasificación de publicaciones de X era **basada en reglas**
  (`ingestion/X/clasificacion.py`), no en Deep Learning.
- No existía una etiqueta de **publicación crítica**.
- No había un modelo entrenado ni un proceso de entrenamiento/validación.
- No existían métricas de F1 ni una evaluación formal del clasificador.
- El test `"que fuentes hay"` fallaba: se esperaba `CATALOGO` y el router
  devolvía `FAQ`.
- El intérprete LLM no funcionaba con el proveedor `opencode`.
- No había kit de usabilidad ni instrumentos para medir SUS.

---

## 3. Objetivo 7 — Clasificador de publicaciones críticas con Deep Learning

### 3.1 Definición operativa

Se definió **publicación crítica** como:

> Publicación que reporta un hecho concreto de violencia de género en México, o
> una alerta de riesgo inmediato, e incluye al menos dos de estos elementos:
> lugar, fecha, tipo de violencia, víctima/agresor o acción institucional.
> Quedan fuera opiniones, estadísticas generales sin caso, campañas, propaganda
> y spam.

Esta definición se documentó en `docs/modelo_criticidad.md` y guió el etiquetado
manual del piloto.

### 3.2 Arquitectura del modelo

Se implementó un **TextCNN** (red convolucional de texto) en PyTorch:

| Componente | Configuración |
|---|---|
| Entrada | Texto limpio tokenizado, máximo 128 tokens |
| Embedding | 100 dimensiones, entrenado desde cero |
| Convoluciones | Kernels de 3, 4 y 5; 100 filtros por kernel |
| Activación | ReLU + max pooling |
| Regularización | Dropout 0.3 |
| Salida | 1 logit → sigmoide (probabilidad de crítica) |
| Umbral de despliegue | 0.5 |
| Pérdida | BCEWithLogitsLoss con peso de clase |

Archivo principal:

```text
ingestion/X/clasificador_dl.py
```

El módulo incluye:

- Tokenización y normalización de texto.
- Construcción y carga de vocabulario.
- Definición y carga del modelo.
- Inferencia por lotes.
- Regla de respaldo si el modelo o PyTorch no están disponibles.
- Filtro de seguridad para descartar crimen organizado sin componente de género.

### 3.3 Datos de entrenamiento

Se usaron dos fuentes:

1. **Etiquetas débiles** para preentrenamiento:
   - `tipo_contenido` = `noticia` o `denuncia` → crítica.
   - Resto de categorías → no crítica.
   - Total: 2,319 publicaciones después de deduplicar.

2. **Piloto anotado manualmente** para ajuste fino y evaluación:
   - `data/processed/etiquetas_criticas_piloto.csv`
   - 100 publicaciones: 32 críticas y 68 no críticas.
   - Muestreo estratificado por tipo de contenido.
   - El piloto se excluye del preentrenamiento para evitar fuga de información.

### 3.4 Proceso de entrenamiento

El script:

```text
ingestion/X/entrenar_clasificador.py
```

Implementa:

1. Preentrenamiento con etiquetas débiles (5 épocas).
2. Ajuste fino supervisado con el piloto.
3. Validación cruzada estratificada de 5 folds.
4. Cálculo de métricas fuera de muestra (out-of-fold).
5. Reentrenamiento final con todo el piloto.
6. Guardado del modelo, vocabulario y configuración.

Comando:

```bash
pip install -r ingestion/requirements-ml.txt
cd ingestion/X
python entrenar_clasificador.py
```

Artefactos generados:

```text
models/clasificador_criticas/
├── modelo.pt      # pesos (3 MB)
├── vocab.json     # vocabulario
└── config.json    # umbral, max_len, arquitectura
```

**Decisión de versionado (opción B):** `models/` está en `.gitignore`; el modelo
no se versiona. Se regenera con el script. El ETL avisa en consola cuando el
modelo no está presente y usa la regla de respaldo.

### 3.5 Resultados del modelo

Validación cruzada fuera de muestra, umbral 0.5:

| Métrica | Modelo TextCNN | Baseline por reglas |
|---|---:|---:|
| Accuracy | **0.86** | 0.73 |
| Precision | **0.8462** | 0.5472 |
| Recall | 0.6875 | **0.9062** |
| F1 | **0.7586** | 0.6824 |
| ROC-AUC | **0.938** | 0.7767 |

Matriz de confusión del modelo (OOF, umbral 0.5):

```text
[[64, 4],
 [10, 22]]
```

F1 por fold:

| Fold | n test | F1 | Accuracy |
|---:|---:|---:|---:|
| 1 | 20 | 0.4444 | 0.75 |
| 2 | 20 | 0.6667 | 0.85 |
| 3 | 20 | 0.9091 | 0.95 |
| 4 | 20 | 0.80 | 0.85 |
| 5 | 20 | 0.8571 | 0.90 |

**Interpretación:** el modelo supera al baseline en F1, precision, accuracy y
ROC-AUC. El recall es menor que el baseline, lo que significa que es más
conservador: pierde algunos casos críticos, pero genera menos falsos positivos.
La varianza entre folds es alta porque el piloto es pequeño (100 casos).

> El F1 in-sample del modelo final es 1.0 porque se entrenó con todo el piloto.
> Esa cifra **no** debe presentarse como generalización. La métrica honesta es
> la validación cruzada: **F1 0.7586**.

### 3.6 Integración en el hub

#### Base de datos

Se agregaron tres columnas a `fact_publicacion`:

| Columna | Tipo | Descripción |
|---|---|---|
| `es_critica` | `ENUM('si','no')` | Resultado del clasificador |
| `prob_critica` | `DECIMAL(5,4)` | Probabilidad estimada |
| `modelo_criticidad` | `VARCHAR(50)` | Versión del modelo |

Migración idempotente:

```text
sql/08_criticidad_publicacion.sql
```

También se actualizó `sql/02_star_schema.sql` para instalaciones nuevas y
`mhub_meta.sem_columna` para que el LLM conozca los nuevos campos.

#### ETL

`ingestion/migracion/etl_star_schema.py` ahora:

- Lee el tipo de contenido de cada publicación.
- Clasifica las publicaciones con el modelo (o con la regla de respaldo).
- Llena `es_critica`, `prob_critica` y `modelo_criticidad`.
- Mantiene la deduplicación y el resto del esquema en estrella.

#### Chat y SQL

- `backend/sql_builder.py` permite filtrar por `solo_criticas` y devuelve
  `es_critica` y `prob_critica` en los resultados.
- `backend/query_spec.py` propaga `solo_criticas`.
- `backend/intent_router.py` reconoce “publicaciones críticas”.
- `backend/interprete.py` y `backend/agente.py` incluyen el campo en sus prompts.
- `backend/consulta_mhub.py` conserva `solo_criticas` en el tema de la
  conversación para seguimientos.

Ejemplo de consulta:

```text
publicaciones críticas de Jalisco
```

Respuesta esperada: lista de publicaciones de X clasificadas como críticas,
con su probabilidad y la aclaración de que no son estadística oficial.

### 3.7 Cómo se cumple el objetivo 7

| Requisito del objetivo | Implementación |
|---|---|
| Entrenar un modelo de clasificación | TextCNN entrenado con PyTorch |
| Aprendizaje profundo | Embedding + convoluciones + dropout + capa densa |
| Identificar publicaciones críticas | `es_critica` y `prob_critica` en `fact_publicacion` |
| Validar el modelo | Validación cruzada de 5 folds + piloto manual |
| Métricas | F1 0.7586, accuracy 0.86, ROC-AUC 0.938 |
| Mitigar el subregistro | Señal complementaria a las fuentes oficiales |
| Integración | ETL, base de datos, SQL, chat y reportes |

**Conclusión:** el objetivo 7 se cumple a nivel de prototipo funcional. El
modelo está entrenado, validado e integrado. La principal limitación es el
tamaño del piloto (100 casos), que afecta la estabilidad de las métricas.

---

## 4. Objetivo 9 — F1, exactitud, usabilidad y test fallido

### 4.1 Evaluación técnica del clasificador

Se creó:

```text
tests/evaluar_clasificador.py
```

El script calcula:

- Accuracy.
- Precision.
- Recall.
- F1.
- ROC-AUC.
- Matriz de confusión.

Uso:

```bash
cd tests
python evaluar_clasificador.py
python evaluar_clasificador.py --csv ../data/processed/mi_test.csv
```

Reportes:

```text
reports/clasificador_metricas.json
reports/clasificador_reporte.md
reports/evaluacion_clasificador.json
```

El reporte de entrenamiento contiene las métricas fuera de muestra. El
evaluador distingue explícitamente entre evaluación in-sample y externa.

### 4.2 Corrección de tests

Se corrigieron dos problemas:

1. **`"que fuentes hay"`** se clasificaba como `FAQ` y el golden esperaba
   `CATALOGO`. Se agregó una regla específica en `intent_router.py`:
   - `"qué fuentes hay"` → `CATALOGO`.
   - `"qué fuentes usa MHub"` → `FAQ`.
2. **Intérprete con OpenCode:** el intérprete solo se habilitaba con `local` o
   `groq`. Se agregó `opencode` y respaldos deterministas para:
   - `"cuántos..."` → operación `conteo`.
   - `"muéstrame/dame/lista..."` → operación `detalle`.

Resultados finales:

| Runner | Resultado |
|---|---|
| `run_golden.py` | **32/32** |
| `run_conversacion.py` | **11/11** |
| `run_interprete.py` | **14/14** |
| `run_clasificador.py` | **7/7** |

Se agregó el caso golden:

```json
{"pregunta": "publicaciones críticas de Jalisco", "tipo": "CONSULTA_DETALLE",
 "fuente": "X", "entidad": "Jalisco", "solo_criticas": true}
```

### 4.3 Pruebas de usabilidad

Se creó el kit:

```text
tests/usabilidad/
├── README.md
├── protocolo.md
├── tareas.csv
├── sus.csv
├── evaluacion_heuristica.md
├── analizar_usabilidad.py
├── validar_tareas_funcional.py
├── resultados_tareas_ejemplo.csv
└── resultados_sus_ejemplo.csv
```

Incluye:

- **Protocolo:** consentimiento, perfil de participantes, 5 tareas y métricas.
- **Tareas:** consultar un valor, comparar entidades, buscar publicaciones
  críticas, pedir rutas de atención e interpretar una gráfica.
- **SUS:** cuestionario de 10 reactivos.
- **Análisis:** éxito por tarea, tiempos, errores y SUS.
- **Evaluación heurística:** 10 heurísticas de Nielsen con hallazgos y
  recomendaciones.
- **Validación funcional:** verifica que los 5 flujos respondan de extremo a
  extremo.

Resultados de la validación funcional:

| Tarea | Pregunta | Resultado | Tiempo |
|---|---|---|---:|
| T1 | promedio de ENDIREH para Jalisco en 2021 | OK | 5.28 s |
| T2 | compara la violencia de pareja entre Jalisco y Puebla en 2021 | OK | 11.88 s |
| T3 | publicaciones críticas de Jalisco | OK | 5.02 s |
| T4 | estoy sufriendo violencia, ¿dónde puedo pedir ayuda? | OK | 4.30 s |
| T5 | muéstrame los indicadores de Puebla | OK | 19.25 s |

**Validación funcional: 5/5.**

El análisis de usabilidad con datos de ejemplo dio:

- Participantes: 5 (ficticios).
- Tasa de éxito: 92%.
- Tiempo promedio: 37 s.
- SUS promedio: 85.

> Esos datos son de ejemplo y está marcado así en el reporte. **No sustituyen**
> las sesiones con personas reales.

### 4.4 Cómo se cumple el objetivo 9

| Requisito del objetivo | Implementación |
|---|---|
| Métricas de precisión técnica | F1, accuracy, precision, recall, ROC-AUC |
| Evaluación del clasificador | Validación cruzada + evaluador reproducible |
| Pruebas de usabilidad | Protocolo, tareas, SUS, análisis y evaluación heurística |
| Garantizar eficacia | Golden sets 32/32, 11/11, 14/14; validación funcional 5/5 |

**Matiz importante:** la parte de métricas técnicas está completamente cubierta.
La parte de usabilidad está cubierta a nivel de **instrumento, evaluación
heurística y validación funcional**, pero las **sesiones con personas reales
siguen pendientes**. Para una defensa estricta, conviene ejecutarlas y
reemplazar los datos de ejemplo por resultados reales.

---

## 5. Cambios por archivo

### Archivos nuevos

| Archivo | Propósito |
|---|---|
| `ingestion/X/clasificador_dl.py` | Modelo TextCNN, inferencia y respaldo |
| `ingestion/X/entrenar_clasificador.py` | Entrenamiento y validación cruzada |
| `ingestion/requirements-ml.txt` | Dependencias de Deep Learning |
| `sql/08_criticidad_publicacion.sql` | Migración de columnas de criticidad |
| `data/processed/etiquetas_criticas_piloto.csv` | Piloto manual (100 casos) |
| `tests/evaluar_clasificador.py` | Evaluación F1/accuracy del modelo |
| `tests/run_clasificador.py` | Pruebas de humo del clasificador |
| `tests/usabilidad/*` | Kit de usabilidad |
| `reports/clasificador_reporte.md` | Reporte de métricas |
| `reports/clasificador_metricas.json` | Métricas en JSON |
| `reports/evaluacion_clasificador.json` | Evaluación del modelo final |
| `reports/usabilidad_reporte.md` | Reporte de usabilidad (ejemplo) |
| `reports/validacion_funcional_tareas.md` | Validación funcional 5/5 |
| `docs/modelo_criticidad.md` | Ficha del modelo |
| `docs/implementacion_objetivos_7_9.md` | Este documento |

### Archivos modificados

| Archivo | Cambio |
|---|---|
| `ingestion/migracion/etl_star_schema.py` | Clasifica criticidad y llena columnas nuevas |
| `ingestion/migracion/migrar_metadata_semantica.py` | Metadata de las columnas nuevas |
| `sql/02_star_schema.sql` | Columnas nuevas para instalaciones limpias |
| `backend/sql_builder.py` | Filtro `solo_criticas` y columnas de salida |
| `backend/query_spec.py` | Propaga `solo_criticas` |
| `backend/intent_router.py` | Detecta “publicaciones críticas” y corrige fuentes |
| `backend/interprete.py` | Campo `solo_criticas`, OpenCode y respaldos |
| `backend/agente.py` | `solo_criticas` en el prompt del agente |
| `backend/consulta_mhub.py` | Conserva `solo_criticas` en el tema |
| `tests/run_golden.py` | Valida `solo_criticas` |
| `tests/golden_set.jsonl` | Caso de publicaciones críticas |
| `README.md` | Documentación de los cambios |
| `.gitignore` | Ignora `models/` |

---

## 6. Cambios en el modelo de datos

```sql
ALTER TABLE fact_publicacion
  ADD COLUMN es_critica ENUM('si','no') DEFAULT 'no',
  ADD COLUMN prob_critica DECIMAL(5,4) NULL,
  ADD COLUMN modelo_criticidad VARCHAR(50) NULL,
  ADD INDEX idx_fp_critica (es_critica);
```

La migración `sql/08_criticidad_publicacion.sql` es idempotente: se puede
ejecutar varias veces sin error.

Estado de la base después del ETL:

| Elemento | Cantidad |
|---|---:|
| Indicadores | 329 |
| Hechos | 17,648 |
| Publicaciones de X | 2,319 |
| Publicaciones críticas | 261 |

---

## 7. Cómo reproducir todo

```bash
# 1. Dependencias
pip install -r backend/requirements.txt
pip install -r ingestion/requirements.txt
pip install -r ingestion/requirements-ml.txt

# 2. Migración de criticidad
cd sql
python run_sql.py 08_criticidad_publicacion.sql --database HUBDATOS

# 3. Entrenar el modelo
cd ../ingestion/X
python entrenar_clasificador.py

# 4. Reejecutar ETL y metadata
cd ../migracion
python etl_star_schema.py
python cargar_sesnsp.py
python poblar_tipo_violencia.py
python migrar_metadata_semantica.py

# 5. Tests
cd ../../tests
python run_golden.py
python run_conversacion.py
python run_interprete.py
python run_clasificador.py
python evaluar_clasificador.py

# 6. Usabilidad
cd usabilidad
python validar_tareas_funcional.py
python analizar_usabilidad.py \
  --tareas resultados_tareas.csv \
  --sus resultados_sus.csv
```

---

## 8. Limitaciones y recomendaciones

### Limitaciones

1. **Piloto pequeño:** 100 publicaciones. La varianza por fold es alta
   (F1 0.44–0.91).
2. **Falsos positivos:** el modelo puede confundir violencia general u
   organizada con violencia de género; se mitigó con un filtro de seguridad,
   pero no es perfecto.
3. **Dominio:** entrenado para español y para X; no se probó en otras redes.
4. **Veracidad:** el modelo mide criticidad, no veracidad. Una publicación
   crítica puede contener datos incorrectos.
5. **Usabilidad real pendiente:** el kit está listo, pero las sesiones con
   personas no se ejecutaron en este entorno.
6. **Modelo no versionado:** `models/` está en `.gitignore`. En un clon nuevo
   hay que entrenarlo o usar la regla de respaldo.

### Recomendaciones

1. Ampliar el piloto a 300–500 publicaciones, con negativos duros
   (crimen organizado, política, campañas).
2. Ejecutar las sesiones de usabilidad con 5–10 personas y reemplazar los datos
   de ejemplo.
3. Evaluar un modelo preentrenado en español (BETO) como alternativa.
4. Mantener el modelo como artefacto reproducible y no versionado.
5. Revisar el PR y fusionarlo a `jaz` o `main` según corresponda.

---

## 9. Conclusión

Los objetivos 7 y 9 quedaron cubiertos de la siguiente forma:

- **Objetivo 7:** implementado de extremo a extremo con un TextCNN entrenado,
  validado con 5 folds y F1 0.7586, integrado a la base de datos, al ETL y al
  chat. Supera al baseline por reglas (F1 0.6824).
- **Objetivo 9:** evaluación técnica completa (F1, accuracy, precision, recall,
  ROC-AUC), tests deterministas corregidos, validación funcional 5/5 y kit de
  usabilidad con protocolo, SUS y evaluación heurística. Las sesiones con
  personas reales quedan pendientes.

El sistema ahora cuenta con una señal de criticidad basada en Deep Learning que
complementa las fuentes oficiales y permite consultar publicaciones críticas de
X desde el lenguaje natural.
