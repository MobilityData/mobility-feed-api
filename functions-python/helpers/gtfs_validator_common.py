import os
from typing import Final

GTFS_VALIDATOR_URL_PROD: Final[
    str
] = "https://gtfs-validator-web-mbzoxaljzq-ue.a.run.app"
GTFS_VALIDATOR_URL_STAGING: Final[
    str
] = "https://stg-gtfs-validator-web-mbzoxaljzq-ue.a.run.app"


def get_gtfs_validator_results_bucket(is_prod: bool) -> str:
    """
    Get the GTFS validator results bucket name based on the environment.
    :param is_prod: true if target environment is production, false otherwise
    :return: the bucket name for the target environment
    """
    if is_prod:
        return "gtfs-validator-results"
    else:
        return "stg-gtfs-validator-results"


def get_gtfs_validator_url(is_prod: bool) -> str:
    """
    Get the GTFS validator URL based on the environment
    or GTFS_VALIDATOR_URL_PROD/GTFS_VALIDATOR_URL_STAGING environment dependent.
    :param is_prod: true if target environment is production if the env variable is found this parameter is ignored
                    , false otherwise
    :return: the GTFS validator URL for the target environment
    """
    # Look up the GTFS validator URL based on the environment
    result = os.getenv("GTFS_VALIDATOR_URL")
    if result:
        return result
    if is_prod:
        return GTFS_VALIDATOR_URL_PROD
    else:
        return GTFS_VALIDATOR_URL_STAGING
