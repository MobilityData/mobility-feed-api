from dataclasses import dataclass
from typing import Optional

@dataclass
class TransitFeedSyncPayload:
    """Data class for transit feed processing payload"""
    external_id: str
    feed_id: str
    feed_url: str
    execution_id: Optional[str]
    spec: str
    auth_info_url: Optional[str]
    auth_param_name: Optional[str]
    type: Optional[str]
    operator_name: Optional[str]
    country: Optional[str]
    state_province: Optional[str]
    city_name: Optional[str]
    source: str
    payload_type: str 