"""Print the SQL INSERTs seeding the country_continent table (liquibase/changes/feat_location_directory.sql).

Every ISO 3166-1 alpha-2 code known to pycountry, plus the user-assigned code XK (Kosovo), is mapped to a
continent with the `Continent_7` classification of the country_converter library, used verbatim with no override:
the Mobility Database does not take a position on which continent a country belongs to. Continent_7 follows
Our World in Data's region definitions (https://ourworldindata.org/world-region-map-definitions). Codes the library
does not know (e.g. CP, Clipperton Island) are skipped and reported on stderr.

country_converter is a dev-only dependency, not part of api/requirements.txt. It needs pandas, and
country_converter 1.3.2 crashes with pandas 3, so install `country_converter pandas<3 pycountry` in a virtualenv:

    python3 -m venv /tmp/seed-venv
    /tmp/seed-venv/bin/pip install country_converter "pandas<3" pycountry
    /tmp/seed-venv/bin/python scripts/country_continent_seed.py > /tmp/country_continent.sql
"""

import logging
import sys

import country_converter
import pycountry

# Continent_7 names, as returned by country_converter, to the codes of the continent table.
CONTINENT_CODES = {
    "Africa": "AF",
    "Antarctica": "AN",
    "Asia": "AS",
    "Europe": "EU",
    "North America": "NA",
    "Oceania": "OC",
    "South America": "SA",
}

# User-assigned codes in use in the geopolygons that pycountry does not list.
EXTRA_COUNTRY_CODES = ["XK"]


def main():
    # country_converter logs a warning for every code it does not know; they are reported below instead.
    logging.getLogger("country_converter").setLevel(logging.ERROR)
    converter = country_converter.CountryConverter()
    codes = sorted({country.alpha_2 for country in pycountry.countries} | set(EXTRA_COUNTRY_CODES))
    rows = []
    skipped = []
    for code in codes:
        continent = converter.convert(code, src="ISO2", to="Continent_7", not_found=None)
        if continent is None:
            skipped.append(code)
            continue
        rows.append((code, CONTINENT_CODES[continent]))

    print("INSERT INTO country_continent (country_code, continent_code) VALUES")
    print(",\n".join(f"    ('{code}', '{continent_code}')" for code, continent_code in rows))
    print("ON CONFLICT (country_code) DO UPDATE SET continent_code = EXCLUDED.continent_code;")
    print(f"-- {len(rows)} countries, skipped: {', '.join(skipped) or 'none'}", file=sys.stderr)


if __name__ == "__main__":
    main()
