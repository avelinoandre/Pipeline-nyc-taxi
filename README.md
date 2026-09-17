# NYC Taxi Data Engineering Pipeline

A Data Engineering portfolio project built on top of the NYC Taxi Trip Data (Kaggle). The
goal is to design a reproducible, well-documented data pipeline — starting from exploratory
data analysis and evolving into an orchestrated pipeline using Apache Airflow, Docker,
PySpark, Parquet, MinIO and PostgreSQL.

This repository currently contains the exploratory analysis stage (`01_exploratory_analysis.ipynb`),
which drives the data quality rules and requirements that will shape the pipeline.

## Prerequisites

- Python 3.10+
- A [Kaggle](https://www.kaggle.com/) account with an active API token

## Setup

### 1. Create and activate a virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate      # Linux/macOS
.venv\Scripts\activate         # Windows
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure your Kaggle credentials

Generate a Kaggle API token from **Kaggle → Account → API → Create New Token**, then create
a `.env` file in the project root with:

```env
KAGGLE_API_TOKEN = your_key
```

> `.env` is git-ignored — never commit your credentials.

### 4. Download the dataset

```bash
python3 ingestion/download_dataset.py
```

This downloads the raw CSV files into `data/bronze/`:

- `taxi_trip_data.csv` — main dataset with taxi trip records
- `taxi_zone_geo.csv` — geographical/reference dataset (zone_id, zone_name, borough, geometry)
- `original_cleaned_nyc_taxi_data_2018.csv` — additional reference dataset

## Running the exploratory analysis

With the virtual environment active and the data downloaded, launch Jupyter and open the
notebook:

```bash
jupyter notebook 01_exploratory_analysis.ipynb
```

Because `taxi_trip_data.csv` is ~1 GB, the notebook uses Polars to load it and works with a
random sample (100,000 records, seed 42) converted to Pandas for analysis.

## Project structure

```
.
├── data/
│   └── bronze/                         # downloaded CSV files (git-ignored)
├── ingestion/
│   └── download_dataset.py          # downloads the dataset from Kaggle
├── 01_exploratory_analysis.ipynb    # EDA notebook
├── requirements.txt
├── .env                              # your Kaggle credentials (git-ignored, not committed)
└── README.md
```

## Roadmap

- [x] Exploratory Data Analysis
- [ ] Data quality rules and transformation layer (PySpark)
- [ ] Storage in Parquet / MinIO
- [ ] Orchestration with Apache Airflow
- [ ] Loading into PostgreSQL
- [ ] Containerization with Docker
