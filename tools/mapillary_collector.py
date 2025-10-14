import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


import json
import logging
import time
from pathlib import Path
from typing import List

from matplotlib import pyplot as plt
from PIL import Image

from src.logging_config import configure_logging
from src.mapillary import MapillaryHandler, MapillaryRetrievalData
from src.zod import DrivingLog
from src.zodvis import plot_traj_on_map


logger = logging.getLogger(__name__)

DATASET_DIR = "./data/single_frames"
mh = MapillaryHandler()


def _format_duration(seconds: float) -> str:
    seconds = int(seconds)
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}h {m:02d}m {s:02d}s"
    return f"{m}m {s:02d}s"


def save_mapillary_results(log_id: str, images: List[MapillaryRetrievalData]) -> None:
    # output dir: output/<log_id>/
    output_dir = Path("output") / log_id
    output_dir.mkdir(parents=True, exist_ok=True)

    # save metadata
    metadata_path = output_dir / f"{log_id}.json"
    metadata = [image.to_metadata_dict() for image in images]
    with metadata_path.open("w", encoding="utf-8") as json_file:
        json.dump(metadata, json_file, ensure_ascii=False, indent=2)

    # save mapillary retrieval images
    saved_images = 0
    for image in images:
        if image.image is None:
            logger.warning(
                "Skipping Mapillary image %s due to missing pixel data", image.id
            )
            continue

        image_id = image.id or f"image_{saved_images:04d}"
        image_path = output_dir / f"{image_id}.jpg"
        Image.fromarray(image.image).save(image_path)
        saved_images += 1

    logger.info(
        "Persisted Mapillary metadata to %s and saved %d images to %s",
        metadata_path,
        saved_images,
        output_dir,
    )


def main(log_id: str) -> None:
    # retrieval images based on one driving log
    logger.info("Processing log %s", log_id)
    log = DrivingLog(log_id)
    traj = log.get_lat_lon()

    start_lat, start_lon = traj[0]

    # retrieve mapillary images along the trajectory
    images = mh.search_images_near_location(
        start_lat,
        start_lon,
        radius=10,
        limit=50,
    )

    logger.info("Found %d images along the trajectory", len(images))

    save_mapillary_results(log_id, images)

    # # save trajectory map
    # traj_path = Path("output") / log_id / f"trajectory.png"
    # image = plot_traj_on_map(traj)
    # plt.imsave(traj_path, image)
    # logger.info("Saved trajectory visualization to %s", traj_path)


if __name__ == "__main__":
    log_file_path = configure_logging()
    logger.info("Logging initialized | log_file=%s", log_file_path)

    dataset_dir = Path(DATASET_DIR)

    # get dir names
    log_ids = [d.name for d in dataset_dir.iterdir() if d.is_dir()]
    logger.info("Discovered %d driving logs to process", len(log_ids))

    failed_logs = []
    start_time = time.time()
    total = len(log_ids)

    for idx, log_id in enumerate(log_ids, start=1):
        try:
            main(log_id)
        except Exception as e:
            logger.error("Failed to process log %s: %s", log_id, e)
            failed_logs.append(log_id)
        finally:
            elapsed = time.time() - start_time
            avg_per_log = elapsed / idx
            remaining = max(total - idx, 0)
            eta_sec = avg_per_log * remaining
            logger.info(
                "Progress %d/%d | Elapsed %s | ETA ~ %s",
                idx,
                total,
                _format_duration(elapsed),
                _format_duration(eta_sec),
            )

    if failed_logs:
        with open("failed_logs.txt", "w") as f:
            for log_id in failed_logs:
                f.write(f"{log_id}\n")
        logger.info("Saved failed logs to failed_logs.txt")
    else:
        logger.info("All logs processed successfully")
