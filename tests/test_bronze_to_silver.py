import unittest
from datetime import datetime, timedelta

from pyspark.sql import SparkSession
from pyspark.sql.types import DoubleType, StructField, StructType, TimestampType

from src.transformations.bronze_to_silver import (
    create_trip_duration_minutes,
    filter_invalid_24h_duration,
    filter_invalid_trip_duration,
    validate_silver,
)


class SilverTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.spark = (
            SparkSession.builder.master("local[2]")
            .appName("NYC Taxi Silver regression tests")
            .getOrCreate()
        )
        cls.spark.sparkContext.setLogLevel("ERROR")
        cls.schema = StructType([
            StructField("pickup_datetime", TimestampType(), True),
            StructField("dropoff_datetime", TimestampType(), True),
            StructField("trip_distance", DoubleType(), True),
        ])

    @classmethod
    def tearDownClass(cls):
        cls.spark.stop()

    def trips(self, durations):
        pickup = datetime(2018, 1, 1, 12)
        return self.spark.createDataFrame(
            [(pickup, pickup + timedelta(minutes=value), 1.0) for value in durations],
            self.schema,
        )

    def test_duration_converts_entire_difference_to_minutes(self):
        actual = create_trip_duration_minutes(self.trips([10, 1.5, 0, -5]))
        self.assertCountEqual(
            [row.trip_duration_minutes for row in actual.collect()],
            [10.0, 1.5, 0.0, -5.0],
        )

    def test_duration_filters_remove_nonpositive_and_next_day_rollover(self):
        actual = create_trip_duration_minutes(
            self.trips([-5, 0, 10, 1399, 1400, 1440, 1450, 1451, 2880])
        )
        actual = filter_invalid_24h_duration(filter_invalid_trip_duration(actual))
        self.assertCountEqual(
            [row.trip_duration_minutes for row in actual.collect()],
            [10.0, 1399.0, 1451.0, 2880.0],
        )

    def test_validation_accepts_correct_duration_and_rejects_old_formula(self):
        from pyspark.sql.functions import col, unix_timestamp

        source = self.trips([10])
        validate_silver(create_trip_duration_minutes(source))
        wrong = source.withColumn(
            "trip_duration_minutes",
            unix_timestamp(col("dropoff_datetime"))
            - unix_timestamp(col("pickup_datetime")) / 60,
        )
        with self.assertRaisesRegex(ValueError, "inconsistent"):
            validate_silver(wrong)

    def test_validation_rejects_empty_and_nonpositive_duration(self):
        with self.assertRaisesRegex(ValueError, "empty"):
            validate_silver(create_trip_duration_minutes(self.trips([])))
        for duration in [0, -5]:
            with self.subTest(duration=duration):
                with self.assertRaisesRegex(ValueError, "invalid trip_duration"):
                    validate_silver(create_trip_duration_minutes(self.trips([duration])))

    def test_validation_rejects_invalid_or_null_distance_and_null_timestamp(self):
        pickup = datetime(2018, 1, 1, 12)
        for distance in [0.0, -1.0, None]:
            with self.subTest(distance=distance):
                source = self.spark.createDataFrame(
                    [(pickup, pickup + timedelta(minutes=10), distance)], self.schema
                )
                with self.assertRaisesRegex(ValueError, "invalid trip_distance"):
                    validate_silver(create_trip_duration_minutes(source))
        source = self.spark.createDataFrame([(pickup, None, 1.0)], self.schema)
        with self.assertRaisesRegex(ValueError, "invalid trip_duration"):
            validate_silver(create_trip_duration_minutes(source))


if __name__ == "__main__":
    unittest.main()
