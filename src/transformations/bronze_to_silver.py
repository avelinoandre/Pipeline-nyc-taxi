from pyspark.sql import SparkSession
from pyspark.sql.functions import col, to_timestamp

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

def main():
    spark = create_spark_session()

    trips = read_bronze(spark)

    print("BRONZE SCHEMA:")
    trips.printSchema()

    silver = transform_trips(trips)
    silver = drop_duplicates(silver)
    
    print("SILVER SCHEMA:")
    silver.printSchema()
    silver.show(5) # = df.head()

    spark.stop()


if __name__ == "__main__":
    main()