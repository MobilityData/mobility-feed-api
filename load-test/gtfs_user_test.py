from locust import HttpUser, TaskSet, task, between

class gtfs_user(HttpUser):
    wait_time = between(5, 15)

    def on_start(self):
        self.client.headers = {'Authorization': 'Bearer eyJhbGciOiJSUzI1NiIsImtpZCI6IjdjZjdmODcyNzA5MWU0Yzc3YWE5OTVkYjYwNzQzYjdkZDJiYjcwYjUiLCJ0eXAiOiJKV1QifQ.eyJuYW1lIjoiSmluZ3NpIEx1IiwicGljdHVyZSI6Imh0dHBzOi8vbGgzLmdvb2dsZXVzZXJjb250ZW50LmNvbS9hL0FDZzhvY0ttOGRCUzJxMGNYZUV1MFdCM1pZdnRqODlHRmU5eXZ6RFhBSTNSZVJKVTZBPXM5Ni1jIiwiaXNzIjoiaHR0cHM6Ly9zZWN1cmV0b2tlbi5nb29nbGUuY29tL21vYmlsaXR5LWZlZWRzLXFhIiwiYXVkIjoibW9iaWxpdHktZmVlZHMtcWEiLCJhdXRoX3RpbWUiOjE3MDQ5MDI3NjQsInVzZXJfaWQiOiJOUnNhUDIwNjBLaGhEeVVvZlo1Z0VxMHJJeTMyIiwic3ViIjoiTlJzYVAyMDYwS2hoRHlVb2ZaNWdFcTBySXkzMiIsImlhdCI6MTcwNDkxNTE2NiwiZXhwIjoxNzA0OTE4NzY2LCJlbWFpbCI6ImppbmdzaUBtb2JpbGl0eWRhdGEub3JnIiwiZW1haWxfdmVyaWZpZWQiOnRydWUsImZpcmViYXNlIjp7ImlkZW50aXRpZXMiOnsiZ29vZ2xlLmNvbSI6WyIxMTQxOTkyMTk5MTkzODY0MDM0MTgiXSwiZW1haWwiOlsiamluZ3NpQG1vYmlsaXR5ZGF0YS5vcmciXX0sInNpZ25faW5fcHJvdmlkZXIiOiJnb29nbGUuY29tIn19.E5O9MZLgFJT8ZvrCFV6JAhzteXTsbgd-DOiMEP5GJzDy0-B6JYLXKbLmhFWzOwvo9A2v0GhWvdmnpHI4NfUYoSFiGlD2N1OqUHKc4v7rbPh2a28caJzdSVXf82xoAwsuSrzMSi7-2LQLrPlRiJdvNwFgSJRYU7CG9Hbxl5UnqqHs1RSLSxrSi6Tv8LOn49xp47Z87qVhha6QJiDkZqg-AuL2PP6nLUeZBmKizsltqzltkKlaj1QymWcucmPv0jGy5_bX0DhYbGl9YkeMZayvQ2iKGi6MSwLEgquwt9q6t5X35npawK0zYemnZO6o5emo5s2up8suUPAmWz9iWDoZqw'}

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

    # @task
    # def gtfs_realtime_feed_byId(self):
    #     self.client.get("/v1/gtfs_rt_feeds/mdb-5")
    
    @task
    def gtfs_feeds_datasets(self):
        self.client.get("/v1/gtfs_feeds/mdb-10/datasets")
    @task
    def gtfs_dataset(self):
        self.client.get("/v1/datasets/gtfs/mdb-10")

   