import requests
import os
import pandas as pd

APPS_SCRIPT_URL = os.environ.get("APPS_SCRIPT_URL")


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


def export_to_google_sheet(outputs: dict):
    if not APPS_SCRIPT_URL:
        print("APPS_SCRIPT_URL set nahi hai -- Sheet export skip ho raha hai.")
        return

    for section, df in outputs.items():
        if df.empty:
            rows = [["No rows"]]
        else:
            safe_df = df.copy()
            rows = [safe_df.columns.tolist()]
            for _, r in safe_df.iterrows():
                rows.append([_json_safe(v) for v in r.tolist()])

        payload = {"sheetName": section[:99], "rows": rows}
        try:
            resp = requests.post(APPS_SCRIPT_URL, json=payload, timeout=30)
            if resp.status_code == 200:
                print(f"Sheet updated: {section} ({len(df)} rows)")
            else:
                print(f"Sheet update failed for {section}: {resp.status_code} {resp.text[:200]}")
        except Exception as e:
            print(f"Sheet export error for {section}: {e}")
