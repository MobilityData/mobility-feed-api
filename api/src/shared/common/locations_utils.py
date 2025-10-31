import logging
from typing import Optional

from sqlalchemy.orm import Session

from shared.database_gen.sqlacodegen_models import Location


def get_country_code(country_name: str) -> Optional[str]:
    """
    Get ISO 3166 country code from country name

    Args:
        country_name (str): Full country name

    Returns:
        Optional[str]: Two-letter ISO country code or None if not found
    """
    import pycountry

    # Return None for empty or whitespace-only strings
    if not country_name or not country_name.strip():
        logging.error("Could not find country code for: empty string")
        return None

    try:
        # Try exact match first
        country = pycountry.countries.get(name=country_name)
        if country:
            return country.alpha_2

        # Try searching with fuzzy matching
        countries = pycountry.countries.search_fuzzy(country_name)
        if countries:
            return countries[0].alpha_2

    except LookupError:
        logging.error(f"Could not find country code for: {country_name}")
    return None


def create_or_get_location(
    session: Session,
    country: Optional[str],
    state_province: Optional[str],
    city_name: Optional[str],
    country_code: Optional[str] = None,
) -> Optional[Location]:
    """
    Create a new location or get existing one

    Args:
        session: Database session
        country: Country name
        state_province: State/province name
        city_name: City name
        country_code: ISO 3166-1 alpha-2 country code

    Returns:
        Optional[Location]: Location object or None if creation failed
    """
    import pycountry

    if not any([country, state_province, city_name]):
        return None

    # Generate location_id using the specified pattern
    location_components = []
    if country_code:
        location_components.append(country_code)
        try:
            py_country = pycountry.countries.get(alpha_2=country_code.strip())
            country = py_country.name if py_country else country
        except LookupError:
            logging.warning("Could not find country code for: %s", country_code)
    elif country:
        country_code = get_country_code(country)
        if country_code:
            location_components.append(country_code)
        else:
            logging.error(f"Could not determine country code for {country}")
            return None

    if state_province:
        location_components.append(state_province)
    if city_name:
        location_components.append(city_name)

    location_id = "-".join(location_components)

    # First check if location already exists
    existing_location = session.query(Location).filter(Location.id == location_id).first()

    if existing_location:
        logging.debug(f"Using existing location: {location_id}")
        return existing_location

    # Create new location
    location = Location(
        id=location_id,
        country_code=country_code,
        country=country,
        subdivision_name=state_province,
        municipality=city_name,
    )
    session.add(location)
    session.flush()
    logging.debug(f"Created new location: {location_id}")

    return location
