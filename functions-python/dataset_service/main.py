#
#   MobilityData 2023
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#
import logging
import uuid
from dataclasses import asdict
from typing import Final
from google.cloud import datastore
from google.cloud.datastore import Client

from dataset_service_commons import (
    DatasetTrace,
    Status,
    PipelineStage,
    BatchExecution,
)

# This files contains the dataset trace and batch execution models and services.
# The dataset trace is used to store the trace of a dataset and the batch execution
# One batch execution can have multiple dataset traces.
# Each dataset trace represents the resulting log of the dataset processing.
# The persistent layer used is Google Cloud Datastore.


dataset_trace_collection: Final[str] = "dataset_trace"
batch_execution_collection: Final[str] = "batch_execution"


class MaxExecutionsReachedError(Exception):
    pass


# Dataset trace service with CRUD operations for the dataset trace
class DatasetTraceService:
    def __init__(self, client: Client = None):
        self.client = datastore.Client() if client is None else client

    def validate_and_save(self, dataset_trace: DatasetTrace, max_executions: int = 1):
        if dataset_trace.execution_id is None or dataset_trace.stable_id is None:
            raise ValueError("Execution ID and Stable ID are required.")
        trace = self.get_by_execution_and_stable_ids(
            dataset_trace.execution_id, dataset_trace.stable_id
        )
        executions = len(trace) if trace else 0
        logging.info(f"[{dataset_trace.stable_id}] Executions: {executions}")
        if executions > 0 and executions >= max_executions:
            raise MaxExecutionsReachedError(
                f"Maximum executions reached for {dataset_trace.stable_id}."
            )
        self.save(dataset_trace)

    # Save the dataset trace
    def save(self, dataset_trace: DatasetTrace):
        entity = self._dataset_trace_to_entity(dataset_trace)
        self.client.put(entity)

    # Get the dataset trace by trace id
    def get_by_id(self, trace_id: str) -> [DatasetTrace]:
        key = self.client.key(dataset_trace_collection, trace_id)
        entity = self.client.get(key)

        if entity:
            return self._entity_to_dataset_trace(entity)
        else:
            return []

    # Get the dataset trace by execution id and stable id
    def get_by_execution_and_stable_ids(
        self, execution_id: str, stable_id: str
    ) -> [DatasetTrace]:
        query = self.client.query(kind=dataset_trace_collection)
        query.add_filter("execution_id", "=", execution_id)
        query.add_filter("stable_id", "=", stable_id)

        results = list(query.fetch())

        if results:
            return [self._entity_to_dataset_trace(result) for result in results]
        else:
            return []

    # Transform the dataset trace to entity
    def _dataset_trace_to_entity(self, dataset_trace: DatasetTrace) -> datastore.Entity:
        trace_id = (
            str(uuid.uuid4()) if not dataset_trace.trace_id else dataset_trace.trace_id
        )
        key = self.client.key(dataset_trace_collection, trace_id)
        entity = datastore.Entity(key=key)

        entity.update(asdict(dataset_trace))
        entity["trace_id"] = trace_id
        entity["status"] = dataset_trace.status.value
        entity["pipeline_stage"] = dataset_trace.pipeline_stage.value

        return entity

    # Transform the entity to dataset trace
    @staticmethod
    def _entity_to_dataset_trace(entity: datastore.Entity) -> DatasetTrace:
        return DatasetTrace(
            trace_id=entity["trace_id"],
            stable_id=entity["stable_id"],
            status=Status(entity["status"]),
            timestamp=entity["timestamp"],
            execution_id=entity.get("execution_id"),
            file_sha256_hash=entity.get("file_sha256_hash"),
            hosted_url=entity.get("hosted_url"),
            error_message=entity.get("error_message"),
            pipeline_stage=PipelineStage(entity.get("pipeline_stage"))
            if entity.get("pipeline_stage")
            else None,
            dataset_id=entity.get("dataset_id"),
        )


# Batch execution service with CRUD operations for the batch execution
class BatchExecutionService:
    def __init__(self):
        self.client = datastore.Client()

    # Save the batch execution
    def save(self, execution: BatchExecution):
        entity = self._execution_to_entity(execution)
        self.client.put(entity)

    # Get the batch execution by execution id
    def get_by_id(self, execution_id: str) -> [BatchExecution]:
        query = self.client.query(kind=batch_execution_collection)
        query.add_filter("execution_id", "=", execution_id)

        results = list(query.fetch())

        if results:
            return self._entity_to_execution(results)
        else:
            return None

    # Transform the entity to batch execution
    def _execution_to_entity(self, execution: BatchExecution) -> datastore.Entity:
        key = self.client.key(batch_execution_collection, execution.execution_id)
        entity = datastore.Entity(key=key)

        entity.update(asdict(execution))

        return entity
