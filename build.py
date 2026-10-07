"""
Media Ecosystem Atlas: static site builder
==========================================

Reads the two CSV files in `data/`, runs them through pipeline.py, injects the
result into index.html (replacing the __RAW_JSON__ placeholder) and writes the
finished page to `dist/index.html`.

Run locally:   python build.py
On GitHub:     the Action in .github/workflows/deploy.yml runs this for you.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

import pipeline as P

ROOT = Path(__file__).parent
TEMPLATE_PATH = ROOT / "index.html"
EUR_CSV = ROOT / "data" / "european_media_outlets.csv"
ECO_CSV = ROOT / "data" / "wider_media_ecosystem.csv"
OUT_DIR = ROOT / "dist"
OUT_FILE = OUT_DIR / "index.html"
PLACEHOLDER = "__RAW_JSON__"


def main() -> None:
    # 1. Make sure every input file exists, with a clear message if not.
    for path in (TEMPLATE_PATH, EUR_CSV, ECO_CSV):
        if not path.exists():
            sys.exit(f"ERROR: missing file: {path.relative_to(ROOT)}")

    # 2. Read the CSVs and build the data structure the dashboard expects.
    df_eur = pd.read_csv(EUR_CSV)
    df_eco = pd.read_csv(ECO_CSV)
    raw = P.build_full_raw(df_eur, df_eco)

    # "</" is escaped so the data can never close the <script> tag early.
    raw_js = json.dumps(raw, ensure_ascii=False).replace("</", "<\\/")

    # 3. Inject the data into the HTML template.
    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    if PLACEHOLDER not in template:
        sys.exit(f"ERROR: placeholder {PLACEHOLDER} not found in index.html")
    html = template.replace(PLACEHOLDER, raw_js)

    # 4. Write the finished page.
    OUT_DIR.mkdir(exist_ok=True)
    OUT_FILE.write_text(html, encoding="utf-8")

    # GitHub Pages runs Jekyll by default; this file turns that off so
    # nothing in the output gets processed or ignored.
    (OUT_DIR / ".nojekyll").write_text("", encoding="utf-8")

    print(f"Wrote {OUT_FILE.relative_to(ROOT)} ({len(html) / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
