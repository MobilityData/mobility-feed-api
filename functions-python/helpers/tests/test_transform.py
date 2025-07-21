from transform import to_boolean, get_nested_value


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
    assert to_boolean(1) is False
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
