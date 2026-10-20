-- Auditoria da base inteira, antes do recorte de negocio.
-- Grao: ano de embarque. Dias observados nao comprovam cobertura completa.
SELECT
    d.year AS pickup_year,
    MIN(d.date) AS first_pickup_date,
    MAX(d.date) AS last_pickup_date,
    COUNT(*) AS trip_count,
    COUNT(DISTINCT d.date) AS observed_days,
    COUNT(*) FILTER (WHERE t.pickup_zone_id = -1) AS unknown_pickup_zone_trips,
    COUNT(*) FILTER (WHERE t.fare_amount IS NULL) AS null_fare_trips,
    COUNT(*) FILTER (WHERE t.fare_amount <= 0) AS nonpositive_fare_trips,
    COUNT(*) FILTER (WHERE t.total_amount IS NULL) AS null_total_trips,
    COUNT(*) FILTER (WHERE t.total_amount <= 0) AS nonpositive_total_trips,
    MAX(t.trip_distance) AS max_distance_miles,
    MAX(t.trip_duration_minutes) AS max_duration_minutes
FROM public.fact_trips AS t
JOIN public.dim_date AS d ON t.pickup_date_id = d.date_id
GROUP BY d.year
ORDER BY d.year;
