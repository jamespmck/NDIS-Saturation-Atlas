from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DOCS_DIR = PROJECT_ROOT / "docs"

source_register = pd.read_csv(DOCS_DIR / "source_register.csv")
download_manifest = pd.read_csv(DOCS_DIR / "download_manifest.csv")
grain_audit = pd.read_csv(DOCS_DIR / "grain_audit.csv")
data_dictionary = pd.read_csv(DOCS_DIR / "data_dictionary.csv")

print("Source register")
display(source_register.head(20))

print("Download manifest")
display(download_manifest.head(20))

print("Grain audit")
display(grain_audit.head(20))

print("Data dictionary")
display(data_dictionary.head(20))
