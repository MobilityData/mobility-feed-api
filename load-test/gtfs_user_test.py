from locust import HttpUser, TaskSet, task, between

class gtfs_user(HttpUser):
    wait_time = between(5, 15)

    def on_start(self):
        self.client.headers = {'Authorization': 'Bearer eyJhbGciOiJSUzI1NiIsImtpZCI6IjdjZjdmODcyNzA5MWU0Yzc3YWE5OTVkYjYwNzQzYjdkZDJiYjcwYjUiLCJ0eXAiOiJKV1QifQ.eyJuYW1lIjoiSmluZ3NpIEx1IiwicGljdHVyZSI6Imh0dHBzOi8vbGgzLmdvb2dsZXVzZXJjb250ZW50LmNvbS9hL0FDZzhvY0ttOGRCUzJxMGNYZUV1MFdCM1pZdnRqODlHRmU5eXZ6RFhBSTNSZVJKVTZBPXM5Ni1jIiwiaXNzIjoiaHR0cHM6Ly9zZWN1cmV0b2tlbi5nb29nbGUuY29tL21vYmlsaXR5LWZlZWRzLXFhIiwiYXVkIjoibW9iaWxpdHktZmVlZHMtcWEiLCJhdXRoX3RpbWUiOjE3MDQ5MDI3NjQsInVzZXJfaWQiOiJOUnNhUDIwNjBLaGhEeVVvZlo1Z0VxMHJJeTMyIiwic3ViIjoiTlJzYVAyMDYwS2hoRHlVb2ZaNWdFcTBySXkzMiIsImlhdCI6MTcwNDkwNjQwMCwiZXhwIjoxNzA0OTEwMDAwLCJlbWFpbCI6ImppbmdzaUBtb2JpbGl0eWRhdGEub3JnIiwiZW1haWxfdmVyaWZpZWQiOnRydWUsImZpcmViYXNlIjp7ImlkZW50aXRpZXMiOnsiZ29vZ2xlLmNvbSI6WyIxMTQxOTkyMTk5MTkzODY0MDM0MTgiXSwiZW1haWwiOlsiamluZ3NpQG1vYmlsaXR5ZGF0YS5vcmciXX0sInNpZ25faW5fcHJvdmlkZXIiOiJnb29nbGUuY29tIn19.PpiNMV-HYHVSR8IXsbUVu6dyyiZQYR6DvyQSxQLJQPQVhlx0xVx2pScfENka98DbPUwKH-HwTjY-6mtP7pN2oxWp9hmzHNxFI-s8PP6nR27iUVdLO4N2F4hZJybcTJVZLPSdiGzGToOXGpJ2Vm3wJkuK0FVbEvOp07Lnlpx7SQCFvqaFxCaCLQ6k7xsu7JuW5aA7glFZXa6fmcYUrG7bq0A6kMDu6IcKTFlyl_75LmZqOMx47LvyXiOCW8yJ5-5gFWcIIi8gTXY4L9DtNGIzmuc2oC4IjHXs1p8TVD094b_o1BF2B5y0rrWIp9go75XYBg-yCTBQeXau4xGWv3quQw'}

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
        self.client.get("/v1/gtfs_rt_feeds/mdb-5")
    
    @task
    def gtfs_feeds_datasets(self):
        self.client.get("/v1/gtfs_feeds/mdb-10/datasets")
    @task
    def gtfs_dataset(self):
        self.client.get("/v1/datasets/gtfs/mdb-10")

   