import os

from common.bq_data_transfer import BigQueryDataTransfer


class BigQueryDataTransferGTFS(BigQueryDataTransfer):
    """BigQuery data transfer for GTFS data"""

    def __init__(self):
        super().__init__()
        current_dir = os.path.dirname(os.path.abspath(__file__))
        self.schema_path = os.path.join(
            current_dir, "../shared/helpers/bq_schema/gtfs_schema.json"
        )
