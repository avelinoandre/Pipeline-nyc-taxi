from pyspark.sql import SparkSession
from pyspark.sql.functions import col, to_timestamp, unix_timestamp, datediff, to_date, count, sum as spark_sum, when


BRONZE_PATH = "data/bronze/taxi_trip_data.csv"
SILVER_PATH = "data/silver/taxi_trips"

def create_spark_session():
    spark =  (
        SparkSession.builder
        .appName("NYC Taxi Bronze to Silver")
        .master("local[*]")
        .getOrCreate()
    )

    return spark

def read_bronze(spark):
    df =(
        spark.read
        .option("header", True) #first line of the csv is a header
        .option("inferSchema", True) #make Spark find the type of th variable
        .csv(BRONZE_PATH)
    )

    return df

def transform_trips(df):
    df = df.withColumn( 
        "pickup_datetime",
        to_timestamp(col("pickup_datetime"))
    )
    df = df.withColumn( 
        "dropoff_datetime",
        to_timestamp(col("dropoff_datetime"))
    )

    return df

def drop_duplicates(df):
    before = df.count()
    df = df.dropDuplicates()
    after = df.count()
    difference = before - after

    print(f"BEFORE DROP_DUPLICATES: {before}")
    print(f"AFTER DROP_DUPLICATES: {after}")
    print(f"TOTAL OF DROPPED DUPLICATES: {difference}")

    return df

def filter_invalid_trip_distance(df):

    before = df.count()

    df = df.filter(col("trip_distance") > 0)

    after = df.count()
    difference = before - after

    print(f"ROWS BEFORE FILTER: {before}")
    print(f"ROWS AFTER FILTER: {after}")
    print(f"ROWS REMOVED WITH TRIP_DISTANCE > 0: {difference}")    

    return df

def create_trip_duration_minutes(df):

    df  = df.withColumn(

        "trip_duration_minutes",
        unix_timestamp(col("dropoff_datetime")) - unix_timestamp(col("pickup_datetime"))
        /60 #coloca-se o /60 no final pq unix_timestamp retorna em segundos, e o /60 divide por 60 transformando assim em minutos

    )

    return  df

def filter_invalid_trip_duration(df):

    df = df.filter(col("trip_duration_minutes") > 0)

    return df

def filter_invalid_24h_duration(df):

    condition1 = datediff(to_date(col("dropoff_datetime")), to_date(col("pickup_datetime"))) == 1

    condition2 = col("trip_duration_minutes").between(1400,1450)

    df = df.filter(
        ~(condition1 & condition2) # ~ pois estou negando essas condições!
    )

    return df

def validate_silver(df):
    metrics = df.agg(
        count("*").alias("total_rows"),

        spark_sum(
            when(col("trip_distance") <= 0, 1).otherwise(0)
        ).alias("invalid_trip_distance"),

        spark_sum(
            when(col("trip_duration_minutes") <= 0, 1).otherwise(0)
        ).alias("invalid_trip_duration")
    ).first()

    if metrics.total_rows == 0:
        raise ValueError("Silver dataset is empty")

    if metrics.invalid_trip_distance > 0:
        raise ValueError("Silver contains invalid trip_distance")

    if metrics.invalid_trip_duration > 0:
        raise ValueError("Silver contains invalid trip_duration")

    print("Silver validation passed")

def main():
    spark = create_spark_session()

    trips = read_bronze(spark)

    print("BRONZE SCHEMA:")
    trips.printSchema()

    silver = transform_trips(trips)
    silver = drop_duplicates(silver)
    silver = filter_invalid_trip_distance(silver)
    silver = create_trip_duration_minutes(silver)
    silver = filter_invalid_trip_duration(silver)
    silver = filter_invalid_24h_duration(silver)

    validate_silver(silver)

    print("SILVER SCHEMA:")
    silver.printSchema()
    silver.show(5) # = df.head()

    spark.stop()


if __name__ == "__main__":
    main()