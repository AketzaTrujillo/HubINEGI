# Comparación de recuperación: FULLTEXT, embeddings e híbrida

**Fecha:** 2026-10-27 14:47:20  
**Golden set:** 36 preguntas (30 dentro de alcance, 6 fuera de alcance)  
**Top-k:** 3  
**Versión oficial:** `FULLTEXT` (esta evaluación no cambia la versión oficial).

## 1. Resumen ejecutivo

Se evaluaron los tres modos sobre el mismo golden set de 36 preguntas. La tabla principal usa las 30 preguntas con respuesta en el corpus; las consultas fuera de alcance se reportan aparte porque no tienen fragmentos relevantes etiquetados.

| Modo | P@1 | P@3 | R@3 | MRR | nDCG@3 | DocHit@3 | Latencia p50 | Latencia p95 | Fallback |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `fulltext` | 0.133 | 0.089 | 0.150 | 0.189 | 0.134 | 0.600 | 8.2 ms | 14.6 ms | 0.0% |
| `embedding` | 0.033 | 0.044 | 0.083 | 0.078 | 0.065 | 0.533 | 16.7 ms | 18.3 ms | 0.0% |
| `hybrid` | 0.100 | 0.100 | 0.183 | 0.167 | 0.144 | 0.633 | 26.2 ms | 33.5 ms | 0.0% |

- **Mejor P@1:** `fulltext`.
- **Mejor P@3:** `hybrid`.
- **Mejor R@3:** `hybrid`.
- **Menor latencia p95:** `fulltext`.
- **Recomendación técnica:** `fulltext`. hybrid mejora P@3 12.5% y R@3 22.2% en términos relativos, pero no cumple todas las condiciones: P@1 cae 25.0%, p95 sube 19 ms, fallback 0.0%.

## 2. Configuración

| Parámetro | Valor |
|---|---|
| Modelo de embeddings | `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` |
| Dimensiones | 384 |
| Top-k | 3 |
| Repeticiones por pregunta | 3 |
| Python | 3.14.0 |
| torch | 2.14.1+cpu |
| sentence-transformers | 6.2.0 |
| numpy | 2.5.3 |
| Equipo | DESKTOP-8JMS32F |
| Sistema | Windows-11-10.0.26200-SP0 |
| CPU lógicas | 16 |
| Carga del índice | 0.58 s |
| Carga del modelo | 12.01 s |
| Primera consulta (embedding) | 18.2 ms |
| Arranque en frío (carga + primera consulta) | 12.03 s |

La carga del modelo incluye la importación de torch y sentence-transformers y la construcción del modelo. La primera consulta de la tabla ya tiene el modelo cargado; el arranque en frío completo es la suma de la carga y esa primera consulta. La latencia por consulta se midió después de tres consultas de calentamiento, con la mediana de tres repeticiones por pregunta.

## 3. Tabla general por modo

| Modo | P@1 | P@3 | R@3 | MRR | nDCG@3 | DocHit@3 | Latencia p50 | Latencia p95 | Fallback |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `fulltext` | 0.133 | 0.089 | 0.150 | 0.189 | 0.134 | 0.600 | 8.2 ms | 14.6 ms | 0.0% |
| `embedding` | 0.033 | 0.044 | 0.083 | 0.078 | 0.065 | 0.533 | 16.7 ms | 18.3 ms | 0.0% |
| `hybrid` | 0.100 | 0.100 | 0.183 | 0.167 | 0.144 | 0.633 | 26.2 ms | 33.5 ms | 0.0% |

> P@k y R@3 se calculan solo sobre las preguntas con respuesta en el corpus. DocHit@3 indica si al menos un documento relevante aparece en el top-3. La tasa de fallback es la proporción de consultas que tuvieron que usar FULLTEXT porque el modelo o el índice no estaban disponibles.

## 4. Tabla por categoría

| Categoría | Modo | n | P@1 | P@3 | R@3 | MRR | nDCG@3 |
|---|---|---:|---:|---:|---:|---:|---:|
| Término exacto | `fulltext` | 8 | 0.250 | 0.167 | 0.250 | 0.375 | 0.250 |
| Término exacto | `embedding` | 8 | 0.125 | 0.083 | 0.125 | 0.188 | 0.125 |
| Término exacto | `hybrid` | 8 | 0.250 | 0.167 | 0.250 | 0.354 | 0.240 |
| Paráfrasis | `fulltext` | 8 | 0.125 | 0.042 | 0.062 | 0.125 | 0.077 |
| Paráfrasis | `embedding` | 8 | 0.000 | 0.042 | 0.062 | 0.042 | 0.038 |
| Paráfrasis | `hybrid` | 8 | 0.125 | 0.125 | 0.250 | 0.167 | 0.188 |
| Sigla | `fulltext` | 6 | 0.167 | 0.111 | 0.167 | 0.222 | 0.153 |
| Sigla | `embedding` | 6 | 0.000 | 0.056 | 0.167 | 0.083 | 0.105 |
| Sigla | `hybrid` | 6 | 0.000 | 0.056 | 0.083 | 0.083 | 0.064 |
| Procedimiento | `fulltext` | 8 | 0.000 | 0.042 | 0.125 | 0.042 | 0.062 |
| Procedimiento | `embedding` | 8 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| Procedimiento | `hybrid` | 8 | 0.000 | 0.042 | 0.125 | 0.042 | 0.062 |

### Consultas fuera de alcance

| Modo | Consultas | Devolvieron resultados | Tasa de falsos positivos |
|---|---:|---:|---:|
| `fulltext` | 6 | 6 | 100.0% |
| `embedding` | 6 | 6 | 100.0% |
| `hybrid` | 6 | 6 | 100.0% |

El corpus no contiene respuestas a estas preguntas. Ningún modo implementa abstención por umbral, así que todos devuelven fragmentos; la columna mide cuántas veces ocurrió. Es una limitación del experimento, no una métrica de ranking.

## 5. Incrementos relativos

| Comparación | P@1 | P@3 | R@3 | MRR | nDCG@3 | Δ p95 |
|---|---:|---:|---:|---:|---:|---:|
| hybrid vs fulltext | -25.0% | 12.5% | 22.2% | -11.8% | 6.8% | +18.9 ms |
| embedding vs fulltext | -75.0% | -50.0% | -44.4% | -58.8% | -52.0% | +3.7 ms |

## 6. Dónde gana cada modo

- **Gana FULLTEXT** (4): ¿Qué es el Modelo de Atención para mujeres que viven violencias?; ¿Qué es el Modelo de Prevención de Violencias contra las Mujeres?; ¿Qué es el Directorio Nacional de los Centros de Justicia para las Mujeres?; ¿Qué significa AVGM?
- **Gana embedding** (1): ¿Qué significa CJM?
- **Gana hybrid** (4): ¿Qué son los Centros de Justicia para las Mujeres?; ¿Qué es el Modelo Integral para la Sanción de las Violencias contra las Mujeres?; Estoy en peligro ahora, ¿a quién puedo llamar?; Mi vecino golpea a su esposa, ¿qué puedo hacer?

## 7. Ejemplos de aciertos y fallos


### `fulltext`

**Aciertos en el primer lugar**

- `T01` ¿Qué es el Banco Nacional de Datos e Información sobre Casos de Violencia contra las Mujeres? → Lineamientos BANAVIM p. 2
- `T04` ¿Qué es el Modelo de Atención para mujeres que viven violencias? → Modelo de Atención p. 11

**Fallos en el primer lugar**

- `T02` ¿Qué son los Centros de Justicia para las Mujeres? → recuperó Violencia de Género en Zonas Indígenas p. 75; esperado: Modelo CJM Secretariado Ejecutivo p. 9, Modelo CJM Secretariado Ejecutivo p. 13
- `T03` ¿Qué es la violencia familiar? → recuperó Protocolo de Atención de los CJM p. 303; esperado: No Estás Sola (CONAVIM) p. 2, Ley General de Acceso de las Mujeres a una Vida Libre de Violencia p. 6

### `embedding`

**Aciertos en el primer lugar**

- `T03` ¿Qué es la violencia familiar? → No Estás Sola (CONAVIM) p. 2

**Fallos en el primer lugar**

- `T01` ¿Qué es el Banco Nacional de Datos e Información sobre Casos de Violencia contra las Mujeres? → recuperó Lineamientos BANAVIM p. 1; esperado: Lineamientos BANAVIM p. 2, Modelo CJM Secretariado Ejecutivo p. 95
- `T02` ¿Qué son los Centros de Justicia para las Mujeres? → recuperó Violencia de Género en Zonas Indígenas p. 75; esperado: Modelo CJM Secretariado Ejecutivo p. 9, Modelo CJM Secretariado Ejecutivo p. 13

### `hybrid`

**Aciertos en el primer lugar**

- `T01` ¿Qué es el Banco Nacional de Datos e Información sobre Casos de Violencia contra las Mujeres? → Lineamientos BANAVIM p. 2
- `T06` ¿Qué es el Modelo Integral para la Sanción de las Violencias contra las Mujeres? → Modelo de Sanción p. 13

**Fallos en el primer lugar**

- `T02` ¿Qué son los Centros de Justicia para las Mujeres? → recuperó Violencia de Género en Zonas Indígenas p. 75; esperado: Modelo CJM Secretariado Ejecutivo p. 9, Modelo CJM Secretariado Ejecutivo p. 13
- `T03` ¿Qué es la violencia familiar? → recuperó Protocolo de Atención de los CJM p. 310; esperado: No Estás Sola (CONAVIM) p. 2, Ley General de Acceso de las Mujeres a una Vida Libre de Violencia p. 6

## 8. Interpretación

### ¿Dónde gana FULLTEXT?

En término exacto, FULLTEXT obtiene P@1 0.250 frente a 0.125 de embedding y 0.250 de hybrid. En procedimiento, las P@1 son FULLTEXT 0.000, embedding 0.000 y hybrid 0.000; ningún modo acierta en el primer lugar, así que no hay ganador claro.

### ¿Dónde ganan los embeddings?

En este conjunto embedding no gana en paráfrasis: obtiene P@1 0.000, P@3 0.042 y R@3 0.062, frente a FULLTEXT P@1 0.125, P@3 0.042 y R@3 0.062. La ventaja esperada de los embeddings no se materializó con este modelo y este golden set.

### ¿La híbrida mejora sin destruir la precisión exacta?

En el conjunto general, hybrid tiene P@3 0.100 y R@3 0.183; FULLTEXT tiene P@3 0.089 y R@3 0.150. En término exacto, la P@1 de hybrid es 0.250 y la de FULLTEXT es 0.250. En acierto de documento (DocHit@3), hybrid obtiene 0.633 y FULLTEXT 0.600. La ganancia de ranking no compensa la caída de P@1 de 25.0%.

## 9. Recomendación

**Recomendación técnica:** `fulltext`.

- hybrid mejora P@3 12.5% y R@3 22.2% en términos relativos, pero no cumple todas las condiciones: P@1 cae 25.0%, p95 sube 19 ms, fallback 0.0%.
- embedding no supera a fulltext en P@3 y R@3.
- embedding reduce P@1 en término exacto de 0.250 a 0.125.
- Se recomienda mantener FULLTEXT como modo oficial.

La decisión final corresponde a la usuaria. Mientras no se revise este reporte, la versión oficial sigue siendo `FULLTEXT` y las ramas `experimento/recuperacion-hibrida` no se fusionan con `jaz` ni con `main`.

## 10. Pruebas de regresión

| Prueba | Resultado | Total | Entorno |
|---|---:|---:|---|
| `run_golden.py` | 31 | 31 | Python 3.14.0, MySQL 8.0.36, sin LLM |
| `run_conversacion.py` | 11 | 11 | Python 3.14.0, sin LLM |
| `run_interprete.py` | 14 | 14 | Ollama local, qwen2.5:7b, MHUB_LLM_PROVIDER=local |

## 11. Limitaciones

- El golden set tiene 36 preguntas y fue definido antes de ejecutar la línea base.
- Las etiquetas de relevancia son páginas específicas; una página que también responde puede no estar etiquetada. Esto afecta los valores absolutos, no la comparación entre modos, porque los tres usan las mismas etiquetas.
- En los ejemplos, un resultado de otra página del mismo tema puede aparecer como fallo aunque sea útil para la persona usuaria.
- Una sola máquina, un solo modelo y una sola configuración de top-k.
- No hay umbral de abstención para consultas fuera de alcance.
- La latencia es de CPU y puede variar con la carga del equipo.
- El corpus es pequeño (3,170 fragmentos); los resultados no se generalizan a corpus mucho mayores sin repetir la medición.

## 12. Reproducibilidad

```powershell
cd HubINEGI/ingestion/embeddings
python generar_embeddings.py
python verificar_embeddings.py
cd ../../tests
python run_corpus.py --modo all --topk 3
```

El detalle por pregunta, incluidos los fragmentos recuperados y sus scores, está en `reports/recuperacion_resultados.json`.
