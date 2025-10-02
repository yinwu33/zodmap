import logging
from typing import List, Tuple

import matplotlib.pyplot as plt
import numpy as np
import osmnx as ox
from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas

from .zod import DrivingLog


logger = logging.getLogger(__name__)


def _draw_bboxes(ax, items, get_bbox_fn, get_label_fn, edge_color: str):
    for it in items:
        bbox = get_bbox_fn(it)
        if bbox is None or len(bbox) != 4:
            continue
        x1, y1, x2, y2 = bbox
        rect = plt.Rectangle(
            (x1, y1),
            x2 - x1,
            y2 - y1,
            fill=False,
            color=edge_color,
            linewidth=2,
        )
        ax.add_patch(rect)
        label = get_label_fn(it)
        if label:
            ax.text(
                x1,
                y1,
                label,
                color="yellow",
                fontsize=12,
                backgroundcolor="black",
            )


def plot_objects_on_image(log: DrivingLog) -> np.ndarray:
    image = log.image
    obj_list = getattr(log, "obj_list", [])
    if image is None:
        raise ValueError("DrivingLog.image is None")
    logger.info(
        "Plotting %d objects for log %s", len(obj_list), getattr(log, "log_id", "unknown")
    )
    fig, ax = plt.subplots(1)
    ax.imshow(image)
    if obj_list:
        _draw_bboxes(
            ax,
            obj_list,
            lambda o: getattr(getattr(o, "box2d", None), "xyxy", None),
            lambda o: getattr(o, "object_type", getattr(o, "category", "")),
            "red",
        )
    ax.axis("off")
    fig.tight_layout(pad=0)
    fig.canvas.draw()
    w, h = fig.canvas.get_width_height()
    arr = np.frombuffer(fig.canvas.get_renderer().buffer_rgba(), dtype=np.uint8)
    arr = arr.reshape((h, w, 4))[:, :, :3]
    plt.close(fig)
    return arr


def plot_traffic_signs_on_image(log: DrivingLog) -> np.ndarray:
    image = log.image
    ts_list = getattr(log, "ts_list", [])
    if image is None:
        raise ValueError("DrivingLog.image is None")
    logger.info(
        "Plotting %d traffic signs for log %s",
        len(ts_list),
        getattr(log, "log_id", "unknown"),
    )
    fig, ax = plt.subplots(1)
    ax.imshow(image)
    if ts_list:
        _draw_bboxes(
            ax,
            ts_list,
            lambda t: getattr(getattr(t, "bounding_box", None), "xyxy", None),
            lambda t: getattr(t, "sign_type", ""),
            "blue",
        )
    ax.axis("off")
    fig.tight_layout(pad=0)
    fig.canvas.draw()
    w, h = fig.canvas.get_width_height()
    arr = np.frombuffer(fig.canvas.get_renderer().buffer_rgba(), dtype=np.uint8)
    arr = arr.reshape((h, w, 4))[:, :, :3]
    plt.close(fig)
    return arr


def plot_traj_on_map(traj: List[Tuple[float, float]]) -> np.ndarray:
    if not traj:
        raise ValueError("traj is empty")

    lats = [lat for lat, _ in traj]
    lons = [lon for _, lon in traj]
    center_lat = float(np.mean(lats))
    center_lon = float(np.mean(lons))

    logger.info(
        "Plotting trajectory map | points=%d | center_lat=%.6f | center_lon=%.6f",
        len(traj),
        center_lat,
        center_lon,
    )

    graph = ox.graph_from_point(
        (center_lat, center_lon),
        dist=300,
        network_type="all",
    )

    fig, ax = ox.plot_graph(
        graph,
        show=False,
        close=False,
        node_size=0,
        edge_linewidth=0.5,
    )

    ax.plot(lons, lats, color="blue", linewidth=2)
    ax.scatter(lons, lats, c="red", s=15)

    # fig.tight_layout(pad=0)
    # fig.canvas.draw()

    canvas = FigureCanvas(fig)
    canvas.draw()

    img = np.array(canvas.buffer_rgba())

    logger.debug("Rendered trajectory map image shape: %s", img.shape)

    return img
