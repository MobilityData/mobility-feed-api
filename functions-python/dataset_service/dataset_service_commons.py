from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional


# Status of the dataset trace
class Status(Enum):
    FAILED = "FAILED"
    SUCCESS = "SUCCESS"
    PUBLISHED = "PUBLISHED"
    NOT_PUBLISHED = "NOT_PUBLISHED"
    PROCESSING = "PROCESSING"


# Stage of the pipeline
class PipelineStage(Enum):
    DATASET_PROCESSING = "DATASET_PROCESSING"
    LOCATION_EXTRACTION = "LOCATION_EXTRACTION"
    GBFS_VALIDATION = "GBFS_VALIDATION"


# Dataset trace class to store the trace of a dataset
@dataclass
class DatasetTrace:
    stable_id: str
    status: Status
    timestamp: datetime
    dataset_id: Optional[str] = None
    trace_id: Optional[str] = None
    execution_id: Optional[str] = None
    file_sha256_hash: Optional[str] = None
    hosted_url: Optional[str] = None
    pipeline_stage: PipelineStage = PipelineStage.DATASET_PROCESSING
    error_message: Optional[str] = None


# Batch execution class to store the trace of a batch execution
@dataclass
class BatchExecution:
    execution_id: str
    timestamp: datetime
    feeds_total: int
