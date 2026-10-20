from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    coalesce, col, count, countDistinct, date_format, dayofmonth,
    dayofweek, lit, month, quarter, sha2, struct, to_date, to_json,
    weekofyear, when, year,
)


SILVER_PATH = "data/silver/taxi_trips"
ZONE_PATH = "data/bronze/taxi_zone_geo.csv"
GOLD_PATH = "data/gold"
UNKNOWN_ID = -1


def create_spark_session():
    spark = (
        SparkSession.builder
        .appName("NYC Taxi Silver to Gold")
        .master("local[*]")
        .getOrCreate()
    )

    return spark


def read_silver(spark):
    df = spark.read.parquet(SILVER_PATH)

    return df


def read_zones(spark):
    df = (
        spark.read
        .option("header", True)
        .schema("zone_id int, zone_name string, borough string, zone_geom string")
        .csv(ZONE_PATH)
    )

    return df


def create_dim_payment_type(spark):
    # TLC data dictionary: https://www.nyc.gov/assets/tlc/downloads/pdf/data_dictionary_trip_records_yellow.pdf
    data = [
        (UNKNOWN_ID, "Unknown / Unmapped"),
        (1, "Credit Card"),
        (2, "Cash"),
        (3, "No Charge"),
        (4, "Dispute"),
        (5, "Unknown"),
        (6, "Voided Trip"),
    ]

    dim_payment_type = spark.createDataFrame(
        data,
        "payment_type int, payment_type_name string",
    )

    return dim_payment_type


def validate_dim_payment_type(silver, dim_payment_type):
    df = silver.select("payment_type").distinct()

    unknown_payment_types = df.join(
        dim_payment_type,
        on="payment_type",
        how="left_anti",
    )

    return unknown_payment_types


def create_dim_zone(spark, zones):
    # As geometrias sao diferentes, mas os atributos analiticos podem ser iguais.
    dim_zone = zones.select("zone_id", "zone_name", "borough").dropDuplicates()

    unknown_zone = spark.createDataFrame(
        [(UNKNOWN_ID, "Unknown", "Unknown")],
        "zone_id int, zone_name string, borough string",
    )

    dim_zone = dim_zone.unionByName(unknown_zone)

    return dim_zone


def create_dim_date(silver):
    pickup_dates = silver.select(to_date(col("pickup_datetime")).alias("date"))
    dropoff_dates = silver.select(to_date(col("dropoff_datetime")).alias("date"))

    dim_date = pickup_dates.unionByName(dropoff_dates).distinct()

    dim_date = (
        dim_date
        .withColumn("date_id", date_format(col("date"), "yyyyMMdd").cast("int"))
        .withColumn("year", year(col("date")))
        .withColumn("quarter", quarter(col("date")))
        .withColumn("month", month(col("date")))
        .withColumn("day", dayofmonth(col("date")))
        .withColumn("day_of_week", dayofweek(col("date")))
        .withColumn("week_of_year", weekofyear(col("date")))
        .withColumn("is_weekend", col("day_of_week").isin(1, 7))
        .select(
            "date_id", "date", "year", "quarter", "month", "day",
            "day_of_week", "week_of_year", "is_weekend",
        )
    )

    return dim_date


def create_fact_trips(silver, dim_payment_type, dim_zone):
    # O hash usa a linha Silver completa; a mesma viagem recebe o mesmo ID.
    df = silver.withColumn(
        "trip_id",
        sha2(
            to_json(
                struct(*[col(name) for name in sorted(silver.columns)]),
                {"timeZone": "UTC", "timestampFormat": "yyyy-MM-dd'T'HH:mm:ss.SSSSSSXXX", "ignoreNullFields": "false"},
            ),
            256,
        ),
    )

    df = df.withColumn("source_payment_type", col("payment_type"))

    payment_types = dim_payment_type.select(
        "payment_type", lit(True).alias("known_payment_type")
    )
    df = df.join(payment_types, on="payment_type", how="left")
    # As chaves reconhecidas ficam iguais; as demais apontam para Unknown.
    df = df.withColumn(
        "payment_type",
        when(col("known_payment_type"), col("payment_type")).otherwise(UNKNOWN_ID),
    ).drop("known_payment_type")

    pickup_zones = dim_zone.select(col("zone_id").alias("pickup_zone_id"))
    dropoff_zones = dim_zone.select(col("zone_id").alias("dropoff_zone_id"))

    df = df.join(pickup_zones, df.pickup_location_id == pickup_zones.pickup_zone_id, "left")
    df = df.join(dropoff_zones, df.dropoff_location_id == dropoff_zones.dropoff_zone_id, "left")

    df = (
        df
        .withColumn("pickup_zone_id", coalesce(col("pickup_zone_id"), lit(UNKNOWN_ID)))
        .withColumn("dropoff_zone_id", coalesce(col("dropoff_zone_id"), lit(UNKNOWN_ID)))
        .withColumn("pickup_date_id", date_format(col("pickup_datetime"), "yyyyMMdd").cast("int"))
        .withColumn("dropoff_date_id", date_format(col("dropoff_datetime"), "yyyyMMdd").cast("int"))
        .select(
            "trip_id", "pickup_date_id", "dropoff_date_id",
            "pickup_zone_id", "dropoff_zone_id", "payment_type", "source_payment_type",
            *[name for name in silver.columns if name != "payment_type"],
        )
    )

    return df


def validate_dimension(df, key):
    metrics = df.agg(
        count("*").alias("total_rows"),
        count(key).alias("nonnull_keys"),
        countDistinct(key).alias("unique_keys"),
    ).first()

    if metrics.total_rows == 0:
        raise ValueError(f"Dimension {key} is empty")

    if metrics.total_rows != metrics.nonnull_keys:
        raise ValueError(f"Dimension {key} contains null keys")

    if metrics.total_rows != metrics.unique_keys:
        raise ValueError(f"Dimension {key} contains duplicate or conflicting keys")

    print(f"Dimension {key} validation passed: {metrics.total_rows} rows")


def validate_fact_trips(silver, fact_trips):
    # Distribuir somente os IDs evita acumular muitos valores distintos por tarefa.
    metrics = (
        fact_trips.select("trip_id")
        .repartition(64, "trip_id")
        .agg(
            count("*").alias("total_rows"),
            count("trip_id").alias("nonnull_keys"),
            countDistinct("trip_id").alias("unique_keys"),
        ).first()
    )

    if metrics.total_rows == 0:
        raise ValueError("fact_trips is empty")

    if metrics.total_rows != silver.count():
        raise ValueError("fact_trips must contain exactly one row per Silver trip")

    if metrics.total_rows != metrics.nonnull_keys or metrics.total_rows != metrics.unique_keys:
        raise ValueError("fact_trips contains null or duplicate trip_id values")

    print(f"fact_trips validation passed: {metrics.total_rows} rows")


def validate_foreign_key(fact_trips, column, dimension, key):
    unknown_keys = (
        fact_trips.select(column).distinct()
        .join(
            dimension.select(col(key).alias(column)),
            on=column,
            how="left_anti",
        )
    )

    if unknown_keys.limit(1).count() > 0:
        raise ValueError(f"fact_trips contains unmapped foreign keys: {column}")


def validate_gold(silver, fact_trips, dim_payment_type, dim_zone, dim_date):
    validate_dimension(dim_payment_type, "payment_type")
    validate_dimension(dim_zone, "zone_id")
    validate_dimension(dim_date, "date_id")
    validate_fact_trips(silver, fact_trips)

    validate_foreign_key(fact_trips, "payment_type", dim_payment_type, "payment_type")
    validate_foreign_key(fact_trips, "pickup_zone_id", dim_zone, "zone_id")
    validate_foreign_key(fact_trips, "dropoff_zone_id", dim_zone, "zone_id")
    validate_foreign_key(fact_trips, "pickup_date_id", dim_date, "date_id")
    validate_foreign_key(fact_trips, "dropoff_date_id", dim_date, "date_id")

    print("Gold validation passed")


def write_gold(df, table_name):
    df.write.mode("overwrite").parquet(f"{GOLD_PATH}/{table_name}")


def main():
    spark = create_spark_session()

    try:
        print("SPARK SESSION TIME ZONE:", spark.conf.get("spark.sql.session.timeZone"))
        silver = read_silver(spark)
        zones = read_zones(spark)

        dim_payment_type = create_dim_payment_type(spark)
        dim_zone = create_dim_zone(spark, zones)
        dim_date = create_dim_date(silver)

        print("SOURCE PAYMENT TYPES WITHOUT A MAPPING (NULL INCLUDED):")
        validate_dim_payment_type(silver, dim_payment_type).show()

        fact_trips = create_fact_trips(silver, dim_payment_type, dim_zone)
        validate_gold(silver, fact_trips, dim_payment_type, dim_zone, dim_date)

        write_gold(dim_payment_type, "dim_payment_type")
        write_gold(dim_zone, "dim_zone")
        write_gold(dim_date, "dim_date")
        write_gold(fact_trips, "fact_trips")

        print("VALIDATING SAVED GOLD PARQUETS:")
        validate_gold(
            silver,
            spark.read.parquet(f"{GOLD_PATH}/fact_trips"),
            spark.read.parquet(f"{GOLD_PATH}/dim_payment_type"),
            spark.read.parquet(f"{GOLD_PATH}/dim_zone"),
            spark.read.parquet(f"{GOLD_PATH}/dim_date"),
        )
    finally:
        spark.stop()


if __name__ == "__main__":
    main()
