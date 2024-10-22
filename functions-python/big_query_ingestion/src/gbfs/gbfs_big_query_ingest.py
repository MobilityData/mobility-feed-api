import os

from ..common.bq_data_transfer import BigQueryDataTransfer


class BigQueryDataTransferGBFS(BigQueryDataTransfer):
    """BigQuery data transfer for GBFS data"""

    def __init__(self):
        super().__init__()
        current_dir = os.path.dirname(os.path.abspath(__file__))
        self.schema_path = os.path.join(
            current_dir, "../helpers/bq_schema/gbfs_schema.json"
        )
