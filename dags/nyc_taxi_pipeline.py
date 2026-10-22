from datetime import datetime, timedelta
import os
from pathlib import Path
import shlex
from zoneinfo import ZoneInfo

from airflow.sdk import DAG
from airflow.providers.standard.operators.bash import BashOperator


PROJECT_ROOT = Path(os.environ.get("NYC_TAXI_PROJECT_ROOT", Path(__file__).resolve().parents[1]))
PYTHON = shlex.quote(str(PROJECT_ROOT / ".venv/bin/python"))
TASK_ENV = {
    "TZ": "America/Sao_Paulo",
    "SPARK_LOCAL_IP": "127.0.0.1",
    "SPARK_MASTER": "local[2]",
    "PYTHONUNBUFFERED": "1",
    "PYSPARK_SUBMIT_ARGS": "--driver-memory 1g --conf spark.sql.session.timeZone=America/Sao_Paulo pyspark-shell",
    "NYC_TAXI_RUN_ID": "{{ run_id }}",
}

with DAG(
    dag_id="nyc_taxi_pipeline",
    description="Snapshot NYC Taxi: Bronze -> Silver -> Gold -> PostgreSQL -> analytics validation",
    start_date=datetime(2026, 1, 1, tzinfo=ZoneInfo("America/Sao_Paulo")),
    schedule=None,
    catchup=False,
    max_active_runs=1,
    max_active_tasks=1,
    dagrun_timeout=timedelta(hours=4),
    default_args={"retries": 1, "retry_delay": timedelta(minutes=2), "execution_timeout": timedelta(hours=2)},
    tags=["nyc-taxi", "local", "batch"],
) as dag:
    def script_task(task_id, command):
        return BashOperator(
            task_id=task_id,
            bash_command=f"{PYTHON} {command}",
            cwd=str(PROJECT_ROOT),
            env=TASK_ENV,
            append_env=True,
            do_xcom_push=False,
        )

    prepare_bronze = script_task("prepare_bronze", "src/ingestion/download_dataset.py")
    bronze_to_silver = script_task("bronze_to_silver", "src/transformations/bronze_to_silver.py")
    silver_to_gold = script_task("silver_to_gold", "src/transformations/silver_to_gold.py")
    create_schema = script_task("create_postgres_schema", "-m src.loading.create_postgres_schema")
    load_postgres = script_task("gold_to_postgres", "src/loading/gold_to_postgres.py")
    validate_pipeline = script_task("validate_pipeline", "-m src.validation.validate_pipeline")

    prepare_bronze >> bronze_to_silver >> silver_to_gold >> create_schema >> load_postgres >> validate_pipeline
