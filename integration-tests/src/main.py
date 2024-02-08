import argparse
import importlib
import os
import pkgutil

from endpoints.integration_tests import IntegrationTests


def parse_class_list(class_list_str):
    """
    Parse a comma-separated list of class names into a list.
    If the input is empty or None, returns an empty list.

    :param class_list_str: String of comma-separated class names
    :return: List of class names
    """
    return class_list_str.split(",") if class_list_str else []


def set_up_configs():
    """
    Set up command line argument parsing and return the configuration values.

    This function defines and parses command line arguments, including an optional
    argument to specify a list of test classes to include in the integration tests.
    This allows for selective execution of tests based on class names, enabling
    more focused and efficient testing.

    :return: Tuple of file path, access token, API URL, dataset validation flag, and list of class names to include
    """
    parser = argparse.ArgumentParser(
        description="Run integration tests with optional filtering of test classes."
    )
    parser.add_argument(
        "--file_path", help="CSV version of the database", required=True
    )
    parser.add_argument("--url", help="API URL", default="http://0.0.0.0:8080")
    parser.add_argument(
        "--include_classes",
        help="Optional, comma-separated list of test class names to include. "
        "Specifies which classes contain the tests to be executed, allowing for targeted "
        "testing of specific components or features.",
        default="",
        type=parse_class_list,
    )
    args = parser.parse_args()
    access_token = os.getenv("ACCESS_TOKEN", None)
    if access_token is None:
        raise ValueError("ACCESS_TOKEN environment variable is not set.")
    return args.file_path, access_token, args.url, args.include_classes


if __name__ == "__main__":
    # Dynamically importing all testing endpoints
    package_name = "endpoints"
    package = importlib.import_module(package_name)
    prefix = package.__name__ + "."

    for importer, modname, ispkg in pkgutil.iter_modules(package.__path__, prefix):
        if not ispkg:
            importlib.import_module(modname)

    data_file_path, api_access_token, api_url, include_classes = set_up_configs()

    IntegrationTests(data_file_path, api_access_token, api_url).test_all(
        target_classes=include_classes
    )
