import csv
import os
from datetime import datetime, timedelta

BASE_DIR = r"c:\Users\Baran\OneDrive\Desktop\crypto-ai-trader\tests_fixtures"
HEADER = [
    "raw_symbol", "raw_timestamp", "open", "high", "low", "close",
    "volume", "trade_count", "event_type", "timeframe", "raw_trade_id",
    "raw_sequence", "spread_bps"
]


def fmt_time(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def write_csv(filename: str, rows):
    path = os.path.join(BASE_DIR, filename)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, quoting=csv.QUOTE_MINIMAL)
        writer.writerow(HEADER)
        writer.writerows(rows)
    print(f"Wrote {len(rows)} rows -> {filename}")
    return len(rows)


def fixture1_small_3sym():
    rows = []
    base_dt = datetime(2026, 8, 10, 10, 0, 0)
    syms = [
        ("BTCUSDT", 60, 65000.00, 65200.00, 1.00, 2.00, 100, 1, ""),
        ("ETHUSDT", 60, 3500.00, 3600.00, 15.00, 25.00, 100, 61, ""),
        ("SOLUSDT", 60, 150.00, 160.00, 1000.00, 1500.00, 100, 121, ""),
    ]
    for sym, n, p0, p1, v0, v1, tc0, seq0, _ in syms:
        for i in range(n):
            t = i / (n - 1)
            close = lerp(p0, p1, t)
            open_p = lerp(p0, p1, (i - 1) / (n - 1)) if i > 0 else p0
            high = max(open_p, close) + abs(p1 - p0) / n * 0.5
            low = min(open_p, close) - abs(p1 - p0) / n * 0.5
            vol = lerp(v0, v1, t)
            tc = tc0 + i
            seq = seq0 + i
            ts = base_dt + timedelta(minutes=i)
            rows.append([
                sym, fmt_time(ts),
                f"{open_p:.2f}", f"{high:.2f}", f"{low:.2f}", f"{close:.2f}",
                f"{vol:.2f}", str(tc),
                "candle", "1m", "", str(seq), ""
            ])
    return write_csv("small_3sym_1h_1m_candles.csv", rows)


def fixture2_stale():
    rows = []
    base_dt = datetime(2025, 1, 1, 10, 0, 0)
    for i in range(10):
        t = i / 9 if i > 0 else 0
        open_p = lerp(42000.0, 42100.0, t)
        close = lerp(42005.0, 42110.0, t)
        high = max(open_p, close) + 5.0
        low = min(open_p, close) - 5.0
        ts = base_dt + timedelta(minutes=i)
        rows.append([
            "BTCUSDT", fmt_time(ts),
            f"{open_p:.2f}", f"{high:.2f}", f"{low:.2f}", f"{close:.2f}",
            f"{lerp(1.0, 2.0, t):.2f}", str(100 + i),
            "candle", "1m", "", str(i + 1), ""
        ])
    return write_csv("edge_stale.csv", rows)


def fixture3_duplicate():
    rows = []
    base_dt = datetime(2026, 8, 10, 10, 0, 0)
    data = [
        (0, 65000.00, 65010.00, 64990.00, 65005.00, 1.00, 100, 1, ""),
        (1, 65005.00, 65020.00, 65000.00, 65015.00, 1.20, 101, 2, ""),
        (2, 65015.00, 65035.00, 65010.00, 65030.00, 1.35, 102, 3, "TRADE-BTC-1002"),
        (3, 65030.00, 65050.00, 65025.00, 65045.00, 1.50, 103, 4, ""),
        (2, 65015.00, 65035.00, 65010.00, 65030.00, 1.35, 102, 5, "TRADE-BTC-1002"),
    ]
    for idx, open_p, high, low, close, vol, tc, seq, tid in data:
        ts = base_dt + timedelta(minutes=idx)
        rows.append([
            "BTCUSDT", fmt_time(ts),
            f"{open_p:.2f}", f"{high:.2f}", f"{low:.2f}", f"{close:.2f}",
            f"{vol:.2f}", str(tc),
            "candle", "1m", tid, str(seq), ""
        ])
    return write_csv("edge_duplicate.csv", rows)


def fixture4_missing():
    rows = []
    base_dt = datetime(2026, 8, 10, 10, 0, 0)
    seqs = list(range(1, 30)) + list(range(32, 61))
    row_idx = 0
    for i in range(60):
        if i == 30 or i == 31:
            continue
        seq = seqs[row_idx]
        row_idx += 1
        t = i / 59
        close = lerp(65000.00, 65200.00, t)
        open_p = lerp(65000.00, 65200.00, (i - 1) / 59) if i > 0 else 65000.00
        high = max(open_p, close) + 1.0
        low = min(open_p, close) - 1.0
        vol = lerp(1.00, 2.00, t)
        ts = base_dt + timedelta(minutes=i)
        rows.append([
            "BTCUSDT", fmt_time(ts),
            f"{open_p:.2f}", f"{high:.2f}", f"{low:.2f}", f"{close:.2f}",
            f"{vol:.2f}", str(100 + i),
            "candle", "1m", "", str(seq), ""
        ])
    return write_csv("edge_missing.csv", rows)


def fixture5_outoforder():
    rows = []
    base_dt = datetime(2026, 8, 10, 10, 0, 0)
    order = [4, 3, 2, 1, 0]
    seqs = [5, 4, 3, 2, 1]
    for i, seq in zip(order, seqs):
        t = i / 4
        open_p = 65000.00 + i * 20
        close = open_p + 15
        high = close + 5
        low = open_p - 5
        vol = 1.0 + i * 0.2
        ts = base_dt + timedelta(minutes=i)
        rows.append([
            "BTCUSDT", fmt_time(ts),
            f"{open_p:.2f}", f"{high:.2f}", f"{low:.2f}", f"{close:.2f}",
            f"{vol:.2f}", str(100 + i),
            "candle", "1m", "", str(seq), ""
        ])
    return write_csv("edge_outoforder.csv", rows)


def fixture6_invalid():
    rows = []
    base_dt = datetime(2026, 8, 10, 10, 0, 0)
    data = [
        ("-65000.00", "-64990.00", "-65010.00", "-64995.00", "1.50", "100"),
        ("65000.00", "65010.00", "0", "0", "1.20", "101"),
        ("65000.00", "65020.00", "64990.00", "65015.00", "-1.50", "102"),
        ("65000.00", "100", "200", "65010.00", "1.00", "103"),
        ("65000.00", "65015.00", "64995.00", "65010.00", "0", "104"),
        ("NaN", "NaN", "NaN", "NaN", "NaN", "105"),
    ]
    for idx, (open_p, high, low, close, vol, tc) in enumerate(data):
        ts = base_dt + timedelta(minutes=idx)
        rows.append([
            "BTCUSDT", fmt_time(ts),
            open_p, high, low, close, vol, tc,
            "candle", "1m", "", str(idx + 1), ""
        ])
    return write_csv("edge_invalid_price_volume.csv", rows)


def fixture7_spread():
    rows = []
    base_dt = datetime(2026, 8, 10, 10, 0, 0)
    for i in range(3):
        open_p = 65000.00 + i * 50
        close = open_p + 30
        high = close + 10
        low = open_p - 10
        vol = 1.0 + i * 0.3
        ts = base_dt + timedelta(minutes=i)
        rows.append([
            "BTCUSDT", fmt_time(ts),
            f"{open_p:.2f}", f"{high:.2f}", f"{low:.2f}", f"{close:.2f}",
            f"{vol:.2f}", str(100 + i),
            "candle", "1m", "", str(i + 1), "6000"
        ])
    return write_csv("edge_abnormal_spread.csv", rows)


if __name__ == "__main__":
    counts = {}
    counts["small_3sym_1h_1m_candles.csv"] = fixture1_small_3sym()
    counts["edge_stale.csv"] = fixture2_stale()
    counts["edge_duplicate.csv"] = fixture3_duplicate()
    counts["edge_missing.csv"] = fixture4_missing()
    counts["edge_outoforder.csv"] = fixture5_outoforder()
    counts["edge_invalid_price_volume.csv"] = fixture6_invalid()
    counts["edge_abnormal_spread.csv"] = fixture7_spread()
    print("\n=== SUMMARY ===")
    total = 0
    for f, c in counts.items():
        print(f"  {f}: {c} rows")
        total += c
    print(f"  TOTAL: {total} rows across {len(counts)} files")
