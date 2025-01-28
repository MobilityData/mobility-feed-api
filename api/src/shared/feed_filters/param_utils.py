def normalize_str_parameter(param_name, **kwargs):
    """
    Process a parameter in the kwargs dictionary, stripping it if it is a string and set empty to None.
    """
    if param_name in kwargs:
        value = kwargs[param_name]
        if isinstance(value, str):
            stripped_value = value.strip()
            kwargs[param_name] = None if stripped_value == "" else stripped_value
    return kwargs
