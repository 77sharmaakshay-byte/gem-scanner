"""
Yeh sirf ek verification script hai -- production scanner ka hissa nahi.
Isko GitHub Actions mein ek baar run karo (network access chahiye), aur
jo dates print hongi, unko apni TradingView CSV files se manually compare
kar lena.
"""
import numpy as np
import pandas as pd
import yfinance as yf

pd.set_option("display.max_rows", 50)


def flatten(df):
    if isinstance(df.columns, pd.MultiIndex):
        df = df.copy()
        df.columns = df.columns.get_level_values(0)
    return df


def group_boundaries(dates: pd.DatetimeIndex, n: int, label: str):
    groups = np.arange(len(dates)) // n
    # sirf poore-complete groups
    last_group = groups[-1]
    if (groups == last_group).sum() < n:
        keep = groups != last_group
        dates = dates[keep]
        groups = groups[keep]

    print(f"\n===== {label} (group size = {n}) — last 12 candles =====")
    df = pd.DataFrame({"date": dates, "group": groups})
    tail_groups = df["group"].unique()[-12:]
    for g in tail_groups:
        rows = df[df["group"] == g]["date"]
        start = rows.iloc[0].strftime("%Y-%m-%d")
        end = rows.iloc[-1].strftime("%Y-%m-%d")
        print(f"  Group covers: {start} -> {end}  (n={len(rows)})")


def main():
    print("Fetching NIFTY 50 (^NSEI) full history...")
    raw = yf.download("^NSEI", period="max", interval="1d", progress=False, auto_adjust=False, actions=False, threads=False)
    raw = flatten(raw).dropna(subset=["Close"])
    dates = pd.DatetimeIndex(raw.index).normalize().sort_values().unique()
    print(f"Total trading sessions in master calendar: {len(dates)}")
    print(f"First date: {dates[0].strftime('%Y-%m-%d')} | Last date: {dates[-1].strftime('%Y-%m-%d')}")

    for n, label in [(2, "2D"), (3, "3D"), (4, "4D"), (7, "7D"), (9, "9D")]:
        group_boundaries(dates, n, label)


if __name__ == "__main__":
    main()
