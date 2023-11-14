# Python Functions

This folder contains Python functions. These functions should not have interdependencies. However, common code can be shared across multiple functions if they are in folders that don't contain functions.

# Python function folders
On each function folder, a file should contain all related configurations. Currently, there is no automated process to deploy all functions; this is why, to be able to deploy it the function should be added to the terraform scripts. In the future, we should automate the deployment.

# Useful scripts
- To locally execute a function use the following command:
```
./scripts/function-python-run.sh --function_name tokens
```
- To locally create a distribution zip use the following command:
```
./scripts/function-python-build.sh --function_name tokens
```
or 
```
./scripts/function-python-build.sh --all
```

# Local variables
To be able to set environment variables, add a file `.env.local` file to a function's folder and provide the name-value pair as follows:
```
export MY_AWESOME_KEY=MY_AWESOME_VALUE
```

# Unit tests
If a folder `tests` is added to a function's folder, the script `api-test.sh` will execute the tests without any further configuration.