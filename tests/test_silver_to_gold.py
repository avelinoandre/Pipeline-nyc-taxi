import tempfile
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from pyspark.sql import SparkSession
from pyspark.sql.functions import col

from src.transformations import silver_to_gold as gold


class GoldTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.spark = (
            SparkSession.builder.master("local[2]")
            .appName("NYC Taxi Gold tests")
            .config("spark.sql.session.timeZone", "UTC")
            .config("spark.sql.shuffle.partitions", "2")
            .getOrCreate()
        )
        cls.spark.sparkContext.setLogLevel("ERROR")

    @classmethod
    def tearDownClass(cls):
        cls.spark.stop()

    def setUp(self):
        self.silver = self.spark.createDataFrame(
            [
                (datetime(2018, 12, 31, 23, 50, tzinfo=timezone.utc), datetime(2019, 1, 1, 0, 10, tzinfo=timezone.utc), 1, 1, 2, 2.0, 20.0, 20.0),
                (datetime(2019, 1, 1, 12, tzinfo=timezone.utc), datetime(2019, 1, 1, 12, 10, tzinfo=timezone.utc), 99, 999, None, 1.0, 10.0, 10.0),
                (datetime(2019, 1, 2, 12, tzinfo=timezone.utc), datetime(2019, 1, 2, 12, 10, tzinfo=timezone.utc), None, None, 1, 1.0, 11.0, 10.0),
            ],
            "pickup_datetime timestamp, dropoff_datetime timestamp, payment_type int, "
            "pickup_location_id int, dropoff_location_id int, trip_distance double, "
            "total_amount double, trip_duration_minutes double",
        )
        self.zones = self.spark.createDataFrame(
            [(1, "Zone One", "Queens", "polygon-a"),
             (1, "Zone One", "Queens", "polygon-b"),
             (2, "Zone Two", "Manhattan", "polygon-c")],
            ["zone_id", "zone_name", "borough", "zone_geom"],
        )
        self.payment = gold.create_dim_payment_type(self.spark)
        self.zone = gold.create_dim_zone(self.spark, self.zones)
        self.date = gold.create_dim_date(self.silver)

    def fact(self):
        return gold.create_fact_trips(self.silver, self.payment, self.zone)

    def test_zone_projection_merges_geometries_without_arbitrary_key_deduplication(self):
        self.assertEqual(self.zone.count(), 3)
        self.assertNotIn("zone_geom", self.zone.columns)
        conflict = self.spark.createDataFrame(
            [(1, "Different Zone", "Bronx", "polygon-d")], self.zones.schema
        )
        dimension = gold.create_dim_zone(self.spark, self.zones.unionByName(conflict))
        with self.assertRaisesRegex(ValueError, "conflicting"):
            gold.validate_dimension(dimension, "zone_id")

    def test_unknown_codes_and_nulls_preserve_trips_and_source_values(self):
        rows = {row.total_amount: row for row in self.fact().collect()}
        self.assertEqual(len(rows), 3)
        self.assertEqual((rows[20.0].payment_type, rows[20.0].pickup_zone_id), (1, 1))
        self.assertEqual((rows[10.0].payment_type, rows[10.0].source_payment_type), (-1, 99))
        self.assertEqual((rows[10.0].pickup_zone_id, rows[10.0].dropoff_zone_id), (-1, -1))
        self.assertEqual(rows[10.0].pickup_location_id, 999)
        self.assertIsNone(rows[10.0].dropoff_location_id)
        self.assertEqual(rows[11.0].payment_type, -1)
        self.assertIsNone(rows[11.0].source_payment_type)
        self.assertEqual(rows[11.0].pickup_zone_id, -1)
        self.assertEqual(rows[20.0].pickup_date_id, 20181231)
        self.assertEqual(rows[20.0].dropoff_date_id, 20190101)
        self.assertEqual({row.date_id for row in self.date.collect()}, {20181231, 20190101, 20190102})
        unknown = gold.validate_dim_payment_type(self.silver, self.payment).collect()
        self.assertEqual({row.payment_type for row in unknown}, {99, None})

    def test_trip_ids_are_stable_across_repartitioning_and_column_order(self):
        first = {row.trip_id for row in self.fact().select("trip_id").collect()}
        reordered = self.silver.select(*reversed(self.silver.columns)).repartition(2)
        second = gold.create_fact_trips(reordered, self.payment, self.zone)
        self.assertEqual(first, {row.trip_id for row in second.select("trip_id").collect()})
        try:
            self.spark.conf.set("spark.sql.session.timeZone", "America/Sao_Paulo")
            other_timezone = self.fact()
            self.assertEqual(first, {row.trip_id for row in other_timezone.select("trip_id").collect()})
        finally:
            self.spark.conf.set("spark.sql.session.timeZone", "UTC")

    def test_dimension_validation_rejects_empty_and_null_keys(self):
        for dimension in [self.zone.limit(0), self.zone.withColumn("zone_id", col("zone_id") * None)]:
            with self.assertRaises(ValueError):
                gold.validate_dimension(dimension, "zone_id")

    def test_validation_detects_missing_foreign_key_and_duplicate_trips(self):
        fact = self.fact()
        with self.assertRaisesRegex(ValueError, "unmapped foreign keys"):
            gold.validate_foreign_key(fact, "pickup_zone_id", self.zone.filter(col("zone_id") != -1), "zone_id")
        duplicated = fact.unionByName(fact.limit(1))
        duplicated_source = self.silver.unionByName(self.silver.limit(1))
        with self.assertRaisesRegex(ValueError, "duplicate trip_id"):
            gold.validate_fact_trips(duplicated_source, duplicated)

    def test_parquet_round_trip_and_overwrite_preserve_schema_and_trip_ids(self):
        fact = self.fact()
        gold.validate_gold(self.silver, fact, self.payment, self.zone, self.date)
        with tempfile.TemporaryDirectory() as directory, patch.object(gold, "GOLD_PATH", directory):
            for table_name, df in [
                ("fact_trips", fact), ("dim_payment_type", self.payment),
                ("dim_zone", self.zone), ("dim_date", self.date),
            ]:
                gold.write_gold(df, table_name)
            original = self.spark.read.parquet(f"{directory}/fact_trips")
            ids = {row.trip_id for row in original.select("trip_id").collect()}
            gold.write_gold(fact.repartition(2), "fact_trips")
            saved = self.spark.read.parquet(f"{directory}/fact_trips")
            self.assertEqual(ids, {row.trip_id for row in saved.select("trip_id").collect()})
            self.assertEqual(fact.dtypes, saved.dtypes)
            gold.validate_gold(
                self.silver, saved,
                self.spark.read.parquet(f"{directory}/dim_payment_type"),
                self.spark.read.parquet(f"{directory}/dim_zone"),
                self.spark.read.parquet(f"{directory}/dim_date"),
            )


if __name__ == "__main__":
    unittest.main()
