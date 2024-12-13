import json
from dataclasses import dataclass, asdict
from typing import Optional


@dataclass
class TransitFeedSyncPayload:
    """Data class for transit feed processing payload"""

    external_id: str
    feed_id: str
    stable_id: str
    entity_types: Optional[str] = None
    feed_url: Optional[str] = None
    execution_id: Optional[str] = None
    spec: Optional[str] = None
    auth_info_url: Optional[str] = None
    auth_param_name: Optional[str] = None
    type: Optional[str] = None
    operator_name: Optional[str] = None
    country: Optional[str] = None
    state_province: Optional[str] = None
    city_name: Optional[str] = None
    source: Optional[str] = None
    payload_type: Optional[str] = None

    def to_dict(self):
        return asdict(self)

    def to_json(self):
        return json.dumps(self.to_dict())
