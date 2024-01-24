import functions_framework
import gtfs_kit
from cloudevents.http import CloudEvent


# Triggered by a change in a storage bucket
@functions_framework.cloud_event
def extract_bounding_box(cloud_event: CloudEvent) -> str:
    """This function is triggered by a change in a storage bucket.

    Args:
        cloud_event: The CloudEvent that triggered this function.
    Returns:
        The event ID, event type, bucket, name, metageneration, and timeCreated.
    """
    data = cloud_event.data
    print(f"data: {data}")
    resource_name = data["protoPayload"]["resourceName"]
    stable_id = resource_name.split('/')[-3]
    folder_id = resource_name.split('/')[-2]
    file_name = resource_name.split('/')[-1]
    url = f"https://storage.googleapis.com/{stable_id}/{folder_id}/{file_name}"

    print(f"url: {url}")
    project_id = data["resource"]["labels"]["project_id"]
    bucket_name = data["resource"]["labels"]["bucket_name"]

    feed = gtfs_kit.read_feed(url, 'km')
    min_longitude, min_latitude, max_longitude, max_latitude = feed.compute_bounds()

    print(f"min_longitude: {min_longitude}, min_latitude: {min_latitude}")
    # TODO update database

    return 'Yup'
