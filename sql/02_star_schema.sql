-- ============================================================
-- Fase 1 — Esquema en estrella
-- Base: HUBDATOS
-- ============================================================

-- ------------------------------------------------------------
-- Tiempo (separado por semántica)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS dim_tiempo (
  id_tiempo   INT AUTO_INCREMENT PRIMARY KEY,
  anio        SMALLINT NULL,
  tipo_tiempo ENUM('dato','publicacion','mencion') NOT NULL,
  UNIQUE KEY uq_tiempo (anio, tipo_tiempo)
);

-- ------------------------------------------------------------
-- Unidades
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS dim_unidad (
  id_unidad INT AUTO_INCREMENT PRIMARY KEY,
  nombre    VARCHAR(50) NOT NULL UNIQUE,
  tipo      ENUM('porcentaje','conteo','tasa','indice') NOT NULL
);

INSERT IGNORE INTO dim_unidad (nombre, tipo) VALUES
  ('porcentaje', 'porcentaje'),
  ('conteo', 'conteo'),
  ('tasa', 'tasa'),
  ('indice', 'indice');

-- ------------------------------------------------------------
-- Indicadores (dimensión conformada)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS dim_indicador (
  id_indicador       INT AUTO_INCREMENT PRIMARY KEY,
  codigo             VARCHAR(191) NOT NULL UNIQUE,
  nombre             TEXT NOT NULL,
  descripcion        TEXT,
  id_fuente          INT NOT NULL,
  tema               VARCHAR(150),
  subtema            VARCHAR(150),
  categoria          VARCHAR(150),
  ambito             VARCHAR(100),
  agresor            VARCHAR(150),
  periodo_medicion   VARCHAR(100),
  poblacion_objetivo TEXT,
  id_unidad          INT,
  CONSTRAINT fk_ind_fuente FOREIGN KEY (id_fuente) REFERENCES fuentes(id_fuente),
  CONSTRAINT fk_ind_unidad FOREIGN KEY (id_unidad) REFERENCES dim_unidad(id_unidad),
  INDEX idx_ind_fuente (id_fuente)
);

CREATE TABLE IF NOT EXISTS dim_indicador_alias (
  id_alias     INT AUTO_INCREMENT PRIMARY KEY,
  alias        VARCHAR(200) NOT NULL,
  id_indicador INT NOT NULL,
  UNIQUE KEY uq_indicador_alias (alias),
  CONSTRAINT fk_indi_alias FOREIGN KEY (id_indicador)
    REFERENCES dim_indicador(id_indicador)
);

-- ------------------------------------------------------------
-- Hechos
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS fact_indicador (
  id_hecho         BIGINT AUTO_INCREMENT PRIMARY KEY,
  id_indicador     INT NOT NULL,
  id_entidad       INT NULL,
  id_tiempo        INT NULL,
  id_fuente        INT NOT NULL,
  id_unidad        INT NULL,
  valor            DECIMAL(14,2),
  fecha_referencia DATE,
  CONSTRAINT fk_fi_indicador FOREIGN KEY (id_indicador) REFERENCES dim_indicador(id_indicador),
  CONSTRAINT fk_fi_entidad   FOREIGN KEY (id_entidad)   REFERENCES dim_entidad(id_entidad),
  CONSTRAINT fk_fi_tiempo    FOREIGN KEY (id_tiempo)    REFERENCES dim_tiempo(id_tiempo),
  CONSTRAINT fk_fi_fuente    FOREIGN KEY (id_fuente)    REFERENCES fuentes(id_fuente),
  CONSTRAINT fk_fi_unidad    FOREIGN KEY (id_unidad)    REFERENCES dim_unidad(id_unidad),
  INDEX idx_fi_indicador (id_indicador),
  INDEX idx_fi_entidad   (id_entidad),
  INDEX idx_fi_tiempo    (id_tiempo),
  INDEX idx_fi_fuente    (id_fuente)
);

CREATE TABLE IF NOT EXISTS fact_publicacion (
  id_publicacion     BIGINT AUTO_INCREMENT PRIMARY KEY,
  id_fuente          INT NOT NULL,
  id_entidad         INT NULL,
  id_tiempo_pub      INT NULL,
  id_tiempo_mencion  INT NULL,
  archivo_origen     VARCHAR(255),
  usuario            TEXT,
  texto_original     LONGTEXT,
  texto_limpio       LONGTEXT,
  violencia_mujer    ENUM('si','no','incierto') DEFAULT 'incierto',
  es_basura          ENUM('si','no') DEFAULT 'no',
  motivo_basura      VARCHAR(150),
  nivel_confianza    DECIMAL(4,2),
  CONSTRAINT fk_fp_fuente   FOREIGN KEY (id_fuente) REFERENCES fuentes(id_fuente),
  CONSTRAINT fk_fp_entidad  FOREIGN KEY (id_entidad) REFERENCES dim_entidad(id_entidad),
  CONSTRAINT fk_fp_tpub     FOREIGN KEY (id_tiempo_pub) REFERENCES dim_tiempo(id_tiempo),
  CONSTRAINT fk_fp_tmencion FOREIGN KEY (id_tiempo_mencion) REFERENCES dim_tiempo(id_tiempo),
  INDEX idx_fp_entidad (id_entidad),
  INDEX idx_fp_tpub    (id_tiempo_pub),
  INDEX idx_fp_basura  (es_basura)
);

-- ------------------------------------------------------------
-- Bridges M:N (catálogos compartidos ya existentes)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS bridge_pub_tipo_violencia (
  id_publicacion    BIGINT NOT NULL,
  id_tipo_violencia INT NOT NULL,
  PRIMARY KEY (id_publicacion, id_tipo_violencia),
  CONSTRAINT fk_bptv_pub  FOREIGN KEY (id_publicacion)    REFERENCES fact_publicacion(id_publicacion),
  CONSTRAINT fk_bptv_tipo FOREIGN KEY (id_tipo_violencia) REFERENCES tipos_violencia(id_tipo_violencia)
);

CREATE TABLE IF NOT EXISTS bridge_pub_tipo_contenido (
  id_publicacion    BIGINT NOT NULL,
  id_tipo_contenido INT NOT NULL,
  PRIMARY KEY (id_publicacion, id_tipo_contenido),
  CONSTRAINT fk_bptc_pub  FOREIGN KEY (id_publicacion)    REFERENCES fact_publicacion(id_publicacion),
  CONSTRAINT fk_bptc_tipo FOREIGN KEY (id_tipo_contenido) REFERENCES tipos_contenido(id_tipo_contenido)
);

CREATE TABLE IF NOT EXISTS bridge_pub_ambito (
  id_publicacion BIGINT NOT NULL,
  id_ambito      INT NOT NULL,
  PRIMARY KEY (id_publicacion, id_ambito),
  CONSTRAINT fk_bpa_pub    FOREIGN KEY (id_publicacion) REFERENCES fact_publicacion(id_publicacion),
  CONSTRAINT fk_bpa_ambito FOREIGN KEY (id_ambito)      REFERENCES ambitos_violencia(id_ambito)
);
