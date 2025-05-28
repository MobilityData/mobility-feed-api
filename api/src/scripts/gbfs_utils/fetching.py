import requests


def fetch_data(auto_discovery_url, logger, urls=[], fields=[]):
    """Fetch data from the auto-discovery URL and return the specified fields."""
    fetched_data = {}
    if not auto_discovery_url:
        return
    try:
        response = requests.get(auto_discovery_url)
        response.raise_for_status()
        data = response.json()
        for field in fields:
            fetched_data[field] = data.get(field)
        feeds = None
        for lang_code, lang_data in data.get("data", {}).items():
            if isinstance(lang_data, list):
                lang_feeds = lang_data
            else:
                lang_feeds = lang_data.get("feeds", [])
            if lang_code == "en":
                feeds = lang_feeds
                break
            elif not feeds:
                feeds = lang_feeds
        logger.debug(f"Feeds found from auto-discovery URL {auto_discovery_url}: {feeds}")
        if feeds:
            for url in urls:
                fetched_data[url] = get_field_url(feeds, url)
        return fetched_data
    except requests.RequestException as e:
        logger.error(f"Error fetching data for autodiscovery url {auto_discovery_url}: {e}")
        return fetched_data


def get_data_content(url, logger):
    """Utility function to fetch data content from a URL."""
    try:
        if url:
            response = requests.get(url)
            response.raise_for_status()
            system_info = response.json().get("data", {})
            return system_info
    except requests.RequestException as e:
        logger.error(f"Error fetching data content for url {url}: {e}")
        return None


def get_field_url(fields, field_name):
    """Utility function to get the URL of a specific feed by name."""
    for field in fields:
        if field.get("name") == field_name:
            return field.get("url")
    return None
