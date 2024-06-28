from datetime import datetime
from typing import Optional, List, Dict

from google.cloud import datastore

from feeds_gen.models.last_fetch_attempt import LastFetchAttempt


def get_lts_traces(stable_ids: List[str]) -> Dict[str, Optional[LastFetchAttempt]]:
    if not stable_ids:
        return {}

    results: Dict[str, Optional[LastFetchAttempt]] = {stable_id: None for stable_id in stable_ids}
    client = datastore.Client()

    try:
        # Step 1: Get the latest timestamp for the first stable_id
        first_result = None
        n = 0
        while not first_result and n < len(stable_ids):  # Retry until we get a result or reach the end
            query = client.query(kind="dataset_trace")
            query.add_filter("stable_id", "=", stable_ids[n])
            query.order = ["-timestamp"]
            first_result = list(query.fetch(limit=1))
            n += 1

        if not first_result:
            return results

        first_stable_id = stable_ids[n - 1]
        latest_timestamp = first_result[0]["timestamp"]

        # Record the result for the first stable_id
        results[first_stable_id] = LastFetchAttempt(
            status=first_result[0]["status"], timestamp=datetime.fromtimestamp(first_result[0]["timestamp"].timestamp())
        )

        # Step 2: Fetch and filter other stable_ids using the latest timestamp
        for i in range(n, len(stable_ids), 30):
            # Fetch 30 stable_ids at a time to avoid exceeding the datastore limit
            batch_stable_ids = stable_ids[i : i + 30]
            query = client.query(kind="dataset_trace")
            query.add_filter("stable_id", "IN", batch_stable_ids)
            query.add_filter("timestamp", ">=", latest_timestamp)
            query.order = ["-timestamp"]

            query_results = list(query.fetch())
            for result in query_results:
                # The first result is the latest timestamp for the stable_id
                if result["stable_id"] in results and results[result["stable_id"]] is None:
                    print(f"Found result for {result['stable_id']}")
                    results[result["stable_id"]] = LastFetchAttempt(
                        status=result["status"], timestamp=datetime.fromtimestamp(result["timestamp"].timestamp())
                    )
    except Exception as e:
        print(f"An error occurred: {e}")
        return {stable_id: None for stable_id in stable_ids}

    return results
