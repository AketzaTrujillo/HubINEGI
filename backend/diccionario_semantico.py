DICCIONARIO_SEMANTICO = """
DICCIONARIO SEMÁNTICO DE MHUB

FUENTES:

- ENDIREH
  -> tabla indicadores_endireh

- SIESVIM
  -> tabla indicadores_siesvim

- INMUJERES
  -> tabla indicadores_inmujeres

- X
- Twitter
- publicaciones
- tweets
  -> tabla registros


UBICACIÓN:

- estado
- entidad
- entidad federativa
  -> columna entidad en ENDIREH y SIESVIM

Para publicaciones de X:
- estado
  -> ubicaciones.estado


TIEMPO:

- año
  -> columna anio en ENDIREH, SIESVIM e INMUJERES

Para X:
- año de publicación
  -> registros.anio_publicacion

- año mencionado
  -> registros.anio_mencionado


OPERACIONES:

- más alto
- mayor
- máximo
  -> ORDER BY valor DESC LIMIT 1

- más bajo
- menor
- mínimo
  -> ORDER BY valor ASC LIMIT 1

- promedio
- media
  -> AVG(valor)

- cuántos
- cantidad
- número de
  -> COUNT(*)

- cinco más altos
- 5 más altos
  -> ORDER BY valor DESC LIMIT 5

- cinco más bajos
- 5 más bajos
  -> ORDER BY valor ASC LIMIT 5


REGLA IMPORTANTE:

Si el usuario quiere conocer también la entidad o el
nombre del indicador correspondiente al mínimo o máximo,
NO utilizar MIN(valor) ni MAX(valor).

Ejemplo:

Incorrecto:
SELECT entidad, MIN(valor)
FROM indicadores_endireh;

Correcto:
SELECT entidad, nombre_indicador, valor
FROM indicadores_endireh
ORDER BY valor ASC
LIMIT 1;
"""