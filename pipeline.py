"""
pipeline.py
-----------
Turns a RAW exported CSV into the aggregated structures the dashboard renders.

This is the piece that makes the dashboard *dynamic*: instead of baking numbers
into the page once, every figure on screen is recomputed from the dataframe each
time the data changes (edit a cell, upload a new CSV, change a filter).

Two schemas are supported and auto-detected:

  * "european"  -> the European Media Outlets export
                   (columns include 'Legal Entity' and 'Revenue Stream')
                   category   = Legal Category
                   secondary  = Revenue Streams
  * "ecosystem" -> the Wider Media Ecosystem export
                   (columns include 'Type of org' and 'Focus areas (for project)')
                   category   = Organisation Type
                   secondary  = Focus Areas

Nothing here touches the network. Country -> lat/lon comes from data/geo_lookup.json.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pandas as pd

DATA_DIR = Path(__file__).parent / "data"

# ----------------------------------------------------------------------------- 
# Static lookups (no network calls)
# ----------------------------------------------------------------------------- 
GEO = json.loads((DATA_DIR / "geo_lookup.json").read_text(encoding="utf-8"))
LEGAL_MAP = json.loads((DATA_DIR / "legal_category_map.json").read_text(encoding="utf-8"))
LEGAL_MAP["not for profit"] = "Non-Profit / NGO"  # semantically non-profit

# Tolerant country spelling -> canonical key used in GEO
COUNTRY_ALIASES = {
    "USA": "USA", "U.S.A.": "USA", "United States": "USA", "US": "USA",
    "The Netherlands": "Netherlands", "Holland": "Netherlands",
    "Hungaria": "Hungary",
    "Brasil": "Brazil",
    "Catalonia": "Spain",
    "Czechia": "Czech Republic",
    "Bosnia-Herzegovina": "Bosnia and Herzegovina",
    "Republic of Ireland": "Ireland", "Eire": "Ireland",
    "UK": "UK", "United Kingdom": "UK", "Great Britain": "UK",
}

# Organisation-type normalisation for the ecosystem schema
ORG_TYPE_MAP = {
    "Big Tech - Large private technology provider": "Big Tech",
    "Medium or small private technology provider": "Mid/Small Tech",
    "Project or intiative": "Project/Initiative",
    "Project or initiative": "Project/Initiative",
    "Research organisation/institute/Think tank": "Research/Think Tank",
    "CSO": "CSO",
    "Ecosystem": "Ecosystem",
    "Media association/fund": "Media association/fund",
    "Media outlet": "Media outlet",
    "Public sector": "Public sector",
}

# Revenue-stream keyword -> bucket (for the european schema)
REVENUE_KEYWORDS = {
    "Subscriptions": "subscriptions",
    "Donations": "individual donations",
    "Grants": "foundation support",
    "Advertising": "advertis",
    "Government Funding": "government support",
    "Crowdfunding": "crowdfunding",
}

# Category colours (shared by map + charts), echoing the original palette.
CATEGORY_COLOURS = {
    # European schema
    "Non-Profit / NGO": "#4A7B5C",
    "Company / Enterprise": "#2E5F8A",
    "For-Profit": "#B33A3A",
    "Other": "#8A8A8A",
    # Ecosystem schema
    "CSO": "#2E5F8A",
    "Media outlet": "#B33A3A",
    "Media association/fund": "#C28C2C",
    "Research/Think Tank": "#4A7B5C",
    "Ecosystem": "#6B4E8A",
    "Project/Initiative": "#1B5666",
    "Mid/Small Tech": "#A85432",
    "Big Tech": "#5C5C5C",
    "Public sector": "#8B5A8C",
}
_FALLBACK_PALETTE = ["#B33A3A", "#2E5F8A", "#C28C2C", "#4A7B5C",
                     "#6B4E8A", "#1B5666", "#A85432", "#5C5C5C", "#8B5A8C"]


def colour_for(category: str, index: int = 0) -> str:
    return CATEGORY_COLOURS.get(category, _FALLBACK_PALETTE[index % len(_FALLBACK_PALETTE)])


def hex_to_rgb(h: str) -> list[int]:
    h = h.lstrip("#")
    return [int(h[i:i + 2], 16) for i in (0, 2, 4)]


# ----------------------------------------------------------------------------- 
# Helpers
# ----------------------------------------------------------------------------- 
def _clean(value) -> str:
    if value is None:
        return ""
    return str(value).replace("\r", "").replace("\n", " ").strip()


def _strip_headers(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(c).strip().lstrip("\ufeff") for c in df.columns]
    return df


def _geocode(country: str):
    key = COUNTRY_ALIASES.get(country, country)
    rec = GEO.get(key)
    if rec:
        return rec["lat"], rec["lon"]
    return None


def _canon_country(country: str) -> str:
    """Clean display name: 'The Netherlands' -> 'Netherlands', 'USA' stays 'USA'."""
    c = _clean(country)
    return COUNTRY_ALIASES.get(c, c)


def _legal_category(legal_entity: str) -> str:
    le = _clean(legal_entity)
    if le in LEGAL_MAP:
        return LEGAL_MAP[le]
    low = le.lower()
    if "non" in low and "profit" in low:
        return "Non-Profit / NGO"
    if "ngo" in low or "foundation" in low or "association" in low:
        return "Non-Profit / NGO"
    if "for-profit" in low or "for profit" in low:
        return "For-Profit"
    if "company" in low or "enterprise" in low:
        return "Company / Enterprise"
    return "Other"


def _shorten_focus(label: str) -> str:
    """Trim parenthetical descriptions so labels match the canonical legend.
    e.g. 'Technical gatekeeping (control of crawlers, bots, attribution.)' ->
         'Technical gatekeeping'."""
    label = label.strip().strip('"').strip()
    if " (" in label:
        label = label.split(" (", 1)[0].strip()
    return label


def _split_focus(cell: str) -> list[str]:
    """Split focus areas on commas that are NOT inside parentheses, then shorten."""
    cell = _clean(cell)
    if not cell:
        return []
    parts = re.split(r",(?![^(]*\))", cell)
    out, seen = [], set()
    for p in parts:
        s = _shorten_focus(p)
        if s and s not in seen:
            seen.add(s)
            out.append(s)
    return out


# ----------------------------------------------------------------------------- 
# Schema detection
# ----------------------------------------------------------------------------- 
def detect_schema(df: pd.DataFrame) -> str:
    cols = {c.strip().lstrip("\ufeff").lower() for c in df.columns}
    if "legal entity" in cols and "revenue stream" in cols:
        return "european"
    if "type of org" in cols:
        return "ecosystem"
    # gentle fallbacks
    if "revenue stream" in cols:
        return "european"
    return "ecosystem"


SCHEMA_META = {
    "european": {
        "label": "European Media Outlets",
        "subtitle": "Independent media organisations across Europe",
        "cat_label": "Legal Category",
        "sec_label": "Revenue Streams",
        "explode_country": True,
    },
    "ecosystem": {
        "label": "Wider Media Ecosystem",
        "subtitle": "CSOs, think tanks, tech & ecosystem organisations",
        "cat_label": "Organisation Type",
        "sec_label": "Focus Areas",
        "explode_country": False,
    },
}


# ----------------------------------------------------------------------------- 
# Normalisation -> tidy one-row-per-(org[, country]) table
# ----------------------------------------------------------------------------- 
def normalise(df: pd.DataFrame, schema: str) -> pd.DataFrame:
    df = _strip_headers(df)
    if schema == "european":
        return _normalise_european(df)
    return _normalise_ecosystem(df)


def _normalise_european(df: pd.DataFrame) -> pd.DataFrame:
    df = df.dropna(subset=["Name"])
    records = []
    for _, r in df.iterrows():
        name = _clean(r.get("Name"))
        if not name:
            continue
        cat = _legal_category(r.get("Legal Entity"))
        revenue = _clean(r.get("Revenue Stream")).lower()
        streams = [bucket for bucket, kw in REVENUE_KEYWORDS.items() if kw in revenue]
        scope = [s.strip() for s in _clean(r.get("Scope")).split(",") if s.strip()]
        year = pd.to_numeric(str(r.get("Founding")).strip()[:4], errors="coerce")
        countries = [c for c in (x.strip() for x in _clean(r.get("Country")).split("/")) if c]
        if not countries:
            countries = [""]
        for c in countries:
            c = _canon_country(c)
            coords = _geocode(c)
            records.append({
                "name": name,
                "category": cat,
                "country": c,
                "lat": coords[0] if coords else None,
                "lon": coords[1] if coords else None,
                "secondary": streams,
                "scope": scope,
                "year": float(year) if pd.notna(year) else None,
                "city": _clean(r.get("City")),
                "website": _clean(r.get("Website")),
            })
    return pd.DataFrame(records)


def _ecosystem_region(location: str) -> str:
    loc = _clean(location)
    m = {"EU/Europe": "Europe", "Global scope": "Global", "Global south": "Global South",
         "North America": "North America", "Regional": "Regional", "Africa": "Africa"}
    return m.get(loc, loc or "")


def _normalise_ecosystem(df: pd.DataFrame) -> pd.DataFrame:
    df = df.dropna(subset=["Name"])
    records = []
    for _, r in df.iterrows():
        name = _clean(r.get("Name"))
        if not name:
            continue
        raw_type = _clean(r.get("Type of org"))
        cat = ORG_TYPE_MAP.get(raw_type, raw_type or "Other")
        focus = _split_focus(r.get("Focus areas (for project)"))
        country = _canon_country(r.get("Country"))
        coords = _geocode(country)
        records.append({
            "name": name,
            "category": cat,
            "country": country,
            "lat": coords[0] if coords else None,
            "lon": coords[1] if coords else None,
            "secondary": focus,
            "scope": [],
            "year": None,
            "city": "",
            "website": _clean(r.get("Link")),
            "region": _ecosystem_region(r.get("Location")),
        })
    return pd.DataFrame(records)


# ----------------------------------------------------------------------------- 
# Aggregation -> everything the views need
# ----------------------------------------------------------------------------- 
def aggregate(tidy: pd.DataFrame, schema: str) -> dict:
    meta = SCHEMA_META[schema]
    out = {"meta": dict(meta), "schema": schema}

    if tidy.empty:
        out.update(total_orgs=0, total_countries=0, top_category="—",
                   cat_totals={}, sec_totals={}, scope_totals={},
                   year_series=[], countries=[], orgs=tidy)
        return out

    out["total_orgs"] = int(len(tidy))
    out["total_countries"] = int(tidy.loc[tidy["country"].astype(bool), "country"].nunique())

    cat_totals = tidy["category"].value_counts().to_dict()
    out["cat_totals"] = cat_totals
    out["top_category"] = max(cat_totals, key=cat_totals.get) if cat_totals else "—"

    sec_counter: dict[str, int] = {}
    for lst in tidy["secondary"]:
        for s in lst:
            sec_counter[s] = sec_counter.get(s, 0) + 1
    out["sec_totals"] = dict(sorted(sec_counter.items(), key=lambda kv: kv[1], reverse=True))

    scope_counter: dict[str, int] = {}
    for lst in tidy["scope"]:
        for s in lst:
            scope_counter[s] = scope_counter.get(s, 0) + 1
    out["scope_totals"] = dict(sorted(scope_counter.items(), key=lambda kv: kv[1], reverse=True))

    years = tidy["year"].dropna()
    if len(years):
        ys = years.astype(int).value_counts().sort_index()
        out["year_series"] = [{"year": int(y), "count": int(c)} for y, c in ys.items()]
    else:
        out["year_series"] = []

    # Country rollup with coordinates + dominant category (for the map)
    countries = []
    mapped = tidy[tidy["lat"].notna()]
    for country, grp in mapped.groupby("country"):
        cats = grp["category"].value_counts().to_dict()
        dom = max(cats, key=cats.get)
        countries.append({
            "country": country,
            "lat": float(grp["lat"].iloc[0]),
            "lon": float(grp["lon"].iloc[0]),
            "total": int(len(grp)),
            "dom_cat": dom,
            "colour": colour_for(dom),
        })
    countries.sort(key=lambda d: d["total"], reverse=True)
    out["countries"] = countries
    out["unmapped"] = sorted(
        tidy.loc[tidy["lat"].isna() & tidy["country"].astype(bool), "country"].unique().tolist()
    )

    out["orgs"] = tidy
    return out


def run_pipeline(df: pd.DataFrame, schema: str | None = None) -> dict:
    """Convenience: detect schema (unless given), normalise, aggregate."""
    schema = schema or detect_schema(df)
    tidy = normalise(df, schema)
    return aggregate(tidy, schema)


def load_default(schema: str) -> pd.DataFrame:
    fname = "european_media_outlets.csv" if schema == "european" else "wider_media_ecosystem.csv"
    return pd.read_csv(DATA_DIR / fname)


# ============================================================================
#  FULL RAW BUILDER — reproduces the exact structure the approved HTML expects
#  RAW = { "d1": {...}, "d2": {...} } so the original dashboard renders unchanged.
# ============================================================================

# Canonical ordering preserves the approved colour assignment (palette is applied
# in this order). New categories/streams from edited data are appended at the end.
CANON_CATS = {
    "european": ["Non-Profit / NGO", "Other", "For-Profit", "Company / Enterprise"],
    "ecosystem": ["CSO", "Media outlet", "Media association/fund", "Ecosystem",
                  "Research/Think Tank", "Project/Initiative", "Mid/Small Tech",
                  "Big Tech", "Public sector"],
}
CANON_SECS = {
    "european": ["Donations", "Advertising", "Crowdfunding", "Grants",
                 "Government Funding", "Subscriptions"],
    "ecosystem": ["Social norms and literacy", "Coalitions and advocacy", "Journalism tools",
                  "Media/journalism production", "Research and audits", "Regulatory and legal",
                  "Data Collaborative", "Funds/Investment", "Preference signalling",
                  "Paid data services", "Business models", "Technical gatekeeping",
                  "Licensing/commercial deals", "Visibility tools"],
}


def _order(keys, canon):
    """Canonical items first (in canon order, if present), then any extras seen."""
    seen = list(keys)
    ordered = [k for k in canon if k in seen]
    ordered += [k for k in seen if k not in canon]
    return ordered


def _region_for(schema, df_row=None):
    return None


def build_raw(df: pd.DataFrame, schema: str, ds_id: str) -> dict:
    """Build one dataset block matching the approved dashboard's RAW[ds] shape."""
    meta_base = SCHEMA_META[schema]
    tidy = normalise(df, schema)

    label = meta_base["label"]
    subtitle = meta_base["subtitle"]

    if tidy.empty:
        return {
            "id": ds_id, "label": label, "subtitle": subtitle, "countries": [],
            "cat_totals": {}, "sec_totals": {}, "sec_by_cat": {}, "scope_totals": {},
            "year_series": [],
            "meta": {"total_orgs": 0, "total_countries": 0, "cats": [], "secs": [],
                     "sec_label": meta_base["sec_label"], "cat_label": meta_base["cat_label"]},
        }

    # ---- unique-org view (top-level sec/scope/year totals are per unique org) ----
    uniq = tidy.drop_duplicates(subset=["name"]).reset_index(drop=True)

    cat_totals: dict[str, int] = {}
    for c in tidy["category"]:               # category counted per (org, country) unit
        cat_totals[c] = cat_totals.get(c, 0) + 1

    sec_totals: dict[str, int] = {}
    for lst in uniq["secondary"]:
        for s in lst:
            sec_totals[s] = sec_totals.get(s, 0) + 1

    sec_by_cat: dict[str, dict[str, int]] = {}
    for _, r in uniq.iterrows():
        d = sec_by_cat.setdefault(r["category"], {})
        for s in r["secondary"]:
            d[s] = d.get(s, 0) + 1

    scope_totals: dict[str, int] = {}
    for lst in uniq["scope"]:
        for s in lst:
            scope_totals[s] = scope_totals.get(s, 0) + 1

    years = uniq["year"].dropna().astype(int)
    year_series = [{"year": int(y), "count": int(c)}
                   for y, c in years.value_counts().sort_index().items()]

    # ---- per-country rollup (orgs counted in every country they belong to) ----
    countries = []
    mapped = tidy[tidy["lat"].notna()]
    for country, grp in mapped.groupby("country"):
        cats = {}
        for c in grp["category"]:
            cats[c] = cats.get(c, 0) + 1
        secondary = {}
        scope = {}
        orgs = []
        years_c = []
        for _, r in grp.iterrows():
            for s in r["secondary"]:
                secondary[s] = secondary.get(s, 0) + 1
            for s in r["scope"]:
                scope[s] = scope.get(s, 0) + 1
            org = {"name": r["name"], "city": r["city"], "cat": r["category"],
                   "website": r["website"]}
            if schema == "european":
                org["year"] = int(r["year"]) if pd.notna(r["year"]) else None
                org["scope"] = r["scope"]
                if pd.notna(r["year"]):
                    years_c.append(int(r["year"]))
            else:
                org["focus"] = r["secondary"]
                org["region"] = r.get("region", "") if "region" in r else ""
            orgs.append(org)
        dom = max(cats, key=cats.get)
        c_obj = {
            "name": country, "lat": float(grp["lat"].iloc[0]), "lon": float(grp["lon"].iloc[0]),
            "total": int(len(grp)), "dom_cat": dom, "cats": cats,
            "secondary": secondary, "scope": scope, "orgs": orgs, "years": years_c,
        }
        if schema == "ecosystem":
            c_obj["is_region"] = False
        countries.append(c_obj)
    countries.sort(key=lambda d: d["total"], reverse=True)

    meta = {
        "total_orgs": int(len(tidy)),
        "total_countries": len(countries),
        "cats": _order(cat_totals.keys(), CANON_CATS[schema]),
        "secs": _order(sec_totals.keys(), CANON_SECS[schema]),
        "sec_label": meta_base["sec_label"],
        "cat_label": meta_base["cat_label"],
    }
    if schema == "ecosystem":
        meta["total_regions"] = 0

    return {
        "id": ds_id, "label": label, "subtitle": subtitle,
        "countries": countries,
        "cat_totals": {k: cat_totals[k] for k in _order(cat_totals.keys(), CANON_CATS[schema])},
        "sec_totals": {k: sec_totals[k] for k in _order(sec_totals.keys(), CANON_SECS[schema])},
        "sec_by_cat": sec_by_cat,
        "scope_totals": scope_totals,
        "year_series": year_series,
        "meta": meta,
    }


def build_full_raw(df_d1: pd.DataFrame, df_d2: pd.DataFrame) -> dict:
    return {"d1": build_raw(df_d1, "european", "d1"),
            "d2": build_raw(df_d2, "ecosystem", "d2")}
