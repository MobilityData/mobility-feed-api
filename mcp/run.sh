#!/usr/bin/env bash
cd "$(dirname "$0")/src"
exec "$(dirname "$0")/.venv/bin/python" main.py stdio
