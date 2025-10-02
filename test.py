import logging
from pathlib import Path

from matplotlib import pyplot as plt

from src.logging_config import configure_logging
from src.mapillary import MapillaryHandler
from src.zod import DrivingLog
from src.zodvis import plot_traj_on_map


logger = logging.getLogger(__name__)


def main(log_id: str = "007674"):
    # retrieval images based on one driving log
    logger.info("Processing log %s", log_id)
    log = DrivingLog(log_id)
    traj = log.get_traj()
    logger.debug("Trajectory sample (first 5 points): %s", traj[:5])

    image = plot_traj_on_map(traj)
    output_path = Path("output") / f"{log_id}_traj_map.png"
    plt.imsave(output_path, image)
    logger.info("Saved trajectory visualization to %s", output_path)

    mh = MapillaryHandler()
    images = mh.search_images_along_trajectory(traj)

    logger.info("Found %d images along the trajectory", len(images))


if __name__ == "__main__":
    log_file_path = configure_logging()
    logger.info("Logging initialized | log_file=%s", log_file_path)

    dataset_dir = Path("./data/mini/single_frames")

    # get dir names
    log_ids = [d.name for d in dataset_dir.iterdir() if d.is_dir()]
    logger.info("Discovered %d driving logs to process", len(log_ids))

    for log_id in log_ids:
        main(log_id)
