import unittest

from gtfs import stop_txt_is_lat_lon_required


class TestStopTxtIsLatLogRequired(unittest.TestCase):
    def test_required_cases(self):
        self.assertTrue(stop_txt_is_lat_lon_required({"location_type": "0"}))
        self.assertTrue(stop_txt_is_lat_lon_required({"location_type": 0}))
        self.assertTrue(stop_txt_is_lat_lon_required({"location_type": "2"}))

    def test_not_required_cases(self):
        self.assertFalse(stop_txt_is_lat_lon_required({"location_type": "3"}))
        self.assertFalse(stop_txt_is_lat_lon_required({"location_type": 3}))
        self.assertFalse(stop_txt_is_lat_lon_required({"location_type": "4"}))
        self.assertFalse(stop_txt_is_lat_lon_required({"location_type": 4}))

    def test_missing_location_type(self):
        self.assertTrue(stop_txt_is_lat_lon_required({}))
        self.assertTrue(stop_txt_is_lat_lon_required({"other": "value"}))
