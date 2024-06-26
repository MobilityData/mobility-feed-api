from google.cloud import datastore
from google.cloud.datastore.query import PropertyFilter


def get_by_stable_ids(stable_id: str):
    try:
        client = datastore.Client()
        query = client.query(kind="dataset_trace")
        query.add_filter(filter=PropertyFilter("stable_id", "=", stable_id))
        # query.order = ["-timestamp"]

        results = list(query.fetch(limit=1))
        # TODO: complete this function
        print(results)
    except Exception as e:
        print(e)
