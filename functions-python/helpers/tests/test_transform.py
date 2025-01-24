from transform import to_boolean


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
