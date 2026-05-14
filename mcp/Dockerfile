FROM python:3.11-slim

WORKDIR /app

# Copy requirements first for layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy shared code from api (symlinks won't work in Docker, copy directly)
COPY api/src/shared /app/shared

# Copy MCP server source
COPY mcp/src/ /app/

# Set Python path so imports work
ENV PYTHONPATH=/app

EXPOSE 8080

CMD ["python", "main.py"]
