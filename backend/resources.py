import os
import json
from pypdf import PdfReader

# Determine path relative to this file
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")

# Read LinkedIn PDF
try:
    reader = PdfReader(os.path.join(DATA_DIR, "linkedin.pdf"))
    linkedin = ""
    for page in reader.pages:
        text = page.extract_text()
        if text:
            linkedin += text
except FileNotFoundError:
    linkedin = "LinkedIn profile not available"

# Read other data files
with open(os.path.join(DATA_DIR, "summary.txt"), "r", encoding="utf-8") as f:
    summary = f.read()

with open(os.path.join(DATA_DIR, "style.txt"), "r", encoding="utf-8") as f:
    style = f.read()

with open(os.path.join(DATA_DIR, "facts.json"), "r", encoding="utf-8") as f:
    facts = json.load(f)