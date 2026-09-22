"""
Datafast MCP Server
===================
MCP server for Datafast Ecuador payment gateway (ACI Worldwide / Oppwa engine).
"""

from config import DATAFAST_BASE_URL, HTTP_TIMEOUT, logger  # noqa: F401
from app import mcp  # noqa: F401
from _http import _auth_headers, _get, _post_form, _delete_form, _json, _is_approved  # noqa: F401

# All 7 tools (form-encoded POST + fiscal engine — incompatible with ToolSpec)
import tools.custom  # noqa: F401, E402

__all__ = ["mcp", "_get", "_post_form", "_delete_form", "_json", "logger"]
