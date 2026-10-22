import json
import os
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from src.loading.gold_to_postgres import create_connection, read_gold, validate_load
from src.dashboard.data import load_analytics, read_queries


def main():
    _, expected_counts = read_gold()
    with create_connection() as connection:
        with connection.transaction():
            connection.execute("SET TRANSACTION READ ONLY")
            validate_load(connection, expected_counts)
    analytics = load_analytics(read_queries())
    business = analytics["coverage"].loc[analytics["coverage"]["pickup_year"].eq(2018)].iloc[0]
    report = {
        "validated_at": datetime.now(ZoneInfo("America/Sao_Paulo")).isoformat(),
        "dag_run_id": os.getenv("NYC_TAXI_RUN_ID", "manual_script"),
        "gold_and_postgres_counts": expected_counts,
        "analytics_2018_trips": int(business["trip_count"]),
        "analytics_2018_observed_days": int(business["observed_days"]),
        "analytics_2018_unknown_pickup_trips": int(business["unknown_pickup_zone_trips"]),
        "analytic_queries_validated": len(read_queries()),
    }
    output = Path(".airflow/validation/latest.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2), flush=True)
    print("Pipeline and dashboard queries validated successfully", flush=True)


if __name__ == "__main__":
    main()
