# Unit test for dict_utils.py


def test_get_safe_value_with_field_present():
    from src.utils.dict_utils import get_safe_value

    dictionary = {"field": "value"}
    field_name = "field"
    default_value = "default"
    assert get_safe_value(dictionary, field_name, default_value) == "value"
    assert get_safe_value(dictionary, field_name, None) == "value"


def test_get_safe_value_with_field_not_present():
    from src.utils.dict_utils import get_safe_value

    dictionary = {"field": "value"}
    field_name = "not_field"
    default_value = "default"
    assert get_safe_value(dictionary, field_name, default_value) == "default"
    assert get_safe_value(dictionary, field_name) is None
