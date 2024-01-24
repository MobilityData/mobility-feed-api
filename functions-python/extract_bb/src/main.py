from cloudevents.http import CloudEvent

import functions_framework


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
    project_id = data["resource"]["labels"]["project_id"]
    bucket_name = data["resource"]["labels"]["bucket_name"]

    return 'Yup'
