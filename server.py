"""
Servidor MCP para Datafast (Dataweb / ACI Worldwide) v2.0.0
============================================================
Permite a un agente de IA procesar pagos con tarjeta de crédito/débito
a través del gateway Datafast Ecuador (motor ACI Worldwide / Oppwa).

⚠️  IMPORTANTE — Formato de petición:
    Las peticiones POST y DELETE usan application/x-www-form-urlencoded,
    NO JSON. Este servidor maneja ese detalle internamente.

MULTI-ACCOUNT SUPPORT (v2.0):
  Cada tool acepta `bearer_token` y (cuando aplica) `entity_id` como
  parámetros explícitos. Esto permite al agente operar en diferentes
  cuentas de comercio sin cambiar variables de entorno.

Flujo estándar:
  1. crear_checkout  →  obtiene checkoutId
  2. [Frontend renderiza el widget de tarjeta con el checkoutId]
  3. verificar_pago_checkout  →  valida si fue aprobado

Códigos de resultado comunes:
  · 000.000.000 / 000.100.112  → Aprobado
  · 800.100.152 / 800.100.162  → Rechazado (banco)
  · 100.400.500                → Error de datos / sumatoria de impuestos

Fuente de verdad técnica: docs/openapi.yaml
"""

import os
import json
import logging
from typing import Any

from dotenv import load_dotenv
import httpx
from mcp.server.fastmcp import FastMCP

load_dotenv()


# ---------------------------------------------------------------------------
# Configuración
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format='{"time":"%(asctime)s", "level":"%(levelname)s", "name":"%(name)s", "message":"%(message)s"}',
)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("datafast-mcp")

# Producción: https://eu-prod.oppwa.com  |  Sandbox: https://eu-test.oppwa.com
DATAFAST_BASE_URL = os.environ.get("DATAFAST_BASE_URL", "https://eu-prod.oppwa.com")
HTTP_TIMEOUT = float(os.environ.get("DATAFAST_HTTP_TIMEOUT", "30"))

mcp = FastMCP(
    "datafast",
    host="0.0.0.0",
    instructions=(
        "MCP server for Datafast Ecuador payment gateway (ACI Worldwide / Oppwa engine). "
        "Supports card payments via hosted checkout widget, recurring charges with tokenized "
        "cards, reversals, refunds and payment status queries. "
        "bearer_token is loaded from DATAFAST_BEARER_TOKEN env var. Pass `entity_id` per call. "
        "STANDARD FLOW: "
        "  1. Call crear_checkout → get checkoutId. "
        "  2. Frontend renders the Datafast widget using that checkoutId. "
        "  3. Call verificar_pago_checkout → confirm the result. "
        "CRITICAL RULES: "
        "  · amount must equal exactly: subtotal_iva0 + subtotal_gravado + valor_iva + valor_ice. "
        "    Mismatch causes error 100.400.500. "
        "  · All monetary amounts are strings with 2 decimal places. Example: '12.50'. "
        "  · Approved result codes: 000.000.000 or 000.100.112. "
        "  · paymentType: DB=Direct debit/purchase, PA=Pre-authorization, "
        "    RV=Reversal (same-day void), RF=Refund (post-day). "
        "  · Set DATAFAST_BASE_URL=https://eu-test.oppwa.com for sandbox testing."
    ))

# ---------------------------------------------------------------------------
# Cliente HTTP reutilizable
# ---------------------------------------------------------------------------


def _resolve_bearer() -> str:
    """Validate and return the Datafast Bearer token."""
    resolved = os.environ.get("DATAFAST_BEARER_TOKEN", "")
    if not resolved:
        raise ValueError(
            "DATAFAST_BEARER_TOKEN env var is required. Configure it in your .env file."
        )
    return resolved


def _auth_headers() -> dict[str, str]:
    """Build Authorization headers for a specific Datafast account."""
    return {"Authorization": f"Bearer {_resolve_bearer()}"}


async def _get(
    path: str,
    *,
    params: dict[str, Any] | None = None) -> dict | list | str:
    """Execute a GET request against the Datafast API."""
    url = f"{DATAFAST_BASE_URL}{path}"
    if params:
        params = {k: v for k, v in params.items() if v is not None and v != ""}

    logger.info("GET %s params=%s", url, params)

    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
        resp = await client.get(url, headers=_auth_headers(), params=params)

    logger.info("Respuesta HTTP %s", resp.status_code)
    return _parse_response(resp)


async def _post_form(
    path: str,
    data: dict[str, Any]) -> dict | list | str:
    """Execute a POST with application/x-www-form-urlencoded."""
    url = f"{DATAFAST_BASE_URL}{path}"
    clean_data = {k: str(v) for k, v in data.items() if v is not None and v != ""}

    logger.info("POST (form) %s data_keys=%s", url, list(clean_data.keys()))

    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
        resp = await client.post(
            url,
            headers=_auth_headers(),
            data=clean_data)

    logger.info("Respuesta HTTP %s", resp.status_code)
    return _parse_response(resp)


async def _delete_form(
    path: str,
    *,
    params: dict[str, Any] | None = None) -> dict | list | str:
    """Execute a DELETE request against the Datafast API."""
    url = f"{DATAFAST_BASE_URL}{path}"
    if params:
        params = {k: v for k, v in params.items() if v is not None and v != ""}

    logger.info("DELETE %s params=%s", url, params)

    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
        resp = await client.delete(url, headers=_auth_headers(), params=params)

    logger.info("Respuesta HTTP %s", resp.status_code)
    return _parse_response(resp)


def _parse_response(resp: httpx.Response) -> dict | list | str:
    """Parse a Datafast HTTP response."""
    if resp.status_code >= 400:
        return {
            "error": True,
            "status_code": resp.status_code,
            "detail": resp.text,
        }
    if not resp.text.strip():
        return {"ok": True, "status_code": resp.status_code}
    try:
        return resp.json()
    except Exception:
        return resp.text


def _is_approved(result_code: str) -> bool:
    """Indicate whether a Datafast result code is a success."""
    return result_code in ("000.000.000", "000.100.112")


# ═══════════════════════════════════════════════════════════════════════════
# CHECKOUT Y VERIFICACIÓN DE PAGO
# ═══════════════════════════════════════════════════════════════════════════


@mcp.tool()
async def crear_checkout(    entity_id: str,
    amount: str,
    payment_type: str,
    subtotal_iva0: str,
    subtotal_gravado: str,
    valor_iva: str,
    valor_ice: str = "0.00",
    currency: str = "USD",
    merchant_transaction_id: str | None = None,
    customer_email: str | None = None,
    customer_nombre: str | None = None,
    customer_apellido: str | None = None,
    customer_doc_tipo: str | None = None,
    customer_doc_numero: str | None = None,
    billing_calle: str | None = None,
    tokenizar_tarjeta: bool = False) -> str:
    """⚠️ MUTATION — Create a Checkout session in Datafast to initiate a card payment — POST /v1/checkouts.

    Use this tool as STEP 1 of the standard Datafast payment flow.
    The returned checkoutId is passed to the frontend Datafast widget (card form).
    After the customer submits the card form, call verificar_pago_checkout.

    ⚠️ CRITICAL TAX RULE (Ecuador):
    The 'amount' field MUST equal EXACTLY:
      subtotal_iva0 + subtotal_gravado + valor_iva + valor_ice
    If the sum does not match, Datafast returns error code 100.400.500.

    REQUIRED PARAMETERS:
      entity_id (str): Commerce entity ID issued by Datafast.
                       Note: Datafast may issue different entityIds for Visa/MC vs Diners/Discover.
      amount (str): ⚠️ TOTAL AMOUNT to charge with 2 decimal places. Example: "12.50"
      payment_type (str): Payment operation type.
                          Valid values: "DB"=Direct debit/purchase, "PA"=Pre-authorization.
      subtotal_iva0 (str): ⚠️ ZERO-RATE BASE (Base Cero - SHOPPER_VAL_BASE0). Example: "0.00"
      subtotal_gravado (str): ⚠️ TAXABLE BASE (Base Imponible / Subtotal 15%). DO NOT confuse with Total. Example: "10.71"
      valor_iva (str): ⚠️ TOTAL VAT AMOUNT (SHOPPER_VAL_IVA). Example: "1.79"

    OPTIONAL PARAMETERS:
      valor_ice (str, default="0.00"): ICE tax amount (SHOPPER_VAL_ICE).
      currency (str, default="USD"): Currency code.
      merchant_transaction_id (str): Your system's order number for reconciliation.
      tokenizar_tarjeta (bool, default=False): Set True to save the card and receive
                                               a registrationId for future charges.
      customer_email, customer_nombre, customer_apellido (str): Customer info.
      customer_doc_tipo (str): "IDCARD" | "PASSPORT"
      customer_doc_numero (str): Customer cedula or passport number.
      billing_calle (str): Billing street address.

    RETURNS:
      JSON with 'id' (checkoutId) and 'result.code' (success = "000.200.100").

    EXAMPLE CALL:
      crear_checkout(bearer_token="tkn...", entity_id="8ac7...",
                     amount="12.50", payment_type="DB",
                     subtotal_iva0="0.00", subtotal_gravado="10.71",
                     valor_iva="1.79")
    """
    data: dict[str, Any] = {
        "entityId": entity_id,
        "amount": amount,
        "currency": currency,
        "paymentType": payment_type,
        "customParameters[SHOPPER_VAL_BASE0]": subtotal_iva0,
        "customParameters[SHOPPER_VAL_BASEIMP]": subtotal_gravado,
        "customParameters[SHOPPER_VAL_IVA]": valor_iva,
        "customParameters[SHOPPER_VAL_ICE]": valor_ice,
    }
    if merchant_transaction_id is not None:
        data["merchantTransactionId"] = merchant_transaction_id
    if customer_email is not None:
        data["customer.email"] = customer_email
    if customer_nombre is not None:
        data["customer.givenName"] = customer_nombre
    if customer_apellido is not None:
        data["customer.surname"] = customer_apellido
    if customer_doc_tipo is not None:
        data["customer.identificationDocType"] = customer_doc_tipo
    if customer_doc_numero is not None:
        data["customer.identificationDocId"] = customer_doc_numero
    if billing_calle is not None:
        data["billing.street1"] = billing_calle
    if tokenizar_tarjeta:
        data["createRegistration"] = "true"

    result = await _post_form("/v1/checkouts", data)
    return json.dumps(result, ensure_ascii=False, default=str)


@mcp.tool()
async def verificar_pago_checkout(    entity_id: str,
    checkout_id: str) -> str:
    """Verify the final status of a Datafast payment after the customer completes the card form — GET /v1/checkouts/{id}/payment.

    Use this tool as STEP 3 of the standard Datafast payment flow, after the frontend
    redirects back with the resourcePath or after receiving a webhook notification.

    REQUIRED PARAMETERS:
      entity_id (str): Commerce entity ID issued by Datafast.
      checkout_id (str): The checkoutId generated by crear_checkout.
                         Example: "1ABC23DEF456GH78"

    RETURNS:
      JSON with transaction result. Key fields:
        - result.code: "000.000.000" or "000.100.112" = Approved.
        - id: Real payment ID (use this for reversals/refunds, NOT the checkoutId).
        - registrationId: Card token (only present if tokenizar_tarjeta=True was set).
        - resultDetails.AuthCode: Bank authorization code.
        - resultDetails.ReferenceNbr: Bank reference number.

    EXAMPLE CALL:
      verificar_pago_checkout(bearer_token="tkn...", entity_id="8ac7...",
                              checkout_id="1ABC23DEF456GH78")
    """
    result = await _get(
        f"/v1/checkouts/{checkout_id}/payment",
        params={"entityId": entity_id})
    return json.dumps(result, ensure_ascii=False, default=str)


# ═══════════════════════════════════════════════════════════════════════════
# CONSULTA POR ID DEL COMERCIO
# ═══════════════════════════════════════════════════════════════════════════


@mcp.tool()
async def consultar_pago_por_orden(    entity_id: str,
    merchant_transaction_id: str) -> str:
    """Search for a transaction by your internal order number — GET /v1/query.

    Use this tool when you do not have the checkoutId but know the order number
    you sent as merchant_transaction_id in crear_checkout.

    REQUIRED PARAMETERS:
      entity_id (str): Commerce entity ID issued by Datafast.
      merchant_transaction_id (str): Your system's order number sent during crear_checkout.
                                     Example: "ORDER-2025-0042"

    RETURNS:
      List of transactions matching the order number, each with result.code,
      amount, id, and payment details.

    EXAMPLE CALL:
      consultar_pago_por_orden(bearer_token="tkn...", entity_id="8ac7...",
                               merchant_transaction_id="ORDER-2025-0042")
    """
    result = await _get(
        "/v1/query",
        params={
            "entityId": entity_id,
            "merchantTransactionId": merchant_transaction_id,
        })
    return json.dumps(result, ensure_ascii=False, default=str)


# ═══════════════════════════════════════════════════════════════════════════
# REVERSALES Y REEMBOLSOS
# ═══════════════════════════════════════════════════════════════════════════


@mcp.tool()
async def reversar_reembolsar_pago(    entity_id: str,
    payment_id: str,
    amount: str,
    payment_type: str,
    currency: str = "USD") -> str:
    """⚠️ MUTATION — Reverse or refund a previously approved payment — POST /v1/payments/{id}.

    Use this tool to cancel or return funds for an approved transaction.

    ⚠️ IMPORTANT:
    - payment_id is the 'id' field from verificar_pago_checkout response.
      It is NOT the checkoutId. It is the real transaction ID issued after approval.

    REQUIRED PARAMETERS:
      entity_id (str): Commerce entity ID issued by Datafast.
      payment_id (str): Real payment ID from verificar_pago_checkout (not checkoutId).
                        Example: "8ac7a4a2123456789abc0123"
      amount (str): Amount to reverse/refund with 2 decimal places.
                    For full reversals, use the original transaction amount. Example: "12.50"
      payment_type (str): Operation type.
                          "RV" = Reversal (void) — same-day ONLY, full cancellation.
                          "RF" = Refund — for days after the transaction.

    OPTIONAL PARAMETERS:
      currency (str, default="USD"): Currency code.

    RETURNS:
      JSON with result.code and refund/reversal confirmation details.

    EXAMPLE CALL:
      reversar_reembolsar_pago(bearer_token="tkn...", entity_id="8ac7...",
                               payment_id="8ac7a4a2123456789abc",
                               amount="12.50", payment_type="RF")
    """
    data: dict[str, Any] = {
        "entityId": entity_id,
        "amount": amount,
        "currency": currency,
        "paymentType": payment_type,
    }
    result = await _post_form(f"/v1/payments/{payment_id}", data)
    return json.dumps(result, ensure_ascii=False, default=str)


# ═══════════════════════════════════════════════════════════════════════════
# PAGOS RECURRENTES / ONECLICK (TARJETAS TOKENIZADAS)
# ═══════════════════════════════════════════════════════════════════════════


@mcp.tool()
async def pago_recurrente_oneclick(    entity_id: str,
    registration_id: str,
    amount: str,
    currency: str = "USD",
    payment_type: str = "DB",
    shopper_result_url: str | None = None) -> str:
    """⚠️ MUTATION — Charge a tokenized (saved) card for recurring or OneClick payments — POST /v1/registrations/{id}/payments.

    Use this tool to charge a card that was previously saved via tokenizar_tarjeta=True
    in crear_checkout. The registrationId was returned in verificar_pago_checkout.

    REQUIRED PARAMETERS:
      entity_id (str): Commerce entity ID issued by Datafast.
      registration_id (str): Card token (registrationId) from verificar_pago_checkout.
                             Example: "8ac7a4a2-abcd-1234-efgh-5678"
      amount (str): Amount to charge with 2 decimal places. Example: "99.00"

    OPTIONAL PARAMETERS:
      currency (str, default="USD"): Currency code.
      payment_type (str, default="DB"): Payment operation. "DB"=Direct purchase.
      shopper_result_url (str): REQUIRED if the card triggers a 3D Secure challenge.
                                The customer will be redirected here after 3DS authentication.

    RETURNS:
      JSON with result.code ("000.000.000"=Approved), transaction id,
      authorizationCode, and card details.

    EXAMPLE CALL:
      pago_recurrente_oneclick(bearer_token="tkn...", entity_id="8ac7...",
                               registration_id="8ac7a4a2-abcd", amount="99.00")
    """
    data: dict[str, Any] = {
        "entityId": entity_id,
        "amount": amount,
        "currency": currency,
        "paymentType": payment_type,
    }
    if shopper_result_url is not None:
        data["shopperResultUrl"] = shopper_result_url

    result = await _post_form(
        f"/v1/registrations/{registration_id}/payments", data)
    return json.dumps(result, ensure_ascii=False, default=str)


@mcp.tool()
async def eliminar_token_tarjeta(    entity_id: str,
    registration_id: str) -> str:
    """⚠️ IRREVERSIBLE MUTATION — Delete a saved card token from the Datafast vault — DELETE /v1/registrations/{id}.

    Use this tool when a customer requests deletion of their saved card.
    Once deleted, the registrationId cannot be used for future charges.

    REQUIRED PARAMETERS:
      entity_id (str): Commerce entity ID issued by Datafast.
      registration_id (str): Card token (registrationId) to delete.
                             Example: "8ac7a4a2-abcd-1234-efgh-5678"

    RETURNS:
      JSON confirmation of the deletion.

    EXAMPLE CALL:
      eliminar_token_tarjeta(bearer_token="tkn...", entity_id="8ac7...",
                             registration_id="8ac7a4a2-abcd-1234-efgh-5678")
    """
    result = await _delete_form(
        f"/v1/registrations/{registration_id}",
        params={"entityId": entity_id})
    return json.dumps(result, ensure_ascii=False, default=str)


# ═══════════════════════════════════════════════════════════════════════════
# UTILIDADES
# ═══════════════════════════════════════════════════════════════════════════


@mcp.tool()
async def interpretar_codigo_resultado(code: str) -> str:
    """Interpret the meaning of a Datafast result code from a transaction response.

    Use this tool to understand whether a result.code from any Datafast operation
    means the transaction was approved, pending, or rejected.
    This tool does NOT require credentials (local lookup only).

    REQUIRED PARAMETERS:
      code (str): Datafast result code to interpret.
                  Examples: "000.000.000" (approved), "800.100.152" (declined by bank),
                             "100.400.500" (tax validation error).

    RETURNS:
      {"code": str, "descripcion": str, "aprobada": bool, "pendiente": bool, "rechazada": bool}

    EXAMPLE CALL:
      interpretar_codigo_resultado(code="800.100.152")
    """
    import re
    approved_patterns = [
        r"^000\.000\.",
        r"^000\.100\.1",
        r"^000\.300\.",
        r"^000\.400\.0",
    ]
    pending_patterns = [
        r"^000\.200\.",
        r"^800\.400\.5",
    ]
    rejected_patterns = [
        r"^800\.100\.",
        r"^900\.100\.",
        r"^800\.200\.",
        r"^100\.400\.",
        r"^200\.300\.",
    ]

    is_approved = any(re.match(p, code) for p in approved_patterns)
    is_pending = any(re.match(p, code) for p in pending_patterns)
    is_rejected = any(re.match(p, code) for p in rejected_patterns)

    known_codes: dict[str, str] = {
        "000.000.000": "✅ APROBADA — Transacción exitosa.",
        "000.100.112": "✅ APROBADA — Transacción aprobada (pendiente de confirmación batch).",
        "800.100.152": "❌ RECHAZADA — Declinada por el banco (fondos insuficientes u otro motivo).",
        "800.100.162": "❌ RECHAZADA — Declinada por el banco (restricción de la cuenta).",
        "100.400.500": "⚠️ ERROR — Datos inválidos. Verificar que la suma de impuestos coincida con el amount total.",
    }

    if code in known_codes:
        descripcion = known_codes[code]
    elif is_approved:
        descripcion = "✅ APROBADA según el patrón del código."
    elif is_pending:
        descripcion = "⏳ PENDIENTE — La transacción está en proceso."
    elif is_rejected:
        descripcion = "❌ RECHAZADA según el patrón del código."
    else:
        descripcion = "❓ DESCONOCIDO — Consultar documentación de ACI Worldwide."

    return json.dumps(
        {
            "code": code,
            "descripcion": descripcion,
            "aprobada": is_approved,
            "pendiente": is_pending,
            "rechazada": is_rejected,
        },
        ensure_ascii=False)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("MCP_PORT", 8000))
    transport_mode = os.getenv("MCP_TRANSPORT_MODE", "sse").lower()
    print(f"Starting Datafast MCP Server on http://0.0.0.0:{port}/mcp ({transport_mode})")
    if transport_mode == "sse":
        app = mcp.sse_app()
    elif transport_mode == "http_stream":
        app = mcp.streamable_http_app()
    else:
        raise ValueError(f"Unknown transport mode: {transport_mode}")
    uvicorn.run(app, host="0.0.0.0", port=port)
