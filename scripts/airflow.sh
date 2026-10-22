#!/usr/bin/env bash
set -euo pipefail
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"
export AIRFLOW_HOME="$PROJECT_ROOT/.airflow"
export AIRFLOW_CONFIG="$AIRFLOW_HOME/airflow.cfg"
export AIRFLOW__DATABASE__SQL_ALCHEMY_CONN="sqlite:///$AIRFLOW_HOME/airflow.db"
export NYC_TAXI_PROJECT_ROOT="$PROJECT_ROOT"
export PATH="$PROJECT_ROOT/.venv-airflow/bin:$PATH"
export AIRFLOW__CORE__DAGS_FOLDER="$PROJECT_ROOT/dags"
export AIRFLOW__CORE__LOAD_EXAMPLES=False
export AIRFLOW__CORE__EXECUTOR=LocalExecutor
export AIRFLOW__CORE__PARALLELISM=1
export AIRFLOW__CORE__MAX_ACTIVE_TASKS_PER_DAG=1
export AIRFLOW__CORE__DEFAULT_TIMEZONE=America/Sao_Paulo
export AIRFLOW__CORE__AUTH_MANAGER=airflow.api_fastapi.auth.managers.simple.simple_auth_manager.SimpleAuthManager
export AIRFLOW__CORE__SIMPLE_AUTH_MANAGER_ALL_ADMINS=False
export AIRFLOW__CORE__SIMPLE_AUTH_MANAGER_USERS=andre:admin
export AIRFLOW__CORE__SIMPLE_AUTH_MANAGER_PASSWORDS_FILE="$AIRFLOW_HOME/ui_passwords.json"
export AIRFLOW__CORE__EXECUTION_API_SERVER_URL=http://127.0.0.1:8081/execution/
export AIRFLOW__API__HOST=127.0.0.1
export AIRFLOW__API__PORT=8081
export AIRFLOW__API__WORKERS=1
export AIRFLOW__API__BASE_URL=http://127.0.0.1:8081
export AIRFLOW__DAG_PROCESSOR__PARSING_PROCESSES=1
export AIRFLOW__SCHEDULER__MAX_TIS_PER_QUERY=1
export TZ=America/Sao_Paulo
if [ ! -x "$PROJECT_ROOT/.venv-airflow/bin/python" ]; then
    echo "Prepare .venv-airflow e instale requirements-airflow.txt antes de continuar." >&2
    exit 1
fi
"$PROJECT_ROOT/.venv-airflow/bin/python" scripts/prepare_airflow.py
source "$AIRFLOW_HOME/runtime.env"
exec "$PROJECT_ROOT/.venv-airflow/bin/airflow" "$@"
