EJEMPLOS_NL_SQL = """
EJEMPLOS CORRECTOS DE PREGUNTAS Y SQL


Pregunta:
¿Qué indicadores ENDIREH hay para Jalisco en 2021?

SQL:
SELECT
    nombre_indicador,
    entidad,
    anio,
    valor,
    unidad
FROM indicadores_endireh
WHERE entidad = 'Jalisco'
AND anio = 2021
LIMIT 100;


Pregunta:
¿Qué indicadores ENDIREH hay para Puebla?

SQL:
SELECT
    nombre_indicador,
    entidad,
    anio,
    valor,
    unidad
FROM indicadores_endireh
WHERE entidad = 'Puebla'
LIMIT 100;


Pregunta:
¿Cuál fue el valor más bajo de ENDIREH en 2021?

SQL:
SELECT
    nombre_indicador,
    entidad,
    anio,
    valor,
    unidad
FROM indicadores_endireh
WHERE anio = 2021
ORDER BY valor ASC
LIMIT 1;


Pregunta:
¿Cuál fue el valor más alto de ENDIREH en 2021?

SQL:
SELECT
    nombre_indicador,
    entidad,
    anio,
    valor,
    unidad
FROM indicadores_endireh
WHERE anio = 2021
ORDER BY valor DESC
LIMIT 1;


Pregunta:
¿Cuáles fueron los 5 valores más altos de ENDIREH en 2021?

SQL:
SELECT
    nombre_indicador,
    entidad,
    anio,
    valor,
    unidad
FROM indicadores_endireh
WHERE anio = 2021
ORDER BY valor DESC
LIMIT 5;


Pregunta:
¿Cuáles fueron los 5 valores más bajos de ENDIREH en 2021?

SQL:
SELECT
    nombre_indicador,
    entidad,
    anio,
    valor,
    unidad
FROM indicadores_endireh
WHERE anio = 2021
ORDER BY valor ASC
LIMIT 5;


Pregunta:
¿Cuántos indicadores de ENDIREH existen para Puebla?

SQL:
SELECT COUNT(*) AS total
FROM indicadores_endireh
WHERE entidad = 'Puebla';


Pregunta:
¿Cuál es el promedio de los valores de ENDIREH para Jalisco en 2021?

SQL:
SELECT AVG(valor) AS promedio
FROM indicadores_endireh
WHERE entidad = 'Jalisco'
AND anio = 2021;


Pregunta:
¿Qué indicadores de SIESVIM existen para Puebla?

SQL:
SELECT
    nombre_indicador,
    tema,
    subtema,
    categoria,
    entidad,
    anio,
    valor,
    unidad
FROM indicadores_siesvim
WHERE entidad = 'Puebla'
LIMIT 100;


Pregunta:
¿Qué indicadores de SIESVIM existen en 2021?

SQL:
SELECT
    nombre_indicador,
    tema,
    subtema,
    entidad,
    anio,
    valor,
    unidad
FROM indicadores_siesvim
WHERE anio = 2021
LIMIT 100;


Pregunta:
¿Cuántas publicaciones de X hay en Jalisco?

SQL:
SELECT COUNT(*) AS total
FROM registros r
JOIN ubicaciones u
    ON r.id_ubicacion = u.id_ubicacion
WHERE u.estado = 'Jalisco';


Pregunta:
¿Cuántas publicaciones están clasificadas como violencia contra la mujer?

SQL:
SELECT COUNT(*) AS total
FROM registros
WHERE violencia_contra_mujer = 'si';


Pregunta:
¿Qué tipos de contenido existen?

SQL:
SELECT
    nombre,
    descripcion
FROM tipos_contenido;


Pregunta:
¿Qué fuentes utiliza MHub?

SQL:
SELECT
    nombre,
    tipo_fuente,
    descripcion
FROM fuentes;


Pregunta:
¿Qué indicadores hay para Jalisco?

SQL:
SELECT
    'ENDIREH' AS fuente,
    nombre_indicador,
    entidad,
    anio,
    valor,
    unidad
FROM indicadores_endireh
WHERE entidad = 'Jalisco'

UNION ALL

SELECT
    'SIESVIM' AS fuente,
    nombre_indicador,
    entidad,
    anio,
    valor,
    unidad
FROM indicadores_siesvim
WHERE entidad = 'Jalisco'

LIMIT 100;

Pregunta anterior:
¿Cuántas publicaciones de X hay en Jalisco?

SQL anterior:
SELECT COUNT(*) AS total
FROM registros r
JOIN ubicaciones u
    ON r.id_ubicacion = u.id_ubicacion
WHERE u.estado = 'Jalisco';

Pregunta actual:
¿Me puedes decir cuántas de cada año?

SQL:
SELECT
    r.anio_publicacion AS anio,
    COUNT(*) AS total
FROM registros r
JOIN ubicaciones u
    ON r.id_ubicacion = u.id_ubicacion
WHERE u.estado = 'Jalisco'
GROUP BY r.anio_publicacion
ORDER BY r.anio_publicacion;

"""