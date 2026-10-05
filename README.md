# Media Ecosystem Atlas — auto-reload edition

Your customer-approved dashboard, pixel-for-pixel. Edit the data files, refresh the
browser, see the changes. That's the whole workflow.

## How to update the data

1. Open one of these two CSV files in Excel:
   - `data/european_media_outlets.csv`
   - `data/wider_media_ecosystem.csv`
2. Add, edit, or delete rows. **Don't rename the column headings.**
3. Save the file (keep it as CSV).
4. Refresh your browser tab showing the dashboard.

The dashboard updates. No upload buttons, no edit mode, nothing to click.

## Setup (one time)

```bash
cd media_atlas_app
python -m venv .venv
.venv\Scripts\activate     # Windows
pip install -r requirements.txt
```

## Run

```bash
streamlit run app.py
```

Opens at http://localhost:8501.

## Files

```
app.py           reads CSVs, injects data into template, renders
template.html    your approved dashboard (HTML/CSS/JS) with a data slot
pipeline.py      turns CSV rows into the data structure the dashboard expects
data/            the two CSV files you edit + country/category lookups
requirements.txt
```

## Notes

- The map and fonts load from the internet (same as the original HTML). The app
  needs to be online the first time.
- If you ever break a CSV (wrong columns, etc.) and the dashboard won't load, your
  original copies are in the zip you downloaded — just paste them back into `data/`.
