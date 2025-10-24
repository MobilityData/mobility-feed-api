from typing import TypedDict, Tuple, List


class RouteCoordinates(TypedDict):
    shape_id: str
    trip_ids: List[str]
    coordinates: List[Tuple[float, float]]
