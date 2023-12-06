# Class to maintain the status of the dataset
import logging
import uuid
from datetime import datetime
from enum import Enum
from dataclasses import dataclass, asdict
from typing import Optional
from google.cloud import datastore


class Status(Enum):
    UPDATED = "UPDATED"
    NOT_UPDATED = "NOT_UPDATED"
    FAILED = "FAILED"
    DO_NOT_RETRY = "DO_NOT_RETRY"
    PUBLISHED = "PUBLISHED"


@dataclass
class DatasetTrace:
    trace_id: str
    stable_id: str
    status: Status
    timestamp: datetime
    execution_id: Optional[str] = None
    file_sha256_hash: Optional[str] = None
    hosted_url: Optional[str] = None


class DatasetTraceService:
    def __init__(self, client):
        self.client = client

    def save(self, dataset_trace: DatasetTrace):
        entity = self._dataset_trace_to_entity(dataset_trace)
        self.client.put(entity)

    def get_by_id(self, trace_id: str) -> Optional[DatasetTrace]:
        key = self.client.key('DatasetTrace', trace_id)
        entity = self.client.get(key)

        if entity:
            return self._entity_to_dataset_trace(entity)
        else:
            return None

    def get_by_execution_and_stable_ids(self, execution_id: str, stable_id: str) ->\
            Optional[DatasetTrace]:
        query = self.client.query(kind='DatasetTrace')
        query.add_filter('execution_id', '=', execution_id)
        query.add_filter('stable_id', '=', stable_id)

        results = list(query.fetch())

        if results:
            # convert list
            return self._entity_to_dataset_trace(results)
        else:
            return None

    def _dataset_trace_to_entity(self, dataset_trace: DatasetTrace) -> datastore.Entity:
        trace_id = str(uuid.uuid4())
        key = self.client.key('DatasetTrace', trace_id)
        entity = datastore.Entity(key=key)

        entity['trace_id'] = trace_id
        entity.update(asdict(dataset_trace))

        return entity

    @staticmethod
    def _entity_to_dataset_trace(entity: datastore.Entity) -> DatasetTrace:
        return DatasetTrace(
            trace_id=entity['trace_id'],
            stable_id=entity['stable_id'],
            status=entity['status'],
            timestamp=entity['timestamp'],
            execution_id=entity.get('execution_id'),
            file_sha256_hash=entity.get('file_sha256_hash'),
            hosted_url=entity.get('hosted_url')
        )
