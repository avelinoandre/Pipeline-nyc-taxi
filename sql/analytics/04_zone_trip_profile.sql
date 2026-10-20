-- Pergunta: como tarifa, total cobrado, distancia e duracao variam por zona?
-- Grao: zona de embarque em 2018. Valores cobrados NAO representam lucro.
-- Medias e medianas incluem valores nao positivos; nulos sao ignorados pelo SQL.
-- Contagens informam os denominadores. Nenhum corte adicional de outlier.
WITH parameters AS (
    SELECT DATE '2018-01-01' AS start_date, DATE '2019-01-01' AS end_date
)
SELECT
    z.zone_id, z.zone_name, z.borough,
    z.zone_id <> -1 AS is_mapped_zone,
    COUNT(*) AS trip_count,
    COUNT(t.fare_amount) AS trips_with_fare,
    COUNT(*) FILTER (WHERE t.fare_amount <= 0) AS nonpositive_fare_trips,
    ROUND(SUM(t.fare_amount), 2) AS recorded_fare_sum_usd,
    ROUND(AVG(t.fare_amount), 2) AS avg_fare_usd,
    ROUND((PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY t.fare_amount))::numeric, 2) AS median_fare_usd,
    COUNT(t.total_amount) AS trips_with_total,
    COUNT(*) FILTER (WHERE t.total_amount <= 0) AS nonpositive_total_trips,
    ROUND(SUM(t.total_amount), 2) AS recorded_total_sum_usd,
    ROUND(AVG(t.total_amount), 2) AS avg_total_usd,
    ROUND((PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY t.total_amount))::numeric, 2) AS median_total_usd,
    ROUND(AVG(t.trip_distance)::numeric, 2) AS avg_distance_miles,
    ROUND((PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY t.trip_distance))::numeric, 2) AS median_distance_miles,
    ROUND(AVG(t.trip_duration_minutes)::numeric, 2) AS avg_duration_minutes,
    ROUND((PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY t.trip_duration_minutes))::numeric, 2) AS median_duration_minutes
FROM public.fact_trips AS t
JOIN public.dim_date AS d ON t.pickup_date_id = d.date_id
JOIN public.dim_zone AS z ON t.pickup_zone_id = z.zone_id
CROSS JOIN parameters AS p
WHERE d.date >= p.start_date AND d.date < p.end_date
GROUP BY z.zone_id, z.zone_name, z.borough
ORDER BY trip_count DESC, z.zone_id;
