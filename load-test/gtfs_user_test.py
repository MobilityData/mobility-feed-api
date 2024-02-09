import sys
import json

from locust import HttpUser, TaskSet, task, between
import os

class gtfs_user(HttpUser):

    wait_time = between(.1, 1)

    def print_response(self, response, indent):
        print(indent, "Contents of response:")
        print(indent, "    text: ", response.text)
        print(indent, "    status code:", response.status_code)
        print(indent, "    headers:", response.headers)
        print(indent, "    URL:", response.url)
        print(indent, "    content:", response.content)

    def get_valid(self, endpoint, allow404=False):
        try:
            response = self.client.get(endpoint, allow_redirects=False)
            if allow404 and response.status_code == 404:
                return
            if response.status_code >= 300:
                print("Error in response.")
                self.print_response(response, "")
                sys.exit(1)
            json_response = response.json()  # Try to parse response content as JSON
        except json.JSONDecodeError:
            print("Error: Response not json.")
            self.print_response(response, "")
            sys.exit(1)

    def on_start(self):
        access_token = os.environ.get('FEEDS_AUTH_TOKEN')
        if access_token is None or access_token == "":
            print("Error: FEEDS_AUTH_TOKEN is not defined or empty")
            sys.exit(1)
        self.client.headers = {'Authorization': "Bearer " + access_token}

    @task
    def feeds(self):
        self.get_valid("/v1/feeds?limit=10")

    @task
    def feed_byId(self):
        # Allow error 404 since we are not sure the feed ID exists
        self.get_valid("/v1/feeds/mdb-10", allow404=True)

    @task
    def gtfs_feeds(self):
        self.get_valid("/v1/gtfs_feeds?limit=1000")

    @task
    def gtfs_feed_byId(self):
        self.get_valid("/v1/gtfs_feeds/mdb-10", allow404=True)

    @task
    def gtfs_realtime_feeds(self):
        self.get_valid("/v1/gtfs_rt_feeds?limit=1000")

    @task
    def gtfs_realtime_feed_byId(self):
        self.get_valid("/v1/gtfs_rt_feeds/mdb-1333", allow404=True)

    @task
    def gtfs_feeds_datasets(self):
        self.get_valid("/v1/gtfs_feeds/mdb-10/datasets", allow404=True)

    @task
    def gtfs_dataset(self):
        self.get_valid("/v1/datasets/gtfs/mdb-10-202402071805", allow404=True)