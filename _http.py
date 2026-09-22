"""
Datafast HTTP client module.

Datafast uses application/x-www-form-urlencoded for POST/DELETE (not JSON).
Provides _get, _post_form, _delete_form, and _parse_response.
"""

from __future__ import annotations

import json
import os
from typing import Any

import httpx

from config import DATAFAST_BASE_URL, HTTP_TIMEOUT, logger


def _resolve_bearer() -> str:
    resolved = os.environ.get("DATAFAST_BEARER_TOKEN", "")
    if not resolved:
        raise ValueError("DATAFAST_BEARER_TOKEN env var is required. Configure it in your .env file.")
    return resolved


def _auth_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {_resolve_bearer()}"}


def _parse_response(resp: httpx.Response) -> dict | list | str:
    if resp.status_code >= 400:
        return {"error": True, "status_code": resp.status_code, "detail": resp.text}
    if not resp.text.strip():
        return {"ok": True, "status_code": resp.status_code}
    try:
        return resp.json()
    except Exception:
        return resp.text


async def _get(path: str, *, params: dict[str, Any] | None = None) -> dict | list | str:
    url = f"{DATAFAST_BASE_URL}{path}"
    if params:
        params = {k: v for k, v in params.items() if v is not None and v != ""}
    logger.info("GET %s params=%s", url, params)
    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
        resp = await client.get(url, headers=_auth_headers(), params=params)
    logger.info("Respuesta HTTP %s", resp.status_code)
    return _parse_response(resp)


async def _post_form(path: str, data: dict[str, Any]) -> dict | list | str:
    url = f"{DATAFAST_BASE_URL}{path}"
    clean_data = {k: str(v) for k, v in data.items() if v is not None and v != ""}
    logger.info("POST (form) %s data_keys=%s", url, list(clean_data.keys()))
    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
        resp = await client.post(url, headers=_auth_headers(), data=clean_data)
    logger.info("Respuesta HTTP %s", resp.status_code)
    return _parse_response(resp)


async def _delete_form(path: str, *, params: dict[str, Any] | None = None) -> dict | list | str:
    url = f"{DATAFAST_BASE_URL}{path}"
    if params:
        params = {k: v for k, v in params.items() if v is not None and v != ""}
    logger.info("DELETE %s params=%s", url, params)
    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
        resp = await client.delete(url, headers=_auth_headers(), params=params)
    logger.info("Respuesta HTTP %s", resp.status_code)
    return _parse_response(resp)


def _is_approved(result_code: str) -> bool:
    """Check if a Datafast result_code is an approval."""
    APPROVED_CODES = {"000.000.000", "000.100.112"}
    return result_code in APPROVED_CODES


def _json(result: Any) -> str:
    return json.dumps(result, ensure_ascii=False, default=str)
