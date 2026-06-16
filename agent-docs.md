# Agent-First Documentation: Datafast MCP Server

## 1. Contexto General
Servidor MCP para el gateway Datafast Ecuador (motor ACI Worldwide / Oppwa).
Soporta pagos con tarjeta vía widget hosted checkout, cobros recurrentes con
tarjetas tokenizadas, reversos y refunds.

⚠️ **IMPORTANTE — Formato de petición**: Las peticiones POST y DELETE usan
`application/x-www-form-urlencoded`, NO JSON. El servidor maneja este detalle.

## 2. Tecnologías Principales
- **FastMCP 3.3.1**.
- **httpx**: Cliente HTTP asíncrono.
- Bearer token `DATAFAST_BEARER_TOKEN` en header `Authorization`.

## 3. Reglas de Negocio Estrictas
- **Montos en centavos como string** (ej: `"99.00"`). El server valida y
  rechaza montos > $10,000 USD (configurable via `MCP_MAX_AMOUNT_USD`).
- **IVA**: el server desglosa `subtotalIva`, `iva`, `subtotalIva0` automáticamente
  a partir de `monto` + `tipo_monto`. El agente NUNCA debe construir el desglose.
- **Reversos mismo día**: el server advierte si la transacción no es del día actual.
- Códigos de resultado comunes:
  - `000.000.000` / `000.100.112` → Aprobado
  - `800.100.152` / `800.100.162` → Rechazado (banco)
  - `100.400.500` → Error de datos / sumatoria de impuestos

## 4. Variables de Entorno
- `DATAFAST_BEARER_TOKEN`: Bearer token. **NO es parámetro de tool** — se lee de env.
- `DATAFAST_ENTITY_ID`: Entity ID por defecto (se puede sobreescribir por llamada).
- `DATAFAST_BASE_URL`: URL base (`https://eu-prod.oppwa.com` por defecto).
- `MCP_HOST`, `MCP_PORT` (default 8008), `MCP_TRANSPORT_MODE`.

## 5. Herramientas Principales (7 totales)
- `crear_checkout`: Crea un checkout para el widget hosted.
- `verificar_pago_checkout`: Verifica el resultado tras el pago.
- `consultar_pago_por_orden`: Busca pago por merchantTransactionId.
- `reversar_reembolsar_pago`: Reversa o reembolsa (RV=void, RF=refund).
- `pago_recurrente_oneclick`: Cobra tarjeta tokenizada.
- `eliminar_token_tarjeta`: Elimina registration de tarjeta.
- `interpretar_codigo_resultado`: Traduce códigos ACI a mensajes accionables.

## 6. Consideraciones de Seguridad
- **Anti-SSRF en `shopper_result_url`**: solo HTTPS, bloquea metadata IPs y rangos privados.
- **No loguear `DATAFAST_BEARER_TOKEN`** (filtrado automático vía mcp_common).
- Reversos solo aplican el mismo día (validación implementada en `reversar_reembolsar_pago`).
- Para montos grandes, coordinar con el banco ANTES de procesar.

## 7. Instrucciones para Edición de Código
- Patrón `@mcp.tool()` con type hints.
- Cliente HTTP centralizado: `_get`, `_post_form`, `_delete_form`.
- Para tools monetarias nuevas, usar el motor fiscal determinista `_calcular_strings_fiscales`.

## 8. Tests
- Pendiente: añadir tests para `_calcular_strings_fiscales` y al menos 1 happy path por tool.
