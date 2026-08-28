# configs/settings.py

import os

from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv())

ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
JWT_SECRET = os.getenv("JWT_SECRET", "")

MAX_UPLOAD_SIZE_MB = int(os.getenv("MAX_UPLOAD_SIZE_MB", "500"))

DATA_DIR = os.getenv("DATA_DIR", "data/")
OUTPUTS_DIR = os.getenv("OUTPUTS_DIR", "data/outputs/")
UPLOADS_DIR = os.getenv("UPLOADS_DIR", "data/uploads/")
