# Ficha del modelo de criticidad — `textcnn-v1`

## 1. Propósito

Clasificar publicaciones de X como **críticas** o **no críticas** en el contexto
de violencia de género en México. La salida se usa como una señal adicional en
el hub; no sustituye la revisión humana ni la estadística oficial.

**Definición operativa de publicación crítica:** publicación que reporta un
hecho concreto de violencia de género en México, o una alerta de riesgo
inmediato, e incluye al menos dos de estos elementos: lugar, fecha, tipo de
violencia, víctima/agresor o acción institucional. Quedan fuera opiniones,
estadísticas generales sin caso, campañas, propaganda y spam.

## 2. Arquitectura

- **Modelo:** TextCNN (red convolucional de texto) en PyTorch.
- **Entrada:** texto limpio de la publicación, tokenizado y truncado a 128 tokens.
- **Embedding:** 100 dimensiones, entrenado desde cero.
- **Convoluciones:** kernels de 3, 4 y 5, con 100 filtros cada uno.
- **Regularización:** dropout 0.3 y pesos de clase para el desbalance.
- **Salida:** probabilidad de crítica (sigmoide).
- **Umbral de despliegue:** 0.5.

## 3. Datos

| Conjunto | Uso | Tamaño |
|---|---|---:|
| `dataset_twitter_limpio.csv` | Preentrenamiento con etiquetas débiles (`tipo_contenido` = noticia/denuncia) | 2,319 publicaciones |
| `etiquetas_criticas_piloto.csv` | Ajuste fino y evaluación externa | 100 publicaciones (32 críticas) |

El piloto se excluye del preentrenamiento para evitar fuga de información.

## 4. Entrenamiento

```bash
pip install -r ingestion/requirements-ml.txt
cd ingestion/X
python entrenar_clasificador.py
```

- Preentrenamiento débil: 5 épocas.
- Ajuste fino: 12 épocas por fold.
- Validación cruzada estratificada: 5 folds.
- Semilla: 42.
- Modelo final: reentrenado con todo el piloto.

## 5. Resultados (validación cruzada fuera de muestra)

| Métrica | Valor |
|---|---:|
| Accuracy | 0.86 |
| Precision | 0.8462 |
| Recall | 0.6875 |
| F1 | **0.7586** |
| ROC-AUC | 0.938 |

Baseline por reglas: F1 0.6824, accuracy 0.73.

> El F1 in-sample del modelo final es 1.0 porque se entrenó con todo el piloto;
> no debe reportarse como resultado de generalización. La métrica honesta es la
> validación cruzada: F1 0.7586.

## 6. Artefactos

```text
models/clasificador_criticas/
├── modelo.pt      # pesos (3 MB)
├── vocab.json     # vocabulario
└── config.json    # umbral, max_len, arquitectura
```

`models/` está en `.gitignore`: **el modelo no se versiona**. Se regenera con
`entrenar_clasificador.py`.

Reportes:

- `reports/clasificador_metricas.json`
- `reports/clasificador_reporte.md`
- `reports/evaluacion_clasificador.json`

## 7. Integración

- `ingestion/migracion/etl_star_schema.py` clasifica las publicaciones y llena
  `fact_publicacion.es_critica`, `prob_critica` y `modelo_criticidad`.
- `backend/sql_builder.py` permite filtrar por `solo_criticas`.
- El chat reconoce “publicaciones críticas” y responde con la fuente X.
- Si el modelo no está disponible, el ETL usa una regla de respaldo
  (noticia/denuncia + marcadores) y lo advierte en consola.

## 8. Limitaciones

- Piloto pequeño (100 casos) y alta varianza por fold (F1 0.44–0.91).
- Posibles falsos positivos en violencia general u organizada; se mitigó con un
  filtro de seguridad, pero se recomienda ampliar el piloto con negativos duros.
- Entrenado para español y para el dominio de X; no se probó en otras redes.
- No mide veracidad: una publicación puede ser crítica y aun así contener datos
  incorrectos. La confiabilidad se evalúa por separado.
- No debe usarse para decisiones automatizadas sobre personas.

## 9. Uso ético

- Las publicaciones son datos públicos, pero pueden contener información
  sensible; no se almacenan datos personales de las víctimas.
- La clasificación es una ayuda para priorizar revisión humana, no un veredicto.
- Citar siempre la fuente X y aclarar que no es estadística oficial.
