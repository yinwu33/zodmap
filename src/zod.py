import logging
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

import h5py
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import requests

from zod import AnnotationProject, ZodDataset, ZodFrame, ZodFrames

from .constants import _DATA_ROOT, _ZOD_VERSION


logger = logging.getLogger(__name__)


_ZOD_DATASET = ZodFrames(_DATA_ROOT, version=_ZOD_VERSION)


class DrivingLog:
    def __init__(self, log_id: str):
        self.log_id = log_id
        self.log_dir = Path(_DATA_ROOT) / log_id

        logger.info("Initializing DrivingLog for %s", log_id)

        self.load_frames(self.log_id)

    def load_frames(self, log_dir: Path) -> ZodFrames:
        """load Zenseact Open Dataset frames

        Args:
            log_dir (Path): _description_

        Returns:
            ZodFrames: _description_
        """
        logger.debug("Loading frames for log %s", log_dir)
        frames = _ZOD_DATASET[self.log_id]
        self.image = frames.get_image()  # TODO: why only one image for frames?
        try:
            self.obj_list = frames.get_annotation(AnnotationProject.OBJECT_DETECTION)
        except Exception as e:
            logging.error("Failed to load object detection annotations: %s", e)
            self.obj_list = []
        try:
            self.ts_list = frames.get_annotation(AnnotationProject.TRAFFIC_SIGNS)
        except Exception as e:
            logging.error("Failed to load traffic sign annotations: %s", e)
            self.ts_list = []
        try:
            self.lm_list = frames.get_annotation(AnnotationProject.LANE_MARKINGS)
        except Exception as e:
            logging.error("Failed to load lane marking annotations: %s", e)
            self.lm_list = []
        self.oxts = frames.oxts
        logger.info(
            "Loaded log %s | oxts poses=%d | objects=%d | traffic_signs=%d",
            self.log_id,
            len(getattr(self.oxts, "poses", [])),
            len(self.obj_list) if self.obj_list is not None else 0,
            len(self.ts_list) if self.ts_list is not None else 0,
        )

    def get_traj(self) -> List:
        """return a list of (lat, lon) of the driving log

        Returns:
            List: _description_
        """
        org_lat, org_lon = self.oxts.origin_lat_lon
        poses = self.oxts.poses  # a list of array, each is [4, 4]

        lats = []
        lons = []
        logger.debug("Computing trajectory for %d poses", len(poses))

        for pose in poses:
            dx = pose[0, 3]
            dy = pose[1, 3]
            dlat = dy / 111320.0  # ~1 degree latitude = 111.32 km
            dlon = dx / (
                40075000 * np.cos((org_lat * np.pi) / 180) / 360
            )  # ~1 degree longitude = cosine(latitude) * 40075km / 360
            lat = org_lat + dlat
            lon = org_lon + dlon
            lats.append(lat)
            lons.append(lon)
        traj = list(zip(lats, lons))
        logger.info("Computed trajectory with %d points", len(traj))
        return traj
