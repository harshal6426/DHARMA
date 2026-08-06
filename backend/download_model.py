"""
download_model.py
=================
Downloads the pre-trained Random Forest fraud detection model from Google Drive.

Usage:
    python download_model.py

The model will be saved to: backend/models/random_forest_fraud_model.joblib
"""

import os
import sys
import subprocess


GDRIVE_FILE_ID = "1ybfsNbwzZiwsb6kJpcBB1_bTem2r2W1v"

MODEL_DIR = os.path.join(os.path.dirname(__file__), "models")
MODEL_PATH = os.path.join(MODEL_DIR, "random_forest_fraud_model.joblib")


def download():
    if os.path.exists(MODEL_PATH):
        print(f"✅ Model already exists at: {MODEL_PATH}")
        print(f"   Size: {os.path.getsize(MODEL_PATH) / (1024 * 1024):.1f} MB")
        return

    if not GDRIVE_FILE_ID:
        print("❌ Error: Google Drive file ID not set.")
        sys.exit(1)

    # Ensure gdown is installed
    try:
        import gdown
    except ImportError:
        print("📦 Installing gdown...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "gdown"])
        import gdown

    os.makedirs(MODEL_DIR, exist_ok=True)

    url = f"https://drive.google.com/uc?id={GDRIVE_FILE_ID}"
    print(f"⬇️  Downloading model from Google Drive...")
    gdown.download(url, MODEL_PATH, quiet=False)

    if os.path.exists(MODEL_PATH):
        size_mb = os.path.getsize(MODEL_PATH) / (1024 * 1024)
        print(f"✅ Model downloaded successfully! ({size_mb:.1f} MB)")
        print(f"   Saved to: {MODEL_PATH}")
    else:
        print("❌ Download failed. Please check the file ID and sharing settings.")
        sys.exit(1)


if __name__ == "__main__":
    download()
