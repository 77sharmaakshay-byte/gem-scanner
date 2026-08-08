import requests
import os
import pandas as pd

APPS_SCRIPT_URL = os.environ.get("APPS_SCRIPT_URL")
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")

INTRADAY_TF_ORDER = ["5m", "15m", "30m", "45m", "1H", "75m", "2H", "150m", "3H", "4H"]
ALL_TF_ORDER = INTRADAY_TF_ORDER + ["1D", "2D", "3D"]

DATA_HEADER = ["Symbol", "SQ%", "RSI Width"]
NEW_SETUP_HEADER = ["Symbol", "Side", "Close", "SQ%"]


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
        resp = requests.get(APPS_SCRIPT_URL, params={"sheetName": section}, timeout=60)
        if resp.status_code == 200:
            data = resp.json()
            return data.get("rows", [])
    except Exception as e:
        print(f"Could not fetch existing rows for {section}: {e}")
    return []


def _parse_existing_generic(rows: list, data_header: list) -> dict:
    blocks = {}
    i = 0
    n = len(rows)
    hlen = len(data_header)
    while i < n:
        row = rows[i]
        if row and isinstance(row[0], str) and row[0].startswith("TF: "):
            tf = row[0][4:].strip()
            scanned_at = ""
            if len(row) > 1 and isinstance(row[1], str) and row[1].startswith("Scanned at: "):
                scanned_at = row[1][len("Scanned at: "):]
            i += 1
            if i < n and list(rows[i][:hlen]) == data_header:
                i += 1
            data_rows = []
            while i < n and rows[i] and not (isinstance(rows[i][0], str) and rows[i][0].startswith("TF: ")):
                if rows[i][0] not in ("", None):
                    data_rows.append(list(rows[i][:hlen]))
                i += 1
            blocks[tf] = (scanned_at, data_rows)
        else:
            i += 1
    return blocks


def _parse_existing_dynamic(rows: list):
    blocks = {}
    header = None
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
            if i < n and rows[i] and rows[i][0] not in ("", None):
                if header is None:
                    header = list(rows[i])
                i += 1
            data_rows = []
            while i < n and rows[i] and not (isinstance(rows[i][0], str) and rows[i][0].startswith("TF: ")):
                if rows[i][0] not in ("", None):
                    data_rows.append(list(rows[i]))
                i += 1
            blocks[tf] = (scanned_at, data_rows)
        else:
            i += 1
    return blocks, header


def _build_intraday_rows(df: pd.DataFrame, due_tfs: list, scanned_at: str) -> list:
    old_blocks = _parse_existing_generic(_fetch_existing_rows("Gem_Setup_Intraday"), DATA_HEADER)

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


def _build_new_setup_rows(df: pd.DataFrame, due_tfs: list, scanned_at: str) -> list:
    old_blocks = _parse_existing_generic(_fetch_existing_rows("New_HA_Squeeze_Setup"), NEW_SETUP_HEADER)

    fresh_blocks = {tf: (scanned_at, []) for tf in due_tfs if tf in ALL_TF_ORDER}
    if not df.empty:
        for tf, g in df.groupby("TF"):
            g = g.sort_values("SQ%", ascending=False)
            data_rows = [[r["Symbol"], r["Side"], r["Close"], r.get("SQ%", "")] for _, r in g.iterrows()]
            fresh_blocks[tf] = (scanned_at, data_rows)

    combined = dict(old_blocks)
    combined.update(fresh_blocks)
    ordered_tfs = [tf for tf in ALL_TF_ORDER if tf in combined]

    rows = []
    for tf in ordered_tfs:
        s_at, data_rows = combined[tf]
        rows.append([f"TF: {tf}", f"Scanned at: {s_at}"])
        rows.append(NEW_SETUP_HEADER)
        for dr in data_rows:
            rows.append([_json_safe(v) for v in dr])
        rows.append([""])
    return rows


def _build_full_carryforward_rows(section: str, df: pd.DataFrame, due_tfs: list, scanned_at: str) -> list:
    existing_raw = _fetch_existing_rows(section)
    old_blocks, existing_header = _parse_existing_dynamic(existing_raw)

    fresh_header = df.columns.tolist() if not df.empty else None
    header_row = fresh_header or existing_header

    fresh_blocks = {}
    if not df.empty and "TF" in df.columns:
        sort_cols = ["TF"]
        ascending = [True]
        if "Gem Score%" in df.columns:
            sort_cols.append("Gem Score%")
            ascending.append(False)
        view = df.sort_values(sort_cols, ascending=ascending)
        for tf, g in view.groupby("TF"):
            data_rows = [[_json_safe(v) for v in r.tolist()] for _, r in g.iterrows()]
            fresh_blocks[tf] = (scanned_at, data_rows)

    for tf in due_tfs:
        if tf not in fresh_blocks:
            fresh_blocks[tf] = (scanned_at, [])

    combined = dict(old_blocks)
    combined.update(fresh_blocks)
    ordered_tfs = [tf for tf in ALL_TF_ORDER if tf in combined]

    rows = []
    for tf in ordered_tfs:
        s_at, data_rows = combined[tf]
        rows.append([f"TF: {tf}", f"Scanned at: {s_at}"])
        if header_row:
            rows.append(header_row)
        for dr in data_rows:
            rows.append(dr)
        rows.append([""])

    if not rows:
        return [["No rows yet"]]
    return rows


def _post(section: str, rows: list) -> None:
    if not APPS_SCRIPT_URL:
        print("APPS_SCRIPT_URL set nahi hai -- Sheet export skip ho raha hai.")
        return
    payload = {"sheetName": section[:99], "rows": rows}
    try:
        resp = requests.post(APPS_SCRIPT_URL, json=payload, timeout=60)
        if resp.status_code == 200:
            print(f"Sheet updated: {section} ({len(rows)} rows written)")
        else:
            print(f"Sheet update failed for {section}: {resp.status_code} {resp.text[:200]}")
    except Exception as e:
        print(f"Sheet export error for {section}: {e}")


def notify_discord(new_setup_df: pd.DataFrame) -> None:
    """Is run mein jo naye HA+Squeeze setup mile, unki Discord pe alert bhejta hai."""
    if not DISCORD_WEBHOOK_URL:
        return
    if new_setup_df is None or new_setup_df.empty:
        return

    lines = ["**New HA + Squeeze Setup mila!**", ""]
    view = new_setup_df.sort_values("TF") if "TF" in new_setup_df.columns else new_setup_df
    for _, r in view.iterrows():
        tf = r.get("TF", "")
        symbol = r.get("Symbol", "")
        side = r.get("Side", "")
        close = r.get("Close", "")
        sq = r.get("SQ%", "")
        lines.append(f"`{tf}` **{symbol}** -- {side} @ {close} (SQ% {sq})")

    content = "\n".join(lines)
    if len(content) > 1900:
        content = content[:1900] + "\n...(trimmed)"

    try:
        resp = requests.post(DISCORD_WEBHOOK_URL, json={"content": content}, timeout=30)
        if resp.status_code not in (200, 204):
            print(f"Discord notify failed: {resp.status_code} {resp.text[:200]}")
        else:
            print(f"Discord notify sent ({len(new_setup_df)} signals)")
    except Exception as e:
        print(f"Discord notify error: {e}")


def export_status_only(scanned_at: str) -> None:
    _post("Status", [["Current scan time:", scanned_at]])


def export_to_google_sheet(outputs: dict, scanned_at: str, due_tfs: list) -> None:
    for section, df in outputs.items():
        if section == "Gem_Setup_Intraday":
            body = _build_intraday_rows(df, due_tfs, scanned_at)
        elif section == "New_HA_Squeeze_Setup":
            body = _build_new_setup_rows(df, due_tfs, scanned_at)
        else:
            body = _build_full_carryforward_rows(section, df, due_tfs, scanned_at)
        _post(section, body)

    notify_discord(outputs.get("New_HA_Squeeze_Setup"))
    export_status_only(scanned_at)
