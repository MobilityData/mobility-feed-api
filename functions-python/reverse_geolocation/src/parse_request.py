import io
import logging
from typing import Tuple, Optional, List

import flask
import pandas as pd
import requests
from jsonpath_ng import parse


def parse_request_parameters(
    request: flask.Request,
) -> Tuple[pd.DataFrame, str, Optional[str], str, List[str]]:
    """
    Parse the request parameters and return a DataFrame with the stops data.
    @:returns Tuple: A tuple containing the stops DataFrame, stable ID, dataset ID, data type, and a list of URLs that
    were used to fetch the data.
    """
    logging.info("Parsing request parameters.")
    request_json = request.get_json(silent=True)
    logging.info("Request JSON: %s", request_json)

    if (
        not request_json
        or (
            ("stops_url" not in request_json or "dataset_id" not in request_json)
            and "station_information_url" not in request_json
            and "vehicle_status_url" not in request_json
        )
        or "stable_id" not in request_json
    ):
        raise ValueError(
            "Missing required parameters: [stops_url, dataset_id  | station_information_url | vehicle_status_url], "
            "stable_id."
        )

    data_type = request_json.get("data_type", "gtfs")
    logging.info("Data type: %s", data_type)
    if data_type == "gtfs":
        df, stable_id, dataset_id, url = parse_request_parameters_gtfs(request_json)
        urls = [url]
    elif data_type == "gbfs":
        df, stable_id, dataset_id, urls = parse_request_parameters_gbfs(request_json)
    else:
        raise ValueError(
            f"Invalid data_type '{data_type}'. Supported types are 'gtfs' and 'gbfs'."
        )
    return df, stable_id, dataset_id, data_type, urls


def parse_request_parameters_gtfs(
    request_json: dict,
) -> Tuple[pd.DataFrame, str, Optional[str], str]:
    """Parse the request parameters for GTFS data."""
    if (
        not request_json
        or "stops_url" not in request_json
        or "stable_id" not in request_json
        or "dataset_id" not in request_json
    ):
        raise ValueError(
            "Invalid request: missing 'stops_url', 'dataset_id' or 'stable_id' parameter."
        )

    stable_id = request_json["stable_id"]
    dataset_id = request_json["dataset_id"]

    # Read the stops from the URL
    try:
        s = requests.get(request_json["stops_url"]).content
        stops_df = pd.read_csv(io.StringIO(s.decode("utf-8")))
    except Exception as e:
        raise ValueError(
            f"Error reading stops from URL {request_json['stops_url']}: {e}"
        )
    return stops_df, stable_id, dataset_id, request_json["stops_url"]


def parse_station_information_url(station_information_url) -> pd.DataFrame:
    """Parse the station information URL and return a DataFrame with the stops' data."""
    response = requests.get(station_information_url)
    response.raise_for_status()
    data = response.json()

    lat_expr = parse("data.stations[*].lat")
    lon_expr = parse("data.stations[*].lon")

    lats = [match.value for match in lat_expr.find(data)]
    lons = [match.value for match in lon_expr.find(data)]

    stations_info = [{"stop_lat": lat, "stop_lon": lon} for lat, lon in zip(lats, lons)]
    return pd.DataFrame(stations_info)


def parse_vehicle_status_url(vehicle_status_url) -> pd.DataFrame:
    """Parse the vehicle status URL and return a DataFrame with vehicle_id, lat, and lon."""
    response = requests.get(vehicle_status_url)
    response.raise_for_status()
    data = response.json()

    lat_expr = parse("data.vehicles[*].lat")
    lon_expr = parse("data.vehicles[*].lon")

    lats = [match.value for match in lat_expr.find(data)]
    lons = [match.value for match in lon_expr.find(data)]

    vehicles_info = [{"stop_lat": lat, "stop_lon": lon} for lat, lon in zip(lats, lons)]

    return pd.DataFrame(vehicles_info)


def parse_free_bike_status_url(free_bike_status_url):
    """Parse the free bike status URL and return a DataFrame with bike_id, lat, and lon."""
    response = requests.get(free_bike_status_url)
    response.raise_for_status()
    data = response.json()

    lat_expr = parse("data.bikes[*].lat")
    lon_expr = parse("data.bikes[*].lon")

    lats = [match.value for match in lat_expr.find(data)]
    lons = [match.value for match in lon_expr.find(data)]

    bikes_info = [{"stop_lat": lat, "stop_lon": lon} for lat, lon in zip(lats, lons)]

    return pd.DataFrame(bikes_info)


def parse_request_parameters_gbfs(
    request_json: dict,
) -> Tuple[pd.DataFrame, str, Optional[str], List[str]]:
    """Parse the request parameters for GBFS data."""
    if (
        not request_json
        or (
            "station_information_url" not in request_json
            and "vehicle_status_url" not in request_json
            and "free_bike_status_url" not in request_json
        )
        or "stable_id" not in request_json
    ):
        raise ValueError(
            "Invalid request: missing ['station_information_url' | 'vehicle_status_url'], 'dataset_id' or 'stable_id' "
            "parameter."
        )

    stable_id = request_json["stable_id"]
    station_information_url = request_json.get("station_information_url")
    vehicle_status_url = request_json.get("vehicle_status_url")
    free_bike_status_url = request_json.get("free_bike_status_url")
    stops_df = pd.DataFrame()
    urls = []
    if station_information_url:
        logging.info("Parsing station information URL")
        stops_df_station_information = parse_station_information_url(
            station_information_url
        )
        stops_df = pd.concat(
            [stops_df, stops_df_station_information], ignore_index=True
        )
        urls.append(station_information_url)
    if vehicle_status_url:
        logging.info("Parsing vehicle status URL")
        stops_df_vehicle_status = parse_vehicle_status_url(vehicle_status_url)
        stops_df = pd.concat([stops_df, stops_df_vehicle_status], ignore_index=True)
        urls.append(vehicle_status_url)
    if free_bike_status_url:
        logging.info("Parsing free bike status URL")
        stops_df_free_bike_status = parse_free_bike_status_url(free_bike_status_url)
        stops_df = pd.concat([stops_df, stops_df_free_bike_status], ignore_index=True)
        urls.append(free_bike_status_url)
    return stops_df, stable_id, None, urls
