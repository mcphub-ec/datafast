"""Datafast MCP Server — configuration module."""

import logging
import os
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='{"time":"%(asctime)s", "level":"%(levelname)s", "name":"%(name)s", "message":"%(message)s"}',
)
logger = logging.getLogger("datafast-mcp")

DATAFAST_BASE_URL: str = os.environ.get("DATAFAST_BASE_URL", "https://eu-prod.oppwa.com")
HTTP_TIMEOUT: float = 30.0
