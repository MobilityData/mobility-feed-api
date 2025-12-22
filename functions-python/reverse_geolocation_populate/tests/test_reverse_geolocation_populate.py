import unittest
from unittest.mock import patch, MagicMock

from faker import Faker

from test_shared.test_utils.database_utils import default_db_url
from main import LocationType

faker = Faker()


class TestReverseGeolocationPopulate(unittest.TestCase):
    def test_parse_request(self):
        from main import parse_request_parameters

        # Valid request
        request = MagicMock()
        request.get_json.return_value = {
            "country_code": "CA",
            "admin_levels": "2, 3, 4",
        }
        result = parse_request_parameters(request)
        self.assertIsNotNone(result[0])
        self.assertEqual(result[0], "CA")
        self.assertIsNotNone(result[1])
        self.assertEqual(result[1], [2, 3, 4])

        # Invalid country code
        request.get_json.return_value = {
            "country_code": "USA",
            "admin_levels": "2, 3, 4",
        }
        with self.assertRaises(ValueError):
            parse_request_parameters(request)

        # Invalid admin levels
        request.get_json.return_value = {
            "country_code": "CA",
            "admin_levels": "1, 3, 4, 5",
        }
        with self.assertRaises(ValueError):
            parse_request_parameters(request)
        request.get_json.return_value = {
            "country_code": "CA",
            "admin_levels": "1, 3, invalid,",
        }
        with self.assertRaises(ValueError):
            parse_request_parameters(request)

        # Missing country code and admin levels
        request.get_json.return_value = {}
        with self.assertRaises(ValueError):
            parse_request_parameters(request)

        # Missing admin levels
        request.get_json.return_value = {
            "country_code": "CA",
        }
        result = parse_request_parameters(request)
        self.assertIsNotNone(result[0])
        self.assertEqual(result[0], "CA")
        self.assertIsNone(result[1])

    def test_fetch_subdivision_admin_levels(self):
        from main import fetch_subdivision_admin_levels

        country_code = "CA"
        client_mock = MagicMock()
        client_mock.query.return_value.result.return_value = [
            MagicMock(admin_level=2),
            MagicMock(admin_level=3),
            MagicMock(admin_level=None),
        ]
        with patch("main.client", client_mock):
            result = fetch_subdivision_admin_levels(country_code)
            self.assertIsNotNone(result)
            self.assertEqual(result, [2, 3])

    def test_fetch_country_admin_levels(self):
        from main import fetch_country_admin_levels

        country_code = "CA"
        client_mock = MagicMock()
        client_mock.query.return_value.result.return_value = [
            MagicMock(admin_level=2),
            MagicMock(admin_level=3),
            MagicMock(admin_level=None),
        ]
        with patch("main.client", client_mock):
            result = fetch_country_admin_levels(country_code)
            self.assertIsNotNone(result)
            self.assertEqual(result, [2, 3])

    def test_generate_query(self):
        from main import generate_query

        country_code = "CA"
        admin_levels = [2, 3]
        result = generate_query(admin_levels, country_code, LocationType.COUNTRY)
        self.assertIsNotNone(result)
        query_result = result[0]
        self.assertNotIn(
            "AND ('name:en', @country_name) IN (SELECT STRUCT(key, value) FROM UNNEST(all_tags))",
            query_result,
        )

        result = generate_query(
            admin_levels, country_code, LocationType.LOCALITY, country_name="Canada"
        )
        self.assertIsNotNone(result)
        query_result = result[0]
        self.assertIn(
            "AND ('name:en', @country_name) IN (SELECT STRUCT(key, value) FROM UNNEST(all_tags))",
            query_result,
        )

        result = generate_query(admin_levels, country_code, LocationType.COUNTRY)
        self.assertIsNotNone(result)
        self.assertIn(
            "AND ('ISO3166-1', @country_code) IN (SELECT STRUCT(key, value) FROM UNNEST(all_tags))",
            result[0],
        )

    @patch("main.generate_query")
    def test_fetch_data(self, mock_generate_query):
        from main import fetch_data

        def gen_mock_row(osm_id, name):
            row_mock = MagicMock(
                all_tags=[{"key": "name:en", "value": name}],
                items={"osm_id": osm_id},
                geometry=MagicMock(type="Point", coordinates=[0, 0]),
            )
            row_mock.__getitem__.side_effect = lambda x: row_mock.items[x]
            return row_mock

        query = faker.sentence()
        mock_generate_query.return_value = [query, []]
        client_mock = MagicMock()
        client_mock.query.return_value.result.return_value = MagicMock(
            total_rows=3,
            __iter__=lambda x: iter(
                [
                    gen_mock_row(1, "Toronto"),
                    gen_mock_row(2, "Vancouver"),
                    gen_mock_row(3, "Montreal"),
                    gen_mock_row(None, "Invalid"),
                ]
            ),
        )
        with patch("main.client", client_mock):
            result = fetch_data(3, "CA", LocationType.SUBDIVISION)
            self.assertIsNotNone(result)
            self.assertEqual(len(result), 3)

    @patch.dict(
        "os.environ",
        {
            "FEEDS_DATABASE_URL": default_db_url,
            "GOOGLE_APPLICATION_CREDENTIALS": faker.file_path(),
        },
    )
    def test_save_to_database(self):
        from main import save_to_database

        data = [
            {
                "osm_id": 1,
                "name": "Toronto",
                "geometry": "POINT(-73.5673 45.5017)",
                "admin_lvl": 4,
                "name:en": "Toronto",
                "iso3166_1": None,
                "iso3166_2": None,
                "alt_name": None,
                "alt_name:en": None,
            },
            {
                "osm_id": 2,
                "name": "Ontario",
                "geometry": "POINT(-73.5673 45.5017)",
                "admin_lvl": 3,
                "name:en": "Ontario",
                "iso3166_1": None,
                "iso3166_2": "CA-ON",
                "alt_name": None,
                "alt_name:en": None,
            },
            {
                "osm_id": 3,
                "name": "Canada",
                "geometry": "POINT(-73.5673 45.5017)",
                "admin_lvl": 2,
                "name:en": "Canada",
                "iso3166_1": "CA",
                "iso3166_2": None,
                "alt_name": None,
                "alt_name:en": None,
            },
            {
                "osm_id": 5,
                "name": None,
                "geometry": None,
                "admin_lvl": 2,
                "name:en": "Canada",
                "iso3166_1": "CA",
                "iso3166_2": None,
                "alt_name": "Kanada",
                "alt_name:en": None,
            },
        ]
        db_session = MagicMock()
        db_session.query.return_value.filter.return_value.first.return_value = None
        save_to_database(data, db_session=db_session)
        self.assertEqual(db_session.add.call_count, 3)

        mock_session = MagicMock()
        mock_session.query.return_value.filter.return_value.first.return_value = (
            MagicMock()
        )
        save_to_database(data, db_session=mock_session)
        self.assertEqual(mock_session.add.call_count, 0)

    @patch(
        "main.fetch_subdivision_admin_levels",
        return_value=[2, 3],
    )
    def test_get_admin_levels(self, _):
        from main import get_locality_admin_levels

        country_code = "CA"
        result = get_locality_admin_levels(country_code, 1, 3)
        self.assertIsNotNone(result)
        self.assertEqual(result, [6, 8])

    @patch("main.bigquery")
    @patch("main.parse_request_parameters")
    @patch("main.fetch_country_admin_levels")
    @patch("main.fetch_data")
    @patch("main.save_to_database")
    @patch("main.fetch_subdivision_admin_levels")
    @patch.dict(
        "os.environ",
        {
            "FEEDS_DATABASE_URL": default_db_url,
            "GOOGLE_APPLICATION_CREDENTIALS": faker.file_path(),
        },
    )
    def test_reverse_geolocation_populate(
        self,
        mock_fetch_subdivision_admin_lvl,
        __,
        mock_fetch_data,
        mock_fetch_country_admin_lvl,
        mock_parse_req,
        mock_bigquery,
    ):
        mock_parse_req.return_value = ("CA", [2])
        mock_bigquery.Client.return_value = MagicMock()
        mock_fetch_subdivision_admin_lvl.return_value = [3]
        from main import reverse_geolocation_populate

        _, response_code = reverse_geolocation_populate(MagicMock())
        self.assertEqual(400, response_code)
        mock_fetch_country_admin_lvl.return_value = [2]
        mock_fetch_data.return_value = [
            {
                "osm_id": 1,
                "name": "Canada",
                "geometry": "POINT(-73.5673 45.5017)",
                "admin_lvl": 2,
                "name:en": "Canada",
                "iso3166_1": "CA",
                "iso3166_2": None,
            }
        ]
        _, response_code = reverse_geolocation_populate(MagicMock())
        self.assertEqual(200, response_code)
