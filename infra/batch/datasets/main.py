from google.cloud import storage
import functions_framework

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
    # Your code here
    print("Hello we are inside the code")
    print("Redeployment test 2")
    print("Redeployment test 3")
    print(request)

    # Create a test file in the specified bucket
    create_test_file("datasets", "test-file.txt")

    # Return an HTTP response
    return 'Function has run successfully yay'
