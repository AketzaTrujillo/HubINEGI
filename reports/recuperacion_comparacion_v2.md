# Recuperación v2: mejoras sobre FULLTEXT, BM25, embeddings e híbrida

**Fecha:** 2026-10-27 17:18:06  
**Golden set:** 36 preguntas (30 dentro de alcance, 6 fuera de alcance)  
**Top-k:** 3  
**Versión oficial:** `FULLTEXT` (esta evaluación no cambia la versión oficial).

## 1. Resumen ejecutivo

La v2 reemplaza la página completa por chunks de ~350 tokens, usa `multilingual-e5-small` (512 tokens), BM25 con análisis español, expansión de siglas/sinónimos y fusión RRF ponderada. La tabla siguiente compara la v2 contra la línea base v1.

| Modo | P@1 | P@3 | R@3 | MRR | nDCG@3 | DocP@1 | DocHit@3 | p50 | p95 | Fallback |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `fulltext` | 0.167 | 0.078 | 0.117 | 0.194 | 0.125 | 0.467 | 0.600 | 7.7 ms | 13.7 ms | 0.0% |
| `bm25` | 0.233 | 0.178 | 0.250 | 0.306 | 0.255 | 0.567 | 0.833 | 16.0 ms | 53.5 ms | 0.0% |
| `embedding` | 0.200 | 0.111 | 0.167 | 0.239 | 0.173 | 0.567 | 0.767 | 22.4 ms | 25.6 ms | 0.0% |
| `hybrid` | 0.267 | 0.178 | 0.267 | 0.344 | 0.261 | 0.600 | 0.900 | 42.0 ms | 83.4 ms | 0.0% |
| `hybrid_rerank` | 0.200 | 0.156 | 0.250 | 0.272 | 0.226 | 0.433 | 0.800 | 503.8 ms | 559.7 ms | 0.0% |

- **Mejor P@1:** `hybrid`.
- **Mejor P@3:** `hybrid`.
- **Mejor R@3:** `hybrid`.
- **Menor latencia p95:** `fulltext`.
- **Recomendación técnica:** `hybrid`. `hybrid` v2 mejora P@3 100.0% y R@3 77.8% relativos; P@1 cambia +100.0% y el p95 sube +69 ms.

`hybrid` y `bm25` empatan en P@3 (0.167) y R@3 (0.250); `hybrid` gana en P@1, MRR, nDCG@3 y DocHit@3. El reranker no mejora a `hybrid` y multiplica la latencia, así que se deja como modo opcional.

**Embeddings v2:** 2979 de 2979 chunks verificados, 384 dimensiones, 0 dimensiones incorrectas y 0 hashes desactualizados.

### Comparación contra la v1

| Comparación | P@1 | P@3 | R@3 | MRR | nDCG@3 | Δ p95 |
|---|---:|---:|---:|---:|---:|---:|
| `bm25` v2 vs fulltext v1 | 75.0% | 100.0% | 66.7% | 61.8% | 89.6% | +39.5 ms |
| `embedding` v2 vs fulltext v1 | 50.0% | 25.0% | 11.1% | 26.5% | 28.4% | +11.6 ms |
| `hybrid` v2 vs fulltext v1 | 100.0% | 100.0% | 77.8% | 82.4% | 94.4% | +69.4 ms |
| `hybrid_rerank` v2 vs fulltext v1 | 50.0% | 75.0% | 66.7% | 44.1% | 68.0% | +545.8 ms |

## 2. Configuración

| Parámetro | Valor |
|---|---|
| Modelo de embeddings | `intfloat/multilingual-e5-small` |
| Dimensiones | 384 |
| Chunk tokens / overlap | 350 / 50 |
| Chunks v2 | 2979 |
| RRF k | 60 |
| Peso léxico / semántico | 2.0 / 1.0 |
| Reranker | `cross-encoder/mmarco-mMiniLMv2-L12-H384-v1` |
| Top-k | 3 |
| Repeticiones | 3 |
| Python | 3.14.0 |
| torch | 2.14.1+cpu |
| sentence-transformers | 6.2.0 |
| Equipo | DESKTOP-8JMS32F |
| Sistema | Windows-11-10.0.26200-SP0 |
| CPU lógicas | 16 |
| Carga BM25 | 9.50 s |
| Carga índice | 0.22 s |
| Carga modelo | 14.79 s |
| Carga reranker | 2.78 s |

La carga del modelo incluye la importación de torch y sentence-transformers y la construcción del modelo; en caliente, la carga es ~3.3 s. La carga de BM25 incluye tokenización, stemming y construcción del índice. La latencia por consulta se midió después de tres consultas de calentamiento, con la mediana de tres repeticiones.

## 3. Resultados v1 (línea base)

| Modo | P@1 | P@3 | R@3 | MRR | nDCG@3 | DocHit@3 | p50 | p95 | Fallback |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `fulltext` v1 | 0.133 | 0.089 | 0.150 | 0.189 | 0.134 | 0.600 | 7.3 ms | 14.0 ms | 0.0% |
| `embedding` v1 | 0.033 | 0.044 | 0.083 | 0.078 | 0.065 | 0.533 | 16.6 ms | 21.3 ms | 0.0% |
| `hybrid` v1 | 0.100 | 0.100 | 0.183 | 0.167 | 0.144 | 0.633 | 25.8 ms | 36.5 ms | 0.0% |

La v1 es la implementación del plan original: páginas completas, MiniLM de 128 tokens, `MATCH ... AGAINST` y RRF sin pesos.

## 4. Resultados v2

| Modo | P@1 | P@3 | R@3 | MRR | nDCG@3 | DocP@1 | DocHit@3 | p50 | p95 | Fallback |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `fulltext` | 0.167 | 0.078 | 0.117 | 0.194 | 0.125 | 0.467 | 0.600 | 7.7 ms | 13.7 ms | 0.0% |
| `bm25` | 0.233 | 0.178 | 0.250 | 0.306 | 0.255 | 0.567 | 0.833 | 16.0 ms | 53.5 ms | 0.0% |
| `embedding` | 0.200 | 0.111 | 0.167 | 0.239 | 0.173 | 0.567 | 0.767 | 22.4 ms | 25.6 ms | 0.0% |
| `hybrid` | 0.267 | 0.178 | 0.267 | 0.344 | 0.261 | 0.600 | 0.900 | 42.0 ms | 83.4 ms | 0.0% |
| `hybrid_rerank` | 0.200 | 0.156 | 0.250 | 0.272 | 0.226 | 0.433 | 0.800 | 503.8 ms | 559.7 ms | 0.0% |

> P@k y R@3 usan las mismas etiquetas de página que la v1. DocP@1 mide si el documento del primer resultado es relevante; DocHit@3, si aparece al menos un documento relevante en el top-3. Las consultas fuera de alcance se reportan aparte.

### Intervalos de confianza (bootstrap, 2,000 remuestreos)

| Modo | P@1 (IC95) | P@3 (IC95) | R@3 (IC95) | MRR (IC95) | nDCG@3 (IC95) |
|---|---|---|---|---|---|
| `fulltext` | 0.167 [0.033, 0.300] | 0.078 [0.033, 0.133] | 0.117 [0.050, 0.200] | 0.194 [0.078, 0.333] | 0.125 [0.051, 0.212] |
| `bm25` | 0.233 [0.100, 0.400] | 0.178 [0.089, 0.267] | 0.250 [0.133, 0.367] | 0.306 [0.156, 0.450] | 0.255 [0.133, 0.380] |
| `embedding` | 0.200 [0.067, 0.333] | 0.111 [0.056, 0.178] | 0.167 [0.083, 0.267] | 0.239 [0.106, 0.378] | 0.173 [0.078, 0.271] |
| `hybrid` | 0.267 [0.100, 0.433] | 0.178 [0.100, 0.256] | 0.267 [0.150, 0.383] | 0.344 [0.194, 0.500] | 0.261 [0.141, 0.387] |
| `hybrid_rerank` | 0.200 [0.067, 0.333] | 0.156 [0.078, 0.233] | 0.250 [0.133, 0.383] | 0.272 [0.133, 0.411] | 0.226 [0.112, 0.347] |

## 5. Ablación: qué aporta cada cambio

| Modo | P@1 | P@3 | R@3 | MRR | nDCG@3 | DocP@1 | DocHit@3 | p50 | p95 | Fallback |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `fulltext` | 0.167 | 0.078 | 0.117 | 0.194 | 0.125 | 0.467 | 0.600 | 7.7 ms | 13.7 ms | 0.0% |
| `bm25` | 0.233 | 0.178 | 0.250 | 0.306 | 0.255 | 0.567 | 0.833 | 16.0 ms | 53.5 ms | 0.0% |
| `embedding` | 0.200 | 0.111 | 0.167 | 0.239 | 0.173 | 0.567 | 0.767 | 22.4 ms | 25.6 ms | 0.0% |
| `hybrid` | 0.267 | 0.178 | 0.267 | 0.344 | 0.261 | 0.600 | 0.900 | 42.0 ms | 83.4 ms | 0.0% |
| `hybrid_rerank` | 0.200 | 0.156 | 0.250 | 0.272 | 0.226 | 0.433 | 0.800 | 503.8 ms | 559.7 ms | 0.0% |

`fulltext` usa la tabla v2 para aislar el efecto del chunking. `bm25` añade análisis español y expansión. `embedding` usa e5-small sobre chunks. `hybrid` combina BM25 y embeddings con RRF ponderado. `hybrid_rerank` añade el cross-encoder sobre el top-10.

## 6. Por categoría

| Categoría | Modo | n | P@1 | P@3 | R@3 | MRR | nDCG@3 | DocP@1 |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| Término exacto | `fulltext` | 8 | 0.375 | 0.208 | 0.312 | 0.479 | 0.317 | 0.625 |
| Término exacto | `bm25` | 8 | 0.625 | 0.333 | 0.438 | 0.667 | 0.518 | 0.750 |
| Término exacto | `embedding` | 8 | 0.375 | 0.125 | 0.188 | 0.375 | 0.230 | 0.625 |
| Término exacto | `hybrid` | 8 | 0.625 | 0.375 | 0.562 | 0.750 | 0.577 | 0.875 |
| Término exacto | `hybrid_rerank` | 8 | 0.375 | 0.208 | 0.312 | 0.417 | 0.317 | 0.750 |
| Paráfrasis | `fulltext` | 8 | 0.125 | 0.042 | 0.062 | 0.125 | 0.077 | 0.375 |
| Paráfrasis | `bm25` | 8 | 0.000 | 0.042 | 0.062 | 0.062 | 0.048 | 0.250 |
| Paráfrasis | `embedding` | 8 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.375 |
| Paráfrasis | `hybrid` | 8 | 0.000 | 0.042 | 0.062 | 0.062 | 0.048 | 0.250 |
| Paráfrasis | `hybrid_rerank` | 8 | 0.125 | 0.042 | 0.062 | 0.125 | 0.077 | 0.250 |
| Sigla | `fulltext` | 6 | 0.167 | 0.056 | 0.083 | 0.167 | 0.102 | 0.333 |
| Sigla | `bm25` | 6 | 0.333 | 0.389 | 0.583 | 0.556 | 0.519 | 0.500 |
| Sigla | `embedding` | 6 | 0.333 | 0.222 | 0.250 | 0.389 | 0.307 | 0.500 |
| Sigla | `hybrid` | 6 | 0.167 | 0.222 | 0.333 | 0.306 | 0.269 | 0.500 |
| Sigla | `hybrid_rerank` | 6 | 0.333 | 0.278 | 0.417 | 0.389 | 0.371 | 0.333 |
| Procedimiento | `fulltext` | 8 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.500 |
| Procedimiento | `bm25` | 8 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.750 |
| Procedimiento | `embedding` | 8 | 0.125 | 0.125 | 0.250 | 0.229 | 0.188 | 0.750 |
| Procedimiento | `hybrid` | 8 | 0.250 | 0.083 | 0.125 | 0.250 | 0.153 | 0.750 |
| Procedimiento | `hybrid_rerank` | 8 | 0.000 | 0.125 | 0.250 | 0.188 | 0.176 | 0.375 |

### Consultas fuera de alcance

| Modo | Consultas | Devolvieron resultados | Tasa |
|---|---:|---:|---:|
| `fulltext` | 6 | 6 | 100.0% |
| `bm25` | 6 | 5 | 83.3% |
| `embedding` | 6 | 6 | 100.0% |
| `hybrid` | 6 | 6 | 100.0% |
| `hybrid_rerank` | 6 | 6 | 100.0% |

## 7. Dónde gana cada versión

- **Gana v2 hybrid** (8): ¿Qué son los Centros de Justicia para las Mujeres?; ¿Qué es la violencia familiar?; ¿Qué es el Modelo de Atención para mujeres que viven violencias?; ¿Qué es el Modelo Integral para la Sanción de las Violencias contra las Mujeres?; ¿Qué significa CONAVIM?…
- **Gana fulltext v1** (1): ¿Cómo se da seguimiento a una orden de protección?

## 8. Ejemplos de aciertos y fallos


### `bm25`

**Aciertos en el primer lugar**

- `T01` ¿Qué es el Banco Nacional de Datos e Información sobre Casos de Violencia contra las Mujeres? → Lineamientos BANAVIM p. 2
- `T02` ¿Qué son los Centros de Justicia para las Mujeres? → Modelo CJM Secretariado Ejecutivo p. 9

**Fallos en el primer lugar**

- `T04` ¿Qué es el Modelo de Atención para mujeres que viven violencias? → recuperó Modelo de Atención p. 39; esperado: Modelo de Atención p. 10, Modelo de Atención p. 11
- `T06` ¿Qué es el Modelo Integral para la Sanción de las Violencias contra las Mujeres? → recuperó Modelo de Atención p. 10; esperado: Modelo de Sanción p. 13, Modelo de Sanción p. 10

### `embedding`

**Aciertos en el primer lugar**

- `T03` ¿Qué es la violencia familiar? → No Estás Sola (CONAVIM) p. 2
- `T04` ¿Qué es el Modelo de Atención para mujeres que viven violencias? → Modelo de Atención p. 10

**Fallos en el primer lugar**

- `T01` ¿Qué es el Banco Nacional de Datos e Información sobre Casos de Violencia contra las Mujeres? → recuperó Lineamientos BANAVIM p. 3; esperado: Lineamientos BANAVIM p. 2, Modelo CJM Secretariado Ejecutivo p. 95
- `T02` ¿Qué son los Centros de Justicia para las Mujeres? → recuperó Protocolo Estandarizado CJM p. 31; esperado: Modelo CJM Secretariado Ejecutivo p. 9, Modelo CJM Secretariado Ejecutivo p. 13

### `hybrid`

**Aciertos en el primer lugar**

- `T03` ¿Qué es la violencia familiar? → No Estás Sola (CONAVIM) p. 2
- `T04` ¿Qué es el Modelo de Atención para mujeres que viven violencias? → Modelo de Atención p. 10

**Fallos en el primer lugar**

- `T01` ¿Qué es el Banco Nacional de Datos e Información sobre Casos de Violencia contra las Mujeres? → recuperó Lineamientos BANAVIM p. 3; esperado: Lineamientos BANAVIM p. 2, Modelo CJM Secretariado Ejecutivo p. 95
- `T02` ¿Qué son los Centros de Justicia para las Mujeres? → recuperó Protocolo de Atención de los CJM p. 33; esperado: Modelo CJM Secretariado Ejecutivo p. 9, Modelo CJM Secretariado Ejecutivo p. 13

### `hybrid_rerank`

**Aciertos en el primer lugar**

- `T02` ¿Qué son los Centros de Justicia para las Mujeres? → Modelo CJM Secretariado Ejecutivo p. 9
- `T03` ¿Qué es la violencia familiar? → No Estás Sola (CONAVIM) p. 2

**Fallos en el primer lugar**

- `T01` ¿Qué es el Banco Nacional de Datos e Información sobre Casos de Violencia contra las Mujeres? → recuperó Modelo de Sanción p. 17; esperado: Lineamientos BANAVIM p. 2, Modelo CJM Secretariado Ejecutivo p. 95
- `T04` ¿Qué es el Modelo de Atención para mujeres que viven violencias? → recuperó Modelo de Atención p. 31; esperado: Modelo de Atención p. 10, Modelo de Atención p. 11

## 9. Cambios técnicos de la v2

- **Chunking:** páginas reconstruidas y cortadas en ~350 tokens con 50 de solapamiento; se eliminan portadas, créditos, índices y líneas repetidas.
- **Embeddings:** `intfloat/multilingual-e5-small`, 384 dimensiones, 512 tokens, prefijos `query:`/`passage:` y vectores BLOB float32.
- **BM25:** índice invertido en memoria con stopwords, stemming Snowball y normalización de acentos.
- **Expansión:** siglas (CJM, BANAVIM, SESNSP, CONAVIM, AVGM, PAIMEF, LGAMVLV, etc.), sinónimos y frases de intención.
- **Fusión:** RRF con peso léxico 2.0 y semántico 1.0.
- **Reranker:** cross-encoder `mmarco-mMiniLMv2-L12-H384-v1` sobre el top-10, con `max_length=256`; es opcional por su latencia.
- **Deduplicación:** se devuelve como máximo un chunk por página.

## 10. Recomendación

**Recomendación técnica:** `hybrid`.

- `hybrid` v2 mejora P@3 100.0% y R@3 77.8% relativos; P@1 cambia +100.0% y el p95 sube +69 ms.
- **Reranker:** `hybrid_rerank` no mejora a `hybrid` (P@1 0.167 vs 0.267) y eleva el p95 a ~0.6 s; se descarta para producción y queda como modo opcional de análisis.

La decisión final corresponde a la usuaria. La versión oficial sigue siendo `FULLTEXT`; la v2 vive en la misma rama experimental y se activa con `MHUB_CORPUS_VERSION=v2`.

## 11. Pruebas de regresión

| Prueba | Resultado | Total | Entorno |
|---|---:|---:|---|
| `run_golden.py (v2)` | 31 | 31 | MHUB_CORPUS_VERSION=v2, MHUB_V2_MODE=hybrid, sin LLM |
| `run_conversacion.py (v2)` | 11 | 11 | MHUB_CORPUS_VERSION=v2, MHUB_V2_MODE=hybrid, sin LLM |
| `run_interprete.py (v2)` | 14 | 14 | Ollama local, qwen2.5:7b, MHUB_CORPUS_VERSION=v2 |

## 12. Limitaciones

- El golden set sigue teniendo 36 preguntas; los intervalos de confianza son amplios y deben leerse con cautela.
- Las etiquetas son páginas específicas; una página correcta no etiquetada cuenta como fallo. Los ejemplos deben revisarse a mano.
- Una sola máquina, un solo modelo de embeddings y un solo reranker.
- El reranker agrega ~0.5 s por consulta en CPU; no es apto para el modo oficial sin optimización (ONNX, cuantización o GPU).
- No hay umbral de abstención calibrado para consultas fuera de alcance.
- El corpus es pequeño; los resultados no se generalizan sin repetir la medición.

## 13. Reproducibilidad

```powershell
cd HubINEGI/sql
python run_sql.py 09_corpus_v2.sql --database HUBDATOS
cd ../ingestion/v2
python rechunk_corpus.py
python generar_embeddings_v2.py
python verificar_v2.py
cd ../../tests
python run_corpus_v2.py --topk 3
```

Detalle por pregunta en `reports/recuperacion_resultados_v2.json`.
