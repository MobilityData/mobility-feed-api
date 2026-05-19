FROM python:3.11-slim

WORKDIR /app

# Copy requirements first for layer caching
COPY mcp/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy shared code from api (symlinks won't work in Docker, copy directly)
COPY api/src/shared /app/shared

# Copy MCP server source
COPY mcp/src/ /app/

# Set Python path so imports work
ENV PYTHONPATH=/app

# Pre-install DuckDB extensions so they're available offline at runtime
RUN python -c "import duckdb; con = duckdb.connect(); con.install_extension('httpfs'); con.close()"

EXPOSE 8080

CMD ["python", "main.py"]
