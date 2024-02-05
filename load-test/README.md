# API load tests

This script `gtfs_user_test.py`, defines a set of tasks for load testing the GTFS API. Each task represents a different API endpoint that will be hit during the load test.

## Setup

### Install Locust

Locust is a Python library, so you can install it with pip. Run the following command in your terminal:

```
pip install locust
```

## Start a Load Test

To start a load test on QA environment, run the following command in your terminal:
```
locust -f gtfs_user_test.py --host=https://api-qa.mobilitydatabase.org -u 100 -r 10
```
The -u option specifies the total number of users to simulate, and the -r option specifies the hatch rate (number of users to start per second)

### Tasks

### `feeds`

This task hits the `/v1/feeds` endpoint, which returns a list of all feeds.

### `feed_byId`

This task hits the `/v1/feeds/mdb-10` endpoint, which returns the feed with the ID `mdb-10`.

### `gtfs_feeds`

This task hits the `/v1/gtfs_feeds` endpoint, which returns a list of all GTFS feeds.

### `gtfs_feed_byId`

This task hits the `/v1/gtfs_feeds/mdb-10` endpoint, which returns the GTFS feed with the ID `mdb-10`.

### `gtfs_realtime_feeds`

This task hits the `/v1/gtfs_rt_feeds` endpoint, which returns a list of all GTFS realtime feeds.

### `gtfs_realtime_feed_byId`

This task hits the `/v1/gtfs_rt_feeds/mdb-1852` endpoint, which returns the GTFS realtime feed with the ID `mdb-1852`.

### `gtfs_feeds_datasets`

This task hits the `/v1/gtfs_feeds/mdb-10/datasets` endpoint, which returns a list of all datasets for the GTFS feed with the ID `mdb-10`.

### `gtfs_dataset`

This task hits the `/v1/datasets/gtfs/mdb-10` endpoint, which returns the dataset for the GTFS feed with the ID `mdb-10`.

## Wait Time

The `wait_time` is set to a random duration between 5 and 15 seconds. This means that after each task is executed, the script will wait for a duration between 5 and 15 seconds before executing the next task.

## Authorization

The `on_start` method sets the 'Authorization' header to the value of the `FEEDS_AUTH_TOKEN` environment variable. This means that all requests sent during the load test will include this authorization token.

