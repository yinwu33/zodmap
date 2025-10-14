"""as this task address the country domain shift, we firstly need to identify
which driving log belongs to which country and also know how many countries are
there in the dataset.
"""

import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from pathlib import Path
from collections import Counter
from typing import Dict, Tuple, List
import csv
import reverse_geocoder as rg
from tqdm import tqdm

from src.zod import DrivingLog

# quantization for speed up
def quantize_latlon(lat: float, lon: float, ndp: int = 3) -> Tuple[float, float]:
    return round(lat, ndp), round(lon, ndp)


DATA_DIR = "./data/single_frames"


def main():
    dataset_dir = Path(DATA_DIR)
    if not dataset_dir.exists():
        raise FileNotFoundError(f"Dataset dir not found: {dataset_dir.resolve()}")

    log_ids = sorted([d.name for d in dataset_dir.iterdir() if d.is_dir()])
    if not log_ids:
        print(f"No driving logs found in {dataset_dir.resolve()}")
        return

    print(f"Discovered {len(log_ids)} driving logs to process")

    # collect starting lat/lon for each log
    lat_lon: Dict[str, Tuple[float, float]] = {}
    lat_lon_q: Dict[str, Tuple[float, float]] = {}
    has_ts_anno: Dict[str, bool] = {}

    failed: List[Tuple[str, str]] = []  # (log_id, error_msg)

    for log_id in tqdm(log_ids, total=len(log_ids), desc="Reading logs"):
        try:
            log = DrivingLog(log_id)
            coords = log.get_lat_lon()
            if not coords:
                raise ValueError("Empty lat/lon sequence")

            if log.ts_list:
                has_ts_anno[log_id] = True
            else:
                has_ts_anno[log_id] = False

            start_lat, start_lon = coords[0]
            lat_lon[log_id] = (float(start_lat), float(start_lon))
            lat_lon_q[log_id] = quantize_latlon(
                float(start_lat), float(start_lon), ndp=3
            )

        except Exception as e:
            print(f"Failed to process log {log_id}: {e}")
            failed.append((log_id, str(e)))

    unique_coords = sorted(set(lat_lon_q.values()))
    if unique_coords:
        results = rg.search(unique_coords)
        coord_to_cc = {coord: res["cc"] for coord, res in zip(unique_coords, results)}
    else:
        coord_to_cc = {}

    country_count: Counter = Counter()
    per_log_rows: List[Tuple[str, float, float, str]] = []

    for log_id in log_ids:
        if log_id not in lat_lon:
            continue
        lat, lon = lat_lon[log_id]
        qcoord = lat_lon_q[log_id]
        cc = coord_to_cc.get(qcoord, "Unknown")
        has_ts_anno_int = 1 if has_ts_anno.get(log_id, False) else 0
        country_count[cc] += 1
        per_log_rows.append((log_id, lat, lon, cc, has_ts_anno_int))

    print("\nCountry counts (desc):")
    for cc, cnt in country_count.most_common():
        print(f"{cc}: {cnt}")

    out_csv = Path("which_country_results.csv")
    with out_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["log_id", "lat", "lon", "country_cc", "has_ts_anno"])
        writer.writerows(per_log_rows)
    print(f"\nSaved per-log results to: {out_csv.resolve()}")

    if failed:
        print(f"\nFailed to process {len(failed)} logs. Examples:")
        for log_id, err in failed[:10]:
            print(f"- {log_id}: {err}")


if __name__ == "__main__":
    main()
