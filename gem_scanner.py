# Install in notebook if needed:
# !pip install yfinance pandas numpy requests tqdm openpyxl -q

from __future__ import annotations

import io
import logging
import os
import random
import time
import warnings
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional, Tuple

import numpy as np
import pandas as pd

try:
    import requests
except ImportError:
    requests = None

try:
    from tqdm import tqdm
except ImportError:
    def tqdm(iterable, *args, **kwargs):
        return iterable

try:
    import yfinance as yf
except ImportError:
    yf = None

try:
    from IPython.display import HTML, display
except Exception:
    HTML = None
    display = None

from sheets_export_webapp import export_to_google_sheet, export_status_only

warnings.filterwarnings("ignore")
logging.getLogger("yfinance").setLevel(logging.CRITICAL)


# =============================================================================
# USER SETTINGS
# =============================================================================

RUN_SCANNER = True
MAX_STOCKS = None
EXPORT_EXCEL = False

INTRADAY_GEM_THRESHOLD = 88.0
HIGHER_TF_GEM_THRESHOLD = 87.0
MIN_VISIBLE_SQUEEZE = 85.0

SQUEEZE_HISTORY_COUNT = 5
SQUEEZE_MOVE_LOOKAHEAD_BARS = 10
GEM_FIRE_TOLERANCE_BARS = 2

RSI_LENGTH = 12
RSI_BB_LENGTH = 20
RSI_BB_MULT = 2.0
RSI_MIN_CONTRACTION = 55.0
RSI_BB_PERSIST_BARS = 2

PRICE_BB_LENGTH = 20
PRICE_BB_MULT = 2.0
PRICE_BB_LOOKBACK = 30
PRICE_CONTRACTION = 75.0
PRICE_SQUEEZE_MEMORY = 4
PRIMING_THRESHOLD = 80.0

VOL_SPIKE_THRESHOLD = 2.0
VOL_BB_LENGTH = 30
VOL_BB_MULT = 2.5
VOL_KC_LENGTH = 14
VOL_KC_MULT = 1.5

MOM_BB_LENGTH = 12
MOM_BB_MULT = 2.0
MOM_KC_LENGTH = 10
MOM_KC_MULT = 1.0

MACD_FAST = 3
MACD_SLOW = 15
MACD_SIGNAL = 5
VORTEX_LENGTH = 5

HA_BB_LENGTH = 20
HA_BB_MULT = 2.0
ENTRY_BUFFER = 0.05
SETUP_VALID_BARS = 3

HA_SETUP_REQUIRES_SQUEEZE = True
HA_SETUP_ACCEPTS_PRICE_ONLY = True
HA_SETUP_ACCEPTS_RSI_ONLY = True
HA_SETUP_ACCEPTS_BOTH = True

HA_SETUP_REQUIRES_BB_BREAKOUT = False
PREV_HA_NOT_STRONG_FILTER = False
PREV_HA_CLOSE_INSIDE_BB_FILTER = False

CHECK_DATA_FRESHNESS = True
REJECT_STALE_DATA = False
DOWNLOAD_DELAY = 0.20
MIN_BARS_SCAN = 80
LOCAL_TIMEZONE = "Asia/Kolkata"
MARKET_OPEN_OFFSET_MINUTES = 9 * 60 + 15


FRESHNESS_THRESHOLDS: Dict[str, Tuple[int, int]] = {
    "5m": (2, 48),
    "15m": (2, 48),
    "30m": (3, 48),
    "45m": (3, 48),
    "1H": (4, 72),
    "75m": (4, 72),
    "90m": (4, 72),
    "2H": (6, 96),
    "150m": (8, 120),
    "3H": (8, 120),
    "4H": (10, 144),
    "1D": (48, 240),
    "2D": (72, 360),
    "3D": (96, 480),
    "4D": (120, 600),
    "7D": (168, 840),
    "9D": (216, 1080),
    "1W": (240, 600),
    "2W": (480, 1200),
    "3W": (720, 1800),
    "4W": (960, 2400),
    "1M": (720, 2160),
    "6M": (4320, 8760),
}


INTRADAY_TIMEFRAMES = ["15m", "30m", "45m", "1H", "75m", "2H", "150m", "3H", "4H"]
HIGHER_TIMEFRAMES = ["1D", "2D", "3D"]
NEW_PATTERN_TIMEFRAMES = ["1D", "2D", "3D", "1W", "1M", "6M"]

TIMEFRAMES: Dict[str, Dict[str, Any]] = {
    "5m": {"interval": "5m", "scan_period": "60d", "resample": None, "tf_days": 5 / 1440},
    "15m": {"interval": "15m", "scan_period": "60d", "resample": None, "tf_days": 15 / 1440},
    "30m": {"interval": "15m", "scan_period": "60d", "resample": "30min", "tf_days": 30 / 1440},
    "45m": {"interval": "15m", "scan_period": "60d", "resample": "45min", "tf_days": 45 / 1440},
    "1H": {"interval": "15m", "scan_period": "60d", "resample": "60min", "tf_days": 1 / 24},
    "75m": {"interval": "15m", "scan_period": "60d", "resample": "75min", "tf_days": 75 / 1440},
    "90m": {"interval": "15m", "scan_period": "60d", "resample": "90min", "tf_days": 90 / 1440},
    "2H": {"interval": "15m", "scan_period": "60d", "resample": "120min", "tf_days": 2 / 24},
    "150m": {"interval": "15m", "scan_period": "60d", "resample": "150min", "tf_days": 150 / 1440},
    "3H": {"interval": "15m", "scan_period": "60d", "resample": "180min", "tf_days": 3 / 24},
    "4H": {"interval": "15m", "scan_period": "60d", "resample": "240min", "tf_days": 4 / 24},
    "1D": {"interval": "1d", "scan_period": "max", "resample": None, "tf_days": 1},
    "2D": {"interval": "1d", "scan_period": "max", "resample": "2D", "tf_days": 2},
    "3D": {"interval": "1d", "scan_period": "max", "resample": "3D", "tf_days": 3},
    "4D": {"interval": "1d", "scan_period": "max", "resample": "4D", "tf_days": 4},
    "7D": {"interval": "1d", "scan_period": "max", "resample": "7D", "tf_days": 7},
    "9D": {"interval": "1d", "scan_period": "max", "resample": "9D", "tf_days": 9},
    "1W": {"interval": "1wk", "scan_period": "max", "resample": None, "tf_days": 7},
    "2W": {"interval": "1wk", "scan_period": "max", "resample": "2W-MON", "tf_days": 14},
    "3W": {"interval": "1wk", "scan_period": "max", "resample": "3W-MON", "tf_days": 21},
    "4W": {"interval": "1wk", "scan_period": "max", "resample": "4W-MON", "tf_days": 28},
    "1M": {"interval": "1mo", "scan_period": "max", "resample": None, "tf_days": 30},
    "6M": {"interval": "1mo", "scan_period": "max", "resample": "6MO", "tf_days": 180},
}

SCAN_TIMEFRAMES = INTRADAY_TIMEFRAMES + HIGHER_TIMEFRAMES


def timeframes_due_now() -> List[str]:
    """Sirf woh timeframes return karta hai jinka bar (roughly) abhi close hua hoga.
    Cron/runner delay ko handle karne ke liye 2-min tolerance rakha hai."""
    TOLERANCE_MINUTES = 2

    now = _local_now_naive()
    open_dt = now.normalize() + pd.Timedelta(minutes=MARKET_OPEN_OFFSET_MINUTES)
    elapsed = int((now - open_dt).total_seconds() // 60)
    if elapsed < 0:
        return []

    due: List[str] = []
    for tf in INTRADAY_TIMEFRAMES:
        tf_minutes = round(TIMEFRAMES[tf]["tf_days"] * 1440)
        if tf_minutes <= 0:
            continue
        remainder = elapsed % tf_minutes
        close_to_boundary = remainder <= TOLERANCE_MINUTES or (tf_minutes - remainder) <= TOLERANCE_MINUTES
        if close_to_boundary:
            due.append(tf)

    if now.hour >= 15:
        due += HIGHER_TIMEFRAMES

    return due


SCAN_INTERVAL_MINUTES = 15
MARKET_CLOSE_OFFSET_MINUTES = 15 * 60 + 15  # 3:15 PM


def compute_next_scan_time(now: pd.Timestamp) -> Optional[pd.Timestamp]:
    """Agla scheduled run kab hoga -- 15-min grid par, market hours ke andar."""
    market_open = now.normalize() + pd.Timedelta(minutes=MARKET_OPEN_OFFSET_MINUTES)
    market_close = now.normalize() + pd.Timedelta(minutes=MARKET_CLOSE_OFFSET_MINUTES)

    if now < market_open:
        return market_open

    interval = pd.Timedelta(minutes=SCAN_INTERVAL_MINUTES)
    elapsed = now - market_open
    steps = int(elapsed / interval) + 1
    nxt = market_open + steps * interval

    if nxt > market_close:
        return None
    return nxt


RSI_CROSS_INTRADAY_TFS = ["30m", "45m", "1H", "2H", "75m", "90m", "150m", "3H", "4H"]
RSI_CROSS_HIGHER_TFS = ["1D", "2D", "3D", "1W", "1M"]
RSI_CROSS_TIMEFRAMES = RSI_CROSS_INTRADAY_TFS + RSI_CROSS_HIGHER_TFS


def rsi_cross_due_now() -> List[str]:
    """RSI-BB Cross setup ke liye apna dedicated due-check -- intraday wale
    TFs har apne boundary par, higher wale sirf 3 PM ke baad."""
    TOLERANCE_MINUTES = 2
    now = _local_now_naive()
    open_dt = now.normalize() + pd.Timedelta(minutes=MARKET_OPEN_OFFSET_MINUTES)
    elapsed = int((now - open_dt).total_seconds() // 60)
    if elapsed < 0:
        return []

    due: List[str] = []
    for tf in RSI_CROSS_INTRADAY_TFS:
        tf_minutes = round(TIMEFRAMES[tf]["tf_days"] * 1440)
        if tf_minutes <= 0:
            continue
        remainder = elapsed % tf_minutes
        close_to_boundary = remainder <= TOLERANCE_MINUTES or (tf_minutes - remainder) <= TOLERANCE_MINUTES
        if close_to_boundary:
            due.append(tf)

    if now.hour >= 15:
        due += RSI_CROSS_HIGHER_TFS

    return due


SYMBOL_RENAMES = {
    "FINNIFTY": None,
    "IDFC": None,
    "GMRINFRA": "GMRAIRPORT",
    "LTFH": "LTFINANCE",
    "LTF": "LTFINANCE",
    "PEL": "POONAWALLA",
    "ZOMATO": "ETERNAL",
}
REMOVE_BAD_YF = {"ISEC", "LTFINANCE", "LTIM", "TATAMOTORS"}

ALWAYS_INCLUDE_SYMBOLS = [
    "DMART",
]

FNO_STOCKS_RAW = [
    "AARTIIND","ABB","ABBOTINDIA","ABCAPITAL","ABFRL","ACC","ADANIENT",
    "ADANIPORTS","ALKEM","AMBUJACEM","ANGELONE","APLAPOLLO","APOLLOHOSP",
    "APOLLOTYRE","ASHOKLEY","ASIANPAINT","ASTRAL","ATUL","AUBANK",
    "AUROPHARMA","AXISBANK","BAJAJ-AUTO","BAJAJFINSV","BAJAJHLDNG",
    "BAJFINANCE","BALKRISIND","BANDHANBNK","BANKBARODA","BANKINDIA",
    "BATAINDIA","BEL","BERGEPAINT","BHARATFORG","BHARTIARTL","BHEL",
    "BIOCON","BLUEDART","BOSCHLTD","BPCL","BRITANNIA","BSOFT","CAMS",
    "CANBK","CANFINHOME","CASTROLIND","CDSL","CESC","CGPOWER","CHAMBLFERT",
    "CHOLAFIN","CIPLA","COALINDIA","COFORGE","COLPAL","CONCOR","COROMANDEL",
    "CROMPTON","CUB","CUMMINSIND","DABUR","DALBHARAT","DEEPAKNTR",
    "DELTACORP","DELHIVERY","DIVISLAB","DIXON","DLF","DRREDDY","EICHERMOT",
    "ELGIEQUIP","EMAMILTD","ENDURANCE","ESCORTS","EXIDEIND","FEDERALBNK",
    "FINNIFTY","FORTIS","GAIL","GLENMARK","GMRINFRA","GNFC","GODREJCP",
    "GODREJPROP","GRANULES","GRAPHITE","GRASIM","GSPL","GUJGASLTD",
    "HAL","HAVELLS","HCLTECH","HDFCAMC","HDFCBANK","HDFCLIFE","HEROMOTOCO",
    "HINDALCO","HINDCOPPER","HINDPETRO","HINDUNILVR","HONAUT","HUDCO",
    "ICICIBANK","ICICIGI","ICICIPRULI","IDEA","IDFC","IDFCFIRSTB",
    "IEX","IGL","INDHOTEL","INDIAMART","INDIGO","INDUSTOWER","INDUSINDBK",
    "INFY","INTELLECT","IOB","IOC","IPCALAB","IRB","IRCTC","ISEC",
    "ITC","JINDALSTEL","JKCEMENT","JSL","JSWENERGY","JSWSTEEL","JUBLFOOD",
    "JUBLINGREA","KAJARIACER","KANSAINER","KEI","KOTAKBANK","KPIL",
    "KRBL","LALPATHLAB","LAURUSLABS","LICHSGFIN","LT","LTFH","LTIM",
    "LTTS","LUPIN","M&M","M&MFIN","MANAPPURAM","MARICO","MARUTI",
    "MCX","METROPOLIS","MFSL","MGL","MPHASIS","MRF","MRPL","MSUMI",
    "MUTHOOTFIN","NAM-INDIA","NATIONALUM","NAUKRI","NAVINFLUOR","NESTLEIND",
    "NLCINDIA","NMDC","NTPC","OBEROIRLTY","OFSS","OIL","ONGC","PAGEIND",
    "PEL","PERSISTENT","PETRONET","PFC","PIDILITIND","PIIND","PNB",
    "POLYCAB","POWERGRID","PRESTIGE","PVRINOX","RAMCOCEM","RAYMOND",
    "RECLTD","RELIANCE","RBLBANK","SAIL","SBICARD","SBILIFE","SBIN",
    "SHREECEM","SHRIRAMFIN","SIEMENS","SJVN","SKFINDIA","SRF","SUNPHARMA",
    "SUNTV","SUPREMEIND","SYNGENE","TATACHEM","TATACOMM","TATACONSUM",
    "TATAELXSI","TATAMOTORS","TATAPOWER","TATASTEEL","TCS","TECHM",
    "TIINDIA","TITAN","TORNTPHARM","TORNTPOWER","TRENT","TVSMOTOR","UBL",
    "UCOBANK","ULTRACEMCO","UNITDSPR","UPL","VEDL","VOLTAS","WHIRLPOOL",
    "WIPRO","ZEEL","ZOMATO","ZYDUSLIFE",
]


def scanner_symbol_universe(base_symbols: Iterable[str]) -> List[str]:
    return list(base_symbols) + ALWAYS_INCLUDE_SYMBOLS


def fix_symbols(sym_list: Iterable[str]) -> Tuple[List[str], List[str]]:
    nse_out, yf_out = [], []
    renamed, removed = [], []
    seen: set = set()

    for raw in sym_list:
        s = str(raw).strip().upper()
        target = SYMBOL_RENAMES.get(s, s)
        if target is None:
            removed.append(s)
            continue
        if target in REMOVE_BAD_YF:
            removed.append(target)
            continue
        if target in seen:
            continue
        seen.add(target)
        if target != s:
            renamed.append(f"{s}->{target}")
        nse_out.append(target)
        yf_out.append(target + ".NS")

    if removed:
        print(
            f"Removed {len(removed)}: {', '.join(removed[:25])}"
            + (" ..." if len(removed) > 25 else "")
        )
    if renamed:
        print(
            f"Renamed {len(renamed)}: {', '.join(renamed[:25])}"
            + (" ..." if len(renamed) > 25 else "")
        )
    print(f"Final symbol list: {len(nse_out)}")
    return nse_out, yf_out


def get_fo_symbols() -> Tuple[List[str], List[str]]:
    if requests is None:
        return fix_symbols(scanner_symbol_universe(FNO_STOCKS_RAW))

    url = "https://archives.nseindia.com/content/fo/fo_mktlots.csv"
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"
        )
    }

    try:
        resp = requests.get(url, headers=headers, timeout=12)
        resp.raise_for_status()
        df = pd.read_csv(io.StringIO(resp.text))
        col = df.columns[0]
        syms = df[col].dropna().astype(str).str.strip().str.upper().tolist()
        syms = [
            s for s in syms
            if (s.isalpha() or "-" in s or "&" in s)
            and len(s) > 1
            and s not in ("SYMBOL", "UNDERLYING")
        ]
        if len(syms) > 50:
            print(f"Loaded {len(syms)} F&O symbols from NSE")
            return fix_symbols(scanner_symbol_universe(syms))
    except Exception as e:
        print(f"NSE fetch failed: {e}. Using built-in list.")

    return fix_symbols(scanner_symbol_universe(FNO_STOCKS_RAW))


def _flatten(df: pd.DataFrame) -> pd.DataFrame:
    if isinstance(df.columns, pd.MultiIndex):
        df = df.copy()
        df.columns = df.columns.get_level_values(0)
    return df


def calc_rsi(series: pd.Series, length: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)
    ag = gain.ewm(alpha=1 / length, min_periods=length, adjust=False).mean()
    al = loss.ewm(alpha=1 / length, min_periods=length, adjust=False).mean()
    rs = ag / al.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    rsi = rsi.where(al != 0, 100)
    rsi = rsi.where(ag != 0, 0)
    rsi = rsi.where(~((ag == 0) & (al == 0)), 50)
    return rsi


def calc_bb(
    series: pd.Series,
    length: int = 20,
    mult: float = 2.0,
) -> Tuple[pd.Series, pd.Series, pd.Series]:
    basis = series.rolling(length).mean()
    std = series.rolling(length).std(ddof=0)
    return basis, basis + mult * std, basis - mult * std


def calc_heikin_ashi(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(
            columns=["HA_Open", "HA_High", "HA_Low", "HA_Close"],
            index=df.index,
        )

    ha_close = (df["Open"] + df["High"] + df["Low"] + df["Close"]) / 4
    ha_close_arr = ha_close.to_numpy(dtype=float)
    ha_open_arr = np.empty(len(df), dtype=float)
    ha_open_arr[0] = float(df["Open"].iloc[0])

    for i in range(1, len(df)):
        ha_open_arr[i] = (ha_open_arr[i - 1] + ha_close_arr[i - 1]) / 2

    ha_high = np.maximum(
        df["High"].to_numpy(dtype=float),
        np.maximum(ha_open_arr, ha_close_arr),
    )
    ha_low = np.minimum(
        df["Low"].to_numpy(dtype=float),
        np.minimum(ha_open_arr, ha_close_arr),
    )

    return pd.DataFrame(
        {
            "HA_Open": ha_open_arr,
            "HA_High": ha_high,
            "HA_Low": ha_low,
            "HA_Close": ha_close_arr,
        },
        index=df.index,
    )


def calc_ema(series: pd.Series, length: int) -> pd.Series:
    return series.ewm(span=length, adjust=False, min_periods=length).mean()


def calc_true_range(df: pd.DataFrame) -> pd.Series:
    high = df["High"].astype(float)
    low = df["Low"].astype(float)
    close = df["Close"].astype(float)
    prev_close = close.shift(1)
    return pd.concat(
        [
            high - low,
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)


def _cross_over(series: pd.Series, upper: pd.Series) -> pd.Series:
    return (series.gt(upper) & series.shift(1).le(upper.shift(1))).fillna(False)


def _cross_under(series: pd.Series, lower: pd.Series) -> pd.Series:
    return (series.lt(lower) & series.shift(1).ge(lower.shift(1))).fillna(False)


def _recent_true(mask: pd.Series, bars: int) -> pd.Series:
    return (
        mask.fillna(False)
        .astype(float)
        .rolling(bars + 1, min_periods=1)
        .max()
        .astype(bool)
    )


def _consecutive_true_count(mask: pd.Series) -> pd.Series:
    counts: List[int] = []
    current = 0
    for value in mask.fillna(False).astype(bool):
        current = current + 1 if value else 0
        counts.append(current)
    return pd.Series(counts, index=mask.index, dtype="int64")


def _bars_since_true(mask: pd.Series, missing: int = 999) -> pd.Series:
    counts: List[int] = []
    last_seen: Optional[int] = None
    for i, value in enumerate(mask.fillna(False).astype(bool)):
        if value:
            last_seen = i
            counts.append(0)
        elif last_seen is None:
            counts.append(missing)
        else:
            counts.append(min(missing, i - last_seen))
    return pd.Series(counts, index=mask.index, dtype="int64")


def _last_when_true(values: pd.Series, mask: pd.Series) -> pd.Series:
    return values.where(mask.fillna(False)).ffill()


def _entry_state(
    buy_setup: pd.Series,
    sell_setup: pd.Series,
    high: pd.Series,
    low: pd.Series,
    ha_high: pd.Series,
    ha_low: pd.Series,
) -> Tuple[pd.Series, pd.Series, pd.Series]:
    signals: List[int] = []
    entries: List[float] = []
    bars_out: List[int] = []

    signal_bar: Optional[int] = None
    signal_type = 0
    entry_price = np.nan

    for i, idx in enumerate(buy_setup.index):
        if bool(buy_setup.loc[idx]):
            signal_bar = i
            entry_price = float(ha_high.loc[idx]) + ENTRY_BUFFER
            signal_type = 3
        elif bool(sell_setup.loc[idx]):
            signal_bar = i
            entry_price = max(0.05, float(ha_low.loc[idx]) - ENTRY_BUFFER)
            signal_type = 4

        bars_since = 999 if signal_bar is None else i - signal_bar

        if 0 < bars_since <= SETUP_VALID_BARS and pd.notna(entry_price):
            if signal_type == 3 and float(high.loc[idx]) >= entry_price:
                signal_type = 5
            elif signal_type == 4 and float(low.loc[idx]) <= entry_price:
                signal_type = 6

        if bars_since > SETUP_VALID_BARS:
            signal_bar = None
            signal_type = 0
            entry_price = np.nan
            bars_since = 999

        signals.append(signal_type)
        entries.append(entry_price)
        bars_out.append(bars_since)

    return (
        pd.Series(signals, index=buy_setup.index, dtype="int64"),
        pd.Series(entries, index=buy_setup.index, dtype="float64"),
        pd.Series(bars_out, index=buy_setup.index, dtype="int64"),
    )


def _clip_0_100(series: pd.Series) -> pd.Series:
    return series.replace([np.inf, -np.inf], np.nan).clip(lower=0, upper=100)


def timeframe_group(tf: str) -> str:
    return "INTRADAY" if tf in INTRADAY_TIMEFRAMES else "HIGHER_TF"


def gem_threshold_for_tf(tf: str) -> float:
    return INTRADAY_GEM_THRESHOLD if timeframe_group(tf) == "INTRADAY" else HIGHER_TF_GEM_THRESHOLD


def assert_yfinance() -> None:
    if yf is None:
        raise RuntimeError("yfinance not installed. Run: !pip install yfinance -q")


def fetch_base(
    sym: str,
    interval: str,
    period: str,
    retries: int = 3,
    auto_adjust: bool = False,
) -> Optional[pd.DataFrame]:
    assert_yfinance()

    for attempt in range(retries + 1):
        try:
            df = yf.download(
                sym,
                interval=interval,
                period=period,
                progress=False,
                auto_adjust=auto_adjust,
                actions=False,
                threads=False,
            )
            if df is not None and not df.empty:
                df = _flatten(df).dropna(subset=["Close"])
                if not df.empty:
                    return df
        except Exception as e:
            msg = str(e).lower()
            if any(x in msg for x in ["429", "too many requests", "rate limit"]):
                time.sleep(min(12.0, (2 ** attempt) + random.uniform(0.2, 1.2)))

        if attempt < retries:
            time.sleep(0.5 + random.uniform(0.0, 0.4))

    return None


def _intraday_offset(rule: str) -> Optional[str]:
    r = str(rule).strip().lower()
    minutes: Optional[int] = None
    if r.endswith("min"):
        try:
            minutes = int(r[:-3])
        except ValueError:
            return None
    elif r.endswith("h"):
        try:
            minutes = int(r[:-1]) * 60
        except ValueError:
            return None
    if not minutes or minutes <= 0:
        return None
    offset_minutes = MARKET_OPEN_OFFSET_MINUTES % minutes
    return f"{offset_minutes}min"


_MASTER_CALENDAR_CACHE: Dict[str, pd.DatetimeIndex] = {}


def get_master_trading_calendar() -> pd.DatetimeIndex:
    """NIFTY 50 index (^NSEI) ka poora trading-date history use karke ek
    shared/master NSE trading-session calendar banata hai -- taaki HAR
    stock ka 2D/3D/4D/7D grouping isi ek common calendar se anchor ho,
    TradingView jaisa, na ki jis stock ka jab data start hota hai wahan se."""
    if "dates" in _MASTER_CALENDAR_CACHE:
        return _MASTER_CALENDAR_CACHE["dates"]

    dates = pd.DatetimeIndex([])
    try:
        idx_df = yf.download(
            "^NSEI",
            period="max",
            interval="1d",
            progress=False,
            auto_adjust=False,
            actions=False,
            threads=False,
        )
        idx_df = _flatten(idx_df).dropna(subset=["Close"])
        if not idx_df.empty:
            dates = pd.DatetimeIndex(idx_df.index).normalize().sort_values().unique()
    except Exception as e:
        print(f"Master calendar fetch failed (falling back to per-symbol anchor): {e}")

    _MASTER_CALENDAR_CACHE["dates"] = dates
    return dates


def _trading_day_group_size(rule: str) -> Optional[int]:
    r = str(rule).strip().upper()
    if r.endswith("D"):
        suffix_len = 1
    elif r.endswith("MO"):
        suffix_len = 2
    else:
        return None
    try:
        count = int(r[:-suffix_len])
    except ValueError:
        return None
    return count if count > 1 else None


def _resample_ohlcv(df: pd.DataFrame, rule: Optional[str]) -> pd.DataFrame:
    if not rule:
        return df.copy()

    work = df.copy()
    if not isinstance(work.index, pd.DatetimeIndex):
        work.index = pd.to_datetime(work.index)

    agg = {
        "Open": "first",
        "High": "max",
        "Low": "min",
        "Close": "last",
        "Volume": "sum",
    }

    trading_days = _trading_day_group_size(rule)
    if trading_days:
        # Shared master calendar (NIFTY 50 se) use karke har date ka
        # "trading session number" nikalo -- taaki grouping hamesha ek
        # common, TradingView-jaisi anchor se ho, is stock ke apne data
        # ki starting row se nahi.
        calendar = get_master_trading_calendar()
        work_dates = pd.DatetimeIndex(work.index).normalize()

        session_numbers: Optional[np.ndarray] = None
        if len(calendar) > 0:
            positions = calendar.searchsorted(work_dates)
            valid = (positions < len(calendar)) & (calendar[np.clip(positions, 0, len(calendar) - 1)] == work_dates)
            if valid.all():
                session_numbers = positions

        if session_numbers is not None:
            groups = session_numbers // trading_days
        else:
            # Fallback (calendar fetch fail hua ya kuch dates match nahi
            # hui) -- purana row-position wala tarika, kam se kam stable
            # to rahega is stock ke liye.
            groups = np.arange(len(work)) // trading_days

        resampled = work.groupby(groups).agg(agg)
        last_index = work.index.to_series().groupby(groups).last()
        resampled.index = pd.DatetimeIndex(last_index.to_numpy())

        # Har group ka size track karo -- taaki aage pata chal sake yeh
        # candle poori (closed) hai ya abhi ban hi rahi hai (live).
        group_sizes = pd.Series(groups).value_counts()
        resampled["_group_size"] = [group_sizes.get(g, 0) for g in sorted(set(groups))]

        return resampled.dropna(subset=["Close"])

    offset = _intraday_offset(rule)
    if offset:
        resampled = work.resample(
            rule,
            origin="start_day",
            offset=offset,
            label="right",
            closed="left",
        ).agg(agg)
    else:
        resampled = work.resample(rule).agg(agg)

    return resampled.dropna(subset=["Close"])


def timeframe_groups(timeframes: Iterable[str]) -> Dict[Tuple[str, str], List[str]]:
    groups: Dict[Tuple[str, str], List[str]] = {}
    for tf in timeframes:
        cfg = TIMEFRAMES[tf]
        key = (cfg["interval"], cfg["scan_period"])
        groups.setdefault(key, []).append(tf)
    return groups


def _local_now_naive() -> pd.Timestamp:
    try:
        return pd.Timestamp.now(tz=LOCAL_TIMEZONE).tz_localize(None)
    except Exception:
        return pd.Timestamp.now()


def _to_local_naive(ts: Any) -> pd.Timestamp:
    out = pd.Timestamp(ts)
    if out.tzinfo is not None:
        try:
            out = out.tz_convert(LOCAL_TIMEZONE)
        except Exception:
            pass
        out = out.tz_localize(None)
    return out


def data_hours_old(df: pd.DataFrame) -> Optional[float]:
    if df.empty or not isinstance(df.index, pd.DatetimeIndex):
        return None
    last_ts = _to_local_naive(df.index[-1])
    return (_local_now_naive() - last_ts).total_seconds() / 3600


def passes_freshness(df: pd.DataFrame, tf: str) -> Tuple[bool, bool]:
    if not CHECK_DATA_FRESHNESS:
        return True, False
    h_old = data_hours_old(df)
    if h_old is None:
        return False, False
    warn_h, reject_h = FRESHNESS_THRESHOLDS.get(tf, (48, 240))
    stale_warn = h_old > warn_h
    if REJECT_STALE_DATA and h_old > reject_h:
        return False, stale_warn
    return True, stale_warn


def compute_scan_frame(df: pd.DataFrame) -> pd.DataFrame:
    df = _flatten(df).copy()
    required = ["Open", "High", "Low", "Close"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Missing columns: {missing}")

    df = df.dropna(subset=required)
    min_bars = max(
        RSI_LENGTH,
        RSI_BB_LENGTH,
        PRICE_BB_LOOKBACK,
        PRICE_BB_LENGTH,
        HA_BB_LENGTH,
        VOL_BB_LENGTH,
        VOL_KC_LENGTH,
        MOM_BB_LENGTH,
        MOM_KC_LENGTH,
        MACD_SLOW + MACD_SIGNAL,
        VORTEX_LENGTH,
    ) + 5
    if len(df) < min_bars:
        return pd.DataFrame(index=df.index)

    open_ = df["Open"].astype(float)
    high = df["High"].astype(float)
    low = df["Low"].astype(float)
    close = df["Close"].astype(float)
    volume = (
        df["Volume"].astype(float)
        if "Volume" in df.columns
        else pd.Series(0.0, index=df.index)
    )

    price_basis, price_upper, price_lower = calc_bb(close, PRICE_BB_LENGTH, PRICE_BB_MULT)
    price_width_pct = ((price_upper - price_lower) / price_basis.replace(0, np.nan)) * 100
    tr = calc_true_range(df)
    kc_basis = calc_ema(close, PRICE_BB_LENGTH)
    kc_atr = tr.rolling(PRICE_BB_LENGTH, min_periods=PRICE_BB_LENGTH).mean()
    squeeze_15 = price_lower.gt(kc_basis - 1.5 * kc_atr) & price_upper.lt(kc_basis + 1.5 * kc_atr)
    squeeze_20 = price_lower.gt(kc_basis - 2.0 * kc_atr) & price_upper.lt(kc_basis + 2.0 * kc_atr)
    price_squeeze_now = (squeeze_15 | squeeze_20).fillna(False)

    width_high = price_width_pct.rolling(PRICE_BB_LOOKBACK, min_periods=5).max()
    price_contraction = _clip_0_100(
        ((width_high - price_width_pct) / width_high.replace(0, np.nan)) * 100
    ).fillna(0.0)
    price_score_ready = price_contraction.ge(PRICE_CONTRACTION).fillna(False)
    price_squeeze_ready = _recent_true(
        price_squeeze_now | price_score_ready,
        max(0, PRICE_SQUEEZE_MEMORY - 1),
    )

    sq_count = _consecutive_true_count(price_squeeze_now)
    price_squeeze_fire = (price_squeeze_now.shift(1).fillna(False) & ~price_squeeze_now).fillna(False)
    price_recent_fire = _recent_true(price_squeeze_fire, 2)
    last_contraction = _last_when_true(price_contraction, price_squeeze_now).fillna(price_contraction)
    last_count = _last_when_true(sq_count.astype(float), price_squeeze_now).fillna(0).astype(int)
    display_contraction = pd.Series(
        np.where(price_recent_fire, last_contraction, price_contraction),
        index=df.index,
        dtype="float64",
    ).fillna(0.0)
    display_sq_count = pd.Series(
        np.where(price_recent_fire, last_count, sq_count),
        index=df.index,
        dtype="int64",
    )

    bb_width_expanding = (
        price_width_pct.gt(price_width_pct.shift(3))
        & price_width_pct.shift(1).gt(price_width_pct.shift(2))
    ).fillna(False)
    bb_low_30 = price_width_pct.rolling(30, min_periods=5).min()
    bb_at_minimum = price_width_pct.le(bb_low_30 * 1.05).fillna(False)

    not_yet_fired = ~(price_squeeze_fire | price_recent_fire)
    is_priming = (
        price_contraction.ge(PRIMING_THRESHOLD)
        & price_squeeze_now
        & not_yet_fired
    ).fillna(False)
    priming_intensity = (
        ((price_contraction - PRIMING_THRESHOLD) / (100 - PRIMING_THRESHOLD) * 50)
        .clip(lower=0)
        .fillna(0)
    )
    priming_intensity = pd.Series(
        np.where(is_priming, priming_intensity + np.where(bb_width_expanding, 20.0, 0.0), 0.0),
        index=df.index,
    ).clip(upper=100)
    super_priming = price_contraction.ge(90.0) & price_squeeze_now & not_yet_fired
    priming_intensity = pd.Series(
        np.where(super_priming, np.maximum(priming_intensity, 80.0), priming_intensity),
        index=df.index,
    )

    rsi = calc_rsi(close, RSI_LENGTH)
    rsi_basis, rsi_upper, rsi_lower = calc_bb(rsi, RSI_BB_LENGTH, RSI_BB_MULT)
    rsi_width = rsi_upper - rsi_lower
    rsi_change = rsi.diff().abs()
    rsi_atr = rsi_change.rolling(RSI_BB_LENGTH, min_periods=RSI_BB_LENGTH).mean() * 1.5
    rsi_kc_upper = rsi_basis + rsi_atr
    rsi_kc_lower = rsi_basis - rsi_atr
    rsi_squeeze_now = (rsi_lower.gt(rsi_kc_lower) & rsi_upper.lt(rsi_kc_upper)).fillna(False)
    rsi_squeeze_fire = (rsi_squeeze_now.shift(1).fillna(False) & ~rsi_squeeze_now).fillna(False)
    rsi_recent_fire = _recent_true(rsi_squeeze_fire, 2)
    rsi_width_high = rsi_width.rolling(30, min_periods=5).max()
    rsi_contraction = _clip_0_100(
        ((rsi_width_high - rsi_width) / rsi_width_high.replace(0, np.nan)) * 100
    ).fillna(0.0)
    rsi_tight = rsi_contraction.ge(RSI_MIN_CONTRACTION).fillna(False)
    rsi_squeeze_ready = _recent_true(rsi_squeeze_now | rsi_tight, RSI_BB_PERSIST_BARS)
    rsi_cross_upper = _cross_over(rsi, rsi_upper)
    rsi_cross_lower = _cross_under(rsi, rsi_lower)

    rsi_prev_inside_bb = (
        rsi.shift(1).le(rsi_upper.shift(1)) & rsi.shift(1).ge(rsi_lower.shift(1))
    ).fillna(False)
    rsi_bb_cross_buy = (rsi.gt(rsi_upper) & rsi_prev_inside_bb).fillna(False)
    rsi_bb_cross_sell = (rsi.lt(rsi_lower) & rsi_prev_inside_bb).fillna(False)
    recent_cross_upper = _bars_since_true(rsi_cross_upper).le(RSI_BB_PERSIST_BARS)
    recent_cross_lower = _bars_since_true(rsi_cross_lower).le(RSI_BB_PERSIST_BARS)
    rsi_above_upper = rsi.gt(rsi_upper).fillna(False)
    rsi_below_lower = rsi.lt(rsi_lower).fillna(False)

    rsi_explosive = pd.Series(0, index=df.index, dtype="int64")
    rsi_explosive.loc[recent_cross_upper & rsi_recent_fire] = 5
    rsi_explosive.loc[recent_cross_lower & rsi_recent_fire] = 6
    rsi_explosive.loc[rsi_explosive.eq(0) & recent_cross_upper] = 3
    rsi_explosive.loc[rsi_explosive.eq(0) & recent_cross_lower] = 4
    rsi_explosive.loc[rsi_explosive.eq(0) & rsi_above_upper] = 1
    rsi_explosive.loc[rsi_explosive.eq(0) & rsi_below_lower] = 2

    both_squeeze_ready = rsi_squeeze_ready & price_squeeze_ready
    either_squeeze_ready = rsi_squeeze_ready | price_squeeze_ready

    mom_val = close - close.shift(10)
    mom_bb_basis = mom_val.rolling(MOM_BB_LENGTH, min_periods=MOM_BB_LENGTH).mean()
    mom_bb_dev = mom_val.rolling(MOM_BB_LENGTH, min_periods=MOM_BB_LENGTH).std(ddof=0)
    mom_bb_upper = mom_bb_basis + mom_bb_dev * MOM_BB_MULT
    mom_bb_lower = mom_bb_basis - mom_bb_dev * MOM_BB_MULT
    mom_kc_basis = calc_ema(mom_val, MOM_KC_LENGTH)
    mom_range = (mom_val - mom_val.shift(1)).abs()
    mom_kc_atr = mom_range.rolling(MOM_KC_LENGTH, min_periods=MOM_KC_LENGTH).mean()
    mom_kc_upper = mom_kc_basis + mom_kc_atr * MOM_KC_MULT
    mom_kc_lower = mom_kc_basis - mom_kc_atr * MOM_KC_MULT
    mom_squeeze = (mom_bb_lower.gt(mom_kc_lower) & mom_bb_upper.lt(mom_kc_upper)).fillna(False)
    mom_squeeze_fire = (mom_squeeze.shift(1).fillna(False) & ~mom_squeeze).fillna(False)

    mom_pos = pd.Series(3, index=df.index, dtype="int64")
    mom_pos.loc[mom_val.gt(mom_bb_upper) & mom_val.gt(mom_kc_upper)] = 5
    mom_pos.loc[mom_pos.eq(3) & mom_val.gt(mom_bb_basis)] = 4
    mom_pos.loc[mom_val.lt(mom_bb_lower) & mom_val.lt(mom_kc_lower)] = 1
    mom_pos.loc[mom_pos.eq(3) & mom_val.lt(mom_bb_basis)] = 2

    vol_sma = volume.rolling(20, min_periods=5).mean()
    rel_vol = (volume / vol_sma.replace(0, np.nan)).replace([np.inf, -np.inf], np.nan).fillna(0.0)
    vol_spike = rel_vol.ge(VOL_SPIKE_THRESHOLD)
    buying_pressure = ((close - low) / (high - low).replace(0, np.nan)).fillna(0.5).clip(0, 1)
    buy_vol_ma = (volume * buying_pressure).rolling(20, min_periods=5).mean()
    sell_vol_ma = (volume * (1 - buying_pressure)).rolling(20, min_periods=5).mean()
    vol_bias = (
        (buy_vol_ma - sell_vol_ma)
        / (buy_vol_ma + sell_vol_ma).replace(0, np.nan)
        * 100
    ).replace([np.inf, -np.inf], np.nan).fillna(0.0)
    vol_building = volume.rolling(5, min_periods=5).mean().gt(volume.rolling(15, min_periods=5).mean())

    vbb_basis = volume.rolling(VOL_BB_LENGTH, min_periods=VOL_BB_LENGTH).mean()
    vbb_dev = volume.rolling(VOL_BB_LENGTH, min_periods=VOL_BB_LENGTH).std(ddof=0)
    vbb_upper = vbb_basis + vbb_dev * VOL_BB_MULT
    vbb_lower = vbb_basis - vbb_dev * VOL_BB_MULT
    vbb_zscore = ((volume - vbb_basis) / vbb_dev.replace(0, np.nan)).replace([np.inf, -np.inf], np.nan).fillna(0.0)
    vbb_pos = pd.Series(3, index=df.index, dtype="int64")
    vbb_pos.loc[vbb_zscore.ge(2.0)] = 5
    vbb_pos.loc[vbb_pos.eq(3) & vbb_zscore.ge(1.0)] = 4
    vbb_pos.loc[vbb_zscore.le(-2.0)] = 1
    vbb_pos.loc[vbb_pos.eq(3) & vbb_zscore.le(-1.0)] = 2

    vkc_basis = calc_ema(volume, VOL_KC_LENGTH)
    vol_change = volume.diff().abs()
    vkc_atr = vol_change.rolling(VOL_KC_LENGTH, min_periods=VOL_KC_LENGTH).mean()
    vkc_upper = vkc_basis + vkc_atr * VOL_KC_MULT
    vkc_lower = vkc_basis - vkc_atr * VOL_KC_MULT
    vkc_pos = pd.Series(3, index=df.index, dtype="int64")
    vkc_pos.loc[volume.gt(vkc_upper)] = 5
    vkc_pos.loc[vkc_pos.eq(3) & volume.gt(vkc_basis)] = 4
    vkc_pos.loc[volume.lt(vkc_lower)] = 1
    vkc_pos.loc[vkc_pos.eq(3) & volume.lt(vkc_basis)] = 2
    vol_squeeze = (vbb_lower.gt(vkc_lower) & vbb_upper.lt(vkc_upper)).fillna(False)
    vol_squeeze_fire = (vol_squeeze.shift(1).fillna(False) & ~vol_squeeze).fillna(False)

    volume_z = vbb_zscore

    ha = calc_heikin_ashi(df)
    ha_bb_basis, ha_bb_upper, ha_bb_lower = calc_bb(ha["HA_Close"], HA_BB_LENGTH, HA_BB_MULT)
    ha_above_bb = ha["HA_Close"].gt(price_upper).fillna(False)
    ha_below_bb = ha["HA_Close"].lt(price_lower).fillna(False)

    body = (ha["HA_Close"] - ha["HA_Open"]).abs()
    candle_range = (ha["HA_High"] - ha["HA_Low"]).replace(0, np.nan)
    ha_body_ratio = body / candle_range
    ha_min_body = pd.concat([ha["HA_Open"], ha["HA_Close"]], axis=1).min(axis=1)
    ha_max_body = pd.concat([ha["HA_Open"], ha["HA_Close"]], axis=1).max(axis=1)
    lower_wick = ha_min_body - ha["HA_Low"]
    upper_wick = ha["HA_High"] - ha_max_body
    tolerance = pd.Series(0.0, index=df.index)  # bilkul zero-wick, koi tolerance nahi

    strong_bull = (
        ha["HA_Close"].gt(ha["HA_Open"])
        & body.gt(0)
        & lower_wick.abs().le(tolerance)
    )
    strong_bear = (
        ha["HA_Close"].lt(ha["HA_Open"])
        & body.gt(0)
        & upper_wick.abs().le(tolerance)
    )
    prev_ha_strong = (strong_bull | strong_bear).shift(1).fillna(False)
    prev_ha_close_inside_bb = (
        ha["HA_Close"].shift(1).le(ha_bb_upper.shift(1))
        & ha["HA_Close"].shift(1).ge(ha_bb_lower.shift(1))
        & ha_bb_upper.shift(1).notna()
        & ha_bb_lower.shift(1).notna()
    ).fillna(False)

    prev2_high_max = high.shift(1).rolling(2, min_periods=2).max()
    prev2_low_min = low.shift(1).rolling(2, min_periods=2).min()
    mid_bb_buy_setup = (
        strong_bull
        & ha["HA_Close"].gt(price_basis)
        & ha["HA_Close"].shift(1).lt(price_basis.shift(1))
        & ha["HA_Close"].shift(2).lt(price_basis.shift(2))
        & prev2_high_max.lt(high)
    ).fillna(False)
    mid_bb_sell_setup = (
        strong_bear
        & ha["HA_Close"].lt(price_basis)
        & ha["HA_Close"].shift(1).gt(price_basis.shift(1))
        & ha["HA_Close"].shift(2).gt(price_basis.shift(2))
        & prev2_low_min.gt(low)
    ).fillna(False)

    buy_breakout = ha_above_bb
    sell_breakout = ha_below_bb

    squeeze_recent_3 = _recent_true(either_squeeze_ready, 2)
    new_buy_setup = (ha_above_bb & squeeze_recent_3).fillna(False)
    new_sell_setup = (ha_below_bb & squeeze_recent_3).fillna(False)

    buy_entry_seed = ha_above_bb & strong_bull & rsi_cross_upper
    sell_entry_seed = ha_below_bb & strong_bear & rsi_cross_lower
    entry_signal, entry_price, bars_since_entry = _entry_state(
        buy_entry_seed,
        sell_entry_seed,
        high,
        low,
        ha["HA_High"],
        ha["HA_Low"],
    )

    accepted_squeeze = pd.Series(False, index=df.index)
    if HA_SETUP_ACCEPTS_PRICE_ONLY:
        accepted_squeeze = accepted_squeeze | (price_squeeze_ready & ~rsi_squeeze_ready)
    if HA_SETUP_ACCEPTS_RSI_ONLY:
        accepted_squeeze = accepted_squeeze | (rsi_squeeze_ready & ~price_squeeze_ready)
    if HA_SETUP_ACCEPTS_BOTH:
        accepted_squeeze = accepted_squeeze | both_squeeze_ready
    if not HA_SETUP_REQUIRES_SQUEEZE:
        accepted_squeeze = pd.Series(True, index=df.index)

    # Sirf uss exact bar pe flag hota hai jismein candle khud strong ho --
    # entry_signal ka multi-bar "still valid" window yahan intentionally
    # nahi use kiya, taaki koi purani strong candle ka carryover na dikhe.
    ha_buy_setup = (strong_bull & accepted_squeeze) | buy_entry_seed
    ha_sell_setup = (strong_bear & accepted_squeeze) | sell_entry_seed

    if HA_SETUP_REQUIRES_BB_BREAKOUT:
        ha_buy_setup = ha_buy_setup & buy_breakout
        ha_sell_setup = ha_sell_setup & sell_breakout
    if PREV_HA_NOT_STRONG_FILTER:
        ha_buy_setup = ha_buy_setup & ~prev_ha_strong
        ha_sell_setup = ha_sell_setup & ~prev_ha_strong
    if PREV_HA_CLOSE_INSIDE_BB_FILTER:
        ha_buy_setup = ha_buy_setup & prev_ha_close_inside_bb
        ha_sell_setup = ha_sell_setup & prev_ha_close_inside_bb

    macd_line = calc_ema(close, MACD_FAST) - calc_ema(close, MACD_SLOW)
    signal_line = calc_ema(macd_line, MACD_SIGNAL)
    macd_bullish = macd_line.gt(signal_line)
    macd_bearish = macd_line.lt(signal_line)
    macd_cross_up = _cross_over(macd_line, signal_line)
    macd_cross_down = _cross_under(macd_line, signal_line)

    vm_plus = (high - low.shift(1)).abs()
    vm_minus = (low - high.shift(1)).abs()
    tr_sum = tr.rolling(VORTEX_LENGTH, min_periods=VORTEX_LENGTH).sum()
    vi_plus = vm_plus.rolling(VORTEX_LENGTH, min_periods=VORTEX_LENGTH).sum() / tr_sum.replace(0, np.nan)
    vi_minus = vm_minus.rolling(VORTEX_LENGTH, min_periods=VORTEX_LENGTH).sum() / tr_sum.replace(0, np.nan)
    vortex_bullish = vi_plus.gt(vi_minus)
    vortex_bearish = vi_plus.lt(vi_minus)
    vortex_cross_up = _cross_over(vi_plus, vi_minus)
    vortex_cross_down = _cross_under(vi_plus, vi_minus)

    mv_signal = pd.Series(0, index=df.index, dtype="int64")
    mv_signal.loc[macd_cross_up & vortex_cross_up] = 5
    mv_signal.loc[macd_cross_down & vortex_cross_down] = 6
    mv_signal.loc[mv_signal.eq(0) & macd_cross_up & vortex_bullish] = 3
    mv_signal.loc[mv_signal.eq(0) & macd_cross_down & vortex_bearish] = 4
    mv_signal.loc[mv_signal.eq(0) & vortex_cross_up & macd_bullish] = 3
    mv_signal.loc[mv_signal.eq(0) & vortex_cross_down & macd_bearish] = 4
    mv_signal.loc[mv_signal.eq(0) & macd_bullish & vortex_bullish] = 1
    mv_signal.loc[mv_signal.eq(0) & macd_bearish & vortex_bearish] = 2
    mv_signal.loc[
        mv_signal.eq(0)
        & ((macd_bullish & vortex_bearish) | (macd_bearish & vortex_bullish))
    ] = 7

    ha_strong_bull_signal = ha_above_bb & strong_bull
    ha_strong_bear_signal = ha_below_bb & strong_bear
    has_ha_strong = ha_strong_bull_signal | ha_strong_bear_signal
    bullish_killer = ha_strong_bull_signal & rsi_explosive.isin([3, 5])
    bearish_killer = ha_strong_bear_signal & rsi_explosive.isin([4, 6])
    has_killer_combo = bullish_killer | bearish_killer

    ha_pts = pd.Series(np.where(has_ha_strong, 25.0, 0.0), index=df.index)
    rsi_pts = pd.Series(0.0, index=df.index)
    rsi_pts.loc[rsi_explosive.isin([5, 6])] = 25.0
    rsi_pts.loc[rsi_explosive.isin([3, 4])] = 15.0
    rsi_pts.loc[rsi_explosive.isin([1, 2])] = 10.0

    sqz_pts = pd.Series(0.0, index=df.index)
    sqz_pts += np.where(vol_squeeze_fire, 15.0, np.where(vol_squeeze, 5.0, 0.0))
    sqz_pts += np.where(mom_squeeze_fire, 15.0, np.where(mom_squeeze, 5.0, 0.0))

    duration_pts = (display_sq_count.astype(float) * 0.8).clip(upper=8.0)
    contract_pts = pd.Series(0.0, index=df.index)
    contract_pts.loc[display_contraction.ge(90)] = 10.0
    contract_pts.loc[contract_pts.eq(0) & display_contraction.ge(85)] = 8.0
    contract_pts.loc[contract_pts.eq(0) & display_contraction.ge(80)] = 6.0
    contract_pts.loc[contract_pts.eq(0) & display_contraction.ge(70)] = 4.0
    bb_pts = pd.Series(0.0, index=df.index)
    bb_pts.loc[bb_width_expanding] = 6.0
    bb_pts.loc[bb_pts.eq(0) & bb_at_minimum] = 4.0
    vol_pts = pd.Series(np.where(rel_vol.ge(2.0), 5.0, 0.0), index=df.index)
    other_pts = (duration_pts + contract_pts + bb_pts + vol_pts).clip(upper=20.0)

    confidence = (ha_pts + rsi_pts + sqz_pts + other_pts).clip(upper=100.0)
    confidence = confidence.mask(price_squeeze_fire, 100.0)
    confidence = pd.Series(
        np.where(price_recent_fire, np.maximum(confidence, 95.0), confidence),
        index=df.index,
    ).fillna(0.0)

    triple_squeeze = (vol_squeeze & mom_squeeze & rsi_contraction.ge(RSI_MIN_CONTRACTION)).fillna(False)

    prediction = pd.Series(0, index=df.index, dtype="int64")
    prediction.loc[entry_signal.eq(5)] = 3
    prediction.loc[entry_signal.eq(6)] = 4
    prediction.loc[prediction.eq(0) & entry_signal.eq(3)] = 1
    prediction.loc[prediction.eq(0) & entry_signal.eq(4)] = 2
    prediction.loc[prediction.eq(0) & mom_pos.isin([4, 5])] = 1
    prediction.loc[prediction.eq(0) & mom_pos.isin([1, 2])] = 2

    master_score = pd.Series(0.0, index=df.index)
    master_score += np.select(
        [
            display_contraction.ge(90),
            display_contraction.ge(85),
            display_contraction.ge(80),
            display_contraction.ge(70),
            display_contraction.ge(60),
        ],
        [5.0, 4.0, 3.5, 2.5, 2.0],
        default=0.0,
    )
    master_score += np.select(
        [
            display_sq_count.ge(15),
            display_sq_count.ge(10),
            display_sq_count.ge(7),
            display_sq_count.ge(4),
            display_sq_count.ge(2),
        ],
        [3.0, 2.5, 2.0, 1.5, 1.0],
        default=0.5,
    )
    master_score += np.where(vol_spike, 1.5, np.where(rel_vol.ge(1.5), 0.75, 0.0))
    master_score += np.where(price_squeeze_fire, 1.5, np.where(price_recent_fire, 1.0, 0.0))
    master_score += np.where(entry_signal.ge(5), 2.0, np.where(entry_signal.ge(3), 1.5, np.where(entry_signal.ge(1), 0.5, 0.0)))
    master_score += np.where(rsi_contraction.ge(80), 1.0, np.where(rsi_contraction.ge(RSI_MIN_CONTRACTION), 0.5, 0.0))
    master_score += np.where(rsi_explosive.ge(3), 1.5, np.where(rsi_explosive.ge(1), 0.75, 0.0))
    master_score += np.where(vol_squeeze_fire, 2.0, np.where(vol_squeeze, 1.0, 0.0))
    master_score += np.where(mom_squeeze_fire, 2.0, np.where(mom_squeeze, 1.0, 0.0))

    out = pd.DataFrame(index=df.index)
    out["Open"] = open_
    out["High"] = high
    out["Low"] = low
    out["Close"] = close
    out["Volume"] = volume

    out["rsi"] = rsi
    out["rsi_bb_basis"] = rsi_basis
    out["rsi_bb_upper"] = rsi_upper
    out["rsi_bb_lower"] = rsi_lower
    out["rsi_width"] = rsi_width
    out["rsi_contraction"] = rsi_contraction
    out["rsi_squeeze_now"] = rsi_squeeze_now.astype(int)
    out["rsi_squeeze_fire"] = rsi_squeeze_fire.astype(int)
    out["rsi_recent_fire"] = rsi_recent_fire.astype(int)
    out["rsi_squeeze_ready"] = rsi_squeeze_ready.astype(int)
    out["rsi_tight"] = rsi_tight.astype(int)
    out["rsi_cross_upper"] = rsi_cross_upper.astype(int)
    out["rsi_cross_lower"] = rsi_cross_lower.astype(int)
    out["rsi_bb_cross_buy"] = rsi_bb_cross_buy.astype(int)
    out["rsi_bb_cross_sell"] = rsi_bb_cross_sell.astype(int)
    out["rsi_explosive"] = rsi_explosive

    out["price_bb_basis"] = price_basis
    out["price_bb_upper"] = price_upper
    out["price_bb_lower"] = price_lower
    out["price_width_pct"] = price_width_pct
    out["price_contraction"] = price_contraction
    out["sq_pct"] = display_contraction
    out["sq_count"] = display_sq_count
    out["price_squeeze_now"] = price_squeeze_now.astype(int)
    out["price_squeeze_fire"] = price_squeeze_fire.astype(int)
    out["price_recent_fire"] = price_recent_fire.astype(int)
    out["price_squeeze_ready"] = price_squeeze_ready.astype(int)
    out["bb_width_expanding"] = bb_width_expanding.astype(int)
    out["bb_at_minimum"] = bb_at_minimum.astype(int)
    out["is_priming"] = is_priming.astype(int)
    out["priming_intensity"] = priming_intensity

    out["both_squeeze_ready"] = both_squeeze_ready.astype(int)
    out["either_squeeze_ready"] = either_squeeze_ready.astype(int)

    out["HA_Open"] = ha["HA_Open"]
    out["HA_High"] = ha["HA_High"]
    out["HA_Low"] = ha["HA_Low"]
    out["HA_Close"] = ha["HA_Close"]
    out["ha_bb_basis"] = ha_bb_basis
    out["ha_bb_upper"] = ha_bb_upper
    out["ha_bb_lower"] = ha_bb_lower
    out["ha_above_bb"] = ha_above_bb.astype(int)
    out["ha_below_bb"] = ha_below_bb.astype(int)
    out["ha_body_ratio"] = ha_body_ratio
    out["strong_bull"] = strong_bull.astype(int)
    out["strong_bear"] = strong_bear.astype(int)
    out["prev_ha_strong"] = prev_ha_strong.astype(int)
    out["prev_ha_close_inside_bb"] = prev_ha_close_inside_bb.astype(int)
    out["mid_bb_buy_setup"] = mid_bb_buy_setup.astype(int)
    out["mid_bb_sell_setup"] = mid_bb_sell_setup.astype(int)
    out["buy_breakout"] = buy_breakout.astype(int)
    out["sell_breakout"] = sell_breakout.astype(int)
    out["new_buy_setup"] = new_buy_setup.astype(int)
    out["new_sell_setup"] = new_sell_setup.astype(int)
    out["ha_buy_setup"] = ha_buy_setup.astype(int)
    out["ha_sell_setup"] = ha_sell_setup.astype(int)
    out["entry_signal"] = entry_signal
    out["entry_price"] = entry_price
    out["bars_since_entry"] = bars_since_entry
    out["buy_above"] = np.where(
        entry_signal.isin([3, 5]),
        entry_price,
        np.where(ha_buy_setup, ha["HA_High"] + ENTRY_BUFFER, np.nan),
    )
    out["sell_below"] = np.where(
        entry_signal.isin([4, 6]),
        entry_price,
        np.where(ha_sell_setup, np.maximum(0.05, ha["HA_Low"] - ENTRY_BUFFER), np.nan),
    )

    out["mom_value"] = mom_val
    out["mom_pos"] = mom_pos
    out["mom_squeeze"] = mom_squeeze.astype(int)
    out["mom_squeeze_fire"] = mom_squeeze_fire.astype(int)

    out["vol_bias"] = vol_bias
    out["rel_vol"] = rel_vol
    out["vol_spike"] = vol_spike.astype(int)
    out["vol_building"] = vol_building.astype(int)
    out["vbb_zscore"] = vbb_zscore
    out["vbb_pos"] = vbb_pos
    out["vkc_pos"] = vkc_pos
    out["vol_squeeze"] = vol_squeeze.astype(int)
    out["vol_squeeze_fire"] = vol_squeeze_fire.astype(int)
    out["volume_z"] = volume_z

    out["mv_signal"] = mv_signal
    out["confidence_pct"] = confidence
    out["prediction"] = prediction
    out["master_score"] = master_score
    out["has_killer_combo"] = has_killer_combo.astype(int)
    out["bullish_killer"] = bullish_killer.astype(int)
    out["bearish_killer"] = bearish_killer.astype(int)
    out["triple_squeeze"] = triple_squeeze.astype(int)
    if "_group_size" in df.columns:
        out["_group_size"] = df["_group_size"]
    return out


def bar_status(sig: pd.DataFrame, tf: str) -> str:
    """Sig ka AAKHRI bar 'LIVE' (abhi ban raha hai) hai ya 'CLOSED'
    (poora ho chuka hai), yeh batata hai. Hum hamesha aakhri bar hi use
    karte hain signal check karne ke liye (taaki trade miss na ho), bas
    is status se pata chalta hai signal confirm hai ya abhi bhi badal
    sakta hai."""
    if sig.empty:
        return "CLOSED"

    if tf in INTRADAY_TIMEFRAMES:
        tf_minutes = round(TIMEFRAMES[tf]["tf_days"] * 1440)
        if tf_minutes <= 0:
            return "CLOSED"
        last_ts = _to_local_naive(sig.index[-1])
        now = _local_now_naive()
        # Candles "label=right" hain (index = bar ka end-time).
        return "CLOSED" if now >= last_ts else "LIVE"

    if "_group_size" in sig.columns:
        trading_days = _trading_day_group_size(TIMEFRAMES[tf].get("resample") or "")
        if trading_days:
            last_size = sig["_group_size"].iloc[-1]
            if pd.notna(last_size):
                return "CLOSED" if last_size >= trading_days else "LIVE"

    # 1D / 1W jaise native (bina resample wale) TFs -- market close time
    # se compare karo.
    last_date = _to_local_naive(sig.index[-1]).normalize()
    now = _local_now_naive()
    if last_date < now.normalize():
        return "CLOSED"
    market_close_today = now.normalize() + pd.Timedelta(minutes=MARKET_CLOSE_OFFSET_MINUTES)
    return "CLOSED" if now >= market_close_today else "LIVE"


def squeeze_type(last: pd.Series) -> str:
    rsi_ready = bool(last.get("rsi_squeeze_ready", 0))
    price_ready = bool(last.get("price_squeeze_ready", 0))
    if rsi_ready and price_ready:
        return "BOTH"
    if price_ready:
        return "PRICE"
    if rsi_ready:
        return "RSI"
    return "NONE"


def _round_or_none(value: Any, places: int = 2) -> Optional[float]:
    try:
        if pd.isna(value):
            return None
        return round(float(value), places)
    except Exception:
        return None


def row_common(sym: str, tf: str, sig: pd.DataFrame, last: pd.Series) -> Dict[str, Any]:
    last_dt = _to_local_naive(sig.index[-1])
    group = timeframe_group(tf)
    threshold = gem_threshold_for_tf(tf)
    sq_pct_raw = last.get("sq_pct", last.get("price_contraction", 0))
    rsi_bb_pct_raw = last.get("rsi_contraction", 0)
    sq_pct = 0.0 if pd.isna(sq_pct_raw) else float(sq_pct_raw)
    rsi_bb_pct = 0.0 if pd.isna(rsi_bb_pct_raw) else float(rsi_bb_pct_raw)
    gem_score = max(sq_pct, rsi_bb_pct)
    gem_hits = []
    if sq_pct >= threshold:
        gem_hits.append("SQ%")
    if rsi_bb_pct >= threshold:
        gem_hits.append("RSI-BB%")
    gem_trigger = "+".join(gem_hits) if gem_hits else "NONE"
    is_gem_setup = bool(gem_hits)

    return {
        "Symbol": sym,
        "TF": tf,
        "TF Group": group,
        "Date": last_dt,
        "Close": round(float(last["Close"]), 2),
        "Gem Threshold%": threshold,
        "Gem Score%": round(gem_score, 1),
        "Gem Trigger": gem_trigger,
        "Is Gem Setup": int(is_gem_setup),
        "Confidence%": _round_or_none(last.get("confidence_pct"), 1),
        "Master Score": _round_or_none(last.get("master_score"), 2),
        "Prediction": int(last.get("prediction", 0)),
        "Entry Signal": int(last.get("entry_signal", 0)),
        "Bars Since Entry": int(last.get("bars_since_entry", 999)),
        "RSI": _round_or_none(last.get("rsi"), 1),
        "RSI Width": _round_or_none(last.get("rsi_width"), 2),
        "RSI-BB%": round(rsi_bb_pct, 1),
        "RSI Explosive": int(last.get("rsi_explosive", 0)),
        "Price Width%": _round_or_none(last.get("price_width_pct"), 2),
        "Price Contraction%": _round_or_none(last.get("price_contraction"), 1),
        "SQ%": round(sq_pct, 1),
        "SQ Count": int(last.get("sq_count", 0)),
        "RSI Sq Now": int(last.get("rsi_squeeze_now", 0)),
        "RSI Sq Fire": int(last.get("rsi_squeeze_fire", 0)),
        "RSI Recent Fire": int(last.get("rsi_recent_fire", 0)),
        "RSI Sq Ready": int(last.get("rsi_squeeze_ready", 0)),
        "Price Sq Now": int(last.get("price_squeeze_now", 0)),
        "Price Sq Fire": int(last.get("price_squeeze_fire", 0)),
        "Price Recent Fire": int(last.get("price_recent_fire", 0)),
        "Price Sq Ready": int(last.get("price_squeeze_ready", 0)),
        "Both Sq Ready": int(last.get("both_squeeze_ready", 0)),
        "Squeeze Type": squeeze_type(last),
        "HA Open": round(float(last["HA_Open"]), 2),
        "HA High": round(float(last["HA_High"]), 2),
        "HA Low": round(float(last["HA_Low"]), 2),
        "HA Close": round(float(last["HA_Close"]), 2),
        "HA Body Ratio": round(float(last["ha_body_ratio"]), 3) if pd.notna(last["ha_body_ratio"]) else None,
        "Strong Bull": int(last.get("strong_bull", 0)),
        "Strong Bear": int(last.get("strong_bear", 0)),
        "Prev HA Strong": int(last.get("prev_ha_strong", 0)),
        "Prev HA Inside BB": int(last.get("prev_ha_close_inside_bb", 0)),
        "HA Above BB": int(last.get("ha_above_bb", 0)),
        "HA Below BB": int(last.get("ha_below_bb", 0)),
        "Buy Breakout": int(last.get("buy_breakout", 0)),
        "Sell Breakout": int(last.get("sell_breakout", 0)),
        "Momentum Pos": int(last.get("mom_pos", 0)),
        "Momentum Sq": int(last.get("mom_squeeze", 0)),
        "Momentum Fire": int(last.get("mom_squeeze_fire", 0)),
        "Rel Vol": _round_or_none(last.get("rel_vol"), 2),
        "Volume Z": _round_or_none(last.get("volume_z"), 2),
        "Volume Sq": int(last.get("vol_squeeze", 0)),
        "Volume Fire": int(last.get("vol_squeeze_fire", 0)),
        "M+V Signal": int(last.get("mv_signal", 0)),
        "Priming": int(last.get("is_priming", 0)),
        "Priming Intensity": _round_or_none(last.get("priming_intensity"), 1),
        "Killer Combo": int(last.get("has_killer_combo", 0)),
        "Triple Squeeze": int(last.get("triple_squeeze", 0)),
    }


def historical_gem_squeeze_moves(
    sig: pd.DataFrame,
    tf: str,
    n: int = SQUEEZE_HISTORY_COUNT,
    lookahead: int = SQUEEZE_MOVE_LOOKAHEAD_BARS,
) -> Dict[str, Any]:
    threshold = gem_threshold_for_tf(tf)
    close = sig["Close"]
    sq_pct = sig["sq_pct"]
    rsi_bb_pct = sig["rsi_contraction"]

    gem_now = (sq_pct.ge(threshold) | rsi_bb_pct.ge(threshold)).fillna(False)
    gem_recent = _recent_true(gem_now, GEM_FIRE_TOLERANCE_BARS)

    fire = sig["price_squeeze_fire"].astype(bool) | sig["rsi_squeeze_fire"].astype(bool)
    gem_fire = (gem_recent & fire).fillna(False)

    fire_positions = np.flatnonzero(gem_fire.to_numpy())
    last_pos = len(sig) - 1
    valid_positions = [p for p in fire_positions if p + lookahead <= last_pos]
    recent_positions = valid_positions[-n:]

    moves: List[float] = []
    for p in recent_positions:
        start_price = float(close.iloc[p])
        if start_price:
            end_price = float(close.iloc[p + lookahead])
            moves.append(round((end_price - start_price) / start_price * 100, 2))

    moves_recent_first = list(reversed(moves))
    return {
        "Last Sq Moves%": "; ".join(f"{m:+.2f}" for m in moves_recent_first) if moves_recent_first else "-",
        "Last Sq Avg Move%": round(float(np.mean(moves)), 2) if moves else None,
        "Last Sq Count": len(moves),
    }


def row_meets_visible_squeeze_floor(row: Dict[str, Any]) -> bool:
    def pct_value(value: Any) -> float:
        try:
            if pd.isna(value):
                return 0.0
            return float(value)
        except Exception:
            return 0.0

    sq_pct = pct_value(row.get("SQ%"))
    rsi_bb_pct = pct_value(row.get("RSI-BB%"))
    return max(sq_pct, rsi_bb_pct) >= MIN_VISIBLE_SQUEEZE


def visible_squeeze_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [row for row in rows if row_meets_visible_squeeze_floor(row)]


def run_scanner(
    syms_nse: List[str],
    syms_yf: List[str],
    scan_timeframes: Optional[List[str]] = None,
) -> Dict[str, pd.DataFrame]:
    if MAX_STOCKS:
        syms_nse = syms_nse[:MAX_STOCKS]
        syms_yf = syms_yf[:MAX_STOCKS]

    groups = timeframe_groups(scan_timeframes or SCAN_TIMEFRAMES)
    print(f"\nGEM SETUP SCANNER | Stocks:{len(syms_yf)} | TFs:{', '.join(SCAN_TIMEFRAMES)}")
    print(
        "Gem thresholds: "
        f"Intraday SQ%/RSI-BB% >= {INTRADAY_GEM_THRESHOLD:.0f} | "
        f"Higher TF SQ%/RSI-BB% >= {HIGHER_TF_GEM_THRESHOLD:.0f}"
    )
    print(f"Visible rows require SQ% or RSI-BB% >= {MIN_VISIBLE_SQUEEZE:.0f}")
    print("Sections: Gem Intraday | Gem Higher TF | Price-BB | RSI-BB | Both | HA strong setup | New HA Squeeze Setup")
    print(f"Freshness: CHECK={CHECK_DATA_FRESHNESS} | REJECT_STALE_DATA={REJECT_STALE_DATA}")

    gem_intraday_rows: List[Dict[str, Any]] = []
    gem_higher_rows: List[Dict[str, Any]] = []
    price_rows: List[Dict[str, Any]] = []
    rsi_rows: List[Dict[str, Any]] = []
    both_rows: List[Dict[str, Any]] = []
    ha_rows: List[Dict[str, Any]] = []
    new_setup_rows: List[Dict[str, Any]] = []
    failed: List[str] = []
    stale_warned: Dict[str, int] = {}

    for nse, yf_sym in tqdm(list(zip(syms_nse, syms_yf)), desc="Scanning", unit="stock"):
        all_fail = True
        for (interval, period), tf_list in groups.items():
            raw = fetch_base(yf_sym, interval, period, auto_adjust=False)
            if raw is None:
                time.sleep(DOWNLOAD_DELAY)
                continue
            all_fail = False

            for tf in tf_list:
                try:
                    df = _resample_ohlcv(raw, TIMEFRAMES[tf]["resample"])
                    if len(df) < MIN_BARS_SCAN:
                        continue

                    ok, stale = passes_freshness(df, tf)
                    if stale:
                        stale_warned[nse] = stale_warned.get(nse, 0) + 1
                    if not ok:
                        continue

                    sig = compute_scan_frame(df)
                    if sig.empty:
                        continue

                    last = sig.iloc[-1]
                    common = row_common(nse, tf, sig, last)
                    common["Status"] = bar_status(sig, tf)
                    common.update(historical_gem_squeeze_moves(sig, tf))

                    price_ready = bool(last.get("price_squeeze_ready", 0))
                    rsi_ready = bool(last.get("rsi_squeeze_ready", 0))
                    both_ready = price_ready and rsi_ready

                    if common.get("Is Gem Setup", 0):
                        if common.get("TF Group") == "INTRADAY":
                            gem_intraday_rows.append(common)
                        else:
                            gem_higher_rows.append(common)

                    if price_ready and not rsi_ready:
                        price_rows.append(common)

                    if rsi_ready and not price_ready:
                        rsi_rows.append(common)

                    if both_ready:
                        both_rows.append(common)

                    if bool(last.get("ha_buy_setup", 0)) or bool(last.get("ha_sell_setup", 0)):
                        side = "BUY" if bool(last.get("ha_buy_setup", 0)) else "SELL"
                        entry = last["buy_above"] if side == "BUY" else last["sell_below"]
                        ha_rows.append(
                            {
                                **common,
                                "Side": side,
                                "Entry": round(float(entry), 2) if pd.notna(entry) else None,
                                "Entry Rule": "Buy Above HA High" if side == "BUY" else "Sell Below HA Low",
                            }
                        )

                    if bool(last.get("new_buy_setup", 0)) or bool(last.get("new_sell_setup", 0)):
                        new_side = "BUY" if bool(last.get("new_buy_setup", 0)) else "SELL"
                        new_setup_rows.append({**common, "Side": new_side})
                except Exception as e:
                    print(f"Scan skip {nse} {tf}: {e}")

            time.sleep(DOWNLOAD_DELAY)

        if all_fail:
            failed.append(nse)

    if stale_warned:
        print(f"\nFreshness note: {len(stale_warned)} stock(s) had stale candles.")
    if failed:
        print(
            f"Download failed: {', '.join(failed[:30])}"
            + (" ..." if len(failed) > 30 else "")
        )
    else:
        print("All scanner downloads OK.")

    outputs = {
        "Gem_Setup_Intraday": pd.DataFrame(visible_squeeze_rows(gem_intraday_rows)),
        "Gem_Setup_HigherTF": pd.DataFrame(visible_squeeze_rows(gem_higher_rows)),
        "Price_BB_Squeeze": pd.DataFrame(visible_squeeze_rows(price_rows)),
        "RSI_BB_Squeeze": pd.DataFrame(visible_squeeze_rows(rsi_rows)),
        "Both_Squeeze": pd.DataFrame(visible_squeeze_rows(both_rows)),
        "New_HA_Squeeze_Setup": pd.DataFrame(visible_squeeze_rows(new_setup_rows)),
    }

    print(
        "\nSignals found: "
        f"Gem Intraday={len(outputs['Gem_Setup_Intraday'])} | "
        f"Gem HigherTF={len(outputs['Gem_Setup_HigherTF'])} | "
        f"Price={len(outputs['Price_BB_Squeeze'])} | "
        f"RSI={len(outputs['RSI_BB_Squeeze'])} | "
        f"Both={len(outputs['Both_Squeeze'])} | "
        f"New Setup={len(outputs['New_HA_Squeeze_Setup'])}"
    )
    return outputs


def scan_rsi_cross_setup(syms_nse: List[str], syms_yf: List[str]) -> pd.DataFrame:
    """RSI-BB Cross setup -- current RSI band se bahar nikla (upar ya neeche),
    aur pichli candle ka RSI band ke andar (upper aur lower ke beech) tha."""
    groups = timeframe_groups(RSI_CROSS_TIMEFRAMES)
    rows: List[Dict[str, Any]] = []

    for nse, yf_sym in tqdm(list(zip(syms_nse, syms_yf)), desc="RSI-BB cross scan", unit="stock"):
        for (interval, period), tf_list in groups.items():
            raw = fetch_base(yf_sym, interval, period, auto_adjust=False)
            if raw is None:
                time.sleep(DOWNLOAD_DELAY)
                continue

            for tf in tf_list:
                try:
                    df = _resample_ohlcv(raw, TIMEFRAMES[tf]["resample"])
                    if len(df) < MIN_BARS_SCAN:
                        continue

                    sig = compute_scan_frame(df)
                    if sig.empty:
                        continue

                    last = sig.iloc[-1]
                    if bool(last.get("rsi_bb_cross_buy", 0)) or bool(last.get("rsi_bb_cross_sell", 0)):
                        side = "BUY" if bool(last.get("rsi_bb_cross_buy", 0)) else "SELL"
                        common = row_common(nse, tf, sig, last)
                        rows.append({**common, "Side": side, "Status": bar_status(sig, tf)})
                except Exception as e:
                    print(f"RSI-BB cross scan skip {nse} {tf}: {e}")

            time.sleep(DOWNLOAD_DELAY)

    return pd.DataFrame(rows)


def scan_mid_bb_setup(syms_nse: List[str], syms_yf: List[str]) -> pd.DataFrame:
    """1D/2D/3D/1W/1M/6M par mid-BB reversal setup dhoondta hai --
    strong HA candle jo middle BB cross karke, pichli 2 candles ke
    high/low se aage nikal jaaye."""
    groups = timeframe_groups(NEW_PATTERN_TIMEFRAMES)
    rows: List[Dict[str, Any]] = []

    for nse, yf_sym in tqdm(list(zip(syms_nse, syms_yf)), desc="Mid-BB scan", unit="stock"):
        for (interval, period), tf_list in groups.items():
            raw = fetch_base(yf_sym, interval, period, auto_adjust=False)
            if raw is None:
                time.sleep(DOWNLOAD_DELAY)
                continue

            for tf in tf_list:
                try:
                    df = _resample_ohlcv(raw, TIMEFRAMES[tf]["resample"])
                    if len(df) < MIN_BARS_SCAN:
                        continue

                    sig = compute_scan_frame(df)
                    if sig.empty:
                        continue

                    last = sig.iloc[-1]
                    if bool(last.get("mid_bb_buy_setup", 0)) or bool(last.get("mid_bb_sell_setup", 0)):
                        side = "BUY" if bool(last.get("mid_bb_buy_setup", 0)) else "SELL"
                        common = row_common(nse, tf, sig, last)
                        rows.append({**common, "Side": side, "Status": bar_status(sig, tf)})
                except Exception as e:
                    print(f"Mid-BB scan skip {nse} {tf}: {e}")

            time.sleep(DOWNLOAD_DELAY)

    return pd.DataFrame(rows)


def export_excel(outputs: Dict[str, pd.DataFrame]) -> Optional[str]:
    if not EXPORT_EXCEL:
        return None

    ts = datetime.now().strftime("%Y%m%d_%H%M")
    fn = f"gem_setup_scanner_{ts}.xlsx"
    with pd.ExcelWriter(fn, engine="openpyxl") as writer:
        summary = []
        for sheet, df in outputs.items():
            df.to_excel(writer, sheet[:31], index=False)
            summary.append({"Section": sheet, "Rows": len(df)})
        pd.DataFrame(summary).to_excel(writer, "Summary", index=False)

    print(f"Saved Excel: {fn}")
    try:
        from google.colab import files
        files.download(fn)
    except Exception:
        pass
    return fn


def main() -> None:
    print("GEM SETUP SCANNER v2")
    print(f"pandas {pd.__version__} | numpy {np.__version__}")
    print("Rules-only scanner using Pine-style SQ%, RSI-BB%, confidence, and setup logic.")

    now = _local_now_naive()
    scanned_str = now.strftime("%d %b %Y, %I:%M %p")

    syms_nse, syms_yf = get_fo_symbols()
    if RUN_SCANNER:
        due_tfs = timeframes_due_now()

        # Higher-TF/EOD scans (Mid-BB reversal, RSI-BB cross ka higher-TF hissa)
        # sirf do situations mein chalenge:
        #   1) Same din 3 PM ke baad (normal scheduled EOD run), YA
        #   2) Jab bhi AAP khud "Run workflow" se manually/forcefully
        #      trigger karo -- automatic (scheduled) runs mein market
        #      hours ke andar yeh baar-baar nahi chalega.
        is_manual_run = os.environ.get("GITHUB_EVENT_NAME", "") == "workflow_dispatch"
        is_eod_window = now.hour >= 16 or is_manual_run

        mid_bb_due_tfs = NEW_PATTERN_TIMEFRAMES if is_eod_window else []
        rsi_cross_due_tfs = rsi_cross_due_now()
        if is_eod_window:
            rsi_cross_due_tfs = list(dict.fromkeys(rsi_cross_due_tfs + RSI_CROSS_HIGHER_TFS))

        print(f"Timeframes due this run: {', '.join(due_tfs) if due_tfs else 'NONE'}")
        print(f"Mid-BB reversal due this run: {', '.join(mid_bb_due_tfs) if mid_bb_due_tfs else 'NONE'}")
        print(f"RSI-BB cross due this run: {', '.join(rsi_cross_due_tfs) if rsi_cross_due_tfs else 'NONE'}")

        if not due_tfs and not mid_bb_due_tfs and not rsi_cross_due_tfs:
            print("Koi timeframe abhi due nahi, is run mein kuch nahi karna.")
            export_status_only(scanned_str)
        else:
            if due_tfs:
                outputs = run_scanner(syms_nse, syms_yf, scan_timeframes=due_tfs)
            else:
                outputs = {
                    "Gem_Setup_Intraday": pd.DataFrame(),
                    "Gem_Setup_HigherTF": pd.DataFrame(),
                    "Price_BB_Squeeze": pd.DataFrame(),
                    "RSI_BB_Squeeze": pd.DataFrame(),
                    "Both_Squeeze": pd.DataFrame(),
                    "New_HA_Squeeze_Setup": pd.DataFrame(),
                }

            outputs["Mid_BB_Reversal_Setup"] = (
                scan_mid_bb_setup(syms_nse, syms_yf) if mid_bb_due_tfs else pd.DataFrame()
            )
            outputs["RSI_BB_Cross_Setup"] = (
                scan_rsi_cross_setup(syms_nse, syms_yf) if rsi_cross_due_tfs else pd.DataFrame()
            )

            export_excel(outputs)
            export_to_google_sheet(outputs, scanned_str, due_tfs, mid_bb_due_tfs, rsi_cross_due_tfs)

    print("\nDone.")


if __name__ == "__main__":
    main()
