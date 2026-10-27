-- ============================================================
-- Fase 1 — Embeddings del corpus documental (base: HUBDATOS)
-- Migración aditiva e idempotente.
--
-- Cada ALTER se ejecuta por separado para que, si la columna ya
-- existe, run_sql.py omita el error 1060 y continúe con las demás.
-- El índice se omite con el error 1061 si ya existe.
--
-- Uso:
--   cd sql
--   python run_sql.py 08_embeddings.sql --database HUBDATOS
-- ============================================================

USE HUBDATOS;

ALTER TABLE fragmentos_documentos
  ADD COLUMN embedding LONGTEXT NULL;

ALTER TABLE fragmentos_documentos
  ADD COLUMN modelo_embedding VARCHAR(150) NULL;

ALTER TABLE fragmentos_documentos
  ADD COLUMN dimensiones SMALLINT NULL;

ALTER TABLE fragmentos_documentos
  ADD COLUMN hash_texto CHAR(64) NULL;

ALTER TABLE fragmentos_documentos
  ADD COLUMN fecha_embedding DATETIME NULL;

CREATE INDEX idx_frag_modelo
  ON fragmentos_documentos (modelo_embedding);
