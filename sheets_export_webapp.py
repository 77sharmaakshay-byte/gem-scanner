import requests
import os
from typing import Dict, List
import pandas as pd

APPS_SCRIPT_URL = os.environ.get("APPS_SCRIPT_URL")
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")

# Per-timeframe channel webhooks (optional -- agar set nahi hain, sirf
# general wala #general channel use hoga, jo pehle se kaam kar raha hai)
DISCORD_TF_WEBHOOKS = {
    "5m": os.environ.get("DISCORD_WEBHOOK_5M"),
    "15m": os.environ.get("DISCORD_WEBHOOK_15M"),
    "30m": os.environ.get("DISCORD_WEBHOOK_30M"),
    "45m": os.environ.get("DISCORD_WEBHOOK_45M"),
    "1H": os.environ.get("DISCORD_WEBHOOK_1H"),
    "75m": os.environ.get("DISCORD_WEBHOOK_75M"),
    "2H": os.environ.get("DISCORD_WEBHOOK_2H"),
    "150m": os.environ.get("DISCORD_WEBHOOK_150M"),
    "3H": os.environ.get("DISCORD_WEBHOOK_3H"),
    "4H": os.environ.get("DISCORD_WEBHOOK_4H"),
    "1D": os.environ.get("DISCORD_WEBHOOK_HIGHER"),
    "2D": os.environ.get("DISCORD_WEBHOOK_HIGHER"),
    "3D": os.environ.get("DISCORD_WEBHOOK_HIGHER"),
}

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


def _fmt_num(value) -> str:
    try:
        if value is None or value == "" or pd.isna(value):
            return ""
        return f"{float(value):.1f}"
    except Exception:
        return str(value)


def notify_discord(outputs: dict) -> None:
    """Is run mein jitni bhi sheets mein naya data mila, sabka ek combined
    alert #general (ya default webhook) pe bhejta hai -- squeeze% details ke saath.
    Saath hi, agar per-TF channel webhooks set hain, to har TF ka apna signal
    uske dedicated channel mein bhi bhejta hai."""
    non_empty = {k: v for k, v in outputs.items() if v is not None and not v.empty}
    if not non_empty:
        return

    def _line(r) -> str:
        tf = r.get("TF", "")
        sym = r.get("Symbol", "")
        side = r.get("Side", "")
        close = r.get("Close", "")
        piece = f"`{tf}` **{sym}**"
        if side:
            piece += f" -- {side}"
        if close != "" and close is not None:
            piece += f" @ {close}"
        sq = _fmt_num(r.get("SQ%"))
        rsi_bb = _fmt_num(r.get("RSI-BB%"))
        extras = []
        if sq:
            extras.append(f"SQ% {sq}")
        if rsi_bb:
            extras.append(f"RSI-BB% {rsi_bb}")
        if extras:
            piece += " (" + ", ".join(extras) + ")"
        return piece

    def _send(webhook: str, content: str) -> None:
        if not webhook or not content:
            return
        if len(content) > 1900:
            content = content[:1900] + "\n...(trimmed)"
        try:
            resp = requests.post(webhook, json={"content": content}, timeout=30)
            if resp.status_code not in (200, 204):
                print(f"Discord notify failed: {resp.status_code} {resp.text[:200]}")
        except Exception as e:
            print(f"Discord notify error: {e}")

    # 1) General/summary channel -- sab kuch ek jagah, jaisa pehle se hai.
    if DISCORD_WEBHOOK_URL:
        lines = ["**Naye Signals mile!**", ""]
        for section, df in non_empty.items():
            lines.append(f"**{section}** ({len(df)}):")
            for _, r in df.head(10).iterrows():
                lines.append(_line(r))
            if len(df) > 10:
                lines.append(f"...+{len(df) - 10} more")
            lines.append("")
        _send(DISCORD_WEBHOOK_URL, "\n".join(lines).strip())
        print(f"Discord general notify sent ({len(non_empty)} sections)")

    # 2) Per-timeframe channels -- har TF ka apna dedicated channel.
    per_tf_rows: Dict[str, List[str]] = {}
    for section, df in non_empty.items():
        if "TF" not in df.columns:
            continue
        for tf, g in df.groupby("TF"):
            webhook = DISCORD_TF_WEBHOOKS.get(tf)
            if not webhook:
                continue
            bucket = per_tf_rows.setdefault(tf, [f"**{section}**"])
            for _, r in g.head(10).iterrows():
                bucket.append(_line(r))
            if len(g) > 10:
                bucket.append(f"...+{len(g) - 10} more")

    for tf, lines in per_tf_rows.items():
        webhook = DISCORD_TF_WEBHOOKS.get(tf)
        _send(webhook, "\n".join(lines).strip())
    if per_tf_rows:
        print(f"Discord per-TF notify sent for: {', '.join(per_tf_rows.keys())}")

def notify_discord_heartbeat(scanned_at: str) -> None:
    """Skip-run (koi TF due nahi tha) mein bhi ek chhota confirmation
    bhejta hai #general mein, taaki pata chale system chal raha hai --
    Sheet ke Status tab jaisa hi behavior."""
    if not DISCORD_WEBHOOK_URL:
        return
    content = f"Scan hua ({scanned_at}) -- koi naya signal nahi mila is cycle mein."
    try:
        resp = requests.post(DISCORD_WEBHOOK_URL, json={"content": content}, timeout=30)
        if resp.status_code not in (200, 204):
            print(f"Discord heartbeat failed: {resp.status_code} {resp.text[:200]}")
    except Exception as e:
        print(f"Discord heartbeat error: {e}")


def export_status_only(scanned_at: str) -> None:
    _post("Status", [["Current scan time:", scanned_at]])
    notify_discord_heartbeat(scanned_at)


def export_to_google_sheet(outputs: dict, scanned_at: str, due_tfs: list) -> None:
    for section, df in outputs.items():
        if section == "Gem_Setup_Intraday":
            body = _build_intraday_rows(df, due_tfs, scanned_at)
        elif section == "New_HA_Squeeze_Setup":
            body = _build_new_setup_rows(df, due_tfs, scanned_at)
        else:
            body = _build_full_carryforward_rows(section, df, due_tfs, scanned_at)
        _post(section, body)

    notify_discord(outputs)
    export_status_only(scanned_at)
