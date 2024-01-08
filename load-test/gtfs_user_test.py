from locust import HttpUser, TaskSet, task, between

class gtfs_user(HttpUser):
    wait_time = between(1, 5)

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
        self.client.get("/v1/gtfs_rt_feeds/mdb-10")
    
    @task
    def gtfs_feeds_datasets(self):
        self.client.get("/v1/gtfs_feeds/mdb-10/datasets")
    @task
    def gtfs_dataset(self):
        self.client.get("/v1/datasets/gtfs/1")

   