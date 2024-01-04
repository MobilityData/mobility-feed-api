from locust import HttpUser, TaskSet, task, between

class FeedUser(HttpUser):
    wait_time = between(1, 5)

    @task
    def feed(self):
        self.client.get("/")