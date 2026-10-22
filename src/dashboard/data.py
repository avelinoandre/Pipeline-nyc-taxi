from datetime import datetime
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import psycopg
from dotenv import dotenv_values


PROJECT_ROOT = Path(__file__).resolve().parents[2]
BUSINESS_YEAR = 2018
QUERY_FILES = {
    "coverage": "00_data_coverage.sql",
    "monthly": "01_monthly_activity.sql",
    "zones": "02_pickup_zones.sql",
    "hourly": "03_zone_weekday_hour.sql",
    "profile": "04_zone_trip_profile.sql",
    "zone_monthly": "05_zone_monthly_activity.sql",
}


def read_queries():
    return {name: (PROJECT_ROOT / "sql/analytics" / filename).read_text(encoding="utf-8")
            for name, filename in QUERY_FILES.items()}


def create_connection():
    settings = dotenv_values(PROJECT_ROOT / ".env.postgres")
    required = ["POSTGRES_DB", "POSTGRES_USER", "POSTGRES_PASSWORD"]
    if any(not settings.get(name) for name in required):
        raise ValueError("Configure as credenciais em .env.postgres.")

    return psycopg.connect(
        host=settings.get("POSTGRES_HOST", "127.0.0.1"),
        port=settings.get("POSTGRES_PORT", "5432"),
        dbname=settings["POSTGRES_DB"],
        user=settings["POSTGRES_USER"],
        password=settings["POSTGRES_PASSWORD"],
        application_name="nyc_taxi_streamlit",
        connect_timeout=10,
        autocommit=True,
    )


def validate_results(results):
    coverage = results["coverage"]
    business = coverage.loc[coverage["pickup_year"].eq(BUSINESS_YEAR)]
    if len(business) != 1 or business.iloc[0]["trip_count"] <= 0:
        raise ValueError("O recorte de 2018 nao possui viagens.")
    expected = int(business.iloc[0]["trip_count"])

    for name in QUERY_FILES:
        if name != "coverage" and results[name]["trip_count"].sum() != expected:
            raise ValueError(f"Contagem divergente: {name}")

    monthly = results["monthly"].set_index("month")["trip_count"].sort_index()
    by_zone = results["zone_monthly"].groupby("month")["trip_count"].sum().sort_index()
    if not monthly.equals(by_zone):
        raise ValueError("Totais mensais divergentes entre as consultas.")
    if len(monthly) != 12 or not monthly.index.year.isin([BUSINESS_YEAR]).all():
        raise ValueError("O dashboard exige os doze meses de 2018.")
    if not results["hourly"].groupby("day_of_week")["observed_weekdays"].nunique().eq(1).all():
        raise ValueError("Denominadores horarios divergentes.")
    if not results["zones"]["is_mapped_zone"].any():
        raise ValueError("Nenhuma zona mapeada no recorte.")


def load_analytics(queries):
    results = {}
    with create_connection() as connection:
        with connection.transaction():
            connection.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
            connection.execute("SET LOCAL statement_timeout = '5min'")
            connection.execute("SET LOCAL lock_timeout = '10s'")
            for name, query in queries.items():
                with connection.cursor() as cursor:
                    cursor.execute(query)
                    columns = [column.name for column in cursor.description]
                    frame = pd.DataFrame(cursor.fetchall(), columns=columns)
                # Conversao somente para apresentacao; nao modifica os NUMERIC do banco.
                results[name] = frame.map(lambda value: float(value) if isinstance(value, Decimal) else value)

    for name in ["monthly", "zone_monthly"]:
        results[name]["month"] = pd.to_datetime(results[name]["month"])
    validate_results(results)
    results["loaded_at"] = datetime.now(ZoneInfo("America/Sao_Paulo"))
    return results
