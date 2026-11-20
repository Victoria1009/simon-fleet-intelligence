-- SIMON | Inicialización de esquema y geocercas
-- Ejecutar sobre una base de datos nueva con PostGIS disponible.
-- No ejecutar sobre simon_db existente sin revisar el impacto.

CREATE EXTENSION IF NOT EXISTS postgis;


CREATE TABLE IF NOT EXISTS public.registros_vehiculos
(
    id serial NOT NULL,
    dispositivo_id character varying(50) COLLATE pg_catalog."default" NOT NULL,
    "timestamp" timestamp with time zone NOT NULL,
    latitud double precision NOT NULL,
    longitud double precision NOT NULL,
    velocidad_kmh double precision,
    combustible_pct double precision,
    geometria geometry(Point,4326),
    CONSTRAINT registros_vehiculos_pkey PRIMARY KEY (id),
    CONSTRAINT registros_vehiculos_latitud_check CHECK (latitud >= '-90'::integer::double precision AND latitud <= 90::double precision),
    CONSTRAINT registros_vehiculos_longitud_check CHECK (longitud >= '-180'::integer::double precision AND longitud <= 180::double precision),
    CONSTRAINT registros_vehiculos_velocidad_kmh_check CHECK (velocidad_kmh >= 0::double precision),
    CONSTRAINT registros_vehiculos_combustible_pct_check CHECK (combustible_pct >= 0::double precision AND combustible_pct <= 100::double precision)
);


CREATE TABLE IF NOT EXISTS public.geocercas
(
    id serial NOT NULL,
    nombre character varying(100) COLLATE pg_catalog."default" NOT NULL,
    tipo character varying(50) COLLATE pg_catalog."default" NOT NULL,
    velocidad_max_kmh double precision NOT NULL,
    prioridad integer NOT NULL DEFAULT 1,
    geometria geometry(Geometry,4326) NOT NULL,
    CONSTRAINT geocercas_pkey PRIMARY KEY (id),
    CONSTRAINT geocercas_velocidad_max_kmh_check CHECK (velocidad_max_kmh > 0::double precision)
);


CREATE INDEX IF NOT EXISTS idx_geocercas_geom
    ON public.geocercas USING gist
    (geometria)
;


CREATE TABLE IF NOT EXISTS public.registros_enriquecidos
(
    id serial NOT NULL,
    registro_bronce_id integer NOT NULL,
    dispositivo_id character varying(50) COLLATE pg_catalog."default" NOT NULL,
    "timestamp" timestamp with time zone NOT NULL,
    geometria geometry(Point,4326),
    geocerca_id integer,
    nombre_geocerca character varying(100) COLLATE pg_catalog."default",
    velocidad_kmh double precision,
    velocidad_max_kmh double precision,
    exceso_velocidad boolean NOT NULL,
    combustible_pct double precision,
    autonomia_km double precision,
    distancia_restante_km double precision,
    alerta_combustible boolean NOT NULL,
    driver_score integer NOT NULL,
    fecha_procesamiento timestamp with time zone DEFAULT now(),
    CONSTRAINT registros_enriquecidos_pkey PRIMARY KEY (id),
    CONSTRAINT registros_enriquecidos_registro_bronce_id_key UNIQUE (registro_bronce_id),
    CONSTRAINT registros_enriquecidos_geocerca_id_fkey FOREIGN KEY (geocerca_id)
        REFERENCES public.geocercas (id) MATCH SIMPLE
        ON UPDATE NO ACTION
        ON DELETE NO ACTION,
    CONSTRAINT registros_enriquecidos_registro_bronce_id_fkey FOREIGN KEY (registro_bronce_id)
        REFERENCES public.registros_vehiculos (id) MATCH SIMPLE
        ON UPDATE NO ACTION
        ON DELETE NO ACTION,
    CONSTRAINT registros_enriquecidos_driver_score_check CHECK (driver_score >= 0 AND driver_score <= 100)
);


CREATE INDEX IF NOT EXISTS idx_plata_geom
    ON public.registros_enriquecidos USING gist
    (geometria)
;


CREATE TABLE IF NOT EXISTS public.registros_oro
(
    id bigserial NOT NULL,
    registro_plata_id integer NOT NULL,
    dispositivo_id character varying(50) COLLATE pg_catalog."default" NOT NULL,
    "timestamp" timestamp with time zone NOT NULL,
    latitud double precision,
    longitud double precision,
    geometria geometry(Point,4326),
    velocidad_kmh double precision,
    combustible_pct double precision,
    nombre_geocerca character varying(150) COLLATE pg_catalog."default",
    limite_velocidad double precision,
    exceso_velocidad boolean,
    alerta_combustible boolean,
    driver_score integer,
    fecha_procesamiento timestamp with time zone DEFAULT now(),
    distancia_restante_km double precision,
    autonomia_km double precision,
    CONSTRAINT registros_oro_pkey PRIMARY KEY (id),
    CONSTRAINT registros_oro_registro_plata_id_key UNIQUE (registro_plata_id)
);


CREATE INDEX IF NOT EXISTS idx_oro_excesos
    ON public.registros_oro USING btree
    ("timestamp" DESC NULLS FIRST)

    WHERE exceso_velocidad = true;


CREATE INDEX IF NOT EXISTS idx_oro_geom
    ON public.registros_oro USING gist
    (geometria)
;


CREATE INDEX IF NOT EXISTS idx_oro_vehiculo_fecha
    ON public.registros_oro USING btree
    (dispositivo_id COLLATE pg_catalog."default" ASC NULLS LAST, "timestamp" DESC NULLS FIRST)
;


-- Geocercas originales exportadas desde la base existente

INSERT INTO public.geocercas (id, nombre, tipo, velocidad_max_kmh, prioridad, geometria)
SELECT 1, 'Zona urbana SIMON', 'urbana', 50.0, 1, ST_GeomFromText('POLYGON((-74.085 4.7,-74.085 4.735,-74.055 4.735,-74.055 4.7,-74.085 4.7),(-74.08 4.71,-74.065 4.71,-74.065 4.725,-74.08 4.725,-74.08 4.71))', 4326)
WHERE NOT EXISTS (SELECT 1 FROM public.geocercas WHERE id = 1);

INSERT INTO public.geocercas (id, nombre, tipo, velocidad_max_kmh, prioridad, geometria)
SELECT 2, 'Zona residencial SIMON', 'residencial', 30.0, 3, ST_GeomFromText('POLYGON((-74.08 4.71,-74.08 4.725,-74.065 4.725,-74.065 4.71,-74.08 4.71))', 4326)
WHERE NOT EXISTS (SELECT 1 FROM public.geocercas WHERE id = 2);

INSERT INTO public.geocercas (id, nombre, tipo, velocidad_max_kmh, prioridad, geometria)
SELECT 3, 'Corredor vial SIMON', 'corredor', 60.0, 2, ST_GeomFromText('POLYGON((-74.11 4.64,-74.11 4.675,-74.085 4.675,-74.085 4.64,-74.11 4.64))', 4326)
WHERE NOT EXISTS (SELECT 1 FROM public.geocercas WHERE id = 3);


SELECT setval(pg_get_serial_sequence('public.geocercas', 'id'), COALESCE((SELECT MAX(id) FROM public.geocercas), 1), true);
