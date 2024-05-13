def get_safe_value(dictionary: dict, field_name, default_value=None):
    """
    Get a value from a dictionary safely, returning a default value if the field is not present
    @param dictionary: Dictionary to get the value from
    @param field_name: Name of the field to get
    @param default_value: Default value to return if the field is not present
    @return: Value of the field or the default value if the field is not present
    """
    return dictionary[field_name] if field_name in dictionary else default_value
