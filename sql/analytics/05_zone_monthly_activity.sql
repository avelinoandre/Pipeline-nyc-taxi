-- Pergunta: o movimento relativo das zonas se mantem nos meses disponiveis?
-- Grao: zona de embarque x mes. Inclui meses sem registros para cada zona observada.
-- Participacao e relativa ao dataset no mes, sem extrapolacao para o mercado.
WITH parameters AS (
    SELECT DATE '2018-01-01' AS start_date, DATE '2019-01-01' AS end_date
),
months AS (
    SELECT month_start::date AS month
    FROM parameters AS p
    CROSS JOIN LATERAL generate_series(
        p.start_date, p.end_date - INTERVAL '1 month', INTERVAL '1 month'
    ) AS month_start
),
trips AS (
    SELECT t.pickup_zone_id, d.date, DATE_TRUNC('month', d.date)::date AS month
    FROM public.fact_trips AS t
    JOIN public.dim_date AS d ON t.pickup_date_id = d.date_id
    CROSS JOIN parameters AS p
    WHERE d.date >= p.start_date AND d.date < p.end_date
),
monthly_totals AS (
    SELECT month, COUNT(*) AS trip_count, COUNT(DISTINCT date) AS observed_days
    FROM trips
    GROUP BY month
),
zone_activity AS (
    SELECT pickup_zone_id, month, COUNT(*) AS trip_count
    FROM trips
    GROUP BY pickup_zone_id, month
),
zones AS (
    SELECT DISTINCT pickup_zone_id FROM zone_activity
)
SELECT
    z.zone_id, z.zone_name, z.borough,
    z.zone_id <> -1 AS is_mapped_zone,
    m.month,
    COALESCE(a.trip_count, 0) AS trip_count,
    COALESCE(t.trip_count, 0) AS dataset_month_trip_count,
    COALESCE(t.observed_days, 0) AS observed_days,
    ROUND(COALESCE(a.trip_count, 0)::numeric / NULLIF(t.observed_days, 0), 2)
        AS trips_per_observed_day,
    ROUND(100.0 * COALESCE(a.trip_count, 0) / NULLIF(t.trip_count, 0), 4)
        AS share_of_month_dataset_pct
FROM zones AS zones
JOIN public.dim_zone AS z ON zones.pickup_zone_id = z.zone_id
CROSS JOIN months AS m
LEFT JOIN monthly_totals AS t ON t.month = m.month
LEFT JOIN zone_activity AS a ON a.pickup_zone_id = z.zone_id AND a.month = m.month
ORDER BY z.zone_id, m.month;
