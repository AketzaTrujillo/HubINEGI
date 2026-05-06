DROP DATABASE IF EXISTS HUBDATOS;
CREATE DATABASE HUBDATOS CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

USE HUBDATOS;

CREATE TABLE fuentes (
    id_fuente INT AUTO_INCREMENT PRIMARY KEY,
    nombre VARCHAR(150) NOT NULL UNIQUE,
    tipo_fuente ENUM(
        'SIESVIM',
        'ENDIREH',
        'SEMUJERES',
        'PDF',
        'X',
        'NOTICIA',
        'GOBIERNO',
        'OTRO'
    ) NOT NULL,
    url TEXT,
    descripcion TEXT,
    fecha_consulta DATE
);

CREATE TABLE tipos_violencia (
    id_tipo_violencia INT AUTO_INCREMENT PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL UNIQUE,
    descripcion TEXT
);

CREATE TABLE ambitos_violencia (
    id_ambito INT AUTO_INCREMENT PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL UNIQUE,
    descripcion TEXT
);

CREATE TABLE tipos_contenido (
    id_tipo_contenido INT AUTO_INCREMENT PRIMARY KEY,
    nombre VARCHAR(50) NOT NULL UNIQUE,
    descripcion TEXT
);

CREATE TABLE ubicaciones (
    id_ubicacion INT AUTO_INCREMENT PRIMARY KEY,
    lugar_detectado VARCHAR(150),
    municipio_alcaldia VARCHAR(150),
    estado VARCHAR(150),
    nivel_ubicacion ENUM(
        'estado',
        'municipio',
        'capital',
        'alcaldia',
        'no_detectado'
    ),
    pais VARCHAR(100) DEFAULT 'México'
);

INSERT INTO ambitos_violencia (nombre) VALUES
('violencia de pareja'),
('violencia familiar'),
('violencia escolar'),
('violencia laboral');

INSERT INTO tipos_violencia (nombre) VALUES
('física'),
('psicológica'),
('emocional'),
('económica'),
('patrimonial'),
('sexual'),
('discriminación');

INSERT INTO tipos_contenido (nombre) VALUES
('estadistica'),
('noticia'),
('denuncia'),
('institucional'),
('opinion'),
('propaganda'),
('otro');

INSERT INTO fuentes (nombre, tipo_fuente, url, descripcion, fecha_consulta) VALUES
('X Twitter', 'X', 'https://x.com', 'Publicaciones recolectadas manualmente desde búsquedas de X', CURDATE()),
('ENDIREH INEGI', 'ENDIREH', 'https://www.inegi.org.mx/programas/endireh/', 'Indicadores oficiales de ENDIREH procesados desde CSV', CURDATE()),
('SIESVIM INEGI', 'SIESVIM', 'https://sc.inegi.org.mx/SIESVIM1/', 'Indicadores del Sistema Integrado de Estadísticas sobre Violencia contra las Mujeres', CURDATE()),
('INMUJERES SIE', 'SEMUJERES', NULL, 'Indicadores del Sistema de Información Estadística de INMUJERES', CURDATE());


--twitter
CREATE TABLE registros (
    id_registro BIGINT AUTO_INCREMENT PRIMARY KEY,

    id_fuente INT NOT NULL,
    id_ambito INT,
    id_tipo_violencia INT,
    id_tipo_contenido INT,
    id_ubicacion INT,

    archivo_origen VARCHAR(255),
    anio_publicacion YEAR,
    anio_mencionado YEAR,
    fecha_publicacion VARCHAR(100),
    usuario VARCHAR(150),

    texto_original LONGTEXT,
    texto_limpio LONGTEXT,

    violencia_contra_mujer ENUM('si','no','incierto') DEFAULT 'incierto',
    es_basura ENUM('si','no') DEFAULT 'no',
    motivo_basura VARCHAR(150),
    nivel_confianza DECIMAL(4,2),

    datos_extra JSON,
    fecha_registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (id_fuente) REFERENCES fuentes(id_fuente),
    FOREIGN KEY (id_ambito) REFERENCES ambitos_violencia(id_ambito),
    FOREIGN KEY (id_tipo_violencia) REFERENCES tipos_violencia(id_tipo_violencia),
    FOREIGN KEY (id_tipo_contenido) REFERENCES tipos_contenido(id_tipo_contenido),
    FOREIGN KEY (id_ubicacion) REFERENCES ubicaciones(id_ubicacion)
);


--endireh
CREATE TABLE indicadores_endireh (
    id_indicador BIGINT AUTO_INCREMENT PRIMARY KEY,

    id_fuente INT NOT NULL,

    codigo_indicador VARCHAR(80),
    nombre_indicador TEXT NOT NULL,
    categoria_indicador VARCHAR(150),
    ambito VARCHAR(100),
    agresor VARCHAR(150),
    periodo_medicion VARCHAR(100),
    poblacion_objetivo TEXT,

    entidad VARCHAR(150),
    anio YEAR,
    valor DECIMAL(8,2),
    unidad VARCHAR(50) DEFAULT 'porcentaje',
    fecha_referencia DATE,

    datos_extra JSON,
    fecha_registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (id_fuente) REFERENCES fuentes(id_fuente)
);


--siesvim

CREATE TABLE indicadores_siesvim (
    id_siesvim BIGINT AUTO_INCREMENT PRIMARY KEY,

    id_fuente INT NOT NULL,

    tema VARCHAR(150),
    subtema VARCHAR(150),
    nombre_indicador TEXT NOT NULL,

    entidad VARCHAR(150),
    anio YEAR,
    categoria VARCHAR(150),
    valor DECIMAL(8,2),
    unidad VARCHAR(50) DEFAULT 'porcentaje',

    datos_extra JSON,
    fecha_registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (id_fuente) REFERENCES fuentes(id_fuente)
);

--inmujeres

CREATE TABLE indicadores_inmujeres (
    id_indicador BIGINT AUTO_INCREMENT PRIMARY KEY,

    id_fuente INT NOT NULL,

    archivo_origen VARCHAR(100),
    numero_tabla INT,
    nombre_indicador TEXT NOT NULL,
    categoria VARCHAR(150),
    subcategoria VARCHAR(150),

    anio YEAR,
    valor DECIMAL(12,2),
    unidad VARCHAR(50) DEFAULT 'conteo',

    datos_extra JSON,
    fecha_registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (id_fuente) REFERENCES fuentes(id_fuente)
);

CREATE INDEX idx_registros_anio ON registros(anio_publicacion);
CREATE INDEX idx_registros_fuente ON registros(id_fuente);
CREATE INDEX idx_registros_tipo_contenido ON registros(id_tipo_contenido);
CREATE INDEX idx_registros_ubicacion ON registros(id_ubicacion);

CREATE INDEX idx_endireh_anio_entidad ON indicadores_endireh(anio, entidad);
CREATE INDEX idx_siesvim_anio_entidad ON indicadores_siesvim(anio, entidad);
CREATE INDEX idx_inmujeres_anio ON indicadores_inmujeres(anio);


--corrección
USE HUBDATOS;

ALTER TABLE registros
MODIFY fecha_publicacion TEXT;

ALTER TABLE registros

MODIFY usuario TEXT;
DELETE FROM registros;
ALTER TABLE registros AUTO_INCREMENT = 1;