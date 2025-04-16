# Code to be able to debug locally without affecting the runtime cloud function

#
# Requirements:
# - Google Cloud SDK installed
# - Make sure to have the following environment variables set in your .env.local file
# - Local database in running state

# Usage:
# - python tasks_executor/main_local_debug.py
# - This can be easily run/debug in a local IDE like PyCharm or VSCode

import flask
from flask.testing import EnvironBuilder

from main import tasks_executor

# Create a Flask app instance
app = flask.Flask(__name__)

if __name__ == "__main__":
    # Create a mock payload
    payload = {"task": "list_tasks"}

    # Push the application context
    with app.app_context():
        # Build a mock request environment
        builder = EnvironBuilder(app=app, method="POST", path="/", json=payload)
        env = builder.get_environ()

        # Create a Flask request object
        mock_request = flask.Request(env)

        # Call the tasks_executor function with the mock request
        response = tasks_executor(mock_request)

        # If the response is a tuple, extract the response object
        if isinstance(response, tuple):
            response, _ = response

        # Print the response data
        print(response.get_data(as_text=True))
