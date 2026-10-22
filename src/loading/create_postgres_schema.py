from pathlib import Path

from src.loading.gold_to_postgres import create_connection


def main():
    statement = Path("sql/create_tables.sql").read_text(encoding="utf-8")
    with create_connection() as connection:
        connection.execute(statement)
    print("PostgreSQL schema prepared without deleting existing tables", flush=True)


if __name__ == "__main__":
    main()
