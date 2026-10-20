-- Pergunta: quais dias e horarios concentram embarques em cada zona?
-- Grao: zona x dia da semana x hora. Horarios preservados da fonte/Gold.
-- Denominador: TODOS os dias observados daquele dia da semana no recorte,
-- inclusive dias sem viagem nessa zona/hora. Nao e produtividade por taxi.
WITH parameters AS (
    SELECT DATE '2018-01-01' AS start_date, DATE '2019-01-01' AS end_date
),
trips AS (
    SELECT t.pickup_zone_id, d.date, d.day_of_week,
           EXTRACT(HOUR FROM t.pickup_datetime)::integer AS pickup_hour
    FROM public.fact_trips AS t
    JOIN public.dim_date AS d ON t.pickup_date_id = d.date_id
    CROSS JOIN parameters AS p
    WHERE d.date >= p.start_date AND d.date < p.end_date
),
observed_days AS (
    SELECT day_of_week, COUNT(DISTINCT date) AS day_count
    FROM trips
    GROUP BY day_of_week
),
zone_activity AS (
    SELECT pickup_zone_id, day_of_week, pickup_hour, COUNT(*) AS trip_count
    FROM trips
    GROUP BY pickup_zone_id, day_of_week, pickup_hour
),
zones AS (
    SELECT DISTINCT pickup_zone_id FROM zone_activity
)
SELECT
    z.zone_id, z.zone_name, z.borough,
    z.zone_id <> -1 AS is_mapped_zone,
    o.day_of_week,
    CASE o.day_of_week
        WHEN 1 THEN 'Domingo' WHEN 2 THEN 'Segunda-feira'
        WHEN 3 THEN 'Terca-feira' WHEN 4 THEN 'Quarta-feira'
        WHEN 5 THEN 'Quinta-feira' WHEN 6 THEN 'Sexta-feira'
        WHEN 7 THEN 'Sabado'
    END AS weekday_name,
    h.pickup_hour,
    COALESCE(a.trip_count, 0) AS trip_count,
    o.day_count AS observed_weekdays,
    ROUND(COALESCE(a.trip_count, 0)::numeric / NULLIF(o.day_count, 0), 2)
        AS trips_per_observed_weekday
FROM zones AS zones
JOIN public.dim_zone AS z ON zones.pickup_zone_id = z.zone_id
CROSS JOIN observed_days AS o
CROSS JOIN generate_series(0, 23) AS h(pickup_hour)
LEFT JOIN zone_activity AS a
    ON a.pickup_zone_id = z.zone_id
   AND a.day_of_week = o.day_of_week
   AND a.pickup_hour = h.pickup_hour
ORDER BY z.zone_id, o.day_of_week, h.pickup_hour;
