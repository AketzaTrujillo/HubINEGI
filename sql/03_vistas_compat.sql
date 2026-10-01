-- ============================================================
-- Fase 1 — Vistas de compatibilidad con el modelo anterior
-- Permiten que el código existente siga funcionando apuntando
-- al star schema sin cambios de contrato.
-- ============================================================

CREATE OR REPLACE VIEW v_indicadores_endireh AS
SELECT
  f.id_hecho           AS id_indicador,
  f.id_fuente          AS id_fuente,
  i.codigo             AS codigo_indicador,
  i.nombre             AS nombre_indicador,
  i.categoria          AS categoria_indicador,
  i.ambito             AS ambito,
  i.agresor            AS agresor,
  i.periodo_medicion   AS periodo_medicion,
  i.poblacion_objetivo AS poblacion_objetivo,
  e.nombre_canonico    AS entidad,
  t.anio               AS anio,
  f.valor              AS valor,
  u.nombre             AS unidad,
  f.fecha_referencia   AS fecha_referencia,
  NULL                 AS datos_extra,
  NULL                 AS fecha_registro
FROM fact_indicador f
JOIN dim_indicador i ON i.id_indicador = f.id_indicador
LEFT JOIN dim_entidad e ON e.id_entidad = f.id_entidad
LEFT JOIN dim_tiempo  t ON t.id_tiempo = f.id_tiempo
LEFT JOIN dim_unidad  u ON u.id_unidad = f.id_unidad
WHERE i.id_fuente = (SELECT id_fuente FROM fuentes WHERE codigo = 'ENDIREH');

CREATE OR REPLACE VIEW v_indicadores_siesvim AS
SELECT
  f.id_hecho        AS id_siesvim,
  f.id_fuente       AS id_fuente,
  i.tema            AS tema,
  i.subtema         AS subtema,
  i.nombre          AS nombre_indicador,
  e.nombre_canonico AS entidad,
  t.anio            AS anio,
  i.categoria       AS categoria,
  f.valor           AS valor,
  u.nombre          AS unidad,
  NULL              AS datos_extra,
  NULL              AS fecha_registro
FROM fact_indicador f
JOIN dim_indicador i ON i.id_indicador = f.id_indicador
LEFT JOIN dim_entidad e ON e.id_entidad = f.id_entidad
LEFT JOIN dim_tiempo  t ON t.id_tiempo = f.id_tiempo
LEFT JOIN dim_unidad  u ON u.id_unidad = f.id_unidad
WHERE i.id_fuente = (SELECT id_fuente FROM fuentes WHERE codigo = 'SIESVIM');

CREATE OR REPLACE VIEW v_indicadores_inmujeres AS
SELECT
  f.id_hecho     AS id_indicador,
  f.id_fuente    AS id_fuente,
  NULL           AS archivo_origen,
  NULL           AS numero_tabla,
  i.nombre       AS nombre_indicador,
  i.categoria    AS categoria,
  i.subtema      AS subcategoria,
  t.anio         AS anio,
  f.valor        AS valor,
  u.nombre       AS unidad,
  NULL           AS datos_extra,
  NULL           AS fecha_registro
FROM fact_indicador f
JOIN dim_indicador i ON i.id_indicador = f.id_indicador
LEFT JOIN dim_tiempo  t ON t.id_tiempo = f.id_tiempo
LEFT JOIN dim_unidad  u ON u.id_unidad = f.id_unidad
WHERE i.id_fuente = (SELECT id_fuente FROM fuentes WHERE codigo = 'INMUJERES');
