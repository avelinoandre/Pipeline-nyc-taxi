import argparse
import os
from pathlib import Path

from dotenv import load_dotenv
import kagglehub


PROJECT_ROOT = Path(__file__).resolve().parents[2]
BRONZE_PATH = PROJECT_ROOT / "data/bronze"
REQUIRED_FILES = ["taxi_trip_data.csv", "taxi_zone_geo.csv"]


def bronze_available():
    return all((BRONZE_PATH / name).is_file() and (BRONZE_PATH / name).stat().st_size > 0
               for name in REQUIRED_FILES)


def download_dataset(force_download=False):
    if bronze_available() and not force_download:
        print("BRONZE FILES ALREADY AVAILABLE: reusing the local snapshot", flush=True)
        return BRONZE_PATH

    load_dotenv(PROJECT_ROOT / ".env")
    if not os.getenv("KAGGLE_API_TOKEN"):
        raise RuntimeError("Configure KAGGLE_API_TOKEN in .env before downloading the dataset")

    # Falhas propagam exit code diferente de zero para o Airflow.
    kagglehub.dataset_download(
        "neilclack/nyc-taxi-trip-data-google-public-data",
        output_dir=str(BRONZE_PATH),
        force_download=force_download,
    )
    if not bronze_available():
        raise RuntimeError("Dataset download did not provide the required nonempty Bronze files")
    print("DATASET DOWNLOADED SUCCESSFULLY", flush=True)
    return BRONZE_PATH


def main():
    parser = argparse.ArgumentParser(description="Prepare the NYC Taxi Bronze snapshot")
    parser.add_argument("--force-download", action="store_true", help="Download again even if Bronze is available")
    args = parser.parse_args()
    download_dataset(force_download=args.force_download)


if __name__ == "__main__":
    main()
