"""Static ISO 3166-1 alpha-2 country code to continent mapping.

Kept as a hand-written table instead of a dependency: the list of countries barely changes and the continent
of a few countries is a matter of convention. The mapping follows the usual seven-continent model, with Central
America and the Caribbean in North America, and the sub-Antarctic territories (BV, GS, HM, TF) in Antarctica.
Transcontinental countries are assigned to a single continent: Russia and Cyprus to Europe; Turkey, Georgia,
Armenia, Azerbaijan and Kazakhstan to Asia; Egypt to Africa.
"""

from dataclasses import dataclass
from typing import Dict, Final, Optional


@dataclass(frozen=True)
class Continent:
    code: str
    slug: str
    name: str


CONTINENTS: Final[Dict[str, Continent]] = {
    continent.code: continent
    for continent in (
        Continent("AF", "africa", "Africa"),
        Continent("AN", "antarctica", "Antarctica"),
        Continent("AS", "asia", "Asia"),
        Continent("EU", "europe", "Europe"),
        Continent("NA", "north-america", "North America"),
        Continent("OC", "oceania", "Oceania"),
        Continent("SA", "south-america", "South America"),
    )
}

CONTINENTS_BY_SLUG: Final[Dict[str, Continent]] = {continent.slug: continent for continent in CONTINENTS.values()}

_COUNTRIES_BY_CONTINENT: Final[Dict[str, str]] = {
    "AF": (
        "AO BF BI BJ BW CD CF CG CI CM CV DJ DZ EG EH ER ET GA GH GM GN GQ GW KE KM LR LS LY MA MG ML MR MU MW "
        "MZ NA NE NG RE RW SC SD SH SL SN SO SS ST SZ TD TG TN TZ UG YT ZA ZM ZW"
    ),
    "AN": "AQ BV GS HM TF",
    "AS": (
        "AE AF AM AZ BD BH BN BT CC CN CX GE HK ID IL IN IO IQ IR JO JP KG KH KP KR KW KZ LA LB LK MM MN MO MV "
        "MY NP OM PH PK PS QA SA SG SY TH TJ TL TM TR TW UZ VN YE"
    ),
    # XK (Kosovo) is a user-assigned code, but it is the one used by the European Commission and by feeds
    # declaring a location in Kosovo.
    "EU": (
        "AD AL AT AX BA BE BG BY CH CY CZ DE DK EE ES FI FO FR GB GG GI GR HR HU IE IM IS IT JE LI LT LU LV MC "
        "MD ME MK MT NL NO PL PT RO RS RU SE SI SJ SK SM UA VA XK"
    ),
    "NA": (
        "AG AI AW BB BL BM BQ BS BZ CA CR CU CW DM DO GD GL GP GT HN HT JM KN KY LC MF MQ MS MX NI PA PM PR SV "
        "SX TC TT US VC VG VI"
    ),
    "OC": "AS AU CK FJ FM GU KI MH MP NC NF NR NU NZ PF PG PN PW SB TK TO TV UM VU WF WS",
    "SA": "AR BO BR CL CO EC FK GF GY PE PY SR UY VE",
}

COUNTRY_CONTINENTS: Final[Dict[str, str]] = {
    country_code: continent_code
    for continent_code, country_codes in _COUNTRIES_BY_CONTINENT.items()
    for country_code in country_codes.split()
}


def get_continent_code(country_code: Optional[str]) -> Optional[str]:
    """Return the continent code of an ISO 3166-1 alpha-2 country code, or None when it is unknown."""
    if not country_code:
        return None
    return COUNTRY_CONTINENTS.get(country_code.strip().upper())
