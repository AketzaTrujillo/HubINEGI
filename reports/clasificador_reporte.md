# Evaluación del clasificador de publicaciones críticas

Modelo: `textcnn-v1` (TextCNN con preentrenamiento débil y ajuste fino)
Validación cruzada: 5 folds estratificados
Umbral de despliegue: **0.5**

## Resultados principales

| Conjunto | n | Positivos | Accuracy | Precision | Recall | F1 | ROC-AUC |
|---|---:|---:|---:|---:|---:|---:|---:|
| Piloto manual (OOF, umbral 0.5) | 100 | 32 | 0.86 | 0.8462 | 0.6875 | 0.7586 | 0.938 |
| Piloto manual (OOF, mejor umbral) | 100 | 32 | 0.87 | 0.7714 | 0.8438 | 0.806 | 0.938 |
| Baseline reglas (piloto) | 100 | 32 | 0.73 | 0.5472 | 0.9062 | 0.6824 | 0.7767 |
| Test débil (preentrenamiento) | 323 | 19 | 0.9319 | 0.4 | 0.3158 | 0.3529 | 0.8229 |

## Matriz de confusión (OOF, umbral 0.5)

```
[[64, 4], [10, 22]]
```

## F1 por fold

| Fold | n test | F1 | Accuracy |
|---:|---:|---:|---:|
| 1 | 20 | 0.4444 | 0.75 |
| 2 | 20 | 0.6667 | 0.85 |
| 3 | 20 | 0.9091 | 0.95 |
| 4 | 20 | 0.8 | 0.85 |
| 5 | 20 | 0.8571 | 0.9 |

## Lectura

- Las etiquetas débiles se derivan de `tipo_contenido` y se usan solo para preentrenar.
- La evaluación principal es el piloto manual con validación cruzada fuera de muestra.
- El baseline por reglas se incluye para comparar; el modelo lo supera en F1.
- El piloto es pequeño (100 casos) y la varianza por fold es alta (F1 0.44–0.91).
- Se observan falsos positivos en publicaciones de violencia general u organizada;
  se recomienda ampliar el piloto con negativos duros antes de productionizar.
- El umbral 0.5 es el de despliegue; el umbral alternativo mejora recall a costa de precisión.
- El modelo final se reentrena con todo el piloto y se guarda en `models/`.
