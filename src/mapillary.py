import json
import logging
from typing import Dict, List, Optional, Tuple

import numpy as np
import requests

from PIL import Image
from io import BytesIO
from dataclasses import dataclass

from .constants import _MAPILLARY_ACCESS_TOKEN


logger = logging.getLogger(__name__)


def meter_to_degree(value: float) -> float:
    """Convert meters to degrees (approximate)."""
    return value / 111320.0  # ~1 degree latitude = 111.32 km


@dataclass
class MapillaryRetrievalData:
    id: str
    compass_angle: float
    captured_at: str
    thumb_original_url: str
    thumb_1024_url: str
    lat: float
    lon: float
    image: Optional[np.ndarray] = None

    @staticmethod
    def from_api_response(
        data: Dict,
        download_image: bool = True,
    ) -> "MapillaryRetrievalData":
        """Create an instance from Mapillary API response data."""
        img_lon, img_lat = data["geometry"]["coordinates"]

        img_array = None
        if download_image:
            url = data["thumb_1024_url"]
            response = requests.get(url, stream=True)
            response.raise_for_status()
            img = Image.open(BytesIO(response.content)).convert("RGB")
            img_array = np.array(img)

        return MapillaryRetrievalData(
            id=data.get("id", ""),
            compass_angle=data.get("compass_angle", 0.0),
            captured_at=data.get("captured_at", ""),
            thumb_original_url=data.get("thumb_original_url", ""),
            thumb_1024_url=data.get("thumb_1024_url", ""),
            lat=img_lat,
            lon=img_lon,
            image=img_array,
        )


class MapillaryHandler:
    def __init__(self, access_token: str = _MAPILLARY_ACCESS_TOKEN):
        self.access_token = access_token
        self.base_url = "https://graph.mapillary.com/"
        self.headers = {"Authorization": f"OAuth {access_token}"}
        logger.debug("Initialized MapillaryHandler with provided access token.")

    def search_images_along_trajectory(
        self,
        trajs: List[Tuple[float, float]],
        radius: int = 10,  # in meters
    ) -> List[Dict]:
        """
        Search for images along a trajectory defined by a list of (lat, lon) tuples.

        Parameters:
        trajs: List of (latitude, longitude) tuples defining the trajectory

        Returns:
        A list of image information dictionaries
        """
        # find the min, max lat and lon
        lats = [lat for lat, lon in trajs]
        lons = [lon for lat, lon in trajs]
        min_lat, max_lat = min(lats), max(lats)
        min_lon, max_lon = min(lons), max(lons)

        margin = meter_to_degree(radius)

        # expand the bounding box slightly
        min_lat -= margin
        max_lat += margin
        min_lon -= margin
        max_lon += margin

        # create a bounding box string
        bbox = f"{min_lon},{min_lat},{max_lon},{max_lat}"
        logger.info(
            "Searching Mapillary images along trajectory | points=%d | bbox=%s",
            len(trajs),
            bbox,
        )

        images = self._search_images_in_bbox(bbox)

        logger.info("Found %d images inside trajectory bounding box", len(images))

        return images

    def search_images_near_location(
        self,
        lat: float,
        lon: float,
        radius: int = 10,  # in meters
        limit: int = 10,
    ) -> List[Dict]:
        """
        Search for images near a specified location.

        Parameters:
        lat, lon: Latitude and longitude coordinates
        radius: Search radius in meters (default 50m)
        limit: Number of results to return (default 10)

        Returns:
        A list of image information dictionaries
        """
        bbox = self._create_bbox(lat, lon, radius)
        logger.info(
            "Searching Mapillary images near location | lat=%.6f | lon=%.6f | radius=%dm | limit=%d",
            lat,
            lon,
            radius,
            limit,
        )
        return self._search_images_in_bbox(bbox, limit)

    def _search_images_in_bbox(
        self, bbox: str, limit: int = 2000
    ) -> List[MapillaryRetrievalData]:
        """
        Search for images within a specified bounding box.

        Parameters:
        bbox: Bounding box string in format: min_lon,min_lat,max_lon,max_lat
        limit: Number of results to return (default 2000)

        Returns:
        A list of image information dictionaries
        """
        # Mapillary API endpoint
        url = f"{self.base_url}/images"

        # Query parameters
        params = {
            "fields": "id,geometry,compass_angle,captured_at,thumb_1024_url,thumb_original_url",
            "bbox": bbox,
            "limit": limit,
            "access_token": self.access_token,
        }

        logger.debug("Issuing Mapillary API request | bbox=%s | limit=%d", bbox, limit)

        try:
            response = requests.get(url, params=params, headers=self.headers, timeout=30)
            response.raise_for_status()

            data = response.json().get("data", [])

            logger.info("Mapillary API returned %d candidate images", len(data))

            ret = [
                MapillaryRetrievalData.from_api_response(item, download_image=True)
                for item in data
            ]
            return ret

        except requests.exceptions.RequestException as exc:
            logger.error("Mapillary API request failed: %s", exc)
            return []
        except json.JSONDecodeError as exc:
            logger.error("Failed to decode Mapillary API response: %s", exc)
            return []

    def _create_bbox(self, lat: float, lon: float, radius: int) -> str:
        """
        Create a bounding box for searching.

        Parameters:
        lat, lon: Center coordinates
        radius: Radius in meters

        Returns:
        Bounding box string in format: min_lon,min_lat,max_lon,max_lat
        """
        # Convert meters to degrees (approximate)

        margin = meter_to_degree(radius)

        min_lat = lat - margin
        max_lat = lat + margin
        min_lon = lon - margin
        max_lon = lon + margin

        return f"{min_lon},{min_lat},{max_lon},{max_lat}"

    def get_closest_image(
        self, lat: float, lon: float, radius: int = 100
    ) -> Optional[Dict]:
        """
        Get the image closest to the specified location.

        Parameters:
        lat, lon: Target latitude and longitude
        radius: Search radius in meters

        Returns:
        The closest image information dictionary
        """
        images = self.search_images_near_location(lat, lon, radius, limit=20)

        if not images:
            return None

        # Find the nearest image
        closest_image = None
        min_distance = float("inf")

        for image in images:
            img_lon, img_lat = image["geometry"]["coordinates"]
            distance = self._calculate_distance(lat, lon, img_lat, img_lon)

            if distance < min_distance:
                min_distance = distance
                closest_image = image
                closest_image["distance"] = distance  # add distance info

        return closest_image

    def _calculate_distance(
        self, lat1: float, lon1: float, lat2: float, lon2: float
    ) -> float:
        """
        Calculate the distance between two latitude/longitude coordinates (in meters)
        using the Haversine formula.
        """
        R = 6371000  # Earth radius in meters

        lat1_rad = math.radians(lat1)
        lon1_rad = math.radians(lon1)
        lat2_rad = math.radians(lat2)
        lon2_rad = math.radians(lon2)

        dlat = lat2_rad - lat1_rad
        dlon = lon2_rad - lon1_rad

        a = (
            math.sin(dlat / 2) ** 2
            + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2) ** 2
        )
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

        return R * c

    def download_image(self, image_url: str) -> np.ndarray:
        """
        Download an image from URL and return it as a numpy array.

        Parameters:
        image_url: URL of the image

        Returns:
        Image as numpy array (H, W, C)
        """
        try:
            response = requests.get(image_url, stream=True)
            response.raise_for_status()

            # 用 PIL 打开并转成 RGB
            img = Image.open(BytesIO(response.content)).convert("RGB")
            img_array = np.array(img)

            print(f"Image downloaded: shape={img_array.shape}")
            return img_array

        except requests.exceptions.RequestException as e:
            print(f"Download failed: {e}")
            return None

    def display_image_info(self, image: Dict):
        """
        Display image information
        """
        if not image:
            print("No image found")
            return

        print("=" * 50)
        print("📷 Image info:")
        print(f"ID: {image.get('id')}")
        print(f"Captured at: {image.get('captured_at')}")
        print(f"Compass angle: {image.get('compass_angle', 'N/A')}°")

        if "distance" in image:
            print(f"Distance from target: {image['distance']:.2f} m")

        img_lon, img_lat = image["geometry"]["coordinates"]
        print(f"Image coordinates: {img_lat:.6f}, {img_lon:.6f}")

        print(f"Thumbnail URL: {image.get('thumb_1024_url')}")
        print(f"Original URL: {image.get('thumb_original_url')}")
        print("=" * 50)


if __name__ == "__main__":

    # Initialize retriever
    retriever = MapillaryHandler(_MAPILLARY_ACCESS_TOKEN)

    # Test locations
    test_locations = [
        (40.7580, -73.9855),  # Times Square, New York
        (48.8584, 2.2945),  # Eiffel Tower, Paris
        (35.6586, 139.7454),  # Tokyo Tower, Tokyo
        (39.9042, 116.4074),  # Tiananmen, Beijing
    ]

    for lat, lon in test_locations:
        print(f"\n🔍 Searching location: {lat}, {lon}")

        # Method 1: search nearby images
        print("Searching nearby images...")
        images = retriever.search_images_near_location(lat, lon, radius=100, limit=5)
        print(f"Found {len(images)} images")

        # Method 2: get the closest image
        print("\nGetting closest image...")
        closest_image = retriever.get_closest_image(lat, lon, radius=200)

        if closest_image:
            retriever.display_image_info(closest_image)

            # Optionally download the image
            image_url = closest_image.get("thumb_1024_url")
            if image_url:
                filename = f"mapillary_{lat}_{lon}.jpg"
                retriever.download_image(image_url, filename)
        else:
            print("No Mapillary images found near this location")

        print("\n" + "-" * 50)
