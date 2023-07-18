# Builder Stage
FROM python:3.11 AS builder

WORKDIR /usr/src/app

RUN python3 -m venv /venv
ENV PATH="/venv/bin:$PATH"

RUN pip install --upgrade pip

COPY src .
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Service Stage
FROM python:3.11 AS service

WORKDIR /root/app/site-packages
COPY --from=builder /venv /venv
COPY --from=builder /usr/src/app .
ENV PATH=/venv/bin:$PATH

# Expose the port Uvicorn will listen on
EXPOSE 8080

# Run the Uvicorn server for the FastAPI application
CMD ["uvicorn", "feeds_gen.main:app", "--host", "0.0.0.0", "--port", "8080"]