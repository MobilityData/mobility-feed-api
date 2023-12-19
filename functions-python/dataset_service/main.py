# Class to maintain the status of the dataset
import logging
import uuid
from datetime import datetime
from enum import Enum
from dataclasses import dataclass, asdict
from typing import Optional, Final
from google.cloud import datastore
from google.cloud.datastore import Client


class Status(Enum):
    FAILED = "FAILED"
    PUBLISHED = "PUBLISHED"
    NOT_PUBLISHED = "NOT_PUBLISHED"


@dataclass
class DatasetTrace:
    stable_id: str
    status: Status
    timestamp: datetime
    trace_id: Optional[str] = None
    execution_id: Optional[str] = None
    file_sha256_hash: Optional[str] = None
    hosted_url: Optional[str] = None
    error_message: Optional[str] = None


@dataclass
class BatchExecution:
    execution_id: str
    timestamp: datetime
    feeds_total: int


dataset_trace_collection: Final[str] = 'dataset_trace'
batch_execution_collection: Final[str] = 'batch_execution'


class DatasetTraceService:
    def __init__(self, client: Client = None):
        self.client = datastore.Client() if client is None else client

    def save(self, dataset_trace: DatasetTrace):
        entity = self._dataset_trace_to_entity(dataset_trace)
        self.client.put(entity)

    def get_by_id(self, trace_id: str) -> [DatasetTrace]:
        key = self.client.key(dataset_trace_collection, trace_id)
        entity = self.client.get(key)

        if entity:
            return self._entity_to_dataset_trace(entity)
        else:
            return []

    def get_by_execution_and_stable_ids(self, execution_id: str, stable_id: str) -> [DatasetTrace]:
        query = self.client.query(kind=dataset_trace_collection)
        query.add_filter('execution_id', '=', execution_id)
        query.add_filter('stable_id', '=', stable_id)

        results = list(query.fetch())

        if results:
            return [self._entity_to_dataset_trace(result) for result in results]
        else:
            return []

    def _dataset_trace_to_entity(self, dataset_trace: DatasetTrace) -> datastore.Entity:
        trace_id = str(uuid.uuid4())
        key = self.client.key(dataset_trace_collection, trace_id)
        entity = datastore.Entity(key=key)

        entity.update(asdict(dataset_trace))
        entity['trace_id'] = trace_id
        entity['status'] = dataset_trace.status.value

        return entity

    @staticmethod
    def _entity_to_dataset_trace(entity: datastore.Entity) -> DatasetTrace:
        return DatasetTrace(
            trace_id=entity['trace_id'],
            stable_id=entity['stable_id'],
            status=Status(entity['status']),
            timestamp=entity['timestamp'],
            execution_id=entity.get('execution_id'),
            file_sha256_hash=entity.get('file_sha256_hash'),
            hosted_url=entity.get('hosted_url'),
            error_message=entity.get('error_message')
        )


class BatchExecutionService:
    def __init__(self, client: Client = None):
        self.client = datastore.Client() if client is None else client

    def save(self, execution: BatchExecution):
        entity = self._execution_to_entity(execution)
        self.client.put(entity)

    def get_by_id(self, execution_id: str) -> [BatchExecution]:
        query = self.client.query(kind=batch_execution_collection)
        query.add_filter('execution_id', '=', execution_id)

        results = list(query.fetch())

        if results:
            return self._entity_to_execution(results)
        else:
            return []

    def _execution_to_entity(self, execution: BatchExecution) -> datastore.Entity:
        key = self.client.key(batch_execution_collection, execution.execution_id)
        entity = datastore.Entity(key=key)

        entity.update(asdict(execution))

        return entity
