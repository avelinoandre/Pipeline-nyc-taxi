-- Consultas de inspecao: podem ser abertas e executadas no pgAdmin.
-- A primeira consulta deve retornar as quatro tabelas.
SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'public'
  AND table_name IN ('dim_payment_type', 'dim_zone', 'dim_date', 'fact_trips')
ORDER BY table_name;

-- Conferir os tipos e a obrigatoriedade das colunas.
SELECT table_name, ordinal_position, column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_schema = 'public'
  AND table_name IN ('dim_payment_type', 'dim_zone', 'dim_date', 'fact_trips')
ORDER BY table_name, ordinal_position;

-- Conferir chaves primarias, estrangeiras e regras de validacao.
SELECT
    conrelid::regclass AS table_name,
    conname AS constraint_name,
    pg_get_constraintdef(oid) AS definition
FROM pg_constraint
WHERE connamespace = 'public'::regnamespace
  AND conrelid IN (
      'public.dim_payment_type'::regclass,
      'public.dim_zone'::regclass,
      'public.dim_date'::regclass,
      'public.fact_trips'::regclass
  )
ORDER BY conrelid::regclass::text, conname;

-- Comparar estas contagens com os metadados dos Parquets Gold apos a carga.
SELECT 'dim_payment_type' AS table_name, COUNT(*) AS total_rows FROM public.dim_payment_type
UNION ALL
SELECT 'dim_zone', COUNT(*) FROM public.dim_zone
UNION ALL
SELECT 'dim_date', COUNT(*) FROM public.dim_date
UNION ALL
SELECT 'fact_trips', COUNT(*) FROM public.fact_trips;
