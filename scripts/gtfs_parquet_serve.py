#!/usr/bin/env python3
"""
gtfs-parquet-serve.py

Serves a directory of Parquet files over HTTP with CORS headers enabled,
so the GTFS Viewer POC (running on a different port) can load them directly
from the browser via DuckDB-WASM HTTP Range requests.

Usage:
    python3 scripts/gtfs_parquet_serve.py [--dir DIR] [--port PORT]

Options:
    --dir DIR    Directory to serve (default: ./gtfs_parquet_output)
    --port PORT  Port to listen on (default: 8888)

Example workflow:
    # 1. Convert a feed
    ./scripts/gtfs-to-parquet.sh --url "https://files.mobilitydatabase.org/mdb-10/..." --output /tmp/gtfs_out

    # 2. Serve it (in another terminal)
    python3 scripts/gtfs_parquet_serve.py --dir /tmp/gtfs_out

    # 3. Open the viewer and load:
    #    http://localhost:8888/metadata.json
"""

import argparse
import os
from http.server import HTTPServer, SimpleHTTPRequestHandler


class CORSRangeHandler(SimpleHTTPRequestHandler):
    """
    Static file handler with:
      - CORS headers (required for browser cross-origin DuckDB-WASM fetches)
      - HTTP 206 Partial Content (Range requests, required for DuckDB row-group skipping)
    """

    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, HEAD, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Range, Content-Type")
        self.send_header("Access-Control-Expose-Headers", "Content-Range, Accept-Ranges, Content-Length")
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()

    def do_GET(self):
        """Handle GET with Range support for Parquet files."""
        range_header = self.headers.get("Range")
        if range_header and self.path.endswith(".parquet"):
            self._serve_range(range_header)
        else:
            super().do_GET()

    def _serve_range(self, range_header: str):
        """Serve a byte range (RFC 7233) — enables DuckDB-WASM row-group skipping."""
        path = self.translate_path(self.path)
        try:
            file_size = os.path.getsize(path)
        except OSError:
            self.send_error(404, "File not found")
            return

        # Parse "bytes=START-END"
        try:
            unit, ranges = range_header.split("=", 1)
            assert unit.strip() == "bytes"
            start_str, end_str = ranges.split("-", 1)
            start = int(start_str) if start_str else 0
            end = int(end_str) if end_str else file_size - 1
        except Exception:
            self.send_error(416, "Requested Range Not Satisfiable")
            return

        end = min(end, file_size - 1)
        length = end - start + 1

        try:
            with open(path, "rb") as f:
                f.seek(start)
                data = f.read(length)
        except OSError:
            self.send_error(500, "Internal Server Error")
            return

        self.send_response(206)
        self.send_header("Content-Type", "application/octet-stream")
        self.send_header("Content-Length", str(length))
        self.send_header("Content-Range", f"bytes {start}-{end}/{file_size}")
        self.send_header("Accept-Ranges", "bytes")
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, fmt, *args):
        super().log_message(fmt, *args)


def main():
    parser = argparse.ArgumentParser(description="CORS-enabled static server for GTFS Parquet POC.")
    parser.add_argument("--dir", default="./gtfs_parquet_output", metavar="DIR",
                        help="Directory to serve (default: ./gtfs_parquet_output)")
    parser.add_argument("--port", type=int, default=8888, metavar="PORT",
                        help="Port to listen on (default: 8888)")
    args = parser.parse_args()

    serve_dir = os.path.abspath(args.dir)
    if not os.path.isdir(serve_dir):
        print(f"[ERROR] Directory not found: {serve_dir}")
        raise SystemExit(1)

    os.chdir(serve_dir)

    # List available tables from metadata.json if present
    meta_path = os.path.join(serve_dir, "metadata.json")
    if os.path.exists(meta_path):
        import json
        with open(meta_path) as f:
            meta = json.load(f)
        tables = meta.get("tables", {})
        print(f"\n📂 Serving: {serve_dir}")
        print(f"   {len(tables)} tables:")
        for name, info in tables.items():
            rows = info.get("row_count", "?")
            size = info.get("size_bytes", 0)
            size_str = f"{size/1e6:.2f} MB" if size >= 1e6 else f"{size/1e3:.1f} KB"
            print(f"   • {name:<20} {rows:>10,} rows   {size_str}")
    else:
        print(f"\n📂 Serving: {serve_dir}")

    print(f"\n🚀 Server running at: http://localhost:{args.port}")
    print(f"\n   Load in the GTFS Viewer (http://localhost:3000/en/gtfs-viewer):")
    print(f"   → http://localhost:{args.port}/metadata.json\n")

    server = HTTPServer(("0.0.0.0", args.port), CORSRangeHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[INFO] Server stopped.")


if __name__ == "__main__":
    main()
