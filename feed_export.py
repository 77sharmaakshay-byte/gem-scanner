"""App ki feed: docs/feed.json likhta hai.

Scanner har run mein sirf un timeframes ko scan karta hai jo us waqt due
hain -- 11 baje sirf intraday, 3:35 par higher TF. Isliye feed ko poora
dobara likhna galat hoga: ek intraday run 1D/1W ka data mita dega. Yahan
purani feed padhi jaati hai aur sirf un (setup, timeframe) ke rows badle
jaate hain jo is run mein asal mein scan hue.

GitHub Pages isi file ko serve karta hai; app use download karke phone ke
andar hi filter karta hai, to koi server nahi chahiye.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Sequence

import pandas as pd

FEED_VERSION = 1

REPO_DIR = os.path.dirname(os.path.abspath(__file__))
FEED_DIR = os.path.join(REPO_DIR, "docs")
FEED_PATH = os.path.join(FEED_DIR, "feed.json")

# Alert rows ke columns, feed mein isi order mein jaate hain.
ALERT_COLS = [
    "setup",
    "tf",
    "sym",
    "side",
    "close",
    "sq",
    "rsibb",
    "sqz_ago",
    "entry",
    "ts",
]

# Universe rows (har stock x TF) -- feed_universe_row() ke keys.
UNIVERSE_COLS = [
    "sym",
    "tf",
    "ts",
    "close",
    "rsi",
    "rsiw",
    "rratio",
    "prw",
    "pratio",
    "sq",
    "rsibb",
    "sqz_ago",
    "psqz_ago",
    "rsq",
    "psq",
    "hab",
    "hbl",
    "mbb_b",
    "mbb_s",
]

# Kaunsa section kis TF-list se aata hai. Jo section is run mein scan nahi
# hua, uske purane rows feed mein waise hi rehte hain.
SECTION_SOURCE = {
    "Gem_Setup_Intraday": "due",
    "Gem_Setup_HigherTF": "due",
    "Price_BB_Squeeze": "due",
    "RSI_BB_Squeeze": "due",
    "Both_Squeeze": "due",
    "New_HA_Squeeze_Setup": "due",
    "Mid_BB_Reversal_Setup": "mid_bb",
    "RSI_BB_Cross_Setup": "cross",
}


def _num(value: Any) -> Optional[float]:
    if value is None or value == "":
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _int(value: Any, default: int = 0) -> int:
    got = _num(value)
    return default if got is None else int(got)


def _text(value: Any) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    return str(value)


def _ts(value: Any) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    if isinstance(value, str):
        return value
    try:
        return pd.Timestamp(value).isoformat(timespec="minutes")
    except Exception:
        return _text(value)


def _alert_row(setup: str, row: Dict[str, Any]) -> List[Any]:
    return [
        setup,
        _text(row.get("TF")),
        _text(row.get("Symbol")),
        _text(row.get("Side")),
        _num(row.get("Close")),
        _num(row.get("SQ%")),
        _num(row.get("RSI-BB%")),
        _int(row.get("Sqz Bars Ago"), 999),
        _num(row.get("Entry")),
        _ts(row.get("Date")),
    ]


def _universe_row(row: Dict[str, Any]) -> List[Any]:
    return [row.get(col) for col in UNIVERSE_COLS]


def _dedupe(rows: List[List[Any]], cols: Sequence[str], key_cols: Sequence[str]) -> List[List[Any]]:
    """Ek key ka ek hi row rakho -- baad wala jeetta hai.

    1D/2D/3D dono scans se guzarte hain (run_scanner aur scan_mid_bb_setup),
    to bina iske har stock un timeframes par do baar dikhta tha.
    """
    index = [cols.index(c) for c in key_cols]
    out: Dict[tuple, List[Any]] = {}
    for row in rows:
        key = tuple(row[i] if i < len(row) else None for i in index)
        out[key] = row
    return list(out.values())


def _load_existing() -> Dict[str, Any]:
    if not os.path.exists(FEED_PATH):
        return {}
    try:
        with open(FEED_PATH, "r", encoding="utf-8") as fh:
            got = json.load(fh)
        return got if isinstance(got, dict) else {}
    except (OSError, ValueError) as exc:
        print(f"Feed: purani feed padh nahi paya ({exc}); nayi se shuru.")
        return {}


def _kept_rows(
    old: Dict[str, Any],
    block: str,
    cols: Sequence[str],
    drop: Iterable[tuple],
    key_cols: Sequence[str],
) -> List[List[Any]]:
    """Purane rows jo is run mein refresh nahi hue.

    Purani feed ke apne column order ke hisaab se padhte hain, taaki
    columns badalne par bhi purana data galat jagah na chala jaye.
    """
    old_block = old.get(block) or {}
    old_cols = old_block.get("cols") or []
    old_rows = old_block.get("rows") or []
    if not old_cols or not old_rows:
        return []

    index = {name: i for i, name in enumerate(old_cols)}
    if any(col not in index for col in key_cols):
        return []

    drop_set = set(drop)
    kept: List[List[Any]] = []
    for row in old_rows:
        if not isinstance(row, list):
            continue
        key = tuple(row[index[col]] if index[col] < len(row) else None for col in key_cols)
        if key in drop_set:
            continue
        kept.append([row[index[col]] if col in index and index[col] < len(row) else None for col in cols])
    return kept


def write_feed(
    outputs: Dict[str, "pd.DataFrame"],
    universe_rows: List[Dict[str, Any]],
    scanned_str: str,
    due_tfs: Sequence[str],
    mid_bb_tfs: Sequence[str],
    cross_tfs: Sequence[str],
    late_eod: bool = False,
) -> Optional[str]:
    """Feed likho aur path return karo (ya None agar fail ho)."""
    scanned_sets = {
        "due": list(due_tfs or []),
        "mid_bb": list(mid_bb_tfs or []),
        "cross": list(cross_tfs or []),
    }

    old = _load_existing()

    # 1) Alerts -- is run mein jo (setup, tf) scan hue unke rows replace,
    #    baaki purane jaise.
    fresh_alerts: List[List[Any]] = []
    refreshed_alerts: List[tuple] = []
    for setup, source in SECTION_SOURCE.items():
        tfs = scanned_sets.get(source, [])
        if not tfs:
            continue
        for tf in tfs:
            refreshed_alerts.append((setup, tf))
        df = outputs.get(setup)
        if df is None or not hasattr(df, "empty") or df.empty:
            continue
        for _, row in df.iterrows():
            fresh_alerts.append(_alert_row(setup, row.to_dict()))

    alerts = _dedupe(
        _kept_rows(old, "alerts", ALERT_COLS, refreshed_alerts, ("setup", "tf")) + fresh_alerts,
        ALERT_COLS,
        ("setup", "tf", "sym"),
    )

    # 2) Universe -- sirf un TFs ke rows badalte hain jo is run mein chale.
    #    Mid-BB scan bhi universe rows deta hai (1W/1M/6M wahin se aate
    #    hain), isliye uske TFs bhi refresh list mein hone chahiye -- warna
    #    purane 1W rows rehte hain aur naye upar add ho jaate hain.
    fresh_universe = [_universe_row(row) for row in universe_rows]
    universe_tfs = list(dict.fromkeys(list(scanned_sets["due"]) + list(scanned_sets["mid_bb"])))
    refreshed_tfs = [(tf,) for tf in universe_tfs]
    universe = _dedupe(
        _kept_rows(old, "universe", UNIVERSE_COLS, refreshed_tfs, ("tf",)) + fresh_universe,
        UNIVERSE_COLS,
        ("sym", "tf"),
    )

    # 3) Har TF ka apna last-updated, taaki app purane TF ko grey dikha sake.
    tf_updated = dict(old.get("tf_updated") or {})
    stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    for tfs in scanned_sets.values():
        for tf in tfs:
            tf_updated[tf] = stamp

    feed = {
        "v": FEED_VERSION,
        "name": "Scan by Akshay",
        "scanned": scanned_str,
        "updated_utc": stamp,
        "run": {
            "due_tfs": scanned_sets["due"],
            "mid_bb_tfs": scanned_sets["mid_bb"],
            "cross_tfs": scanned_sets["cross"],
            "late_eod": bool(late_eod),
        },
        "tf_updated": tf_updated,
        "counts": {
            "alerts": len(alerts),
            "universe": len(universe),
        },
        "alerts": {"cols": ALERT_COLS, "rows": alerts},
        "universe": {"cols": UNIVERSE_COLS, "rows": universe},
    }

    try:
        os.makedirs(FEED_DIR, exist_ok=True)
        with open(FEED_PATH, "w", encoding="utf-8") as fh:
            json.dump(feed, fh, separators=(",", ":"), ensure_ascii=False)
    except OSError as exc:
        print(f"Feed likh nahi paya: {exc}")
        return None

    size_kb = os.path.getsize(FEED_PATH) / 1024
    print(
        f"Feed likhi: docs/feed.json | alerts={len(alerts)} "
        f"(naye {len(fresh_alerts)}) | universe={len(universe)} "
        f"(naye {len(fresh_universe)}) | {size_kb:.0f} KB"
    )
    return FEED_PATH
