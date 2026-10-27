-- ============================================================
-- Fase 2 (v2) — Corpus re-fragmentado para recuperación mejorada
-- Base: HUBDATOS
--
-- La tabla v1 (fragmentos_documentos) no se modifica.
-- Esta tabla es derivada y se puede reconstruir con:
--   cd ingestion/v2
--   python rechunk_corpus.py
--
-- Uso:
--   cd sql
--   python run_sql.py 09_corpus_v2.sql --database HUBDATOS
-- ============================================================

USE HUBDATOS;

CREATE TABLE IF NOT EXISTS fragmentos_documentos_v2 (
  id_fragmento_v2    INT AUTO_INCREMENT PRIMARY KEY,
  id_documento       INT NOT NULL,
  id_fragmento_origen INT NULL,
  pagina             INT NULL,
  orden              INT NOT NULL DEFAULT 0,
  texto              LONGTEXT NOT NULL,
  embedding          LONGBLOB NULL,
  modelo_embedding   VARCHAR(150) NULL,
  dimensiones        SMALLINT NULL,
  hash_texto         CHAR(64) NULL,
  version_chunk      VARCHAR(40) NULL,
  fecha_embedding    DATETIME NULL,
  CONSTRAINT fk_frag_v2_doc FOREIGN KEY (id_documento)
    REFERENCES documentos(id_documento),
  FULLTEXT KEY ft_fragmento_v2 (texto)
);

CREATE INDEX idx_frag_v2_modelo
  ON fragmentos_documentos_v2 (modelo_embedding);

CREATE INDEX idx_frag_v2_origen
  ON fragmentos_documentos_v2 (id_fragmento_origen);
