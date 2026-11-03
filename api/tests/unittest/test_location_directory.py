import pytest
from fastapi import HTTPException

from feeds.impl.location_directory import DirectoryNode, parse_directory_node
from feeds_gen.models.location_directory_level import LocationDirectoryLevel
from shared.common.continents import CONTINENTS, CONTINENTS_BY_SLUG, get_continent_code
from shared.common.country_slugs import COUNTRY_SLUGS, get_country_code, get_country_slug


def test_continent_mapping():
    assert get_continent_code("ca") == "NA"
    assert get_continent_code(" FR ") == "EU"
    assert get_continent_code("XK") == "EU"
    assert get_continent_code("BR") == "SA"
    assert get_continent_code("AQ") == "AN"
    assert get_continent_code("ZZ") is None
    assert get_continent_code(None) is None
    assert {continent.slug for continent in CONTINENTS.values()} == set(CONTINENTS_BY_SLUG)


def test_country_slugs():
    assert get_country_slug("pt") == "portugal"
    assert get_country_slug(" US ") == "united-states"
    assert get_country_slug("CI") == "cote-d-ivoire"
    assert get_country_slug("CD") == "democratic-republic-of-the-congo"
    assert get_country_slug("XK") == "kosovo"
    assert get_country_slug("ZZ") is None
    assert get_country_slug(None) is None
    assert get_country_code(" Portugal ") == "PT"
    assert get_country_code("pt") is None
    assert get_country_code(None) is None
    for slug in COUNTRY_SLUGS.values():
        assert slug == slug.strip("-") and all(c.isascii() and (c.isalnum() or c == "-") for c in slug)
        assert slug == slug.lower() and "--" not in slug


def test_parse_root():
    node = parse_directory_node(None, " ", "", None)
    assert node == DirectoryNode()
    assert node.level == LocationDirectoryLevel.ROOT
    assert node.path() == []


def test_parse_normalizes_parameters():
    node = parse_directory_node(" North-America ", "Canada", "Quebec", "MONTREAL")
    assert node.continent.code == "NA"
    assert node.country_code == "CA"
    assert node.subdivision == "quebec"
    assert node.municipality == "montreal"
    assert node.level == LocationDirectoryLevel.MUNICIPALITY
    assert [path_node.level for path_node in node.path()] == [
        LocationDirectoryLevel.CONTINENT,
        LocationDirectoryLevel.COUNTRY,
        LocationDirectoryLevel.SUBDIVISION,
        LocationDirectoryLevel.MUNICIPALITY,
    ]
    assert node.path()[1] == DirectoryNode(continent=node.continent, country_code="CA")


def test_parse_unknown_continent_returns_none():
    assert parse_directory_node("atlantis", None, None, None) is None


@pytest.mark.parametrize("country", ["atlantis", "ca"])
def test_parse_unknown_country_returns_none(country):
    assert parse_directory_node("north-america", country, None, None) is None


@pytest.mark.parametrize(
    "params",
    [
        (None, "canada", None, None),
        ("north-america", None, "quebec", None),
        ("north-america", "canada", None, "montreal"),
        ("europe", "canada", None, None),
    ],
)
def test_parse_invalid_parameters(params):
    with pytest.raises(HTTPException) as error:
        parse_directory_node(*params)
    assert error.value.status_code == 400
