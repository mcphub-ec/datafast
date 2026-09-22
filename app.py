"""Datafast FastMCP application instance."""

import os
from mcp.server.fastmcp import FastMCP

mcp = FastMCP(
    "datafast",
    host=os.getenv("MCP_HOST", "0.0.0.0"),  # nosec B104
    instructions=(
        "MCP server for Datafast Ecuador payment gateway (ACI Worldwide / Oppwa engine). "
        "Supports card payments via hosted checkout widget, recurring charges with tokenized "
        "cards, reversals, refunds and payment status queries. "
        "bearer_token is loaded from DATAFAST_BEARER_TOKEN env var. Pass `entity_id` per call. "
        "DO NOT pass bearer_token as a function argument — it is not in the signature. "
        "STANDARD FLOW: "
        "  1. Call crear_checkout → get checkoutId. "
        "  2. Frontend renders the Datafast widget using that checkoutId. "
        "  3. Call verificar_pago_checkout → confirm the result. "
        "MONETARY INPUT RULES (agent must follow strictly): "
        "  · Pass `monto` (float) with the EXACT number the user stated. "
        "  · Pass `tipo_monto`='subtotal' if the amount is WITHOUT IVA (default). "
        "  · Pass `tipo_monto`='total_con_iva' if the amount ALREADY INCLUDES IVA. "
        "  · NEVER calculate subtotals, IVA, or string-format amounts yourself. "
        "  · The server computes subtotal_gravado, valor_iva, and amount from monto+tipo_monto. "
        "  · Approved result codes: 000.000.000 or 000.100.112. "
        "  · paymentType: DB=Direct debit/purchase, PA=Pre-authorization, "
        "    RV=Reversal (same-day void), RF=Refund (post-day). "
        "  · Set DATAFAST_BASE_URL=https://eu-test.oppwa.com for sandbox testing. "
        "The IVA rate is read from IVA_EC_PERCENTAGE env var (default 15%)."
    ),
)
