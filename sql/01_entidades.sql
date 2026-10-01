-- ============================================================
-- Fase 0 — Normalización de entidades
-- Base: HUBDATOS
-- ============================================================

ALTER TABLE fuentes ADD COLUMN codigo VARCHAR(20) UNIQUE;

UPDATE fuentes SET codigo = 'X'         WHERE nombre = 'X Twitter';
UPDATE fuentes SET codigo = 'ENDIREH'   WHERE nombre = 'ENDIREH INEGI';
UPDATE fuentes SET codigo = 'SIESVIM'   WHERE nombre = 'SIESVIM INEGI';
UPDATE fuentes SET codigo = 'INMUJERES' WHERE nombre = 'INMUJERES SIE';

-- ------------------------------------------------------------
-- Dimensión de entidades
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS dim_entidad (
  id_entidad      INT AUTO_INCREMENT PRIMARY KEY,
  nombre_canonico VARCHAR(150) NOT NULL UNIQUE,
  nivel           ENUM('pais','estado','municipio','alcaldia') NOT NULL DEFAULT 'estado',
  entidad_padre   INT NULL,
  codigo_iso      VARCHAR(10) NULL,
  CONSTRAINT fk_entidad_padre FOREIGN KEY (entidad_padre)
    REFERENCES dim_entidad(id_entidad)
);

CREATE TABLE IF NOT EXISTS dim_entidad_alias (
  id_alias   INT AUTO_INCREMENT PRIMARY KEY,
  alias      VARCHAR(150) NOT NULL,
  id_entidad INT NOT NULL,
  id_fuente  INT NULL,
  UNIQUE KEY uq_entidad_alias (alias),
  CONSTRAINT fk_alias_entidad FOREIGN KEY (id_entidad)
    REFERENCES dim_entidad(id_entidad),
  CONSTRAINT fk_alias_fuente FOREIGN KEY (id_fuente)
    REFERENCES fuentes(id_fuente)
);

-- ------------------------------------------------------------
-- Entidades canónicas (32 estados + país)
-- ------------------------------------------------------------
INSERT IGNORE INTO dim_entidad (nombre_canonico, nivel) VALUES
  ('Estados Unidos Mexicanos', 'pais'),
  ('Aguascalientes', 'estado'),
  ('Baja California', 'estado'),
  ('Baja California Sur', 'estado'),
  ('Campeche', 'estado'),
  ('Chiapas', 'estado'),
  ('Chihuahua', 'estado'),
  ('Ciudad de México', 'estado'),
  ('Coahuila', 'estado'),
  ('Colima', 'estado'),
  ('Durango', 'estado'),
  ('Estado de México', 'estado'),
  ('Guanajuato', 'estado'),
  ('Guerrero', 'estado'),
  ('Hidalgo', 'estado'),
  ('Jalisco', 'estado'),
  ('Michoacán', 'estado'),
  ('Morelos', 'estado'),
  ('Nayarit', 'estado'),
  ('Nuevo León', 'estado'),
  ('Oaxaca', 'estado'),
  ('Puebla', 'estado'),
  ('Querétaro', 'estado'),
  ('Quintana Roo', 'estado'),
  ('San Luis Potosí', 'estado'),
  ('Sinaloa', 'estado'),
  ('Sonora', 'estado'),
  ('Tabasco', 'estado'),
  ('Tamaulipas', 'estado'),
  ('Tlaxcala', 'estado'),
  ('Veracruz', 'estado'),
  ('Yucatán', 'estado'),
  ('Zacatecas', 'estado');

-- ------------------------------------------------------------
-- Alias conocidos
-- ------------------------------------------------------------
INSERT IGNORE INTO dim_entidad_alias (alias, id_entidad)
SELECT a.alias, e.id_entidad
FROM (
  SELECT 'Coahuila de Zaragoza'             AS alias, 'Coahuila'             AS canonico
  UNION ALL SELECT 'Michoacán de Ocampo',              'Michoacán'
  UNION ALL SELECT 'Veracruz de Ignacio de la Llave',  'Veracruz'
  UNION ALL SELECT 'Estado de Mexico',                 'Estado de México'
  UNION ALL SELECT 'Edomex',                           'Estado de México'
  UNION ALL SELECT 'México',                           'Estados Unidos Mexicanos'
  UNION ALL SELECT 'CDMX',                             'Ciudad de México'
  UNION ALL SELECT 'Ciudad de Mexico',                 'Ciudad de México'
  UNION ALL SELECT 'Distrito Federal',                 'Ciudad de México'
  UNION ALL SELECT 'Nacional',                         'Estados Unidos Mexicanos'
  UNION ALL SELECT 'México (país)',                    'Estados Unidos Mexicanos'
) AS a
JOIN dim_entidad e ON e.nombre_canonico = a.canonico;
