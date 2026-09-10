import os
from dotenv import load_dotenv
import kagglehub

load_dotenv()

token = os.getenv("KAGGLE_API_TOKEN")

if not token:
    raise RuntimeError("KAGGLE_API_TOKEN NOT FOUND")

try:
    path = kagglehub.dataset_download(
        "neilclack/nyc-taxi-trip-data-google-public-data",
        output_dir="data/raw",
        force_download=True
        )
    
    print("DATASET DOWNLOADED SUCCESSFULLY!")
    print(f"DATASET LOCATION: {path}")

except Exception as e:
    print("ERROR! FAILED TO DOWNLOAD THE DATASET")
    print(f"ERROR DESCRIPTION: {e}")
