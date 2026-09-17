ESQUEMA_DB = """
BASE DE DATOS: HUBDATOS


TABLA: fuentes

Descripción:
Contiene las fuentes de información utilizadas por MHub.

Columnas:
- id_fuente
- nombre
- tipo_fuente
- url
- descripcion
- fecha_consulta

Ejemplos de nombre:
- ENDIREH INEGI
- SIESVIM INEGI
- INMUJERES SIE
- X Twitter

IMPORTANTE:
fuentes.nombre representa una fuente de información.
NO representa un estado de México.


TABLA: indicadores_endireh

Descripción:
Contiene indicadores provenientes de ENDIREH.

Columnas:
- id_indicador
- id_fuente
- codigo_indicador
- nombre_indicador
- categoria_indicador
- ambito
- agresor
- periodo_medicion
- poblacion_objetivo
- entidad
- anio
- valor
- unidad
- fecha_referencia
- datos_extra
- fecha_registro

Relación:
indicadores_endireh.id_fuente = fuentes.id_fuente

IMPORTANTE:
- entidad contiene entidades federativas de México.
- anio contiene el año del indicador.
- valor contiene el valor estadístico.
- unidad normalmente contiene porcentaje.


TABLA: indicadores_siesvim

Descripción:
Contiene indicadores provenientes de SIESVIM.

Columnas:
- id_siesvim
- id_fuente
- tema
- subtema
- nombre_indicador
- entidad
- anio
- categoria
- valor
- unidad
- datos_extra
- fecha_registro

Relación:
indicadores_siesvim.id_fuente = fuentes.id_fuente

IMPORTANTE:
- entidad contiene entidades federativas.
- anio representa el año.
- valor representa el valor del indicador.


TABLA: indicadores_inmujeres

Descripción:
Contiene indicadores provenientes de INMUJERES.

Columnas:
- id_indicador
- id_fuente
- archivo_origen
- numero_tabla
- nombre_indicador
- categoria
- subcategoria
- anio
- valor
- unidad
- datos_extra
- fecha_registro

Relación:
indicadores_inmujeres.id_fuente = fuentes.id_fuente

IMPORTANTE:
Esta tabla NO tiene columna entidad.
No utilizarla para consultas por estado.


TABLA: registros

Descripción:
Contiene publicaciones provenientes de la plataforma X.

Columnas:
- id_registro
- id_fuente
- id_ambito
- id_tipo_violencia
- id_tipo_contenido
- id_ubicacion
- archivo_origen
- anio_publicacion
- anio_mencionado
- fecha_publicacion
- usuario
- texto_original
- texto_limpio
- violencia_contra_mujer
- es_basura
- motivo_basura
- nivel_confianza
- datos_extra
- fecha_registro


TABLA: ubicaciones

Columnas:
- id_ubicacion
- lugar_detectado
- municipio_alcaldia
- estado
- nivel_ubicacion
- pais

Relación:
registros.id_ubicacion = ubicaciones.id_ubicacion


TABLA: ambitos_violencia

Columnas:
- id_ambito
- nombre
- descripcion

Relación:
registros.id_ambito = ambitos_violencia.id_ambito


TABLA: tipos_violencia

Columnas:
- id_tipo_violencia
- nombre
- descripcion

Relación:
registros.id_tipo_violencia = tipos_violencia.id_tipo_violencia


TABLA: tipos_contenido

Columnas:
- id_tipo_contenido
- nombre
- descripcion

Relación:
registros.id_tipo_contenido = tipos_contenido.id_tipo_contenido
"""