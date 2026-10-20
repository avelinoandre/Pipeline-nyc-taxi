-- Pergunta: como o movimento registrado varia ao longo de 2018?
-- Grao: mes de embarque. Zero significa ausencia de registros na base.
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
activity AS (
    SELECT
        DATE_TRUNC('month', d.date)::date AS month,
        COUNT(*) AS trip_count,
        COUNT(DISTINCT d.date) AS observed_days,
        COUNT(*) FILTER (WHERE t.pickup_zone_id = -1) AS unknown_pickup_zone_trips
    FROM public.fact_trips AS t
    JOIN public.dim_date AS d ON t.pickup_date_id = d.date_id
    CROSS JOIN parameters AS p
    WHERE d.date >= p.start_date AND d.date < p.end_date
    GROUP BY 1
)
SELECT
    m.month,
    EXTRACT(DAY FROM m.month + INTERVAL '1 month - 1 day')::integer AS calendar_days,
    COALESCE(a.observed_days, 0) AS observed_days,
    COALESCE(a.trip_count, 0) AS trip_count,
    ROUND(a.trip_count::numeric / NULLIF(a.observed_days, 0), 2) AS trips_per_observed_day,
    COALESCE(a.unknown_pickup_zone_trips, 0) AS unknown_pickup_zone_trips
FROM months AS m
LEFT JOIN activity AS a ON m.month = a.month
ORDER BY m.month;
