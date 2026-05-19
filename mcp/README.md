# MobilityDatabase MCP Server

An [MCP (Model Context Protocol)](https://modelcontextprotocol.io) server that exposes MobilityDatabase's GTFS/GBFS data as AI-accessible tools. Connect it to Claude Desktop (or any MCP client) to query feeds, search by location, and explore transit data conversationally.

## What's been implemented

**Step 1 — Smart Search (`search_feeds` tool)**

Searches the Mobility Database using PostgreSQL full-text search against the `FeedSearch` materialized view. Returns rich location and metadata context so the AI can disambiguate results — e.g. distinguishing "Montréal, QC, Canada" from "Montréal-du-Gers, France."

| Parameter | Type | Default | Description |
|---|---|---|---|
| `search_query` | string | — | Free-text search (e.g. `"Montreal"`, `"STM"`, `"Japan"`) |
| `data_type` | string | `gtfs` | `gtfs`, `gtfs_rt`, or `gbfs` |
| `is_official` | boolean | none | Filter to official feeds only |
| `limit` | integer | `30` | Max results |

**Step 2 — Validation Results (`get_validation_results` tool)**

Returns per-feed validation results enriched with:
- Rule documentation (description + link to official validator docs)
- Sample rows from the affected GTFS file (fetched from GCS public URLs)
- Full validation summary (error/warning/info counts)

| Parameter | Type | Default | Description |
|---|---|---|---|
| `feed_id` | string | — | Mobility Database feed ID (e.g. `mdb-1210`) |
| `severity_filter` | string | `all` | `all`, `errors`, `warnings`, or `info` |

> Rule documentation is fetched from `https://gtfs-validator.mobilitydata.org/rules.json` on first use and cached in memory for 24 hours. No manual refresh needed.

**Step 3 — GTFS SQL Query Engine (`query_gtfs` tool)**

Loads a feed's extracted GTFS files into an in-memory DuckDB database and executes SQL queries against them. Results are cached per feed for 10 minutes so follow-up queries are instant.

| Parameter | Type | Default | Description |
|---|---|---|---|
| `feed_id` | string | — | Mobility Database feed ID (e.g. `mdb-1210`) |
| `query` | string | — | `SCHEMA` to list tables/columns, or any SQL `SELECT` statement |
| `files` | list[string] | — | GTFS files to load (e.g. `["stops", "routes"]`). **Required for SELECT queries.** Omit for SCHEMA queries to discover all available tables. |

> Use `SCHEMA` first to discover available tables, then write SQL to answer your question. Only `SELECT` queries are allowed. If some GTFS files are unavailable (e.g. not extracted), they are reported in `failed_files` rather than silently skipped.

## Running locally

### Prerequisites

- Python 3.11+
- Access to the MobilityDatabase PostgreSQL instance (or a local copy)

### Setup

```bash
# 1. From the repo root, link shared code into mcp/src/shared/
./scripts/function-python-setup.sh --mcp

# 2. Install dependencies
cd mcp
pip install -r requirements.txt

# 3. Configure environment
cp .env.rename_me .env
# Edit .env and set FEEDS_DATABASE_URL to your database connection string

# 4. Start the server
cd src
PYTHONPATH=. python main.py stdio
```

### Environment variables

| Variable | Description | Example |
|---|---|---|
| `FEEDS_DATABASE_URL` | PostgreSQL connection string for Mobility Database data | `postgresql://user:pass@host:5432/feeds` |
| `DATASETS_BUCKET_URL` | Base URL for GCS-hosted extracted GTFS files. Used to fetch sample rows when enriching validation notices. No auth required — public bucket. | `https://storage.googleapis.com/mobilitydata-datasets-prod` |
| `FEED_CACHE_TTL_SECONDS` | How long to cache loaded GTFS datasets in memory (seconds) | `600` |
| `PORT` | Server port for SSE transport | `8080` |

```bash
DATASETS_BUCKET_URL=https://storage.googleapis.com/mobilitydata-datasets-prod
```

### Running tests

```bash
cd mcp
python -m pytest tests/ -v
```

### Testing with the MCP Inspector

Start the server locally, then in a separate terminal launch the [MCP Inspector](https://github.com/modelcontextprotocol/inspector) to interactively test tools:

```bash
# 1. Start the server (SSE mode, default)
cd mcp/src
PYTHONPATH=. python main.py

# 2. In another terminal, launch the inspector
DANGEROUSLY_OMIT_AUTH=true npx @modelcontextprotocol/inspector
```

Open the URL printed by the inspector, enter `http://localhost:8080/sse` as the server URL, and you can list and call tools directly and test them like any API. This is a great way to iterate on tool outputs and debug without needing to connect a full MCP client.

## Running with Docker

The Dockerfile build context is the **repo root** (needed to copy shared code):

```bash
# Build
docker build -f mcp/Dockerfile -t mcp-server .

# Run
docker run -p 8080:8080 \
  -e FEEDS_DATABASE_URL="postgresql://user:pass@host:5432/feeds" \
  -e DATASETS_BUCKET_URL="https://storage.googleapis.com/mobilitydata-datasets-prod" \
  mcp-server
```

## Connecting to Claude Desktop

Add the following to your Claude Desktop config (`~/Library/Application Support/Claude/claude_desktop_config.json` on macOS).

Replace `/path/to/mobility-feed-api` with your actual repo path, and update the environment values as needed:

```json
{
  "mcpServers": {
    "mobilitydatabase": {
      "command": "python",
      "args": ["main.py", "stdio"],
      "cwd": "/path/to/mobility-feed-api/mcp/src",
      "env": {
        "PYTHONPATH": "/path/to/mobility-feed-api/mcp/src",
        "FEEDS_DATABASE_URL": "postgresql://user:pass@localhost:5432/feeds",
        "DATASETS_BUCKET_URL": "https://storage.googleapis.com/mobilitydata-datasets-prod",
        "FEED_CACHE_TTL_SECONDS": "600"
      }
    }
  }
}
```

> If you use a virtual environment, point `command` to the venv's Python binary (e.g. `/path/to/mobility-feed-api/mcp/.venv/bin/python`).

Restart Claude Desktop. You should see the `search_feeds`, `get_validation_results`, and `query_gtfs` tools available. Try:
> *"Find active GTFS feeds in Montreal"*
> *"Search for STM feeds"*
> *"Show me official feeds in Japan"*
> *"What validation errors does mdb-1210 have?"*
> *"Show me the errors in the STM feed"*


## Deployment

Terraform infrastructure is in `infra/mcp/`. The module creates a Cloud Run service (`mcp-server-{env}`) and is wired into the root `infra/main.tf`. Deploy by building and pushing the Docker image to Artifact Registry, then running terraform deployment.
