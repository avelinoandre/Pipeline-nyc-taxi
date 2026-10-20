import os
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
import tempfile
import unittest
from uuid import uuid4

import pyarrow as pa
import pyarrow.parquet as pq
import psycopg
from psycopg import sql

from src.loading import gold_to_postgres as loader


class BatchTests(unittest.TestCase):
    def test_timestamp_preserves_spark_session_calendar_across_midnight(self):
        batch = pa.record_batch([
            pa.array([datetime(2019, 1, 1, 1, 50)], type=pa.timestamp("ns")),
            pa.array([datetime(2019, 1, 1, 2, 10)], type=pa.timestamp("ns")),
        ], names=["pickup_datetime", "dropoff_datetime"])
        row = loader.prepare_batch(batch).to_pylist()[0]
        self.assertEqual(row["pickup_datetime"], datetime(2018, 12, 31, 23, 50))
        self.assertEqual(row["dropoff_datetime"], datetime(2019, 1, 1, 0, 10))

    def test_timestamp_with_timezone_is_not_assumed_utc_twice(self):
        batch = pa.record_batch([
            pa.array([datetime(2019, 1, 1, 1, 50)], type=pa.timestamp("us", "UTC")),
        ], names=["pickup_datetime"])
        self.assertEqual(loader.prepare_batch(batch).to_pylist()[0]["pickup_datetime"], datetime(2018, 12, 31, 23, 50))

    def test_dimension_batch_is_unchanged(self):
        batch = pa.record_batch([pa.array([1, -1]), pa.array(["", None], type=pa.string())], names=["code", "label"])
        self.assertTrue(loader.prepare_batch(batch).equals(batch))


@unittest.skipUnless(os.getenv("RUN_POSTGRES_TESTS") == "1", "Set RUN_POSTGRES_TESTS=1 for isolated PostgreSQL integration tests")
class PostgresLoadTests(unittest.TestCase):
    def setUp(self):
        self.connection = loader.create_connection()
        self.schema = "test_gold_" + uuid4().hex[:12]
        self.connection.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(self.schema)))
        ddl = Path("sql/create_tables.sql").read_text().replace("public.", self.schema + ".")
        self.connection.execute(ddl)
        self.directory = tempfile.TemporaryDirectory()
        self.gold_path = Path(self.directory.name)
        self.schemas = {
            name: pq.ParquetDataset(loader.GOLD_PATH / name).schema
            for name in loader.TABLE_NAMES
        }
        self.write_source()

    def tearDown(self):
        self.connection.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(self.schema)))
        self.connection.close()
        self.directory.cleanup()

    def write_source(self, bad_payment=False, bad_date=False, replacement=False):
        dates = []
        for day in [date(2018, 12, 31), date(2019, 1, 1)]:
            dates.append({
                "date_id": int(day.strftime("%Y%m%d")), "date": day,
                "year": day.year, "quarter": (day.month - 1) // 3 + 1,
                "month": day.month, "day": day.day,
                "day_of_week": (day.weekday() + 1) % 7 + 1,
                "week_of_year": day.isocalendar().week, "is_weekend": day.weekday() >= 5,
            })
        first = {field.name: None for field in self.schemas["fact_trips"]}
        first.update({
            "trip_id": "a" * 64, "pickup_date_id": 20190101 if bad_date else 20181231,
            "dropoff_date_id": 20190101, "pickup_zone_id": -1, "dropoff_zone_id": -1,
            "payment_type": 999 if bad_payment else -1, "source_payment_type": 99,
            "pickup_datetime": datetime(2019, 1, 1, 1, 50),
            "dropoff_datetime": datetime(2019, 1, 1, 2, 10),
            "trip_distance": 1.5, "trip_duration_minutes": 20.0,
            "total_amount": 99.0 if replacement else 12.3456789,
            "fare_amount": -5.123456, "pickup_location_id": 999,
        })
        second = dict(first)
        second.update({
            "trip_id": "b" * 64, "pickup_date_id": 20190101,
            "payment_type": 1, "source_payment_type": 1,
            "pickup_zone_id": 1, "dropoff_zone_id": 1,
            "pickup_datetime": datetime(2019, 1, 1, 14, 0),
            "dropoff_datetime": datetime(2019, 1, 1, 14, 10),
            "trip_duration_minutes": 10.0, "store_and_fwd_flag": "", "total_amount": 9.1,
        })
        rows = {
            "dim_payment_type": [
                {"payment_type": -1, "payment_type_name": "Unknown"},
                {"payment_type": 1, "payment_type_name": "Credit Card"},
            ],
            "dim_zone": [
                {"zone_id": -1, "zone_name": "Unknown", "borough": "Unknown"},
                {"zone_id": 1, "zone_name": "Replacement" if replacement else 'Zone, "A"\nNorth', "borough": "Queens"},
            ],
            "dim_date": dates,
            "fact_trips": [first, second],
        }
        for name, data in rows.items():
            folder = self.gold_path / name
            folder.mkdir(exist_ok=True)
            pq.write_table(pa.Table.from_pylist(data, schema=self.schemas[name]), folder / "part-00000.parquet")

    def load(self):
        return loader.load_gold(self.connection, self.gold_path, self.schema)

    def snapshot(self):
        result = {}
        for name, key in [("dim_payment_type", "payment_type"), ("dim_zone", "zone_id"), ("dim_date", "date_id"), ("fact_trips", "trip_id")]:
            result[name] = self.connection.execute(
                sql.SQL("SELECT * FROM {} ORDER BY {}").format(sql.Identifier(self.schema, name), sql.Identifier(key))
            ).fetchall()
        return result

    def test_round_trip_and_reexecution_preserve_values_and_do_not_duplicate(self):
        self.assertEqual(self.load(), {name: 2 for name in loader.TABLE_NAMES})
        before = self.snapshot()
        self.load()
        self.assertEqual(before, self.snapshot())
        row = self.connection.execute(sql.SQL("SELECT total_amount, fare_amount, source_payment_type, pickup_location_id, dropoff_location_id, store_and_fwd_flag FROM {} ORDER BY trip_id").format(sql.Identifier(self.schema, "fact_trips"))).fetchall()
        self.assertEqual(row[0], (Decimal("12.3456789"), Decimal("-5.123456"), 99, 999, None, None))
        self.assertEqual(row[1][-1], "")
        zone = self.connection.execute(sql.SQL("SELECT zone_name FROM {} WHERE zone_id = 1").format(sql.Identifier(self.schema, "dim_zone"))).fetchone()[0]
        self.assertEqual(zone, 'Zone, "A"\nNorth')

    def test_foreign_key_failure_rolls_back_all_tables(self):
        self.load()
        before = self.snapshot()
        self.write_source(bad_payment=True, replacement=True)
        with self.assertRaises(psycopg.errors.ForeignKeyViolation):
            self.load()
        self.assertEqual(before, self.snapshot())

    def test_validation_failure_after_copy_rolls_back_all_tables(self):
        self.load()
        before = self.snapshot()
        self.write_source(bad_date=True, replacement=True)
        with self.assertRaisesRegex(ValueError, "dim_date"):
            self.load()
        self.assertEqual(before, self.snapshot())

    def test_empty_source_is_rejected_before_truncating(self):
        self.load()
        before = self.snapshot()
        pq.write_table(pa.Table.from_pylist([], schema=self.schemas["fact_trips"]), self.gold_path / "fact_trips/part-00000.parquet")
        with self.assertRaisesRegex(ValueError, "empty"):
            self.load()
        self.assertEqual(before, self.snapshot())


if __name__ == "__main__":
    unittest.main()
