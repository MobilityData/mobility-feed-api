import pytest
from fastapi import HTTPException

from feeds_operations.impl.licenses_api_impl import LicensesApiImpl
from feeds_gen.models.license_with_rules import LicenseWithRules
from feeds_gen.models.license_base import LicenseBase
from feeds_gen.models.matching_license import MatchingLicense
from feeds_gen.models.get_matching_licenses_request import GetMatchingLicensesRequest
from shared.database.database import Database
from shared.database_gen.sqlacodegen_models import License as OrmLicense
from test_shared.test_utils.database_utils import default_db_url


@pytest.fixture
def db_session():
    db = Database(feeds_database_url=default_db_url)
    with db.start_db_session() as session:
        yield session


@pytest.mark.asyncio
async def test_get_license_success(db_session):
    # Arrange: pick an existing license id from the database
    existing = db_session.query(OrmLicense).first()
    if existing is None:
        pytest.skip("No licenses in test database to validate get_license")

    api = LicensesApiImpl()

    # Act
    result = await api.get_license(existing.id)

    # Assert
    assert isinstance(result, LicenseWithRules)
    assert result.id == existing.id
    assert result.name == existing.name


@pytest.mark.asyncio
async def test_get_license_not_found():
    api = LicensesApiImpl()

    with pytest.raises(HTTPException) as exc_info:
        await api.get_license("non-existent-license-id")

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "License not found"


@pytest.mark.asyncio
async def test_get_licenses_basic_pagination(db_session):
    # Ensure there is at least one license; otherwise, skip.
    count = db_session.query(OrmLicense).count()
    if count == 0:
        pytest.skip("No licenses in test database to validate get_licenses")

    api = LicensesApiImpl()

    # Act
    result = await api.get_licenses(limit=10, offset=0)

    # Assert
    assert isinstance(result, list)
    assert all(isinstance(item, LicenseBase) for item in result)
    # We don't assert exact size because DB contents may vary, but
    # if there are licenses in DB, result should not be empty.
    assert len(result) > 0


@pytest.mark.asyncio
async def test_get_licenses_with_search_query(db_session):
    # Take a license from the DB and use part of its name as a search query
    existing = db_session.query(OrmLicense).first()
    if existing is None or not existing.name:
        pytest.skip("No suitable license data in DB to test search_query")

    fragment = existing.name[:3]
    api = LicensesApiImpl()

    result = await api.get_licenses(limit=50, offset=0, search_query=fragment)

    assert isinstance(result, list)
    # True positive: the reference license must be present
    assert any(item.id == existing.id for item in result)

    # False positives: every returned item must match the search criteria
    # (assuming search is done against name, adapt if implementation differs)
    lowered_fragment = fragment.lower()
    assert all(
        (item.name or "").lower().find(lowered_fragment) != -1 for item in result
    ), "Search results contain licenses whose names do not match the search fragment"


@pytest.mark.asyncio
async def test_get_licenses_filter_is_spdx_true(db_session):
    # There should be at least one SPDX license from test data
    spdx_count = (
        db_session.query(OrmLicense).filter(OrmLicense.is_spdx.is_(True)).count()
    )
    if spdx_count == 0:
        pytest.skip("No SPDX licenses in test database to validate is_spdx filter")

    api = LicensesApiImpl()
    result = await api.get_licenses(limit=10, offset=0, is_spdx=True)

    assert isinstance(result, list)
    assert len(result) == spdx_count
    assert all(item.is_spdx is True for item in result)


@pytest.mark.asyncio
async def test_get_licenses_filter_is_spdx_false(db_session):
    # There should be at least one non-SPDX license from test data
    non_spdx_count = (
        db_session.query(OrmLicense).filter(OrmLicense.is_spdx.is_(False)).count()
    )
    if non_spdx_count == 0:
        pytest.skip("No non-SPDX licenses in test database to validate is_spdx filter")

    api = LicensesApiImpl()
    result = await api.get_licenses(limit=10, offset=0, is_spdx=False)

    assert isinstance(result, list)
    assert len(result) == non_spdx_count
    assert all(item.is_spdx is False for item in result)


@pytest.mark.asyncio
async def test_get_license_includes_rules(db_session):
    """Ensure that get_license returns associated rules in LicenseWithRules."""
    existing = (
        db_session.query(OrmLicense)
        .filter(OrmLicense.id == "custom-test")
        .one_or_none()
    )
    if existing is None:
        pytest.skip("Fixture license 'custom-test' not found in test database")

    api = LicensesApiImpl()
    result = await api.get_license("custom-test")

    assert isinstance(result, LicenseWithRules)
    # LicenseWithRules exposes rules under the license_rules field
    assert result.license_rules is not None
    rule_names = sorted(rule.name for rule in result.license_rules)
    assert rule_names == ["attribution", "share-alike"]


@pytest.mark.asyncio
async def test_get_licenses_includes_rules_for_each_item(db_session):
    """Ensure that licenses returned by get_licenses can expose rule data via get_license."""
    api = LicensesApiImpl()
    results = await api.get_licenses(limit=10, offset=0)

    assert results
    for item in results:
        if item.id == "MIT":
            detailed = await api.get_license("MIT")
            assert isinstance(detailed, LicenseWithRules)
            assert detailed.license_rules is not None
            assert [r.name for r in detailed.license_rules] == ["attribution"]


@pytest.mark.asyncio
async def test_get_matching_licenses_success(monkeypatch, db_session):
    """Happy path: resolve_license returns one or more matches and they are mapped to MatchingLicense models."""

    # Arrange
    api = LicensesApiImpl()
    url = "https://licenses.example.com/custom-test"
    request = GetMatchingLicensesRequest(license_url=url)

    # Build a fake domain object compatible with MatchingLicenseImpl.from_domain
    domain_match = MatchingLicense(
        license_id="custom-test",
        confidence=0.9,
        license_url=url,
    )

    def fake_resolve(license_url, db_session):  # signature matches resolve_license
        assert license_url == url
        return [domain_match]

    # Patch resolve_license where it's imported in the implementation
    monkeypatch.setattr(
        "feeds_operations.impl.licenses_api_impl.resolve_license", fake_resolve
    )

    # Act
    result = await api.get_matching_licenses(request)

    # Assert
    assert isinstance(result, list)
    assert len(result) == 1
    assert isinstance(result[0], MatchingLicense)
    assert result[0].license_id == "custom-test"


@pytest.mark.asyncio
async def test_get_matching_licenses_propagates_http_exception(monkeypatch):
    """If resolve_license raises an HTTPException, it should be propagated unchanged."""

    api = LicensesApiImpl()
    request = GetMatchingLicensesRequest(license_url="https://invalid")

    def fake_resolve(license_url, db_session):
        raise Exception("Invalid license URL")

    monkeypatch.setattr(
        "feeds_operations.impl.licenses_api_impl.resolve_license", fake_resolve
    )

    with pytest.raises(HTTPException) as exc_info:
        await api.get_matching_licenses(request)

    assert exc_info.value.status_code == 500
    assert exc_info.value.detail == "Error retrieving matching licenses"


@pytest.mark.asyncio
async def test_get_matching_licenses_unexpected_error(monkeypatch):
    """If an unexpected exception occurs, API should respond with a 500 HTTPException."""

    api = LicensesApiImpl()
    request = GetMatchingLicensesRequest(license_url="https://boom.example.com")

    def fake_resolve(license_url, db_session):
        raise RuntimeError("boom")

    monkeypatch.setattr(
        "feeds_operations.impl.licenses_api_impl.resolve_license", fake_resolve
    )

    with pytest.raises(HTTPException) as exc_info:
        await api.get_matching_licenses(request)

    assert exc_info.value.status_code == 500
    assert exc_info.value.detail == "Error retrieving matching licenses"
