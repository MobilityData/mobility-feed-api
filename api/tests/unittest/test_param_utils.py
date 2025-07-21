from shared.feed_filters.param_utils import normalize_str_parameter


def test_normalize_str_parameter():
    """
    Test the normalize_str_parameter function.
    """
    # Test with empty string
    assert normalize_str_parameter("downloaded_at__lte", downloaded_at__lte="  ") == {"downloaded_at__lte": None}
    # Test with non-empty string
    assert normalize_str_parameter("downloaded_at__lte", downloaded_at__lte=" 2021-01-01 ") == {
        "downloaded_at__lte": "2021-01-01"
    }
    # Test with non-str parameter
    assert normalize_str_parameter("counter", counter=1, downloaded_at__lte=" 2021-01-01 ") == {
        "counter": 1,
        "downloaded_at__lte": " 2021-01-01 ",
    }
    # Test with non-existing parameter
    assert normalize_str_parameter("counter", downloaded_at__lte=" 2021-01-01 ") == {
        "downloaded_at__lte": " 2021-01-01 "
    }
