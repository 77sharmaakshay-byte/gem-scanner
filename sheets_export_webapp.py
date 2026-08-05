import requests
import os
import pandas as pd
 
APPS_SCRIPT_URL = os.environ.get("APPS_SCRIPT_URL")
 
# Sections jinme squeeze% ke bands ke hisaab se bhi sub-grouping honi hai
SQUEEZE_BAND_SECTIONS = {"Gem_Setup_Intraday"}
 
 
def _json_safe(value):
    """Timestamp / datetime / NaT ko JSON-safe string mein convert karta hai."""
    if pd.isna(value):
        return ""
    if isinstance(value, (pd.Timestamp,)):
        return str(value)
    try:
        import datetime
        if isinstance(value, (datetime.datetime, datetime.date)):
            return str(value)
    except Exception:
        pass
    return value
 
 
def _squeeze_band(score: float) -> str:
    try:
        band_low = int(float(score) // 5) * 5
        return f"{band_low}-{band_low + 5}%"
    except Exception:
        return "?"
 
 
def _build_grouped_rows(section: str, df: pd.DataFrame) -> list:
    if df.empty:
        return [["No rows"]]
 
    has_tf = "TF" in df.columns
    has_score = "Gem Score%" in df.columns
    group_by_squeeze = section in SQUEEZE_BAND_SECTIONS and has_score
 
    sort_cols, ascending = [], []
    if has_tf:
        sort_cols.append("TF")
        ascending.append(True)
    if has_score:
        sort_cols.append("Gem Score%")
        ascending.append(False)
    view = df.sort_values(sort_cols, ascending=ascending) if sort_cols else df
 
    cols = view.columns.tolist()
    rows = []
    current_tf, current_band = None, None
 
    for _, r in view.iterrows():
        tf = r["TF"] if has_tf else None
        if has_tf and tf != current_tf:
            rows.append([f"=== Timeframe: {tf} ==="])
            rows.append(cols)
            current_tf = tf
            current_band = None
 
        if group_by_squeeze:
            band = _squeeze_band(r["Gem Score%"])
            if band != current_band:
                rows.append([f"--- Squeeze band: {band} ---"])
                current_band = band
 
        rows.append([_json_safe(v) for v in r.tolist()])
 
    return rows
 
 
def _post(section: str, rows: list) -> None:
    if not APPS_SCRIPT_URL:
        print("APPS_SCRIPT_URL set nahi hai -- Sheet export skip ho raha hai.")
        return
    payload = {"sheetName": section[:99], "rows": rows}
    try:
        resp = requests.post(APPS_SCRIPT_URL, json=payload, timeout=30)
        if resp.status_code == 200:
            print(f"Sheet updated: {section} ({len(rows)} rows written)")
        else:
            print(f"Sheet update failed for {section}: {resp.status_code} {resp.text[:200]}")
    except Exception as e:
        print(f"Sheet export error for {section}: {e}")
 
 
def export_status_only(scanned_at: str, next_scan: str, note: str = "") -> None:
    """Jab is run mein koi timeframe due nahi tha, tab bhi 'zinda hai' wala
    status update karta hai -- data tabs ko touch nahi karta."""
    rows = [
        ["Scanned at:", scanned_at],
        ["Next scan:", next_scan],
        ["Note:", note or "No new timeframe due this run -- data tabs unchanged"],
    ]
    _post("Status", rows)
 
 
def export_to_google_sheet(outputs: dict, scanned_at: str, next_scan: str) -> None:
    for section, df in outputs.items():
        header = [
            ["Scanned at:", scanned_at],
            ["Next scan:", next_scan],
            [""],
        ]
        rows = header + _build_grouped_rows(section, df)
        _post(section, rows)
 
    export_status_only(scanned_at, next_scan, note="Full scan completed this run")
