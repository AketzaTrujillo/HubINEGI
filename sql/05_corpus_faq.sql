-- ============================================================
-- Fase 3 — Corpus documental para FAQ (base: HUBDATOS)
-- Rescatado de main. Sin columnas de embedding.
-- ============================================================

CREATE TABLE IF NOT EXISTS documentos (
  id_documento   INT AUTO_INCREMENT PRIMARY KEY,
  id_fuente      INT NOT NULL,
  nombre         VARCHAR(255) NOT NULL,
  nombre_archivo VARCHAR(255),
  ruta_archivo   TEXT,
  total_paginas  INT,
  total_chunks   INT,
  incluido_faq   TINYINT(1) DEFAULT 1,
  observaciones  TEXT,
  fecha_registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uq_documento_nombre (nombre),
  CONSTRAINT fk_doc_fuente FOREIGN KEY (id_fuente) REFERENCES fuentes(id_fuente)
);

CREATE TABLE IF NOT EXISTS fragmentos_documentos (
  id_fragmento INT AUTO_INCREMENT PRIMARY KEY,
  id_documento INT NOT NULL,
  chunk_id     INT,
  pagina       INT,
  texto        LONGTEXT NOT NULL,
  CONSTRAINT fk_frag_doc FOREIGN KEY (id_documento)
    REFERENCES documentos(id_documento),
  FULLTEXT KEY ft_fragmento (texto)
);
