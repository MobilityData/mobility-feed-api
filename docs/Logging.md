# How to use the logging framework
Al our services runs in GCP. To get the best out of the log traces, we should use a common pattern acrosss all functions and services. This documents describes how to use the shared logging functions.

## General guidances

- Parameters instead of string interpolation

Use log parameters instead of string interpolation. String interpolation always creates a string concatenation even if the log is not send due to the environment log level settings.
Example:
```
# Avoid string interpolation.
logging.info(f"Total of feeds: {total}")

# Use this optimized version
logging.info(f"Total of feeds: %s", total)
```

- Use logging levels properly
By default the logging level the functions are set to INFO. 
Avoid to log unnecessary or repetitive information in INFO level. It might make sense to log every single message in a loop; this can be overwhelming in production.
Use info, warning and debug levels wisely.

- Logging a dictionary or json
When logging a dictionary or JSON use a field named "message" to be able to easily spot the record on the GCP Log Explorer. Example:
```python
dict = {
    "message": "This will be visible in the log explorer without expanding the record",
    "single_field": "my value",
    "another_dictionary": {
        "internal": "value1"
    }
} 
logging.info(dict)
```

- Log main function reponse
This is necessary in cases that we would like to get the response in the logs as GCP doesn't log the responses by default.

## API implementation
The API logging is based in a custom GCP Logging filter. This is necessary as the GCP internal mechanism is based on Flask, not fully compatible with our FastApi in terms of to stackdriver(cloud logging) compatibility.

The logging context is already inittialized when the application starts.
To log messages use the standard logging library. Example:
```python
import logging

logging.info("This message is awesome")
```

## Python functions

### Logging level
The logging level is by default [INFO](https://github.com/MobilityData/mobility-feed-api/blob/a857ca794b5991aa8b6e7ecedb197914ae1eca04/api/src/shared/common/logging_utils.py#L5).
The logging level can be changed at runtime by setting the function variable `LOGGING_LEVEL` to the desired value, example DEBUG

### Initialize logging
 On the main file initialize the logging client by calling the following function:
```
init_logger()
```
The [init_logger](https://github.com/MobilityData/mobility-feed-api/blob/a857ca794b5991aa8b6e7ecedb197914ae1eca04/functions-python/helpers/logger.py#L49) will set the right logging level and initialize the GCP cloud client if it's not running in local environment. 

### Logging messages
There are two ways to log messages:

 1. Logs messages without specific stable_id.

```
 import logging

 logging.info("Total feeds: %s", total_feeds)

```

2. Using a stable id
```
 import logging

 logger = logging.get_logger("my logger name", "mdb-001")
 logging.info("Total feeds: %s", total_feeds) # This will output the following format for total_feeds equals to 10: [mdb-001] Total feeds: 10
```
