from locust import HttpUser, TaskSet, task, between
import os

class gtfs_user(HttpUser):
    wait_time = between(5, 15)

    def on_start(self):
        # put the refresh token as github action secret
        # get the access token and pass it to the script
        self.client.headers = {'Authorization': os.environ.get('FEEDS_AUTH_TOKEN')}

    @task
    def feeds(self):
        self.client.get("/v1/feeds")

    @task
    def feed_byId(self):
        self.client.get("/v1/feeds/mdb-10")

    @task
    def gtfs_feeds(self):
        self.client.get("/v1/gtfs_feeds")

    @task
    def gtfs_feed_byId(self):
        self.client.get("/v1/gtfs_feeds/mdb-10")

    @task
    def gtfs_realtime_feeds(self):
        self.client.get("/v1/gtfs_rt_feeds")

    @task
    def gtfs_realtime_feed_byId(self):
        self.client.get("/v1/gtfs_rt_feeds/mdb-1852")

    @task
    def gtfs_feeds_datasets(self):
        self.client.get("/v1/gtfs_feeds/mdb-10/datasets")

    @task
    def gtfs_dataset(self):
        self.client.get("/v1/datasets/gtfs/mdb-10")
