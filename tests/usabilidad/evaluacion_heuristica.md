# Evaluación heurística — MHub

Evaluación experta de la interfaz (Asistente MHub y Panel) basada en las 10
heurísticas de Nielsen. Complementa las pruebas con usuarios de `protocolo.md`.

| # | Heurística | Hallazgo | Severidad | Recomendación |
|---|---|---|---|---|
| 1 | Visibilidad del estado | El chat muestra `TypingIndicator`, el botón se deshabilita mientras espera y el Panel muestra estados de carga. | — | Mantener. Añadir un mensaje explícito si la consulta tarda más de 10 s. |
| 2 | Lenguaje del usuario | La interfaz está en español, con sugerencias como “Violencia familiar 2024” y “Rutas de atención”. | — | Mantener. Evitar tecnicismos como “ENDIREH” sin una breve explicación en la primera interacción. |
| 3 | Control y libertad | No hay un botón visible para iniciar una conversación nueva o limpiar el contexto. | Media | Añadir “Nueva conversación” en la cabecera del chat. |
| 4 | Consistencia | “Asistente MHub”, “Panel” y “Rutas de atención” se usan de forma consistente. | — | Mantener. |
| 5 | Prevención de errores | El campo vacío no se envía; el botón se deshabilita durante la espera. | Baja | Validar preguntas demasiado cortas o ambiguas con una sugerencia. |
| 6 | Reconocimiento | Hay sugerencias iniciales y filtros dependientes en el Panel. | — | Mantener. Añadir ejemplos de seguimiento (“¿y en 2021?”). |
| 7 | Flexibilidad y eficiencia | Enter envía, Shift+Enter hace salto de línea; el Panel permite combinar filtros. | — | Mantener. Añadir atajos para limpiar filtros. |
| 8 | Diseño minimalista | La interfaz es limpia; las gráficas y el texto no compiten. | — | Mantener. |
| 9 | Recuperación de errores | Los errores de conexión indican la URL del backend y sugieren verificar que esté en marcha. | Baja | Añadir un botón “Reintentar” en el mensaje de error. |
| 10 | Ayuda y documentación | Hay sugerencias, respuestas de ayuda y rutas de atención. | Baja | Añadir un enlace visible a “¿Cómo preguntar?” y al aviso de privacidad. |

## Hallazgos adicionales

- El texto del compositor dice “Sin recolección de datos personales”, pero el
  backend registra la pregunta en `logs/turnos.jsonl`. Es una inconsistencia de
  confianza que debe resolverse antes de la presentación (ver objetivo 8).
- Las gráficas incluyen una tabla accesible; es una buena práctica.
- No se observó un flujo de “empezar de cero”; el contexto se conserva en memoria
  hasta recargar la página.

## Conclusión

La interfaz es clara para el flujo principal. Las mejoras de mayor impacto son:
botón de nueva conversación, enlace de ayuda/privacidad y mensaje de reintento.
Las pruebas con usuarios de `protocolo.md` deben confirmar estos hallazgos.
