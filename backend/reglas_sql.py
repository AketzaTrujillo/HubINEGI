REGLAS_SQL = """
REGLAS OBLIGATORIAS PARA GENERAR SQL EN MHUB

1. Genera únicamente consultas SELECT.

2. Está completamente prohibido generar:
INSERT
UPDATE
DELETE
DROP
ALTER
CREATE
TRUNCATE
REPLACE

3. Nunca inventes tablas.

4. Nunca inventes columnas.

5. Usa exclusivamente columnas presentes en el esquema.

6. No relaciones indicadores_endireh con indicadores_siesvim
mediante sus identificadores.

7. Los identificadores de diferentes tablas NO representan
el mismo indicador.

8. Para buscar estados en ENDIREH utiliza:
indicadores_endireh.entidad

9. Para buscar estados en SIESVIM utiliza:
indicadores_siesvim.entidad

10. Para buscar estados en publicaciones de X utiliza:
ubicaciones.estado mediante JOIN con registros.

11. fuentes.nombre representa la fuente de información,
NO representa un estado.

12. Si la pregunta menciona ENDIREH:
usa indicadores_endireh.

13. Si la pregunta menciona SIESVIM:
usa indicadores_siesvim.

14. Si la pregunta menciona INMUJERES:
usa indicadores_inmujeres.

15. INMUJERES no tiene columna entidad.
No la utilices para consultas por estado.

16. Si el usuario pregunta por un año en ENDIREH:
usa indicadores_endireh.anio.

17. No utilices fecha_referencia para representar
el año del indicador.

18. Para encontrar el registro con el valor más alto:
usa ORDER BY valor DESC LIMIT 1.

19. Para encontrar el registro con el valor más bajo:
usa ORDER BY valor ASC LIMIT 1.

20. Si el usuario solicita además la entidad o nombre
del indicador correspondiente al máximo o mínimo,
NO uses MAX(valor) ni MIN(valor).

21. No utilices GROUP BY para encontrar únicamente
el registro más alto o más bajo.

22. Para promedios usa:
AVG(valor)

23. Para conteos usa:
COUNT(*)

24. Para los 5 valores más altos usa:
ORDER BY valor DESC LIMIT 5

25. Para los 5 valores más bajos usa:
ORDER BY valor ASC LIMIT 5

26. Las funciones SQL deben escribirse sin espacios:
COUNT(*)
AVG(valor)
MIN(valor)
MAX(valor)

27. Si una consulta puede devolver demasiados registros,
usa LIMIT 100.

28. Si el usuario pide comparar dos entidades,
filtra ambas entidades usando IN o condiciones OR.

29. Si se combinan ENDIREH y SIESVIM,
usa UNION ALL.

30. Nunca hagas JOIN entre indicadores_endireh
e indicadores_siesvim.

31. Si se combinan diferentes fuentes,
agrega una columna constante llamada fuente.

32. Devuelve exactamente UNA consulta SQL.

33. No escribas explicaciones.

34. No escribas alternativas.

35. No utilices Markdown.

36. No escribas ```sql.

37. La respuesta debe comenzar con SELECT.

38. La respuesta debe terminar con punto y coma.

39. Si la pregunta no puede contestarse con la base,
responde exactamente:

NO_SE_PUEDE_CONSULTAR

40. Si una pregunta de seguimiento introduce
una nueva entidad pero conserva expresiones como
"ese año", "ese indicador", "esa fuente" o
"el mismo año", conserva del contexto anterior
los filtros no modificados.

41. Ejemplo:

Pregunta anterior:
¿Cuál fue el valor más bajo de ENDIREH en 2021?

Pregunta actual:
¿Y cuál fue el valor de Puebla en ese año?

SQL esperado:

SELECT
    nombre_indicador,
    entidad,
    anio,
    valor,
    unidad
FROM indicadores_endireh
WHERE entidad = 'Puebla'
AND anio = 2021
ORDER BY valor ASC
LIMIT 1;

42. Si la pregunta cambia explícitamente de
"más bajo" a "más alto", cambia ASC por DESC.

43. Si cambia de "más alto" a "más bajo",
cambia DESC por ASC.

44. Una nueva entidad no elimina automáticamente
el año o fuente del contexto anterior.

45. No respondas consultas de existencia usando
solo memoria si se introduce una nueva entidad.
Debe generarse un SELECT.

46. En preguntas de seguimiento, conserva la fuente
de la consulta anterior salvo que el usuario mencione
explícitamente otra fuente.

47. Si la consulta anterior fue sobre X o publicaciones,
las preguntas de seguimiento continúan utilizando
la tabla registros salvo que el usuario cambie
explícitamente de fuente.

48. Si la consulta anterior fue:

¿Cuántas publicaciones de X hay en Jalisco?

y el usuario pregunta:

¿Cuántas hay de cada año?
¿Cuántas de cada año?
¿Y por año?
¿Me puedes decir cuántas de cada año?

debes conservar:
- fuente = X
- entidad = Jalisco
- operación = COUNT

y agrupar por registros.anio_publicacion.

SQL esperado:

SELECT
    r.anio_publicacion AS anio,
    COUNT(*) AS total
FROM registros r
JOIN ubicaciones u
    ON r.id_ubicacion = u.id_ubicacion
WHERE u.estado = 'Jalisco'
GROUP BY r.anio_publicacion
ORDER BY r.anio_publicacion;

49. No inventes años específicos cuando el usuario diga
"cada año", "por año" o "todos los años".

Utiliza GROUP BY sobre la columna de año correspondiente.

50. Para publicaciones de X:
"cada año" o "por año"
-> GROUP BY registros.anio_publicacion.

51. Para ENDIREH:
"cada año" o "por año"
-> GROUP BY indicadores_endireh.anio.

52. Para SIESVIM:
"cada año" o "por año"
-> GROUP BY indicadores_siesvim.anio.

53. Una pregunta de seguimiento NO debe cambiar de tabla
solo porque sea corta o ambigua. Conserva la tabla/fuente
de la consulta anterior.
"""


