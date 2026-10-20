-- Pergunta: onde se concentram os embarques registrados em 2018?
-- Grao: zona de embarque. Participacao sobre TODAS as viagens do recorte.
-- A zona -1 permanece na reconciliacao, mas nao identifica um local para o piloto.
WITH parameters AS (
    SELECT DATE '2018-01-01' AS start_date, DATE '2019-01-01' AS end_date
),
zone_activity AS (
    SELECT t.pickup_zone_id, COUNT(*) AS trip_count
    FROM public.fact_trips AS t
    JOIN public.dim_date AS d ON t.pickup_date_id = d.date_id
    CROSS JOIN parameters AS p
    WHERE d.date >= p.start_date AND d.date < p.end_date
    GROUP BY t.pickup_zone_id
),
observed_days AS (
    SELECT COUNT(DISTINCT t.pickup_date_id) AS day_count
    FROM public.fact_trips AS t
    JOIN public.dim_date AS d ON t.pickup_date_id = d.date_id
    CROSS JOIN parameters AS p
    WHERE d.date >= p.start_date AND d.date < p.end_date
)
SELECT
    z.zone_id,
    z.zone_name,
    z.borough,
    z.zone_id <> -1 AS is_mapped_zone,
    a.trip_count,
    ROUND(100.0 * a.trip_count / NULLIF(SUM(a.trip_count) OVER (), 0), 4) AS share_of_dataset_pct,
    o.day_count AS observed_days,
    ROUND(a.trip_count::numeric / NULLIF(o.day_count, 0), 2) AS trips_per_observed_day
FROM zone_activity AS a
JOIN public.dim_zone AS z ON a.pickup_zone_id = z.zone_id
CROSS JOIN observed_days AS o
ORDER BY a.trip_count DESC, z.zone_id;
