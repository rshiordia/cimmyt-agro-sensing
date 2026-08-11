#!/usr/bin/env python3
"""
CIMMYT dashboard exporter.

Reads the logger's uplinks.csv without modifying it and produces:
  - latest.json  : newest valid public-safe uplink
  - history.json : all valid public-safe uplinks

Examples:
    python export_dashboard.py "C:/path/to/uplinks.csv" "C:/path/to/repo/dashboard/data"
    python export_dashboard.py "C:/path/to/uplinks.csv" "C:/path/to/repo/dashboard/data" --watch 30
"""

import argparse
import csv
import json
import os
import tempfile
import time
from pathlib import Path

REQUIRED_COLUMNS = {
    "received_at_local",
    "device_id",
    "frame_counter",
    "temperature_c",
    "humidity_pct",
    "pressure_hpa",
    "interval_seconds",
    "gateway_id",
    "rssi_dbm",
    "snr_db",
}

PUBLIC_MAP = {
    "device_id": "device_id",
    "frame_counter": "frame_counter",
    "timestamp": "received_at_local",
    "temperature": "temperature_c",
    "humidity": "humidity_pct",
    "pressure": "pressure_hpa",
    "interval_seconds": "interval_seconds",
    "rssi": "rssi_dbm",
    "snr": "snr_db",
    "gateway_id": "gateway_id",
}

NUMERIC_TYPES = {
    "frame_counter": int,
    "temperature": float,
    "humidity": float,
    "pressure": float,
    "interval_seconds": float,
    "rssi": float,
    "snr": float,
}

def convert_value(public_name, raw_value):
    value = (raw_value or "").strip()
    if not value:
        return None
    converter = NUMERIC_TYPES.get(public_name)
    if converter is None:
        return value
    try:
        return converter(value)
    except (TypeError, ValueError):
        return None

def valid_row(row):
    core = (
        "received_at_local",
        "device_id",
        "frame_counter",
        "temperature_c",
        "humidity_pct",
        "pressure_hpa",
    )
    return all((row.get(name) or "").strip() for name in core)

def public_record(row):
    return {
        public_name: convert_value(public_name, row.get(csv_name))
        for public_name, csv_name in PUBLIC_MAP.items()
    }

def load_public_history(csv_path):
    records = []
    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        columns = set(reader.fieldnames or [])
        missing = REQUIRED_COLUMNS - columns
        if missing:
            raise RuntimeError(
                "CSV is missing required columns: " + ", ".join(sorted(missing))
            )
        for row in reader:
            if valid_row(row):
                records.append(public_record(row))
    if not records:
        raise RuntimeError("No valid uplink rows found.")
    return records

def atomic_write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(
        prefix=path.name + ".",
        suffix=".tmp",
        dir=path.parent,
        text=True,
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(data, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    except Exception:
        try:
            os.unlink(temp_name)
        except FileNotFoundError:
            pass
        raise

def export(csv_path, output_dir):
    history = load_public_history(csv_path)
    latest = history[-1]
    atomic_write_json(output_dir / "latest.json", latest)
    atomic_write_json(output_dir / "history.json", history)
    return latest, len(history)

def main():
    parser = argparse.ArgumentParser(
        description="Export CIMMYT uplinks.csv to public dashboard JSON."
    )
    parser.add_argument("csv", type=Path, help="Path to the live uplinks.csv")
    parser.add_argument(
        "output_dir",
        type=Path,
        help="Dashboard data directory, e.g. repo/dashboard/data",
    )
    parser.add_argument(
        "--watch",
        type=float,
        metavar="SECONDS",
        help="Continuously re-export when the CSV changes, checking every N seconds.",
    )
    args = parser.parse_args()

    if not args.csv.exists():
        raise SystemExit(f"CSV not found: {args.csv}")

    last_mtime_ns = None

    while True:
        try:
            mtime_ns = args.csv.stat().st_mtime_ns
            if last_mtime_ns != mtime_ns:
                latest, count = export(args.csv, args.output_dir)
                print(
                    f"Exported {count} records | "
                    f"latest FCnt={latest['frame_counter']} | "
                    f"{latest['timestamp']}",
                    flush=True,
                )
                last_mtime_ns = mtime_ns
        except Exception as exc:
            print(f"Export warning: {exc}", flush=True)

        if args.watch is None:
            break
        time.sleep(max(args.watch, 1.0))

if __name__ == "__main__":
    main()
