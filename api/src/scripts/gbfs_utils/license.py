LICENSE_URL_MAP = {
    "CC0-1.0": "https://creativecommons.org/publicdomain/zero/1.0/",
    "CC-BY-4.0": "https://creativecommons.org/licenses/by/4.0/",
    "CDLA-Permissive-1.0": "https://cdla.io/permissive-1-0/",
    "ODC-By-1.0": "https://www.opendatacommons.org/licenses/by/1.0/",
}

DEFAULT_LICENSE_URL = "https://creativecommons.org/licenses/by/4.0/"


def get_license_url(system_info, logger):
    try:
        if system_info is None:
            return None

        # Fetching license_url or license_id
        license_url = system_info.get("license_url")
        if not license_url:
            license_id = system_info.get("license_id")
            if license_id:
                return LICENSE_URL_MAP.get(license_id, DEFAULT_LICENSE_URL)
            return DEFAULT_LICENSE_URL
        return license_url
    except Exception as e:
        logger.error(f"Error fetching license url data from system info {system_info}: \n{e}")
        return None
