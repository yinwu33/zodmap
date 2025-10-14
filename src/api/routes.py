import logging
from functools import lru_cache
from io import BytesIO
from pathlib import Path
from typing import Iterable, List, Tuple

import numpy as np
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel
from PIL import Image

from ..zod import DrivingLog
from ..constants import _DATA_ROOT, SHOW_TRAJ


logger = logging.getLogger(__name__)


_DATA_ROOT_FRAMES = Path(_DATA_ROOT) / "single_frames"


class BoundingBox(BaseModel):
    min_lat: float
    min_lon: float
    max_lat: float
    max_lon: float


class TrajectoryPoint(BaseModel):
    lat: float
    lon: float


class DrivingLogListItem(BaseModel):
    log_id: str
    num_points: int | None = None
    bounds: BoundingBox | None = None


class DrivingLogDetail(BaseModel):
    log_id: str
    num_points: int
    bounds: BoundingBox
    trajectory: List[TrajectoryPoint]


class DrivingLogListResponse(BaseModel):
    total: int
    items: List[DrivingLogListItem]
    next_offset: int | None = None
    show_traj: bool


router = APIRouter(prefix="/logs", tags=["logs"])

@lru_cache(maxsize=1)
def _list_available_logs() -> Iterable[str]:
    if not _DATA_ROOT_FRAMES.exists():
        logger.warning("Dataset directory %s does not exist", _DATA_ROOT_FRAMES)
        return []

    return sorted(entry.name for entry in _DATA_ROOT_FRAMES.iterdir() if entry.is_dir())


def _compute_bounds(trajectory: List[Tuple[float, float]]) -> BoundingBox:
    lats = [point[0] for point in trajectory]
    lons = [point[1] for point in trajectory]

    return BoundingBox(
        min_lat=min(lats),
        min_lon=min(lons),
        max_lat=max(lats),
        max_lon=max(lons),
    )


@lru_cache(maxsize=64)
def _get_cached_trajectory(log_id: str) -> List[Tuple[float, float]]:
    logger.info("Loading trajectory for log %s", log_id)
    log = DrivingLog(log_id)
    return [(float(lat), float(lon)) for lat, lon in log.get_lat_lon()]


@lru_cache(maxsize=64)
def _get_cached_preview_image(log_id: str) -> bytes:
    logger.info("Loading preview image for log %s", log_id)
    log = DrivingLog(log_id)
    image = getattr(log, "image", None)

    if image is None:
        raise ValueError("Preview image not available")

    if isinstance(image, Image.Image):
        pil_image = image
    else:
        array = np.array(image)
        if array.dtype != np.uint8:
            array = np.clip(array, 0, 255).astype(np.uint8)
        pil_image = Image.fromarray(array)

    buffer = BytesIO()
    pil_image.save(buffer, format="JPEG", quality=85)
    return buffer.getvalue()


@router.get("", response_model=DrivingLogListResponse)
def list_logs(
    include_details: bool = Query(False),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
) -> DrivingLogListResponse:
    """Return available driving logs with optional summary metadata."""
    all_log_ids = list(_list_available_logs())
    total = len(all_log_ids)
    items: List[DrivingLogListItem] = []

    if offset >= total:
        sliced_ids: List[str] = []
    else:
        sliced_ids = all_log_ids[offset : offset + limit]

    for log_id in sliced_ids:
        item = DrivingLogListItem(log_id=log_id)

        if include_details:
            try:
                trajectory = _get_cached_trajectory(log_id)
            except Exception as exc:  # pragma: no cover - defensive logging
                logger.error("Failed to load trajectory for %s: %s", log_id, exc)
                continue

            item.num_points = len(trajectory)
            item.bounds = _compute_bounds(trajectory)

        items.append(item)

    next_offset = offset + len(sliced_ids)
    if next_offset >= total:
        next_offset = None

    return DrivingLogListResponse(
        total=total,
        items=items,
        next_offset=next_offset,
        show_traj=SHOW_TRAJ,
    )


@router.get("/{log_id}", response_model=DrivingLogDetail)
def get_log(log_id: str) -> DrivingLogDetail:
    """Return a specific driving log trajectory."""
    available_logs = set(_list_available_logs())
    if log_id not in available_logs:
        raise HTTPException(status_code=404, detail=f"Unknown log id: {log_id}")

    try:
        trajectory = _get_cached_trajectory(log_id)
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.exception("Failed to load trajectory for %s", log_id)
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    if not trajectory:
        raise HTTPException(status_code=404, detail=f"No trajectory data for {log_id}")

    if SHOW_TRAJ:
        points = [TrajectoryPoint(lat=lat, lon=lon) for lat, lon in trajectory]
        bounds = _compute_bounds(trajectory)
    else:
        first_lat, first_lon = trajectory[0]
        points = [TrajectoryPoint(lat=first_lat, lon=first_lon)]
        bounds = BoundingBox(
            min_lat=first_lat,
            min_lon=first_lon,
            max_lat=first_lat,
            max_lon=first_lon,
        )

    return DrivingLogDetail(
        log_id=log_id,
        num_points=len(trajectory),
        bounds=bounds,
        trajectory=points,
    )


@router.get("/{log_id}/image", response_class=Response)
def get_log_image(log_id: str) -> Response:
    """Return a JPEG preview image for the driving log."""
    available_logs = set(_list_available_logs())
    if log_id not in available_logs:
        raise HTTPException(status_code=404, detail=f"Unknown log id: {log_id}")

    try:
        image_bytes = _get_cached_preview_image(log_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.exception("Failed to render preview image for %s", log_id)
        raise HTTPException(
            status_code=500, detail="Failed to generate preview image"
        ) from exc

    return Response(content=image_bytes, media_type="image/jpeg")
