-- ============================================================
-- Fase 7 — Relación indicador <-> tipo de violencia
-- Base: HUBDATOS
-- ============================================================

CREATE TABLE IF NOT EXISTS bridge_indicador_tipo_violencia (
  id_indicador      INT NOT NULL,
  id_tipo_violencia INT NOT NULL,
  PRIMARY KEY (id_indicador, id_tipo_violencia),
  CONSTRAINT fk_bitv_ind FOREIGN KEY (id_indicador)
    REFERENCES dim_indicador(id_indicador),
  CONSTRAINT fk_bitv_tv FOREIGN KEY (id_tipo_violencia)
    REFERENCES tipos_violencia(id_tipo_violencia)
);
