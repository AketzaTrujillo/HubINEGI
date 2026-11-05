-- ============================================================
-- Fase 8 — Criticidad de publicaciones de X (objetivo 7)
-- Base: HUBDATOS
-- Migración idempotente para bases ya creadas.
-- ============================================================

SET @col_es_critica = (
  SELECT COUNT(*) FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE()
    AND TABLE_NAME = 'fact_publicacion'
    AND COLUMN_NAME = 'es_critica'
);
SET @sql_es_critica = IF(
  @col_es_critica = 0,
  'ALTER TABLE fact_publicacion ADD COLUMN es_critica ENUM(''si'',''no'') DEFAULT ''no''',
  'SELECT 1'
);
PREPARE stmt FROM @sql_es_critica;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @col_prob_critica = (
  SELECT COUNT(*) FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE()
    AND TABLE_NAME = 'fact_publicacion'
    AND COLUMN_NAME = 'prob_critica'
);
SET @sql_prob_critica = IF(
  @col_prob_critica = 0,
  'ALTER TABLE fact_publicacion ADD COLUMN prob_critica DECIMAL(5,4) NULL',
  'SELECT 1'
);
PREPARE stmt FROM @sql_prob_critica;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @col_modelo = (
  SELECT COUNT(*) FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE()
    AND TABLE_NAME = 'fact_publicacion'
    AND COLUMN_NAME = 'modelo_criticidad'
);
SET @sql_modelo = IF(
  @col_modelo = 0,
  'ALTER TABLE fact_publicacion ADD COLUMN modelo_criticidad VARCHAR(50) NULL',
  'SELECT 1'
);
PREPARE stmt FROM @sql_modelo;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @idx_critica = (
  SELECT COUNT(*) FROM information_schema.STATISTICS
  WHERE TABLE_SCHEMA = DATABASE()
    AND TABLE_NAME = 'fact_publicacion'
    AND INDEX_NAME = 'idx_fp_critica'
);
SET @sql_idx = IF(
  @idx_critica = 0,
  'ALTER TABLE fact_publicacion ADD INDEX idx_fp_critica (es_critica)',
  'SELECT 1'
);
PREPARE stmt FROM @sql_idx;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;
