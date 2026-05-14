# MobilityDatabase MCP Server

An [MCP (Model Context Protocol)](https://modelcontextprotocol.io) server that exposes MobilityDatabase's GTFS/GBFS data as AI-accessible tools. Connect it to Claude Desktop (or any MCP client) to query feeds, search by location, and explore transit data conversationally.

## What's been implemented

**Step 1 — Smart Search (`search_feeds` tool)**

Searches the Mobility Database using PostgreSQL full-text search against the `FeedSearch` materialized view. Returns rich location and metadata context so the AI can disambiguate results — e.g. distinguishing "Montréal, QC, Canada" from "Montréal-du-Gers, France."

| Parameter | Type | Default | Description |
|---|---|---|---|
| `search_query` | string | — | Free-text search (e.g. `"Montreal"`, `"STM"`, `"Japan"`) |
| `data_type` | string | `gtfs` | `gtfs`, `gtfs_rt`, or `gbfs` |
| `status` | string | none | `active`, `inactive`, or `deprecated` |
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

> Use `SCHEMA` first to discover available tables, then write SQL to answer your question. Only `SELECT` queries are allowed.

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

## Questions that feel like magic

### Single-tool deep dives

Once Claude can query raw GTFS tables directly, you can ask things that would be painful to answer by hand:

> *"Which route in the STM network serves the most unique stops?"*
> *"Are there any trips that depart after midnight? List them with their headsigns."*
> *"What percentage of stops in the Tokyo feed have wheelchair boarding info?"*
> *"Which agency in the feed operates the most distinct routes?"*
> *"Find all stops within 500m of each other that belong to different routes — potential transfer point opportunities."*
> *"How many trips run on weekdays vs weekends for each route?"*
> *"What's the average dwell time between consecutive stops on the busiest route?"*
> *"Show me routes that have no shapes defined — they'll render as straight lines on a map."*
> *"Which stops appear in stop_times but are missing from stops.txt?"*
> *"What's the earliest first departure and latest last departure across all routes?"*

These are the kinds of questions that become conversational once an AI can inspect `trips.txt`, `stop_times.txt`, `routes.txt`, `calendar.txt`, `shapes.txt`, and the rest through SQL.

### Cross-tool investigations

The real power emerges when the tools chain together. Claude will figure out the sequence — you just ask the question.

> *"Find all active GTFS feeds in California, then tell me which ones have validation errors and what those errors are."*
> → `search_feeds` (California) → `get_validation_results` for each → summary report

> *"I'm traveling in Tokyo next month — which feed covers the Tokyo Metro, does it have any errors that could affect trip planning, and what routes serve Shinjuku station?"*
> → `search_feeds` (Tokyo Metro) → `get_validation_results` → `query_gtfs` (stops near Shinjuku)

> *"Compare the data quality of the top 5 transit agencies in Canada — who has the cleanest feed?"*
> → `search_feeds` (Canada, limit=5) → `get_validation_results` for each → ranked comparison by error count

> *"The STM feed has a `stop_times_with_only_arrival_time` warning — can you show me which trips are affected and what the schedule looks like for those stops?"*
> → `get_validation_results` (mdb-956, warnings) → `query_gtfs` (SELECT from stop_times WHERE arrival_time IS NOT NULL AND departure_time IS NULL)

> *"Are there any official feeds in Europe with zero validation errors? If so, what GTFS features do they support?"*
> → `search_feeds` (Europe, is_official=true) → `get_validation_results` for each → filter zero errors → list features

> *"Find the feed for the Paris Métro, check if it has wheelchair accessibility data, and count what fraction of stops actually have it filled in."*
> → `search_feeds` (Paris Métro) → `get_validation_results` (check features list) → `query_gtfs` (SELECT COUNT(*) by wheelchair_boarding value)

> *"Which city in Japan has the most comprehensive GTFS feed — most routes, most stops, fewest errors?"*
> → `search_feeds` (Japan) → `get_validation_results` for each → `query_gtfs` SCHEMA on top candidates → compare route/stop counts

## Architecture

```
Claude Desktop (or any MCP client)
        │  MCP Protocol (stdio locally, SSE when deployed)
        ▼
  MCP Server (Python)
        ├──► SQLAlchemy → PostgreSQL (feed metadata, search, validation reports)
        └──► DuckDB (in-memory) ← GTFS CSVs fetched from GCS public URLs
```

The server connects **directly to the database** — it does not call the public Feed API. It reuses the shared database models and query logic from `api/src/shared/` (linked via symlinks in `src/shared/`).

## Deployment

Terraform infrastructure is in `infra/mcp/`. The module creates a Cloud Run service (`mcp-server-{env}`) and is wired into the root `infra/main.tf`. Deploy by building and pushing the Docker image to Artifact Registry, then running terraform:

```bash
# Build and push (from repo root)
docker build -f mcp/Dockerfile -t {region}-docker.pkg.dev/{project}/{repo}/mcp-server:{version} .
docker push {region}-docker.pkg.dev/{project}/{repo}/mcp-server:{version}

# Apply terraform
cd infra
terraform apply -var="mcp_image_version={version}"
```
