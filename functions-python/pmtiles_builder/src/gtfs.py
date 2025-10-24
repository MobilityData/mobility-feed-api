from shared.helpers.transform import get_safe_value_from_csv

# TODO: Move this file to a shared folder


def stop_txt_is_lat_lon_required(stop_row):
    """
    Conditionally Required:
    - Required for locations which are stops (location_type=0), stations (location_type=1)
    or entrances/exits (location_type=2).
    - Optional for locations which are generic nodes (location_type=3) or boarding areas (location_type=4).

    Args:
        row (dict): The data row to check.

    Returns:
        bool: True if both latitude and longitude is required, False otherwise.
    """
    location_type = get_safe_value_from_csv(stop_row, "location_type", "0")
    return location_type in ("0", "1", "2")


def is_lat_lon_required(location_type):
    return location_type in ("0", "1", "2")
