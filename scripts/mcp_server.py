"""Launcher for the MCP server that works from any folder:
    claude mcp add viral-scout -s user -- python D:/repo/viral-scout/scripts/mcp_server.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from viral_scout import config  # noqa: E402

config.load_env()
from viral_scout.mcp_server import main  # noqa: E402

main()
