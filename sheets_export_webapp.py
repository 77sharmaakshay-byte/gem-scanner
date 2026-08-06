import requests
import os
import pandas as pd

APPS_SCRIPT_URL = os.environ.get("APPS_SCRIPT_URL")

# Fixed order jisme intraday timeframes sheet mein dikhne chahiye
INTRADAY_TF_ORDER = ["5m", "15m", "30m", "45m", "1H", "75m", "2H", "150m", "3H", "4H"]

DATA_HEADER = ["Symbol", "SQ%", "RSI Width"]


def _json_safe(value):
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


def _fetch_existing_rows(section: str) -> list:
    if not APPS_SCRIPT_URL:
        return []
    try:
        resp = requests.get(APPS_SCRIPT_URL, params={"sheetName": section}, timeout=30)
        if resp.status_code == 200:
            data = resp.json()
            return data.get("rows", [])
    except Exception as e:
        print(f"Could not fetch existing rows for {section}: {e}")
    return []


def _parse_existing_intraday(rows: list) -> dict:
    """Purani Sheet content se har TF-block (uski scanned-at time + data rows)
    wapas nikalta hai, taaki carry-forward kiya ja sake."""
    blocks = {}
    i = 0
    n = len(rows)
    while i < n:
        row = rows[i]
        if row and isinstance(row[0], str) and row[0].startswith("TF: "):
            tf = row[0][4:].strip()
            scanned_at = ""
            if len(row) > 1 and isinstance(row[1], str) and row[1].startswith("Scanned at: "):
                scanned_at = row[1][len("Scanned at: "):]
            i += 1
            if i < n and list(rows[i][:3]) == DATA_HEADER:
                i += 1
            data_rows = []
            while i < n and rows[i] and not (isinstance(rows[i][0], str) and rows[i][0].startswith("TF: ")):
                if rows[i][0] not in ("", None):
                    data_rows.append(list(rows[i][:3]))
                i += 1
            blocks[tf] = (scanned_at, data_rows)
        else:
            i += 1
    return blocks


def _build_intraday_rows(df: pd.DataFrame, due_tfs: list, scanned_at: str) -> list:
    old_blocks = _parse_existing_intraday(_fetch_existing_rows("Gem_Setup_Intraday"))

    fresh_blocks = {tf: (scanned_at, []) for tf in due_tfs if tf in INTRADAY_TF_ORDER}
    if not df.empty:
        for tf, g in df.groupby("TF"):
            g = g.sort_values("SQ%", ascending=False)
            data_rows = [[r["Symbol"], r["SQ%"], r.get("RSI Width", "")] for _, r in g.iterrows()]
            fresh_blocks[tf] = (scanned_at, data_rows)

    combined = dict(old_blocks)
    combined.update(fresh_blocks)

    ordered_tfs = [tf for tf in INTRADAY_TF_ORDER if tf in combined]

    rows = []
    for tf in ordered_tfs:
        s_at, data_rows = combined[tf]
        rows.append([f"TF: {tf}", f"Scanned at: {s_at}"])
        rows.append(DATA_HEADER)
        for dr in data_rows:
            rows.append([_json_safe(v) for v in dr])
        rows.append([""])
    return rows


def _build_grouped_rows(section: str, df: pd.DataFrame) -> list:
    if df.empty:
        return [["No rows"]]

    has_tf = "TF" in df.columns
    sort_cols, ascending = [], []
    if has_tf:
        sort_cols += ["TF"]
        ascending += [True]
    if "Gem Score%" in df.columns:
        sort_cols += ["Gem Score%"]
        ascending += [False]
    view = df.sort_values(sort_cols, ascending=ascending) if sort_cols else df

    cols = view.columns.tolist()
    rows = []
    current_tf = None
    for _, r in view.iterrows():
        tf = r["TF"] if has_tf else None
        if has_tf and tf != current_tf:
            rows.append([f"TF: {tf}"])
            rows.append(cols)
            current_tf = tf
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


def export_status_only(scanned_at: str) -> None:
    _post("Status", [["Current scan time:", scanned_at]])


def export_to_google_sheet(outputs: dict, scanned_at: str, due_tfs: list) -> None:
    for section, df in outputs.items():
        if section == "Gem_Setup_Intraday":
            body = _build_intraday_rows(df, due_tfs, scanned_at)
        else:
            body = [["Scanned at:", scanned_at], [""]] + _build_grouped_rows(section, df)
        _post(section, body)

    export_status_only(scanned_at)
