import os
from pathlib import Path
import unittest
from uuid import uuid4

from psycopg import sql
from psycopg.rows import dict_row

from src.loading.gold_to_postgres import create_connection


@unittest.skipUnless(os.getenv("RUN_POSTGRES_TESTS") == "1", "Requires local PostgreSQL")
class AnalyticsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.connection = create_connection()
        cls.connection.autocommit = False
        cls.schema = "test_analytics_" + uuid4().hex
        try:
            cls.connection.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(cls.schema)))
            cls.connection.execute(sql.SQL("SET LOCAL search_path TO {}").format(sql.Identifier(cls.schema)))
            cls.connection.execute("""
                CREATE TABLE dim_date (date_id integer, date date, year integer, day_of_week integer);
                CREATE TABLE dim_zone (zone_id integer, zone_name text, borough text);
                CREATE TABLE fact_trips (
                    pickup_date_id integer, pickup_zone_id integer, pickup_datetime timestamp,
                    fare_amount numeric, total_amount numeric,
                    trip_distance double precision, trip_duration_minutes double precision
                );
                INSERT INTO dim_date VALUES
                    (20171231, '2017-12-31', 2017, 1),
                    (20180101, '2018-01-01', 2018, 2),
                    (20180108, '2018-01-08', 2018, 2),
                    (20180109, '2018-01-09', 2018, 3),
                    (20180201, '2018-02-01', 2018, 5),
                    (20190101, '2019-01-01', 2019, 3);
                INSERT INTO dim_zone VALUES
                    (-1, 'Unknown', 'Unknown'), (1, 'Zone A', 'Borough A'), (2, 'Zone B', 'Borough B');
                INSERT INTO fact_trips VALUES
                    (20171231, 1, '2017-12-31 23:59:59', 100, 100, 1, 1),
                    (20180101, 1, '2018-01-01 08:00:00', 10, 12, 2, 10),
                    (20180101, 1, '2018-01-01 08:30:00', -2, 0, 4, 20),
                    (20180108, 2, '2018-01-08 08:00:00', NULL, NULL, 6, 30),
                    (20180109, -1, '2018-01-09 09:00:00', 0, -1, 8, 40),
                    (20180201, 1, '2018-02-01 10:00:00', 20, 24, 1000, 2000),
                    (20190101, 1, '2019-01-01 00:00:00', 100, 100, 1, 1);
            """)
        except Exception:
            cls.connection.rollback()
            cls.connection.close()
            raise

    @classmethod
    def tearDownClass(cls):
        # O schema e os dados de teste nunca sao confirmados no banco.
        cls.connection.rollback()
        cls.connection.close()

    def query(self, filename):
        statement = (Path("sql/analytics") / filename).read_text()
        statement = statement.replace("public.", self.schema + ".")
        with self.connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute(statement)
            return cursor.fetchall()

    def test_coverage_keeps_dates_outside_business_period(self):
        rows = self.query("00_data_coverage.sql")
        self.assertEqual([(r["pickup_year"], r["trip_count"]) for r in rows], [(2017, 1), (2018, 5), (2019, 1)])
        self.assertEqual(rows[1]["observed_days"], 4)
        self.assertEqual(rows[1]["unknown_pickup_zone_trips"], 1)
        self.assertEqual(rows[1]["null_total_trips"], 1)
        self.assertEqual(rows[1]["nonpositive_total_trips"], 2)

    def test_counts_reconcile_and_empty_months_remain_visible(self):
        monthly = self.query("01_monthly_activity.sql")
        zones = self.query("02_pickup_zones.sql")
        zone_monthly = self.query("05_zone_monthly_activity.sql")
        self.assertEqual(len(monthly), 12)
        self.assertEqual(len(zone_monthly), 36)
        for rows in [monthly, zones, zone_monthly]:
            self.assertEqual(sum(r["trip_count"] for r in rows), 5)
        self.assertEqual(monthly[0]["observed_days"], 3)
        self.assertEqual(monthly[1]["calendar_days"], 28)
        self.assertEqual(monthly[2]["trip_count"], 0)
        self.assertIsNone(monthly[2]["trips_per_observed_day"])
        unknown = next(r for r in zones if r["zone_id"] == -1)
        self.assertFalse(unknown["is_mapped_zone"])
        self.assertEqual(unknown["share_of_dataset_pct"], 20)
        self.assertEqual(sum(r["share_of_dataset_pct"] for r in zones), 100)
        empty_zone_month = next(r for r in zone_monthly if r["zone_id"] == 2 and r["month"].month == 2)
        self.assertEqual(empty_zone_month["trip_count"], 0)
        self.assertEqual(empty_zone_month["trips_per_observed_day"], 0)

    def test_hourly_average_includes_days_without_zone_trips(self):
        rows = self.query("03_zone_weekday_hour.sql")
        self.assertEqual(len(rows), 3 * 3 * 24)
        self.assertEqual(sum(r["trip_count"] for r in rows), 5)
        monday = next(r for r in rows if r["zone_id"] == 1 and r["day_of_week"] == 2 and r["pickup_hour"] == 8)
        self.assertEqual(monday["trip_count"], 2)
        self.assertEqual(monday["observed_weekdays"], 2)
        self.assertEqual(monday["trips_per_observed_weekday"], 1)
        self.assertTrue(any(r["trip_count"] == 0 for r in rows))

    def test_profile_preserves_nulls_negatives_and_outliers(self):
        rows = self.query("04_zone_trip_profile.sql")
        zone_a = next(r for r in rows if r["zone_id"] == 1)
        zone_b = next(r for r in rows if r["zone_id"] == 2)
        self.assertEqual(sum(r["trip_count"] for r in rows), 5)
        self.assertEqual(zone_a["recorded_fare_sum_usd"], 28)
        self.assertEqual(zone_a["median_fare_usd"], 10)
        self.assertEqual(zone_a["nonpositive_fare_trips"], 1)
        self.assertEqual(zone_a["median_distance_miles"], 4)
        self.assertEqual(zone_a["median_duration_minutes"], 20)
        self.assertGreater(zone_a["avg_duration_minutes"], 600)
        self.assertEqual(zone_b["trips_with_total"], 0)
        self.assertIsNone(zone_b["avg_total_usd"])
        self.assertIsNone(zone_b["recorded_total_sum_usd"])


if __name__ == "__main__":
    unittest.main()
