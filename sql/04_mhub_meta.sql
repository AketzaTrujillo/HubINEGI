-- ============================================================
-- Fase 2 — Metadata semántica (base: mhub_meta)
-- ============================================================

CREATE TABLE IF NOT EXISTS sem_tabla (
  id_tabla    INT AUTO_INCREMENT PRIMARY KEY,
  tabla       VARCHAR(100) NOT NULL UNIQUE,
  descripcion TEXT,
  grano       VARCHAR(200),
  es_fact     TINYINT(1) DEFAULT 0
);

CREATE TABLE IF NOT EXISTS sem_columna (
  id_columna   INT AUTO_INCREMENT PRIMARY KEY,
  tabla        VARCHAR(100) NOT NULL,
  columna      VARCHAR(100) NOT NULL,
  descripcion  TEXT,
  tipo_dato    VARCHAR(50),
  sinonimos    TEXT,
  es_filtrable TINYINT(1) DEFAULT 0,
  es_agrupable TINYINT(1) DEFAULT 0,
  es_medida    TINYINT(1) DEFAULT 0,
  ejemplo      VARCHAR(200),
  UNIQUE KEY uq_col (tabla, columna)
);

CREATE TABLE IF NOT EXISTS sem_metrica (
  id_metrica       INT AUTO_INCREMENT PRIMARY KEY,
  nombre           VARCHAR(50) NOT NULL UNIQUE,
  expresion_sql    VARCHAR(120) NOT NULL,
  sinonimos        TEXT,
  requiere_columna VARCHAR(100),
  descripcion      TEXT
);

INSERT IGNORE INTO sem_metrica (nombre, expresion_sql, sinonimos, requiere_columna, descripcion) VALUES
  ('detalle',  'SELECT',   'lista,listado,muestra,ensename,que indicadores', 'valor', 'Devuelve filas de indicadores'),
  ('conteo',   'COUNT',    'cuantos,cuantas,cantidad,numero,total,cuantos hay', 'valor', 'Cuenta registros'),
  ('promedio', 'AVG',      'promedio,media,mean,en promedio', 'valor', 'Promedio aritmetico del valor'),
  ('maximo',   'MAX',      'maximo,mayor,mas alto,el mas alto,el mayor,mayor valor', 'valor', 'Registro con el valor mas alto'),
  ('minimo',   'MIN',      'minimo,menor,mas bajo,el mas bajo,el menor,menor valor', 'valor', 'Registro con el valor mas bajo'),
  ('suma',     'SUM',      'suma,total acumulado,sumatoria', 'valor', 'Suma de los valores'),
  ('top_n',    'LIMIT',    'top,los primeros,los mayores,los mas altos,ranking', 'valor', 'N valores mas altos o mas bajos');

CREATE TABLE IF NOT EXISTS sem_sinonimo (
  id_sinonimo  INT AUTO_INCREMENT PRIMARY KEY,
  termino      VARCHAR(200) NOT NULL,
  tipo_destino ENUM('entidad','indicador','fuente','metrica','columna','termino') NOT NULL,
  id_destino   VARCHAR(200),
  UNIQUE KEY uq_sin (termino, tipo_destino)
);

INSERT IGNORE INTO sem_sinonimo (termino, tipo_destino, id_destino) VALUES
  ('twitter', 'fuente', 'X'),
  ('tweets', 'fuente', 'X'),
  ('publicaciones de x', 'fuente', 'X'),
  ('encuesta', 'fuente', 'ENDIREH'),
  ('endireh', 'fuente', 'ENDIREH'),
  ('siesvim', 'fuente', 'SIESVIM'),
  ('inmujeres', 'fuente', 'INMUJERES'),
  ('semujeres', 'fuente', 'INMUJERES'),
  ('banavim', 'termino', 'Banco Nacional de Datos e Información sobre Casos de Violencia contra las Mujeres'),
  ('cjm', 'termino', 'Centros de Justicia para las Mujeres'),
  ('conavim', 'termino', 'Comisión Nacional para Prevenir y Erradicar la Violencia contra las Mujeres'),
  ('sesnsp', 'termino', 'Secretariado Ejecutivo del Sistema Nacional de Seguridad Pública'),
  ('lgamvlv', 'termino', 'Ley General de Acceso de las Mujeres a una Vida Libre de Violencia');

CREATE TABLE IF NOT EXISTS sem_ejemplo (
  id_ejemplo   INT AUTO_INCREMENT PRIMARY KEY,
  pregunta     TEXT NOT NULL,
  spec_json    JSON NULL,
  consulta_sql TEXT NULL,
  id_intencion VARCHAR(50)
);

CREATE TABLE IF NOT EXISTS sem_regla (
  id_regla INT AUTO_INCREMENT PRIMARY KEY,
  grupo    VARCHAR(50) NOT NULL,
  orden    INT NOT NULL,
  texto    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS cat_intencion (
  id_intencion VARCHAR(50) PRIMARY KEY,
  descripcion  TEXT,
  requiere_bd  TINYINT(1) DEFAULT 0,
  prioridad    INT DEFAULT 100
);

INSERT IGNORE INTO cat_intencion (id_intencion, descripcion, requiere_bd, prioridad) VALUES
  ('FAQ_EXACTA','Coincidencia exacta con FAQ',0,10),
  ('FAQ_SEMANTICA','Alta similitud con FAQ',0,20),
  ('FAQ_CORPUS','Respondida desde el corpus documental',0,25),
  ('SEGUIMIENTO','Usa contexto anterior',1,30),
  ('CONSULTA_AGREGACION','Agregacion sobre datos',1,40),
  ('CONSULTA_DETALLE','Listado de filas',1,50),
  ('CONVERSACION','Saludo/ayuda/fuera de tema',0,60);

CREATE TABLE IF NOT EXISTS faq (
  id_faq       INT AUTO_INCREMENT PRIMARY KEY,
  pregunta     TEXT NOT NULL,
  patron       VARCHAR(255) NULL,
  sinonimos    TEXT,
  id_intencion VARCHAR(50) NOT NULL,
  respuesta    TEXT NOT NULL,
  consulta_sql TEXT NULL,
  requiere_bd  TINYINT(1) DEFAULT 0,
  prioridad    INT DEFAULT 100,
  activo       TINYINT(1) DEFAULT 1,
  FULLTEXT KEY ft_faq (pregunta, sinonimos),
  CONSTRAINT fk_faq_intencion FOREIGN KEY (id_intencion)
    REFERENCES cat_intencion(id_intencion)
);

INSERT IGNORE INTO faq (pregunta, patron, sinonimos, id_intencion, respuesta, requiere_bd, prioridad) VALUES
  ('¿Qué es ENDIREH?', 'que es endireh|endireh', 'encuesta nacional dinamica relaciones hogares inegi', 'FAQ_EXACTA',
   'La ENDIREH es la Encuesta Nacional sobre la Dinámica de las Relaciones en los Hogares, del INEGI. Mide la violencia contra las mujeres en México por entidad y año. MHub usa sus indicadores para consultas de datos.', 0, 10),
  ('¿Qué es SIESVIM?', 'que es siesvim|siesvim', 'sistema integrado estadisticas violencia mujeres inegi', 'FAQ_EXACTA',
   'El SIESVIM es el Sistema Integrado de Estadísticas sobre Violencia contra las Mujeres, del INEGI. Reúne indicadores por tema, subtema y entidad federativa.', 0, 10),
  ('¿Qué es INMUJERES?', 'que es inmujeres|inmujeres|semujeres', 'instituto nacional mujeres sistema informacion estadistica', 'FAQ_EXACTA',
   'INMUJERES es el Instituto Nacional de las Mujeres. Sus indicadores en MHub son conteos nacionales (no porcentajes) sobre violencia y atención a mujeres.', 0, 10),
  ('¿Qué fuentes usa MHub?', 'que fuentes|fuentes usa|de donde vienen los datos', 'endireh siesvim inmujeres x twitter', 'FAQ_EXACTA',
   'MHub integra ENDIREH y SIESVIM (INEGI), INMUJERES/SEMUJERES y publicaciones de X. Las cifras oficiales provienen de INEGI e INMUJERES. Los datos de X son publicaciones, no casos ni estadística oficial.', 0, 10),
  ('¿Qué es prevalencia?', 'que es prevalencia|prevalencia', 'proporcion mujeres que han vivido violencia', 'FAQ_EXACTA',
   'La prevalencia es la proporción de mujeres que han vivido violencia en algún momento de su vida. No debe confundirse con incidencia, que mide casos nuevos en un periodo.', 0, 10),
  ('¿Qué es incidencia?', 'que es incidencia|incidencia', 'casos nuevos en un periodo', 'FAQ_EXACTA',
   'La incidencia mide casos nuevos de violencia en un periodo determinado. Es distinta de la prevalencia, que mide el total acumulado a lo largo de la vida.', 0, 10),
  ('¿Cuál es la diferencia entre prevalencia e incidencia?', 'diferencia prevalencia incidencia|prevalencia e incidencia', 'mediciones distintas comparar', 'FAQ_EXACTA',
   'La prevalencia mide cuántas mujeres han vivido violencia alguna vez en su vida. La incidencia mide casos nuevos en un periodo. Son mediciones distintas y no deben mezclarse ni compararse directamente.', 0, 10),
  ('¿Qué es subregistro?', 'que es subregistro|subregistro', 'datos no reportados cifra negra', 'FAQ_EXACTA',
   'El subregistro es la parte de la violencia que no se reporta a instituciones ni se registra en estadísticas oficiales. Por eso las cifras oficiales suelen ser una cota inferior de la realidad.', 0, 10),
  ('¿Cómo se recolectan los datos de X?', 'como se recolectan|recolectan los datos de x', 'twitter recoleccion manual publicaciones', 'FAQ_EXACTA',
   'Las publicaciones de X se recolectan manualmente desde búsquedas. En MHub se presentan como "publicaciones" o "registros de X", nunca como casos ni estadística oficial.', 0, 10),
  ('¿Qué es BANAVIM?', 'que es banavim|banavim', 'banco nacional datos informacion violencia mujeres', 'FAQ_EXACTA',
   'El BANAVIM es el Banco Nacional de Datos e Información sobre Casos de Violencia contra las Mujeres. Sus lineamientos forman parte del corpus documental de MHub.', 0, 20);
