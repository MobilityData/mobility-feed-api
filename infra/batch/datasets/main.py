from google.cloud import storage
import functions_framework

def create_bucket(bucket_name):
    storage_client = storage.Client()
    # Check if the bucket already exists
    bucket = storage_client.lookup_bucket(bucket_name)
    if bucket is None:
        # If not, create the bucket
        bucket = storage_client.create_bucket(bucket_name)
        print(f'Bucket {bucket} created.')
    else:
        print(f'Bucket {bucket_name} already exists.')

def create_test_file(bucket_name, file_name):
    # Create a storage client
    storage_client = storage.Client()
    bucket = storage_client.get_bucket(bucket_name)
    blob = bucket.blob(file_name)

    # Write data to the blob
    blob.upload_from_string('This is test data for redeployment test.')


# Register an HTTP function with the Functions Framework
@functions_framework.http
def batch_dataset(request):
    bucket_name = "mobility-datasets"
    create_bucket(bucket_name)
    create_test_file(bucket_name, "test.txt")
    # Your code here
    print("Hello we are inside the code")
    print("Redeployment test 2")
    print("Redeployment test 3")
    print(request)
    # Return an HTTP response
    return 'Function has run successfully yay'

