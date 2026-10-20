-- Estrutura inicial da Gold no PostgreSQL.
-- Executar conectado ao banco nyc_taxi.
-- Este script cria tabelas; a carga dos Parquets sera feita separadamente.

BEGIN;

-- Os IDs ja existem na Gold: nao utilizar SERIAL para gerar outros valores.
CREATE TABLE IF NOT EXISTS public.dim_payment_type (
    payment_type INTEGER PRIMARY KEY,
    payment_type_name TEXT NOT NULL
);

-- Sem geometria: a dimensao Gold contem somente os atributos analiticos.
CREATE TABLE IF NOT EXISTS public.dim_zone (
    zone_id INTEGER PRIMARY KEY,
    zone_name TEXT NOT NULL,
    borough TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS public.dim_date (
    date_id INTEGER PRIMARY KEY,
    date DATE NOT NULL UNIQUE,
    year INTEGER NOT NULL,
    quarter INTEGER NOT NULL CHECK (quarter BETWEEN 1 AND 4),
    month INTEGER NOT NULL CHECK (month BETWEEN 1 AND 12),
    day INTEGER NOT NULL CHECK (day BETWEEN 1 AND 31),
    day_of_week INTEGER NOT NULL CHECK (day_of_week BETWEEN 1 AND 7),
    week_of_year INTEGER NOT NULL CHECK (week_of_year BETWEEN 1 AND 53),
    is_weekend BOOLEAN NOT NULL
);

-- Grao: uma linha por viagem da Gold.
CREATE TABLE IF NOT EXISTS public.fact_trips (
    trip_id VARCHAR(64) PRIMARY KEY CHECK (char_length(trip_id) = 64),
    pickup_date_id INTEGER NOT NULL,
    dropoff_date_id INTEGER NOT NULL,
    pickup_zone_id INTEGER NOT NULL,
    dropoff_zone_id INTEGER NOT NULL,
    payment_type INTEGER NOT NULL,
    source_payment_type INTEGER,
    vendor_id INTEGER,
    pickup_datetime TIMESTAMP WITHOUT TIME ZONE NOT NULL,
    dropoff_datetime TIMESTAMP WITHOUT TIME ZONE NOT NULL,
    passenger_count INTEGER,
    trip_distance DOUBLE PRECISION NOT NULL CHECK (trip_distance > 0),
    rate_code INTEGER,
    store_and_fwd_flag TEXT,

    -- NUMERIC nao limita a escala: nao arredondar os valores da Gold na carga.
    -- Valores negativos sao preservados; nao ha regra de exclusao por sinal.
    fare_amount NUMERIC,
    extra NUMERIC,
    mta_tax NUMERIC,
    tip_amount NUMERIC,
    tolls_amount NUMERIC,
    imp_surcharge NUMERIC,
    total_amount NUMERIC,

    -- Codigos originais: podem ser nulos ou nao ter correspondencia na referencia.
    pickup_location_id INTEGER,
    dropoff_location_id INTEGER,
    trip_duration_minutes DOUBLE PRECISION NOT NULL CHECK (trip_duration_minutes > 0),

    CONSTRAINT fk_trips_pickup_date
        FOREIGN KEY (pickup_date_id) REFERENCES public.dim_date (date_id),
    CONSTRAINT fk_trips_dropoff_date
        FOREIGN KEY (dropoff_date_id) REFERENCES public.dim_date (date_id),
    CONSTRAINT fk_trips_pickup_zone
        FOREIGN KEY (pickup_zone_id) REFERENCES public.dim_zone (zone_id),
    CONSTRAINT fk_trips_dropoff_zone
        FOREIGN KEY (dropoff_zone_id) REFERENCES public.dim_zone (zone_id),
    CONSTRAINT fk_trips_payment_type
        FOREIGN KEY (payment_type) REFERENCES public.dim_payment_type (payment_type)
);

COMMIT;
