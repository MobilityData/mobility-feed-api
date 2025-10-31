import unittest
from unittest.mock import patch, MagicMock

from shared.db_models.location_impl import LocationImpl
from shared.database_gen.sqlacodegen_models import Location as LocationOrm


class TestLocationImpl(unittest.TestCase):
    def test_from_orm(self):
        result = LocationImpl.from_orm(
            LocationOrm(
                country_code="US", subdivision_name="California", municipality="Los Angeles", country="United States"
            )
        )
        assert result == LocationImpl(
            country_code="US", country="United States", subdivision_name="California", municipality="Los Angeles"
        )

        assert LocationImpl.from_orm(None) is None

    @patch("shared.db_models.location_impl.create_or_get_location")
    def test_to_orm_from_dict_valid(self, mock_create_or_get_location):
        """Ensure to_orm_from_dict delegates to create_or_get_location with the right args and returns its result."""
        mock_session = MagicMock(name="session")
        expected = LocationOrm(
            id="loc-1",
            country_code="CA",
            subdivision_name="QC",
            municipality="Montreal",
            country="Canada",
        )
        mock_create_or_get_location.return_value = expected

        payload = {
            "country": "Canada",
            "subdivision_name": "QC",
            "municipality": "Montreal",
            "country_code": "CA",
        }

        result = LocationImpl.to_orm_from_dict(payload, db_session=mock_session)

        assert result is expected
        mock_create_or_get_location.assert_called_once_with(
            session=mock_session,
            country="Canada",
            state_province="QC",
            city_name="Montreal",
            country_code="CA",
        )

    @patch("shared.db_models.location_impl.create_or_get_location")
    def test_to_orm_from_dict_allows_none_values(self, mock_create_or_get_location):
        """None values are passed through to the factory; still returns its result."""
        mock_session = MagicMock(name="session")
        expected = LocationOrm(id="loc-2", country_code=None, subdivision_name=None, municipality=None, country=None)
        mock_create_or_get_location.return_value = expected

        payload = {
            "country": None,
            "subdivision_name": None,
            "municipality": None,
            "country_code": None,
        }

        result = LocationImpl.to_orm_from_dict(payload, db_session=mock_session)

        assert result is expected
        mock_create_or_get_location.assert_called_once_with(
            session=mock_session,
            country=None,
            state_province=None,
            city_name=None,
            country_code=None,
        )

    def test_to_orm_from_dict_missing_keys_raises_keyerror(self):
        """Missing required keys should raise KeyError before calling the factory."""
        mock_session = MagicMock(name="session")

        with patch("shared.db_models.location_impl.create_or_get_location") as mock_factory:
            with self.assertRaises(KeyError):
                LocationImpl.to_orm_from_dict({"country": "CA"}, db_session=mock_session)
            mock_factory.assert_not_called()
