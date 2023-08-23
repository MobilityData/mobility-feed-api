import functions_framework


# Register an HTTP function with the Functions Framework
@functions_framework.http
def batch_dataset(request):
    # Your code here
    print("Hello we are inside the code")
    print("Redeployment test 2")
    print("Redeployment test 3")
    print(request)
    # Return an HTTP response
    return 'Function has run successfully yay'
