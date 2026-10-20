from pathlib import Path

import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.csv as csv
import pyarrow.parquet as pq
import psycopg
from psycopg import sql
from dotenv import dotenv_values


GOLD_PATH = Path("data/gold")
ENV_PATH = Path(".env.postgres")
BATCH_SIZE = 50000
TABLE_NAMES = ["dim_payment_type", "dim_zone", "dim_date", "fact_trips"]
# A Gold atual foi gerada pelo Spark com esse fuso de sessao.
GOLD_TIME_ZONE = "America/Sao_Paulo"


def create_connection():
    settings = dotenv_values(ENV_PATH)
    required = ["POSTGRES_DB", "POSTGRES_USER", "POSTGRES_PASSWORD"]

    if any(not settings.get(name) for name in required):
        raise ValueError("Configure POSTGRES_DB, POSTGRES_USER and POSTGRES_PASSWORD in .env.postgres")

    connection = psycopg.connect(
        host=settings.get("POSTGRES_HOST", "127.0.0.1"),
        port=settings.get("POSTGRES_PORT", "5432"),
        dbname=settings["POSTGRES_DB"],
        user=settings["POSTGRES_USER"],
        password=settings["POSTGRES_PASSWORD"],
        application_name="nyc_taxi_gold_load",
        connect_timeout=10,
        autocommit=True,
    )

    return connection


def read_gold(gold_path=GOLD_PATH):
    datasets = {}
    expected_counts = {}

    for table_name in TABLE_NAMES:
        dataset = pq.ParquetDataset(Path(gold_path) / table_name)
        total_rows = sum(fragment.count_rows() for fragment in dataset.fragments)

        if total_rows == 0:
            raise ValueError(f"Gold table is empty: {table_name}")

        for fragment in dataset.fragments:
            if not fragment.physical_schema.equals(dataset.schema, check_metadata=False):
                raise ValueError(f"Gold files have different schemas: {table_name}")

        datasets[table_name] = dataset
        expected_counts[table_name] = total_rows

    return datasets, expected_counts


def validate_columns(connection, datasets, schema="public"):
    for table_name, dataset in datasets.items():
        rows = connection.execute(
            """SELECT column_name FROM information_schema.columns
               WHERE table_schema = %s AND table_name = %s
               ORDER BY ordinal_position""",
            (schema, table_name),
        ).fetchall()

        columns = [row[0] for row in rows]
        if columns != dataset.schema.names:
            raise ValueError(f"PostgreSQL columns differ from Gold: {table_name}. Check sql/create_tables.sql")


def prepare_batch(batch):
    # INT96 do Spark e lido sem fuso pelo Arrow. Reproduzir os horarios da sessao
    # que gerou as chaves de datas, em vez de deslocar as viagens no calendario.
    for name in ["pickup_datetime", "dropoff_datetime"]:
        index = batch.schema.get_field_index(name)
        if index < 0:
            continue

        timestamps = batch.column(index)
        if timestamps.type.tz is None:
            timestamps = pc.assume_timezone(timestamps, "UTC")

        timestamps = timestamps.cast(pa.timestamp(timestamps.type.unit, tz=GOLD_TIME_ZONE))
        timestamps = pc.local_timestamp(timestamps).cast(pa.timestamp("us"), safe=True)
        batch = batch.set_column(index, name, timestamps)

    return batch


def load_table(connection, table_name, dataset, total_rows, schema="public"):
    columns = sql.SQL(", ").join(sql.Identifier(name) for name in dataset.schema.names)
    statement = sql.SQL("COPY {} ({}) FROM STDIN WITH (FORMAT CSV)").format(
        sql.Identifier(schema, table_name), columns,
    )

    loaded_rows = 0
    next_report = 1000000
    options = csv.WriteOptions(include_header=False)

    with connection.cursor() as cursor:
        for fragment in dataset.fragments:
            for batch in fragment.to_batches(batch_size=BATCH_SIZE, use_threads=False):
                batch = prepare_batch(batch)
                output = pa.BufferOutputStream()
                csv.write_csv(batch, output, write_options=options)

                # Um COPY por lote limita os eventos de verificacao das FKs.
                # Todos os lotes continuam dentro da mesma transacao da carga.
                with cursor.copy(statement) as copy:
                    copy.write(output.getvalue().to_pybytes())

                loaded_rows += batch.num_rows
                if loaded_rows >= next_report:
                    print(f"{table_name}: {loaded_rows}/{total_rows} rows sent", flush=True)
                    next_report += 1000000


    if loaded_rows != total_rows:
        raise ValueError(f"Source row count changed while loading: {table_name}")

    print(f"{table_name}: {loaded_rows} rows sent", flush=True)


def validate_load(connection, expected_counts, schema="public"):
    for table_name in TABLE_NAMES:
        count = connection.execute(
            sql.SQL("SELECT COUNT(*) FROM {}").format(sql.Identifier(schema, table_name))
        ).fetchone()[0]

        if count != expected_counts[table_name]:
            raise ValueError(f"Row count mismatch: {table_name}, expected {expected_counts[table_name]}, got {count}")

        print(f"PostgreSQL count validated: {table_name} = {count}", flush=True)

    mismatched_dates = connection.execute(
        sql.SQL("""SELECT COUNT(*)
            FROM {} AS trips
            JOIN {} AS pickup ON trips.pickup_date_id = pickup.date_id
            JOIN {} AS dropoff ON trips.dropoff_date_id = dropoff.date_id
            WHERE trips.pickup_datetime::date <> pickup.date
               OR trips.dropoff_datetime::date <> dropoff.date""").format(
            sql.Identifier(schema, "fact_trips"),
            sql.Identifier(schema, "dim_date"),
            sql.Identifier(schema, "dim_date"),
        )
    ).fetchone()[0]

    if mismatched_dates:
        raise ValueError("Trip timestamps do not match dim_date; check GOLD_TIME_ZONE")

    print("Timestamp/date-key consistency validated", flush=True)


def load_gold(connection, gold_path=GOLD_PATH, schema="public"):
    # Conferir os arquivos antes de modificar o banco.
    datasets, expected_counts = read_gold(gold_path)

    # COMMIT somente depois da carga completa e das validacoes.
    # Se houver erro, inclusive depois do TRUNCATE, o bloco executa ROLLBACK.
    with connection.transaction():
        connection.execute("SET LOCAL lock_timeout = '10s'")
        validate_columns(connection, datasets, schema)

        tables = sql.SQL(", ").join(sql.Identifier(schema, name) for name in TABLE_NAMES)
        connection.execute(sql.SQL("TRUNCATE TABLE {}").format(tables))

        for table_name in TABLE_NAMES:
            load_table(connection, table_name, datasets[table_name], expected_counts[table_name], schema)

        validate_load(connection, expected_counts, schema)

    print("Gold load committed successfully", flush=True)
    return expected_counts


def main():
    with create_connection() as connection:
        load_gold(connection)

        # Atualizar estatisticas para o planejador das consultas SQL.
        for table_name in TABLE_NAMES:
            connection.execute(sql.SQL("ANALYZE {}").format(sql.Identifier("public", table_name)))

    print("PostgreSQL statistics updated", flush=True)


if __name__ == "__main__":
    main()
