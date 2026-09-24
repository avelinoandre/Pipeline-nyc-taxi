from pyspark.sql import SparkSession
#from pyspark.sql.functions import col, to_timestamp, unix_timestamp, datediff, to_date, count, sum as spark_sum, when


SILVER_PATH = "data/silver/taxi_trips"
GOLD_PATH = "data/gold"

#GOAL
# Silver
#   ↓
#   ├── fact_trips
#   ├── dim_zone
#   ├── dim_payment_type
#   └── dim_date

def create_spark_session():
    spark =  (

        SparkSession.builder
        .appName("NYC Taxi Silver to Gold")
        .master("local[*]")
        .getOrCreate()

    )

    return spark

def read_silver(spark):
    df =(

        spark.read
        .parquet(SILVER_PATH)

    )

    return df

def validate_dim_payment_type(silver, dim_payment_type):
    df = (
        silver
        .select("payment_type")
        .distinct()
    )

    unknown_payment_types = df.join(
        dim_payment_type,
        on = "payment_type",
        how = "left_anti" #to see whats is missing in our dim
    )

    return unknown_payment_types


def create_dim_payment_type(spark):
    data = [

        (1, "Credit Card"),
        (2, "Cash"),
        (3, "No Charge"),
        (4, "Dispute")

    ]

    columns = [

        "payment_type",
        "payment_type_name"

    ]

    dim_payment_type = spark.createDataFrame(

        data,
        columns

    )

    return dim_payment_type

def main():
    spark = create_spark_session()

    silver = read_silver(spark)

    silver.printSchema()
    silver.show(5)

    dim_payment_type = create_dim_payment_type(spark)
    dim_payment_type.show()

    unknown_payment_types = validate_dim_payment_type(silver,dim_payment_type)
    unknown_payment_types.show()
    
    spark.stop()

if __name__ == "__main__":
    main()