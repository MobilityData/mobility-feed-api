#
# MobilityData 2023
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

# Builder Stage
FROM --platform=$BUILDPLATFORM python:3.9 AS builder

WORKDIR /usr/src/app

RUN python3 -m venv /venv
ENV PATH="/venv/bin:$PATH"

RUN pip install --upgrade pip

COPY src .
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Service Stage
FROM --platform=$TARGETPLATFORM python:3.9 AS service

WORKDIR /root/app/site-packages
COPY --from=builder /venv /venv
COPY --from=builder /usr/src/app .
ENV PATH=/venv/bin:$PATH

# Set the environment variable for the port or use default (8080)
ENV PORT=${PORT:-8080}

# Expose the port Uvicorn will listen on
EXPOSE $PORT

# Run the Uvicorn server for the FastAPI application
CMD ["uvicorn", "feeds_gen.main:app", "--host", "0.0.0.0", "--port", "8080"]