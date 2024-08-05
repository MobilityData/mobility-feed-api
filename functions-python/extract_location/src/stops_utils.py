import logging
import numpy as np
import gtfs_kit
import random


def extract_extreme_points(stops):
    """
    Extract the extreme points based on latitude and longitude.

    @@:param stops: ndarray of stops with columns for latitude and longitude.
    @@:return: Tuple containing points at min_lon, max_lon, min_lat, max_lat.
    """
    min_lon_point = tuple(stops[np.argmin(stops[:, 1])])
    max_lon_point = tuple(stops[np.argmax(stops[:, 1])])
    min_lat_point = tuple(stops[np.argmin(stops[:, 0])])
    max_lat_point = tuple(stops[np.argmax(stops[:, 0])])
    return min_lon_point, max_lon_point, min_lat_point, max_lat_point


def find_center_point(stops, min_lat, max_lat, min_lon, max_lon):
    """
    Find a point closest to the center of the bounding box.

    @@:param stops: ndarray of stops with columns for latitude and longitude.
    @:param min_lat: Minimum latitude of the bounding box.
    @:param max_lat: Maximum latitude of the bounding box.
    @:param min_lon: Minimum longitude of the bounding_box.
    @:param max_lon: Maximum longitude of the bounding box.
    @:return: Tuple representing the point closest to the center.
    """
    center_lat, center_lon = (min_lat + max_lat) / 2, (min_lon + max_lon) / 2
    return tuple(
        min(stops, key=lambda pt: (pt[0] - center_lat) ** 2 + (pt[1] - center_lon) ** 2)
    )


def select_additional_points(stops, selected_points, num_points):
    """
    Select additional points randomly from the dataset.

    @:param stops: ndarray of stops with columns for latitude and longitude.
    @:param selected_points: Set of already selected unique points.
    @:param num_points: Total number of points to select.
    @:return: Updated set of selected points including additional points.
    """
    remaining_points_needed = num_points - len(selected_points)
    # Get remaining points that aren't already selected
    remaining_points = set(map(tuple, stops)) - selected_points
    for _ in range(remaining_points_needed):
        if len(remaining_points) == 0:
            logging.warning(
                f"Not enough points in GTFS data to select {num_points} distinct points."
            )
            break
        pt = random.choice(list(remaining_points))
        selected_points.add(pt)
        remaining_points.remove(pt)
    return selected_points


def get_gtfs_feed_bounds_and_points(url: str, dataset_id: str, num_points: int = 5):
    """
    Retrieve the bounding box and a specified number of representative points from the GTFS feed.

    @:param url: URL to the GTFS feed.
    @:param dataset_id: ID of the dataset for logs.
    @:param num_points: Number of points to retrieve. Default is 5.
    @:return: Tuple containing bounding box (min_lon, min_lat, max_lon, max_lat) and the specified number of points.
    """
    try:
        feed = gtfs_kit.read_feed(url, "km")
        stops = feed.stops[["stop_lat", "stop_lon"]].to_numpy()

        if len(stops) < num_points:
            logging.warning(
                f"[{dataset_id}] Not enough points in GTFS data to select {num_points} distinct points."
            )
            return None, None

        # Calculate bounding box
        min_lon, min_lat, max_lon, max_lat = feed.compute_bounds()

        # Extract extreme points
        (
            min_lon_point,
            max_lon_point,
            min_lat_point,
            max_lat_point,
        ) = extract_extreme_points(stops)

        # Use a set to ensure uniqueness of points
        selected_points = {min_lon_point, max_lon_point, min_lat_point, max_lat_point}

        # Find a central point and add it to the set
        center_point = find_center_point(stops, min_lat, max_lat, min_lon, max_lon)
        selected_points.add(center_point)

        # Add random points if needed
        if len(selected_points) < num_points:
            selected_points = select_additional_points(
                stops, selected_points, num_points
            )

        # Convert to list and limit to the requested number of points
        selected_points = list(selected_points)[:num_points]
        return (min_lon, min_lat, max_lon, max_lat), selected_points

    except Exception as e:
        logging.error(f"[{dataset_id}] Error processing GTFS feed from {url}: {e}")
        raise Exception(e)
