import unittest
from enum import Enum

import pandas as pd

from transform import (
    to_boolean,
    get_nested_value,
    to_float,
    get_safe_value_from_csv,
    get_safe_float_from_csv,
    get_safe_int_from_csv,
    sanitize_value,
    to_enum,
)


def test_to_boolean():
    assert to_boolean(True) is True
    assert to_boolean(False) is False
    assert to_boolean("true") is True
    assert to_boolean("True") is True
    assert to_boolean("1") is True
    assert to_boolean("yes") is True
    assert to_boolean("y") is True
    assert to_boolean("false") is False
    assert to_boolean("False") is False
    assert to_boolean("0") is False
    assert to_boolean("no") is False
    assert to_boolean("n") is False
    assert to_boolean(1) is True
    assert to_boolean(0) is False
    assert to_boolean(None) is False
    assert to_boolean([]) is False
    assert to_boolean({}) is False


def test_get_nested_value():
    # Test case 1: Nested dictionary with string value
    assert get_nested_value({"a": {"b": {"c": "d"}}}, ["a", "b", "c"]) == "d"

    # Test case 2: Nested dictionary with integer value
    assert get_nested_value({"a": {"b": {"c": 1}}}, ["a", "b", "c"]) == 1

    # Test case 3: Nested dictionary with float value
    assert get_nested_value({"a": {"b": {"c": 1.5}}}, ["a", "b", "c"]) == 1.5

    # Test case 4: Nested dictionary with boolean value
    assert get_nested_value({"a": {"b": {"c": True}}}, ["a", "b", "c"]) is True

    # Test case 5: Nested dictionary with string value that needs trimming
    assert get_nested_value({"a": {"b": {"c": "  d  "}}}, ["a", "b", "c"]) == "d"

    # Test case 6: Key not found in the dictionary
    assert get_nested_value({"a": {"b": {"c": "d"}}}, ["a", "b", "x"]) is None
    assert (
        get_nested_value({"a": {"b": {"c": "d"}}}, ["a", "b", "x"], "default")
        == "default"
    )
    assert get_nested_value({"a": {"b": {"c": "d"}}}, ["a", "b", "x"], []) == []

    # Test case 7: Intermediate key not found in the dictionary
    assert get_nested_value({"a": {"b": {"c": "d"}}}, ["a", "x", "c"]) is None
    assert (
        get_nested_value({"a": {"b": {"c": "d"}}}, ["a", "x", "c"], "default")
        == "default"
    )
    assert get_nested_value({"a": {"b": {"c": "d"}}}, ["a", "x", "c"], []) == []

    # Test case 8: Empty keys list
    assert get_nested_value({"a": {"b": {"c": "d"}}}, []) is None
    assert get_nested_value({"a": {"b": {"c": "d"}}}, [], {}) == {}

    # Test case 9: Non-dictionary data
    assert get_nested_value("not a dict", ["a", "b", "c"]) is None
    assert get_nested_value("not a dict", ["a", "b", "c"], []) == []


class TestToFloat(unittest.TestCase):
    def test_valid_float(self):
        self.assertEqual(to_float("3.14"), 3.14)
        self.assertEqual(to_float(2.5), 2.5)
        self.assertEqual(to_float("0"), 0.0)
        self.assertEqual(to_float(0), 0.0)

    def test_invalid_float(self):
        self.assertIsNone(to_float("abc"))
        self.assertIsNone(to_float(None))
        self.assertIsNone(to_float(""))

    def test_default_value(self):
        self.assertEqual(to_float("abc", default_value=1.23), 1.23)
        self.assertEqual(to_float(None, default_value=4.56), 4.56)
        self.assertEqual(to_float("", default_value=7.89), 7.89)


class TestGetSafeValue(unittest.TestCase):
    def test_valid_value(self):
        row = {"name": " Alice "}
        self.assertEqual(get_safe_value_from_csv(row, "name"), "Alice")

    def test_missing_column(self):
        row = {"age": 30}
        self.assertIsNone(get_safe_value_from_csv(row, "name"))

    def test_empty_string(self):
        row = {"name": "   "}
        self.assertIsNone(get_safe_value_from_csv(row, "name"))

    def test_nan_value(self):
        row = {"name": pd.NA}
        self.assertIsNone(get_safe_value_from_csv(row, "name"))
        row = {"name": float("nan")}
        self.assertIsNone(get_safe_value_from_csv(row, "name"))

    def test_default_value(self):
        row = {"name": ""}
        self.assertEqual(
            get_safe_value_from_csv(row, "name", default_value="default"), "default"
        )


class TestGetSafeFloat(unittest.TestCase):
    def test_valid_float(self):
        row = {"value": "3.14"}
        self.assertEqual(get_safe_float_from_csv(row, "value"), 3.14)
        row = {"value": 2.5}
        self.assertEqual(get_safe_float_from_csv(row, "value"), 2.5)
        row = {"value": "0"}
        self.assertEqual(get_safe_float_from_csv(row, "value"), 0.0)
        row = {"value": 0}
        self.assertEqual(get_safe_float_from_csv(row, "value"), 0.0)

    def test_missing_column(self):
        row = {"other": 1.23}
        self.assertIsNone(get_safe_float_from_csv(row, "value"))

    def test_empty_string(self):
        row = {"value": "   "}
        self.assertIsNone(get_safe_float_from_csv(row, "value"))

    def test_nan_value(self):
        row = {"value": pd.NA}
        self.assertIsNone(get_safe_float_from_csv(row, "value"))
        row = {"value": float("nan")}
        self.assertIsNone(get_safe_float_from_csv(row, "value"))

    def test_invalid_float(self):
        row = {"value": "abc"}
        self.assertIsNone(get_safe_float_from_csv(row, "value"))
        row = {"value": None}
        self.assertIsNone(get_safe_float_from_csv(row, "value"))

    def test_default_value(self):
        row = {"value": ""}
        self.assertEqual(
            get_safe_float_from_csv(row, "value", default_value=1.23), 1.23
        )
        row = {"value": "abc"}
        self.assertEqual(
            get_safe_float_from_csv(row, "value", default_value=4.56), 4.56
        )
        row = {"value": None}
        self.assertEqual(
            get_safe_float_from_csv(row, "value", default_value=7.89), 7.89
        )


class TestGetSafeInt(unittest.TestCase):
    def test_valid_int(self):
        row = {"value": "42"}
        self.assertEqual(get_safe_int_from_csv(row, "value"), 42)

    def test_invalid_int(self):
        row = {"value": "abc"}
        self.assertIsNone(get_safe_int_from_csv(row, "value"))

    def test_missing_key(self):
        row = {}
        self.assertIsNone(get_safe_int_from_csv(row, "value"))

    def test_empty_string(self):
        row = {"value": ""}
        self.assertIsNone(get_safe_int_from_csv(row, "value"))


class TestSanitizeValue(unittest.TestCase):
    def test_simple_strings(self):
        self.assertEqual(sanitize_value(" Alice "), "Alice")
        self.assertIsNone(sanitize_value("   "))
        # Empty string short-circuits to itself per current implementation
        self.assertEqual(sanitize_value(""), "")

    def test_preserve_falsy_non_strings(self):
        self.assertIsNone(sanitize_value(None))
        self.assertEqual(sanitize_value(0), 0)
        self.assertFalse(sanitize_value(False))
        self.assertEqual(sanitize_value([]), [])
        self.assertEqual(sanitize_value({}), {})

    def test_dict_sanitization(self):
        data = {
            "name": " Bob ",
            "age": 30,
            "empty": "  ",
            "nested": {"note": "  hi  ", "blank": "   "},
        }
        expected = {
            "name": "Bob",
            "age": 30,
            "empty": None,
            "nested": {"note": "hi", "blank": None},
        }
        self.assertEqual(sanitize_value(data), expected)

    def test_list_sanitization(self):
        data = [" a ", "b", "", 1, True, "  "]
        expected = ["a", "b", "", 1, True, None]
        self.assertEqual(sanitize_value(data), expected)

    def test_nested_structures(self):
        data = {
            "user": {
                "name": " Alice ",
                "tags": [" a ", "", "b"],
                "meta": {"note": "  ", "ok": True},
            }
        }
        expected = {
            "user": {
                "name": "Alice",
                "tags": ["a", "", "b"],
                "meta": {"note": None, "ok": True},
            }
        }
        self.assertEqual(sanitize_value(data), expected)


class TestToEnum(unittest.TestCase):
    class Color(Enum):
        RED = "RED"
        BLUE = "BLUE"
        GREEN = "GREEN"

    def test_passthrough_when_already_enum(self):
        self.assertIs(
            to_enum(self.Color.RED, enum_class=self.Color, default_value=None),
            self.Color.RED,
        )

    def test_convert_from_string_value(self):
        self.assertEqual(
            to_enum("RED", enum_class=self.Color, default_value=None), self.Color.RED
        )
        self.assertEqual(
            to_enum("GREEN", enum_class=self.Color, default_value=None),
            self.Color.GREEN,
        )

    def test_invalid_value_returns_none(self):
        self.assertIsNone(to_enum("PURPLE", enum_class=self.Color))
        self.assertIsNone(to_enum(123, enum_class=self.Color))
        # whitespace or different casing won't match since implementation doesn't trim/lower
        self.assertIsNone(to_enum(" red ", enum_class=self.Color))
        self.assertIsNone(to_enum("red", enum_class=self.Color))

    def test_invalid_value_with_default(self):
        self.assertEqual(
            to_enum("PURPLE", enum_class=self.Color, default_value=self.Color.BLUE),
            self.Color.BLUE,
        )
        self.assertEqual(
            to_enum(None, enum_class=self.Color, default_value="fallback"),
            "fallback",
        )

    def test_missing_enum_class_returns_default(self):
        # When enum_class is None, conversion fails and default is returned
        self.assertIsNone(to_enum("RED"))
        self.assertEqual(to_enum("RED", enum_class=None, default_value=0), 0)
