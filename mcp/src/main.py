import os
import sys
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

from mcp.server.fastmcp import FastMCP
from tools.get_validation_results import get_validation_results_tool
from tools.query_gtfs import query_gtfs_tool
from tools.search_feeds import search_feeds_tool

port = int(os.getenv("PORT", "8080"))

# host and port must be passed to the constructor in mcp 1.x (not to run())
mcp = FastMCP("mobilitydatabase-mcp", host="0.0.0.0", port=port)
mcp.tool()(search_feeds_tool)
mcp.tool()(get_validation_results_tool)
mcp.tool()(query_gtfs_tool)

if __name__ == "__main__":
    transport = sys.argv[1] if len(sys.argv) > 1 else "sse"
    mcp.run(transport=transport)
