import io
import logging
from typing import Tuple, Optional

import flask
import pandas as pd
import requests
from jsonpath_ng import parse


def parse_request_parameters(
    request: flask.Request,
) -> Tuple[pd.DataFrame, str, Optional[str], str, str]:
    """
    Parse the request parameters and return a DataFrame with the stops data.
    @:returns Tuple: A tuple containing the stops DataFrame, stable ID, and dataset ID.
    """
    logging.info("Parsing request parameters.")
    request_json = request.get_json(silent=True)
    logging.info(f"Request JSON: {request_json}")

    if (
            not request_json
            or (
                ("stops_url" not in request_json or "dataset_id" not in request_json) and
                "station_information_url" not in request_json and
                "vehicle_status_url" not in request_json
            )
            or "stable_id" not in request_json
    ):
        raise ValueError(
            "Missing required parameters: [stops_url, dataset_id  | station_information_url | vehicle_status_url], "
            "stable_id."
        )

    data_type = request_json.get("data_type", "gtfs")
    logging.info(f"Data type: {data_type}")
    if data_type == "gtfs":
        df, stable_id, dataset_id, url = parse_request_parameters_gtfs(request_json)
    elif data_type == "gbfs":
        df, stable_id, dataset_id, url = parse_request_parameters_gbfs(request_json)
    else:
        raise ValueError(
            f"Invalid data_type '{data_type}'. Supported types are 'gtfs' and 'gbfs'."
        )
    return df, stable_id, dataset_id, data_type, url


def parse_request_parameters_gtfs(request_json: dict) -> Tuple[pd.DataFrame, str, Optional[str], str]:
    """ Parse the request parameters for GTFS data. """
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
    """ Parse the station information URL and return a DataFrame with the stops' data. """
    response = requests.get(station_information_url)
    response.raise_for_status()
    data = response.json()

    lat_expr = parse('data.stations[*].lat')
    lon_expr = parse('data.stations[*].lon')
    station_id_expr = parse('data.stations[*].station_id')

    lats = [match.value for match in lat_expr.find(data)]
    lons = [match.value for match in lon_expr.find(data)]
    station_ids = [match.value for match in station_id_expr.find(data)]

    stations_info = [
        {"station_id": sid, "stop_lat": lat, "stop_lon": lon}
        for sid, lat, lon in zip(station_ids, lats, lons)
    ]
    return pd.DataFrame(stations_info)


def parse_vehicle_status_url(vehicle_status_url) -> pd.DataFrame:
    """ Parse the vehicle status URL and return a DataFrame with vehicle_id, lat, and lon. """
    response = requests.get(vehicle_status_url)
    response.raise_for_status()
    data = response.json()

    lat_expr = parse('data.vehicles[*].lat')
    lon_expr = parse('data.vehicles[*].lon')
    vehicle_id_expr = parse('data.vehicles[*].vehicle_id')

    lats = [match.value for match in lat_expr.find(data)]
    lons = [match.value for match in lon_expr.find(data)]
    vehicle_ids = [match.value for match in vehicle_id_expr.find(data)]

    vehicles_info = [
        {"vehicle_id": vid, "stop_lat": lat, "stop_lon": lon}
        for vid, lat, lon in zip(vehicle_ids, lats, lons)
    ]

    return pd.DataFrame(vehicles_info)


def parse_request_parameters_gbfs(request_json: dict) -> Tuple[pd.DataFrame, str, Optional[str], str]:
    """ Parse the request parameters for GBFS data. """
    if (
            not request_json
            or ("station_information_url" not in request_json and "vehicle_status_url" not in request_json)
            or "stable_id" not in request_json
    ):
        raise ValueError(
            "Invalid request: missing ['station_information_url' | 'vehicle_status_url'], 'dataset_id' or 'stable_id' "
            "parameter."
        )

    stable_id = request_json["stable_id"]
    station_information_url = request_json.get("station_information_url")
    vehicle_status_url = request_json.get("vehicle_status_url")
    if station_information_url:
        logging.info('Parsing station information URL')
        stops_df = parse_station_information_url(station_information_url)
    else:
        logging.info('Parsing vehicle status URL')
        stops_df = parse_vehicle_status_url(vehicle_status_url)
    return stops_df, stable_id, None, station_information_url or vehicle_status_url

